from typing import Optional
from .base import ProxySource, RawProxy


class ProxyScrapeSource(ProxySource):
    """ProxyScrape API proxy source."""

    name = "proxyscrape"
    base_url = "https://api.proxyscrape.com/v2/"

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from ProxyScrape API."""
        proxies = []
        protocols = [protocol] if protocol else ["http", "socks4", "socks5"]

        for proto in protocols:
            params = {
                "request": "displayproxies",
                "protocol": proto,
                "timeout": 10000,
                "country": country or "all",
                "ssl": "all",
                "anonymity": "all",
            }

            try:
                async with self.session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        continue

                    text = await response.text()
                    for line in text.strip().split("\n"):
                        line = line.strip()
                        if not line or ":" not in line:
                            continue

                        try:
                            ip, port = line.split(":")
                            proxies.append(RawProxy(
                                ip=ip.strip(),
                                port=int(port.strip()),
                                protocol=self.normalize_protocol(proto),
                                country=country.upper() if country else None,
                                source=self.name,
                            ))
                        except (ValueError, IndexError):
                            continue

            except Exception:
                continue

        return proxies
