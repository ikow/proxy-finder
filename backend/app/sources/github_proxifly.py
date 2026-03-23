from typing import Optional
from .base import ProxySource, RawProxy


class ProxiflySource(ProxySource):
    """proxifly/free-proxy-list GitHub proxy source.

    Provides proxies with geolocation, updated every 5 minutes.
    https://github.com/proxifly/free-proxy-list
    """

    name = "proxifly"

    # CDN URLs for faster access (JSON format with full data)
    json_urls = {
        "http": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.json",
        "socks4": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.json",
        "socks5": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.json",
    }

    # Plain text alternatives
    text_urls = {
        "http": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "socks4": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt",
        "socks5": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    }

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from proxifly GitHub repository."""
        proxies = []

        # Determine which protocols to fetch
        if protocol:
            protocols = [protocol] if protocol in self.json_urls else []
        else:
            protocols = list(self.json_urls.keys())

        for proto in protocols:
            # Try JSON first for richer data
            json_url = self.json_urls[proto]
            try:
                async with self.session.get(json_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data:
                            try:
                                # Filter by country if specified
                                proxy_country = item.get("geolocation", {}).get("country")
                                if country and proxy_country and proxy_country.upper() != country.upper():
                                    continue

                                proxies.append(RawProxy(
                                    ip=item["ip"],
                                    port=item["port"],
                                    protocol=self.normalize_protocol(proto),
                                    country=proxy_country.upper() if proxy_country else None,
                                    city=item.get("geolocation", {}).get("city"),
                                    anonymity=self._map_anonymity(item.get("anonymity")),
                                    source=self.name,
                                ))
                            except (KeyError, TypeError, ValueError):
                                continue
                        continue  # Move to next protocol
            except Exception:
                pass

            # Fallback to plain text
            text_url = self.text_urls[proto]
            try:
                async with self.session.get(text_url) as response:
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
        """Map proxifly anonymity values to our standard values."""
        if not anonymity:
            return None

        anonymity = anonymity.lower()
        if anonymity in ("elite", "high anonymous"):
            return "elite"
        elif anonymity == "anonymous":
            return "anonymous"
        elif anonymity == "transparent":
            return "transparent"
        return None
