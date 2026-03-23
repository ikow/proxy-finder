import asyncio
from typing import Optional
from datetime import datetime

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Proxy
from ..sources.base import RawProxy
from ..sources.proxyscrape import ProxyScrapeSource
from ..sources.geonode import GeoNodeSource
from ..sources.freeproxy import FreeProxyListSource, SslProxySource
from ..sources.github_speedx import SpeedXSource
from ..sources.github_monosans import MonosansSource
from ..sources.github_proxifly import ProxiflySource


class ProxyFetcher:
    """Service for fetching proxies from multiple sources."""

    def __init__(self):
        self.sources = [
            ProxyScrapeSource,
            GeoNodeSource,
            FreeProxyListSource,
            SslProxySource,
            # GitHub-based sources (large proxy lists)
            SpeedXSource,
            MonosansSource,
            ProxiflySource,
        ]

    async def fetch_all(
        self,
        protocol: Optional[str] = None,
        country: Optional[str] = None,
    ) -> list[RawProxy]:
        """Fetch proxies from all sources concurrently.

        Args:
            protocol: Filter by protocol
            country: Filter by country code

        Returns:
            List of unique proxies from all sources
        """
        all_proxies = []
        seen = set()

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as session:
            tasks = []
            for source_class in self.sources:
                source = source_class(session)
                tasks.append(source.fetch(protocol=protocol, country=country))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue
                for proxy in result:
                    key = (proxy.ip, proxy.port, proxy.protocol)
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(proxy)

        return all_proxies

    async def save_proxies(
        self,
        db: AsyncSession,
        proxies: list[RawProxy],
    ) -> int:
        """Save proxies to database, updating existing ones.

        Args:
            db: Database session
            proxies: List of raw proxies to save

        Returns:
            Number of new proxies added
        """
        new_count = 0

        for raw_proxy in proxies:
            # Check if proxy already exists
            stmt = select(Proxy).where(
                Proxy.ip == raw_proxy.ip,
                Proxy.port == raw_proxy.port,
                Proxy.protocol == raw_proxy.protocol,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing proxy info if we have more details
                if raw_proxy.country and not existing.country:
                    existing.country = raw_proxy.country
                if raw_proxy.country_name and not existing.country_name:
                    existing.country_name = raw_proxy.country_name
                if raw_proxy.city and not existing.city:
                    existing.city = raw_proxy.city
                if raw_proxy.anonymity and not existing.anonymity:
                    existing.anonymity = raw_proxy.anonymity
            else:
                # Create new proxy
                proxy = Proxy(
                    ip=raw_proxy.ip,
                    port=raw_proxy.port,
                    protocol=raw_proxy.protocol,
                    country=raw_proxy.country,
                    country_name=raw_proxy.country_name,
                    city=raw_proxy.city,
                    anonymity=raw_proxy.anonymity,
                    source=raw_proxy.source,
                    is_active=True,
                )
                db.add(proxy)
                new_count += 1

        await db.commit()
        return new_count

    async def refresh_proxies(
        self,
        db: AsyncSession,
        protocol: Optional[str] = None,
        country: Optional[str] = None,
    ) -> tuple[int, int]:
        """Fetch and save proxies from all sources.

        Args:
            db: Database session
            protocol: Filter by protocol
            country: Filter by country code

        Returns:
            Tuple of (new_proxies_count, total_fetched)
        """
        proxies = await self.fetch_all(protocol=protocol, country=country)
        new_count = await self.save_proxies(db, proxies)
        return new_count, len(proxies)
