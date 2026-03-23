from typing import Optional
from .base import ProxySource, RawProxy


class GeoNodeSource(ProxySource):
    """GeoNode API proxy source."""

    name = "geonode"
    base_url = "https://proxylist.geonode.com/api/proxy-list"

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from GeoNode API."""
        proxies = []

        params = {
            "limit": 500,
            "page": 1,
            "sort_by": "lastChecked",
            "sort_type": "desc",
        }

        if protocol:
            params["protocols"] = protocol
        if country:
            params["country"] = country.upper()

        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    return proxies

                data = await response.json()

                for item in data.get("data", []):
                    ip = item.get("ip")
                    port = item.get("port")

                    if not ip or not port:
                        continue

                    # GeoNode can return multiple protocols per proxy
                    protocols_list = item.get("protocols", ["http"])

                    for proto in protocols_list:
                        if protocol and proto.lower() != protocol.lower():
                            continue

                        proxies.append(RawProxy(
                            ip=ip,
                            port=int(port),
                            protocol=self.normalize_protocol(proto),
                            country=item.get("country"),
                            country_name=item.get("countryName"),
                            city=item.get("city"),
                            anonymity=self.normalize_anonymity(item.get("anonymityLevel", "unknown")),
                            source=self.name,
                        ))

        except Exception:
            pass

        return proxies
