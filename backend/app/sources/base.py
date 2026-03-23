from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import aiohttp


@dataclass
class RawProxy:
    """Raw proxy data from a source."""
    ip: str
    port: int
    protocol: str
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    anonymity: Optional[str] = None
    source: Optional[str] = None


class ProxySource(ABC):
    """Base class for proxy sources."""

    name: str = "base"
    url: str = ""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = False

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            self._owns_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session and self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("Session not initialized. Use async with context.")
        return self._session

    @abstractmethod
    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from the source.

        Args:
            protocol: Filter by protocol (http, https, socks4, socks5)
            country: Filter by country code (e.g., 'us', 'uk')

        Returns:
            List of RawProxy objects
        """
        pass

    def normalize_protocol(self, protocol: str) -> str:
        """Normalize protocol string."""
        protocol = protocol.lower().strip()
        if protocol in ("http", "https", "socks4", "socks5"):
            return protocol
        if protocol == "socks":
            return "socks5"
        return "http"

    def normalize_anonymity(self, anonymity: str) -> str:
        """Normalize anonymity level string."""
        anonymity = anonymity.lower().strip()
        if "elite" in anonymity or "high" in anonymity:
            return "elite"
        if "anonymous" in anonymity:
            return "anonymous"
        return "transparent"
