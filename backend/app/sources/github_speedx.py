from typing import Optional
from .base import ProxySource, RawProxy


class SpeedXSource(ProxySource):
    """TheSpeedX/PROXY-List GitHub proxy source.

    Provides large lists of proxies updated regularly.
    https://github.com/TheSpeedX/PROXY-List
    """

    name = "speedx"

    # Raw GitHub URLs for each protocol
    urls = {
        "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    }

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from TheSpeedX GitHub repository."""
        proxies = []

        # Determine which protocols to fetch
        if protocol:
            protocols = [protocol] if protocol in self.urls else []
        else:
            protocols = list(self.urls.keys())

        for proto in protocols:
            url = self.urls[proto]
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
