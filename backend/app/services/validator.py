import asyncio
import time
import socket
from typing import Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Proxy
from ..config import get_settings

settings = get_settings()


# Multiple test URLs for validation - using fast, reliable endpoints
TEST_URLS = [
    ("http://ip-api.com/json", "query"),
    ("http://httpbin.org/ip", "origin"),
    ("http://api.ipify.org?format=json", "ip"),
]

# Faster test URLs for quick checks
QUICK_TEST_URLS = [
    ("http://ip-api.com/json", "query"),
    ("http://api.ipify.org?format=json", "ip"),
]


@dataclass
class ValidationResult:
    """Result of proxy validation."""
    proxy_id: int
    is_valid: bool
    speed: Optional[float] = None  # milliseconds
    anonymity: Optional[str] = None
    error: Optional[str] = None
    test_url: Optional[str] = None
    response_ip: Optional[str] = None


@dataclass
class ValidationProgress:
    """Progress update during bulk validation."""
    total: int
    completed: int
    successful: int
    failed: int
    current_proxy: Optional[str] = None
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def percent(self) -> float:
        return (self.completed / self.total * 100) if self.total > 0 else 0


class ProxyValidator:
    """Service for validating proxy connectivity and performance."""

    def __init__(
        self,
        timeout: int = None,
        concurrency: int = None,
        quick_timeout: int = 5,
    ):
        self.timeout = timeout or settings.validation_timeout
        self.concurrency = concurrency or settings.validation_concurrency
        self.quick_timeout = quick_timeout

    def _get_proxy_type(self, protocol: str) -> ProxyType:
        """Get aiohttp-socks proxy type."""
        mapping = {
            "socks4": ProxyType.SOCKS4,
            "socks5": ProxyType.SOCKS5,
            "http": ProxyType.HTTP,
            "https": ProxyType.HTTP,
        }
        return mapping.get(protocol, ProxyType.HTTP)

    async def _quick_tcp_check(self, ip: str, port: int, timeout: float = 3) -> bool:
        """Quick TCP connectivity check - fastest way to verify port is open."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _create_session(
        self, proxy: Proxy, timeout: int = None
    ) -> aiohttp.ClientSession:
        """Create an aiohttp session with appropriate proxy configuration."""
        timeout_val = timeout or self.timeout
        client_timeout = aiohttp.ClientTimeout(total=timeout_val, connect=timeout_val)

        if proxy.protocol in ("socks4", "socks5"):
            connector = ProxyConnector(
                proxy_type=self._get_proxy_type(proxy.protocol),
                host=proxy.ip,
                port=proxy.port,
                rdns=True,
            )
            return aiohttp.ClientSession(connector=connector, timeout=client_timeout)
        else:
            return aiohttp.ClientSession(timeout=client_timeout)

    async def _test_single_url(
        self,
        session: aiohttp.ClientSession,
        proxy: Proxy,
        test_url: str,
        ip_field: str,
    ) -> tuple[bool, Optional[float], Optional[str], Optional[str]]:
        """Test proxy with a specific URL.

        Returns: (is_valid, speed_ms, response_ip, error)
        """
        start_time = time.time()

        try:
            proxy_url = None
            if proxy.protocol not in ("socks4", "socks5"):
                proxy_url = f"http://{proxy.ip}:{proxy.port}"

            async with session.get(test_url, proxy=proxy_url, ssl=False) as response:
                if response.status == 200:
                    elapsed = (time.time() - start_time) * 1000
                    try:
                        data = await response.json()
                        response_ip = data.get(ip_field, "")
                        return True, round(elapsed, 2), response_ip, None
                    except Exception:
                        return True, round(elapsed, 2), None, None
                else:
                    return False, None, None, f"HTTP {response.status}"

        except asyncio.TimeoutError:
            return False, None, None, "Timeout"
        except aiohttp.ClientProxyConnectionError:
            return False, None, None, "Proxy connection failed"
        except aiohttp.ClientConnectorError as e:
            return False, None, None, f"Connection error"
        except Exception as e:
            return False, None, None, str(type(e).__name__)

    async def _test_urls_parallel(
        self,
        session: aiohttp.ClientSession,
        proxy: Proxy,
        test_urls: list[tuple[str, str]],
    ) -> tuple[bool, Optional[float], Optional[str], Optional[str], Optional[str]]:
        """Test multiple URLs in parallel, return first success.

        Returns: (is_valid, speed_ms, response_ip, test_url, error)
        """
        tasks = [
            self._test_single_url(session, proxy, url, ip_field)
            for url, ip_field in test_urls
        ]

        # Use asyncio.as_completed to get first successful result
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            is_valid, speed, response_ip, error = await coro
            if is_valid:
                # Cancel remaining tasks
                for task in tasks:
                    if hasattr(task, 'cancel'):
                        task.cancel()
                return True, speed, response_ip, test_urls[i][0], None

        # All failed - return last error
        return False, None, None, None, error or "All test URLs failed"

    async def validate_single(
        self,
        proxy: Proxy,
        my_ip: Optional[str] = None,
        quick: bool = False,
    ) -> ValidationResult:
        """Validate a single proxy.

        Args:
            proxy: Proxy to validate
            my_ip: Our real IP address for anonymity detection
            quick: If True, use faster timeout and fewer tests

        Returns:
            ValidationResult with status and metrics
        """
        timeout = self.quick_timeout if quick else self.timeout
        test_urls = QUICK_TEST_URLS if quick else TEST_URLS

        # Quick TCP check first - fail fast if port is closed
        if not await self._quick_tcp_check(proxy.ip, proxy.port, timeout=2):
            return ValidationResult(
                proxy_id=proxy.id,
                is_valid=False,
                error="Port unreachable",
            )

        # Full proxy test
        try:
            session = await self._create_session(proxy, timeout)
            try:
                # Test URLs in parallel for faster results
                is_valid, speed, response_ip, test_url, error = await self._test_urls_parallel(
                    session, proxy, test_urls
                )

                if is_valid:
                    anonymity = self._detect_anonymity(proxy.ip, response_ip, my_ip)
                    return ValidationResult(
                        proxy_id=proxy.id,
                        is_valid=True,
                        speed=speed,
                        anonymity=anonymity,
                        test_url=test_url,
                        response_ip=response_ip,
                    )
                else:
                    return ValidationResult(
                        proxy_id=proxy.id,
                        is_valid=False,
                        error=error,
                    )
            finally:
                await session.close()
        except Exception as e:
            return ValidationResult(
                proxy_id=proxy.id,
                is_valid=False,
                error=str(type(e).__name__),
            )

    def _detect_anonymity(
        self,
        proxy_ip: str,
        response_ip: Optional[str],
        my_ip: Optional[str],
    ) -> str:
        """Detect proxy anonymity level."""
        if not response_ip:
            return "unknown"

        if my_ip and my_ip in response_ip:
            return "transparent"

        if proxy_ip in response_ip:
            return "anonymous"  # Shows proxy IP, not elite

        if "," in response_ip:
            return "transparent"

        return "elite"

    async def validate_many(
        self,
        proxies: list[Proxy],
        my_ip: Optional[str] = None,
        quick: bool = False,
    ) -> list[ValidationResult]:
        """Validate multiple proxies concurrently."""
        semaphore = asyncio.Semaphore(self.concurrency)

        async def validate_with_semaphore(proxy: Proxy) -> ValidationResult:
            async with semaphore:
                return await self.validate_single(proxy, my_ip, quick)

        tasks = [validate_with_semaphore(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def validate_with_progress(
        self,
        proxies: list[Proxy],
        my_ip: Optional[str] = None,
        quick: bool = False,
    ) -> AsyncGenerator[ValidationProgress, None]:
        """Validate proxies with progress updates via generator.

        Yields ValidationProgress updates as proxies are validated.
        """
        total = len(proxies)
        completed = 0
        successful = 0
        failed = 0
        results = []

        semaphore = asyncio.Semaphore(self.concurrency)

        # Create a queue for results
        result_queue: asyncio.Queue[ValidationResult] = asyncio.Queue()

        async def validate_and_queue(proxy: Proxy):
            async with semaphore:
                result = await self.validate_single(proxy, my_ip, quick)
                await result_queue.put(result)

        # Start all validation tasks
        tasks = [asyncio.create_task(validate_and_queue(p)) for p in proxies]

        # Yield progress as results come in
        while completed < total:
            result = await result_queue.get()
            results.append(result)
            completed += 1

            if result.is_valid:
                successful += 1
            else:
                failed += 1

            # Find the proxy for current result
            current_proxy = next(
                (f"{p.ip}:{p.port}" for p in proxies if p.id == result.proxy_id),
                None
            )

            yield ValidationProgress(
                total=total,
                completed=completed,
                successful=successful,
                failed=failed,
                current_proxy=current_proxy,
                results=[result],  # Only include latest result
            )

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

    async def validate_and_update(
        self,
        db: AsyncSession,
        proxies: list[Proxy],
        quick: bool = False,
    ) -> list[ValidationResult]:
        """Validate proxies and update their status in database."""
        my_ip = await self._get_my_ip()
        results = await self.validate_many(proxies, my_ip, quick)

        for result in results:
            proxy = next((p for p in proxies if p.id == result.proxy_id), None)
            if not proxy:
                continue

            if result.is_valid:
                proxy.is_active = True
                proxy.speed = result.speed
                proxy.success_count += 1
                if result.anonymity and result.anonymity != "unknown":
                    proxy.anonymity = result.anonymity
            else:
                proxy.fail_count += 1
                total_checks = proxy.success_count + proxy.fail_count
                if total_checks >= 3:
                    success_rate = proxy.success_count / total_checks
                    if success_rate < 0.2:
                        proxy.is_active = False

            proxy.last_check = datetime.utcnow()
            self._update_score(proxy)

        await db.commit()
        return results

    async def validate_and_update_with_progress(
        self,
        db: AsyncSession,
        proxies: list[Proxy],
        quick: bool = False,
    ) -> AsyncGenerator[ValidationProgress, None]:
        """Validate proxies with progress updates and database updates."""
        my_ip = await self._get_my_ip()

        async for progress in self.validate_with_progress(proxies, my_ip, quick):
            # Update database for completed results
            for result in progress.results:
                proxy = next((p for p in proxies if p.id == result.proxy_id), None)
                if not proxy:
                    continue

                if result.is_valid:
                    proxy.is_active = True
                    proxy.speed = result.speed
                    proxy.success_count += 1
                    if result.anonymity and result.anonymity != "unknown":
                        proxy.anonymity = result.anonymity
                else:
                    proxy.fail_count += 1
                    total_checks = proxy.success_count + proxy.fail_count
                    if total_checks >= 3:
                        success_rate = proxy.success_count / total_checks
                        if success_rate < 0.2:
                            proxy.is_active = False

                proxy.last_check = datetime.utcnow()
                self._update_score(proxy)

            yield progress

        await db.commit()

    async def _get_my_ip(self) -> Optional[str]:
        """Get our real public IP address."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get("http://api.ipify.org?format=json") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("ip")
        except Exception:
            pass
        return None

    def _update_score(self, proxy: Proxy) -> None:
        """Update proxy score based on metrics."""
        # Speed score (0-40 points)
        speed_score = 0
        if proxy.speed:
            if proxy.speed < 500:
                speed_score = 40
            elif proxy.speed < 1000:
                speed_score = 30
            elif proxy.speed < 2000:
                speed_score = 20
            elif proxy.speed < 5000:
                speed_score = 10
            else:
                speed_score = 5

        # Stability score (0-30 points)
        total_checks = proxy.success_count + proxy.fail_count
        if total_checks > 0:
            success_rate = proxy.success_count / total_checks
            stability_score = success_rate * 30
        else:
            stability_score = 15

        # Anonymity score (0-30 points)
        anonymity_scores = {
            "elite": 30,
            "anonymous": 20,
            "transparent": 5,
            "unknown": 10,
        }
        anonymity_score = anonymity_scores.get(proxy.anonymity, 10)

        proxy.score = round(speed_score + stability_score + anonymity_score, 2)
