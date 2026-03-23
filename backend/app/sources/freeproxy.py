from typing import Optional
from bs4 import BeautifulSoup
from .base import ProxySource, RawProxy


class FreeProxyListSource(ProxySource):
    """Free-Proxy-List.net scraper."""

    name = "freeproxylist"
    url = "https://free-proxy-list.net/"

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch proxies from Free-Proxy-List.net."""
        proxies = []

        try:
            async with self.session.get(self.url) as response:
                if response.status != 200:
                    return proxies

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                table = soup.find("table", class_="table")
                if not table:
                    return proxies

                tbody = table.find("tbody")
                if not tbody:
                    return proxies

                for row in tbody.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) < 8:
                        continue

                    try:
                        ip = cols[0].text.strip()
                        port = int(cols[1].text.strip())
                        country_code = cols[2].text.strip()
                        country_name = cols[3].text.strip()
                        anonymity_text = cols[4].text.strip().lower()
                        is_https = cols[6].text.strip().lower() == "yes"

                        # Determine protocol
                        proto = "https" if is_https else "http"

                        # Filter by protocol if specified
                        if protocol and protocol.lower() != proto:
                            continue

                        # Filter by country if specified
                        if country and country.upper() != country_code.upper():
                            continue

                        # Parse anonymity
                        anonymity = self.normalize_anonymity(anonymity_text)

                        proxies.append(RawProxy(
                            ip=ip,
                            port=port,
                            protocol=proto,
                            country=country_code,
                            country_name=country_name,
                            anonymity=anonymity,
                            source=self.name,
                        ))

                    except (ValueError, IndexError):
                        continue

        except Exception:
            pass

        return proxies


class SslProxySource(ProxySource):
    """SSL Proxy scraper (HTTPS proxies only)."""

    name = "sslproxy"
    url = "https://www.sslproxies.org/"

    async def fetch(self, protocol: Optional[str] = None, country: Optional[str] = None) -> list[RawProxy]:
        """Fetch HTTPS proxies from SSLProxies.org."""
        # Only return results if no protocol filter or https is requested
        if protocol and protocol.lower() != "https":
            return []

        proxies = []

        try:
            async with self.session.get(self.url) as response:
                if response.status != 200:
                    return proxies

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                table = soup.find("table", class_="table")
                if not table:
                    return proxies

                tbody = table.find("tbody")
                if not tbody:
                    return proxies

                for row in tbody.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) < 7:
                        continue

                    try:
                        ip = cols[0].text.strip()
                        port = int(cols[1].text.strip())
                        country_code = cols[2].text.strip()
                        country_name = cols[3].text.strip()
                        anonymity_text = cols[4].text.strip().lower()

                        # Filter by country if specified
                        if country and country.upper() != country_code.upper():
                            continue

                        anonymity = self.normalize_anonymity(anonymity_text)

                        proxies.append(RawProxy(
                            ip=ip,
                            port=port,
                            protocol="https",
                            country=country_code,
                            country_name=country_name,
                            anonymity=anonymity,
                            source=self.name,
                        ))

                    except (ValueError, IndexError):
                        continue

        except Exception:
            pass

        return proxies
