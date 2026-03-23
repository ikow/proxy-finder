from typing import Optional
from .base import ProxySource, RawProxy


class MonosansSource(ProxySource):
    """monosans/proxy-list GitHub proxy source.

    Provides proxies with geolocation data in JSON format.
    https://github.com/monosans/proxy-list
    """

    name = "monosans"

    # JSON endpoint with full proxy data including geolocation
    json_url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"

    # Alternative plain text URLs
    text_urls = {
        "http": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "socks4": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    }

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from monosans GitHub repository."""
        proxies = []

        # Try JSON endpoint first for richer data
        try:
            async with self.session.get(self.json_url) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data:
                        try:
                            proto = item.get("protocol", "http").lower()

                            # Filter by protocol if specified
                            if protocol and proto != protocol:
                                continue

                            # Filter by country if specified
                            proxy_country = item.get("geolocation", {}).get("country", {}).get("code")
                            if country and proxy_country and proxy_country.upper() != country.upper():
                                continue

                            proxies.append(RawProxy(
                                ip=item["host"],
                                port=item["port"],
                                protocol=self.normalize_protocol(proto),
                                country=proxy_country.upper() if proxy_country else None,
                                country_name=item.get("geolocation", {}).get("country", {}).get("name"),
                                city=item.get("geolocation", {}).get("city"),
                                anonymity=self._map_anonymity(item.get("anonymity")),
                                source=self.name,
                            ))
                        except (KeyError, TypeError, ValueError):
                            continue

                    if proxies:
                        return proxies
        except Exception:
            pass

        # Fallback to plain text URLs
        if protocol:
            protocols = [protocol] if protocol in self.text_urls else []
        else:
            protocols = list(self.text_urls.keys())

        for proto in protocols:
            url = self.text_urls[proto]
            try:
                async with self.session.get(url) as response:
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
                                source=self.name,
                            ))
                        except (ValueError, IndexError):
                            continue

            except Exception:
                continue

        return proxies

    def _map_anonymity(self, anonymity: Optional[str]) -> Optional[str]:
        """Map monosans anonymity values to our standard values."""
        if not anonymity:
            return None

        anonymity = anonymity.lower()
        if anonymity in ("high", "elite"):
            return "elite"
        elif anonymity in ("anonymous", "medium"):
            return "anonymous"
        elif anonymity in ("transparent", "low"):
            return "transparent"
        return None
