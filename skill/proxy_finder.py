#!/usr/bin/env python3
"""
Proxy Finder - Find and validate free proxies instantly.

Standalone tool for agents and CLI use. Auto-installs dependencies.
All progress/status goes to stderr; only results go to stdout.

Usage:
    python3 proxy_finder.py                              # 5 best validated proxies
    python3 proxy_finder.py -n 10 -t socks5              # 10 SOCKS5 proxies
    python3 proxy_finder.py -c us -f json                # US proxies as JSON
    python3 proxy_finder.py --fast -n 3                   # Quick mode, 3 proxies
    python3 proxy_finder.py -f env                        # Export as env vars
    python3 proxy_finder.py -f curl                       # Ready-to-use curl commands
    python3 proxy_finder.py --no-validate -n 50 -f plain  # Raw list, skip validation
"""

import subprocess
import sys
import os


def _ensure_deps():
    """Auto-install missing dependencies silently."""
    required = {
        "aiohttp": "aiohttp",
        "aiohttp_socks": "aiohttp-socks",
        "bs4": "beautifulsoup4",
    }
    missing = []
    for mod, pkg in required.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"  Installing: {', '.join(missing)}...", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing, "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


_ensure_deps()

import asyncio
import json
import time
import random
import argparse
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from bs4 import BeautifulSoup


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

CACHE_DIR = Path(os.environ.get("PROXY_FINDER_CACHE_DIR", "/tmp"))
CACHE_FILE = CACHE_DIR / "proxy_finder_cache.json"
CACHE_TTL_RAW = 1800       # 30 min for raw proxy lists
CACHE_TTL_VALIDATED = 600   # 10 min for validated results

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

TEST_URLS = [
    ("http://ip-api.com/json", "query"),
    ("http://httpbin.org/ip", "origin"),
    ("http://api.ipify.org?format=json", "ip"),
]


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class RawProxy:
    ip: str
    port: int
    protocol: str
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    anonymity: Optional[str] = None
    source: Optional[str] = None


@dataclass
class ValidatedProxy:
    ip: str
    port: int
    protocol: str
    speed: float  # milliseconds
    anonymity: str
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    source: Optional[str] = None

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "address": self.address,
            "url": self.url,
            "speed_ms": self.speed,
            "anonymity": self.anonymity,
            "country": self.country,
            "country_name": self.country_name,
            "city": self.city,
            "source": self.source,
        }

    def to_cache(self) -> dict:
        """Serializable dict with only constructor params."""
        return {
            "ip": self.ip, "port": self.port, "protocol": self.protocol,
            "speed": self.speed, "anonymity": self.anonymity,
            "country": self.country, "country_name": self.country_name,
            "city": self.city, "source": self.source,
        }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _norm_proto(p: str) -> str:
    p = p.lower().strip()
    if p in ("http", "https", "socks4", "socks5"):
        return p
    return "socks5" if p == "socks" else "http"


def _norm_anon(a: str) -> str:
    a = a.lower().strip()
    if "elite" in a or "high" in a:
        return "elite"
    if "anonymous" in a or "medium" in a:
        return "anonymous"
    return "transparent"


def _log(msg: str, quiet: bool = False):
    if not quiet:
        print(msg, file=sys.stderr)


# ──────────────────────────────────────────────
# Proxy Sources (7 sources)
# ──────────────────────────────────────────────

async def _fetch_proxyscrape(session, protocol=None, country=None):
    """ProxyScrape API - fast, large lists."""
    proxies = []
    protocols = [protocol] if protocol else ["http", "socks4", "socks5"]
    for proto in protocols:
        params = {
            "request": "displayproxies", "protocol": proto,
            "timeout": 10000, "country": country or "all",
            "ssl": "all", "anonymity": "all",
        }
        try:
            async with session.get("https://api.proxyscrape.com/v2/", params=params) as r:
                if r.status != 200:
                    continue
                for line in (await r.text()).strip().split("\n"):
                    line = line.strip()
                    if ":" not in line:
                        continue
                    try:
                        ip, port = line.split(":")
                        proxies.append(RawProxy(
                            ip=ip.strip(), port=int(port.strip()),
                            protocol=_norm_proto(proto),
                            country=country.upper() if country else None,
                            source="proxyscrape",
                        ))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            continue
    return proxies


async def _fetch_geonode(session, protocol=None, country=None):
    """GeoNode API - rich metadata."""
    proxies = []
    params = {"limit": 500, "page": 1, "sort_by": "lastChecked", "sort_type": "desc"}
    if protocol:
        params["protocols"] = protocol
    if country:
        params["country"] = country.upper()
    try:
        async with session.get("https://proxylist.geonode.com/api/proxy-list", params=params) as r:
            if r.status != 200:
                return proxies
            data = await r.json()
            for item in data.get("data", []):
                ip, port = item.get("ip"), item.get("port")
                if not ip or not port:
                    continue
                for proto in item.get("protocols", ["http"]):
                    if protocol and proto.lower() != protocol.lower():
                        continue
                    proxies.append(RawProxy(
                        ip=ip, port=int(port), protocol=_norm_proto(proto),
                        country=item.get("country"),
                        country_name=item.get("countryName"),
                        city=item.get("city"),
                        anonymity=_norm_anon(item.get("anonymityLevel", "unknown")),
                        source="geonode",
                    ))
    except Exception:
        pass
    return proxies


async def _fetch_freeproxylist(session, protocol=None, country=None):
    """Free-Proxy-List.net + SSLProxies.org - HTML scrape."""
    proxies = []
    targets = [
        ("https://free-proxy-list.net/", None),
        ("https://www.sslproxies.org/", "https"),
    ]
    for url, force_proto in targets:
        if force_proto and protocol and protocol != force_proto:
            continue
        try:
            async with session.get(url) as r:
                if r.status != 200:
                    continue
                soup = BeautifulSoup(await r.text(), "html.parser")
                table = soup.find("table", class_="table")
                if not table:
                    continue
                tbody = table.find("tbody")
                if not tbody:
                    continue
                for row in tbody.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) < 7:
                        continue
                    try:
                        ip = cols[0].text.strip()
                        port = int(cols[1].text.strip())
                        cc = cols[2].text.strip()
                        cn = cols[3].text.strip()
                        anon = _norm_anon(cols[4].text.strip())
                        proto = force_proto or (
                            "https" if len(cols) > 6
                            and cols[6].text.strip().lower() == "yes"
                            else "http"
                        )
                        if protocol and protocol != proto:
                            continue
                        if country and country.upper() != cc.upper():
                            continue
                        proxies.append(RawProxy(
                            ip=ip, port=port, protocol=proto,
                            country=cc, country_name=cn,
                            anonymity=anon, source="freeproxylist",
                        ))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            continue
    return proxies


async def _fetch_speedx(session, protocol=None, country=None):
    """TheSpeedX/PROXY-List GitHub - huge plain text lists."""
    proxies = []
    urls = {
        "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    }
    protos = [protocol] if protocol and protocol in urls else list(urls.keys())
    for proto in protos:
        try:
            async with session.get(urls[proto]) as r:
                if r.status != 200:
                    continue
                for line in (await r.text()).strip().split("\n"):
                    line = line.strip()
                    if ":" not in line:
                        continue
                    try:
                        ip, port = line.split(":")
                        proxies.append(RawProxy(
                            ip=ip.strip(), port=int(port.strip()),
                            protocol=_norm_proto(proto), source="speedx",
                        ))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            continue
    return proxies


async def _fetch_monosans(session, protocol=None, country=None):
    """monosans/proxy-list GitHub - JSON with geolocation."""
    proxies = []
    try:
        async with session.get(
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"
        ) as r:
            if r.status == 200:
                for item in await r.json():
                    try:
                        proto = item.get("protocol", "http").lower()
                        if protocol and proto != protocol:
                            continue
                        geo = item.get("geolocation", {})
                        pc = geo.get("country", {}).get("code")
                        if country and pc and pc.upper() != country.upper():
                            continue
                        anon_raw = (item.get("anonymity") or "").lower()
                        anon = (
                            "elite" if anon_raw in ("high", "elite")
                            else "anonymous" if anon_raw in ("anonymous", "medium")
                            else "transparent" if anon_raw in ("transparent", "low")
                            else None
                        )
                        proxies.append(RawProxy(
                            ip=item["host"], port=item["port"],
                            protocol=_norm_proto(proto),
                            country=pc.upper() if pc else None,
                            country_name=geo.get("country", {}).get("name"),
                            city=geo.get("city"),
                            anonymity=anon, source="monosans",
                        ))
                    except (KeyError, TypeError, ValueError):
                        continue
                if proxies:
                    return proxies
    except Exception:
        pass

    # Fallback to plain text
    urls = {
        "http": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "socks4": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    }
    protos = [protocol] if protocol and protocol in urls else list(urls.keys())
    for proto in protos:
        try:
            async with session.get(urls[proto]) as r:
                if r.status != 200:
                    continue
                for line in (await r.text()).strip().split("\n"):
                    line = line.strip()
                    if ":" not in line:
                        continue
                    try:
                        ip, port = line.split(":")
                        proxies.append(RawProxy(
                            ip=ip.strip(), port=int(port.strip()),
                            protocol=_norm_proto(proto), source="monosans",
                        ))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            continue
    return proxies


async def _fetch_proxifly(session, protocol=None, country=None):
    """proxifly/free-proxy-list GitHub - JSON, updated every 5 min."""
    proxies = []
    json_urls = {
        "http": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.json",
        "socks4": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.json",
        "socks5": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.json",
    }
    protos = [protocol] if protocol and protocol in json_urls else list(json_urls.keys())
    for proto in protos:
        try:
            async with session.get(json_urls[proto]) as r:
                if r.status != 200:
                    continue
                for item in await r.json():
                    try:
                        pc = item.get("geolocation", {}).get("country")
                        if country and pc and pc.upper() != country.upper():
                            continue
                        anon_raw = (item.get("anonymity") or "").lower()
                        anon = (
                            "elite" if anon_raw in ("elite", "high anonymous")
                            else "anonymous" if anon_raw == "anonymous"
                            else "transparent" if anon_raw == "transparent"
                            else None
                        )
                        proxies.append(RawProxy(
                            ip=item["ip"], port=item["port"],
                            protocol=_norm_proto(proto),
                            country=pc.upper() if pc else None,
                            city=item.get("geolocation", {}).get("city"),
                            anonymity=anon, source="proxifly",
                        ))
                    except (KeyError, TypeError, ValueError):
                        continue
        except Exception:
            continue
    return proxies


# Source registry
_ALL_SOURCES = [
    _fetch_proxyscrape, _fetch_geonode, _fetch_freeproxylist,
    _fetch_speedx, _fetch_monosans, _fetch_proxifly,
]
_FAST_SOURCES = [_fetch_speedx, _fetch_monosans, _fetch_proxifly, _fetch_proxyscrape]


# ──────────────────────────────────────────────
# Aggregator
# ──────────────────────────────────────────────

async def fetch_all(protocol=None, country=None, fast=False):
    """Fetch from all sources concurrently, deduplicate."""
    sources = _FAST_SOURCES if fast else _ALL_SOURCES
    all_proxies = []
    seen = set()

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": UA},
    ) as session:
        tasks = [src(session, protocol, country) for src in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            for p in result:
                key = (p.ip, p.port, p.protocol)
                if key not in seen:
                    seen.add(key)
                    all_proxies.append(p)

    return all_proxies


# ──────────────────────────────────────────────
# Validator
# ──────────────────────────────────────────────

async def _tcp_check(ip: str, port: int, timeout: float = 2) -> bool:
    """Quick TCP port check - fail fast."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def _get_my_ip() -> Optional[str]:
    """Get our real public IP for anonymity detection."""
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5)
        ) as s:
            async with s.get("http://api.ipify.org?format=json") as r:
                if r.status == 200:
                    return (await r.json()).get("ip")
    except Exception:
        pass
    return None


def _detect_anonymity(proxy_ip, response_ip, my_ip):
    if not response_ip:
        return "unknown"
    if my_ip and my_ip in response_ip:
        return "transparent"
    if proxy_ip in response_ip:
        return "anonymous"
    if "," in response_ip:
        return "transparent"
    return "elite"


async def _validate_one(proxy: RawProxy, timeout: int, my_ip: str) -> Optional[ValidatedProxy]:
    """Validate a single proxy. Returns ValidatedProxy or None."""
    # Quick TCP check first
    if not await _tcp_check(proxy.ip, proxy.port, timeout=min(timeout, 3)):
        return None

    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout)

    try:
        if proxy.protocol in ("socks4", "socks5"):
            ptype = ProxyType.SOCKS4 if proxy.protocol == "socks4" else ProxyType.SOCKS5
            connector = ProxyConnector(
                proxy_type=ptype, host=proxy.ip, port=proxy.port, rdns=True,
            )
            session = aiohttp.ClientSession(connector=connector, timeout=client_timeout)
            proxy_url = None
        else:
            session = aiohttp.ClientSession(timeout=client_timeout)
            proxy_url = f"http://{proxy.ip}:{proxy.port}"

        try:
            for test_url, ip_field in TEST_URLS:
                try:
                    start = time.time()
                    async with session.get(test_url, proxy=proxy_url, ssl=False) as r:
                        if r.status == 200:
                            elapsed = (time.time() - start) * 1000
                            response_ip = None
                            try:
                                data = await r.json()
                                response_ip = data.get(ip_field, "")
                            except Exception:
                                pass

                            anonymity = _detect_anonymity(proxy.ip, response_ip, my_ip)
                            if anonymity == "unknown" and proxy.anonymity:
                                anonymity = proxy.anonymity

                            return ValidatedProxy(
                                ip=proxy.ip, port=proxy.port,
                                protocol=proxy.protocol,
                                speed=round(elapsed, 1),
                                anonymity=anonymity,
                                country=proxy.country,
                                country_name=proxy.country_name,
                                city=proxy.city, source=proxy.source,
                            )
                except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
                    continue
        finally:
            await session.close()
    except Exception:
        pass

    return None


async def validate_proxies(
    raw_proxies: list,
    count: int = 5,
    timeout: int = 8,
    concurrency: int = 100,
    anonymous_only: bool = False,
    quiet: bool = False,
) -> list:
    """Validate proxies concurrently with early-stop when enough found."""
    my_ip = await _get_my_ip()
    valid = []
    semaphore = asyncio.Semaphore(concurrency)
    stop_event = asyncio.Event()
    checked = [0]  # mutable counter
    total = len(raw_proxies)

    async def _worker(proxy):
        if stop_event.is_set():
            return
        async with semaphore:
            if stop_event.is_set():
                return
            result = await _validate_one(proxy, timeout, my_ip)
            checked[0] += 1

            if result:
                if anonymous_only and result.anonymity not in ("elite", "anonymous"):
                    return
                valid.append(result)
                if not quiet:
                    print(
                        f"\r  [{len(valid)}/{count}] {result.address} "
                        f"({result.speed:.0f}ms, {result.anonymity})"
                        + " " * 10,
                        end="", file=sys.stderr,
                    )
                # Collect 2x target for better sorting
                if len(valid) >= count * 2:
                    stop_event.set()
            elif not quiet and checked[0] % 100 == 0:
                print(
                    f"\r  Checking... {checked[0]}/{total}, {len(valid)} valid"
                    + " " * 10,
                    end="", file=sys.stderr,
                )

    _log(
        f"  Validating {total} proxies "
        f"(concurrency={concurrency}, timeout={timeout}s)...",
        quiet,
    )

    # Process in chunks for better early-stop
    chunk_size = concurrency * 2
    for i in range(0, total, chunk_size):
        if stop_event.is_set():
            break
        chunk = raw_proxies[i : i + chunk_size]
        tasks = [asyncio.create_task(_worker(p)) for p in chunk]
        await asyncio.gather(*tasks, return_exceptions=True)

    if not quiet:
        print(
            f"\r  Done: {len(valid)} valid proxies found "
            f"(checked {checked[0]}/{total})" + " " * 20,
            file=sys.stderr,
        )

    # Sort by speed, return top N
    valid.sort(key=lambda p: p.speed)
    return valid[:count]


# ──────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────

def _cache_key(protocol, country, anonymous_only):
    return f"v:{protocol or 'all'}:{country or 'all'}:{anonymous_only}"


def _load_cache():
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data):
    try:
        CACHE_FILE.write_text(json.dumps(data, default=str))
    except Exception:
        pass


def get_cached(protocol, country, anonymous_only):
    cache = _load_cache()
    key = _cache_key(protocol, country, anonymous_only)
    entry = cache.get(key)
    if entry and time.time() - entry.get("ts", 0) < CACHE_TTL_VALIDATED:
        try:
            return [ValidatedProxy(**p) for p in entry["proxies"]]
        except Exception:
            pass
    return None


def set_cached(proxies, protocol, country, anonymous_only):
    cache = _load_cache()
    key = _cache_key(protocol, country, anonymous_only)
    cache[key] = {
        "ts": time.time(),
        "proxies": [p.to_cache() for p in proxies],
    }
    _save_cache(cache)


# ──────────────────────────────────────────────
# Output Formatters
# ──────────────────────────────────────────────

def fmt_table(proxies):
    if not proxies:
        return "No valid proxies found."
    header = f"{'Protocol':<10}{'Address':<24}{'Country':<10}{'Speed':<10}{'Anonymity':<12}"
    sep = "-" * len(header)
    lines = [header, sep]
    for p in proxies:
        speed_str = f"{p.speed:.0f}ms"
        lines.append(
            f"{p.protocol:<10}{p.address:<24}{p.country or '??':<10}"
            f"{speed_str:<10}{p.anonymity:<12}"
        )
    return "\n".join(lines)


def fmt_json(proxies):
    return json.dumps([p.to_dict() for p in proxies], indent=2)


def fmt_plain(proxies):
    """ip:port per line - for piping into tools."""
    return "\n".join(p.address for p in proxies)


def fmt_url(proxies):
    """protocol://ip:port per line."""
    return "\n".join(p.url for p in proxies)


def fmt_curl(proxies):
    """Ready-to-paste curl commands."""
    lines = []
    for p in proxies:
        if p.protocol in ("socks4", "socks5"):
            lines.append(f"curl --proxy {p.url} http://httpbin.org/ip")
        else:
            lines.append(f"curl -x {p.address} http://httpbin.org/ip")
    return "\n".join(lines)


def fmt_env(proxies):
    """Environment variable exports for the best proxy."""
    if not proxies:
        return ""
    p = proxies[0]
    return "\n".join([
        f"export HTTP_PROXY={p.url}",
        f"export HTTPS_PROXY={p.url}",
        f"export http_proxy={p.url}",
        f"export https_proxy={p.url}",
    ])


def fmt_python(proxies):
    """Python dict/code snippet for requests library."""
    if not proxies:
        return "# No proxies found"
    p = proxies[0]
    lines = [
        "# Use with requests:",
        "proxies = {",
        f'    "http": "{p.url}",',
        f'    "https": "{p.url}",',
        "}",
        'response = requests.get("http://httpbin.org/ip", proxies=proxies)',
    ]
    if len(proxies) > 1:
        lines.append("")
        lines.append("# All found proxies:")
        lines.append("proxy_list = [")
        for px in proxies:
            lines.append(f'    "{px.url}",')
        lines.append("]")
    return "\n".join(lines)


def fmt_proxychains(proxies):
    """proxychains.conf format."""
    lines = ["# Add to /etc/proxychains.conf or proxychains4.conf", "[ProxyList]"]
    for p in proxies:
        proto = p.protocol
        if proto == "https":
            proto = "http"
        lines.append(f"{proto} {p.ip} {p.port}")
    return "\n".join(lines)


FORMATTERS = {
    "table": fmt_table,
    "json": fmt_json,
    "plain": fmt_plain,
    "url": fmt_url,
    "curl": fmt_curl,
    "env": fmt_env,
    "python": fmt_python,
    "proxychains": fmt_proxychains,
}


# ──────────────────────────────────────────────
# Main CLI
# ──────────────────────────────────────────────

async def run(args):
    """Core run logic."""
    # Normalize inputs
    protocol = args.type
    country = args.country.upper() if args.country else None

    # Check cache first (only for validated results)
    if not args.refresh and not args.no_validate:
        cached = get_cached(protocol, country, args.anonymous)
        if cached and len(cached) >= args.count:
            _log("  Using cached results (use --refresh for fresh)", args.quiet)
            print(FORMATTERS[args.format](cached[: args.count]))
            return

    # Fetch proxies
    mode = "fast" if args.fast else "full"
    _log(f"  Fetching proxies ({mode}, {len(_FAST_SOURCES if args.fast else _ALL_SOURCES)} sources)...", args.quiet)

    t0 = time.time()
    raw = await fetch_all(protocol, country, args.fast)
    _log(f"  Fetched {len(raw)} proxies in {time.time() - t0:.1f}s", args.quiet)

    if not raw:
        print("No proxies found. Try different filters.", file=sys.stderr)
        sys.exit(1)

    # No-validate mode: return raw list
    if args.no_validate:
        results = [
            ValidatedProxy(
                ip=p.ip, port=p.port, protocol=p.protocol,
                speed=0, anonymity=p.anonymity or "unknown",
                country=p.country, country_name=p.country_name,
                city=p.city, source=p.source,
            )
            for p in raw[: args.count]
        ]
        print(FORMATTERS[args.format](results))
        return

    # Shuffle: prefer proxies with metadata (more likely to be good)
    with_meta = [p for p in raw if p.anonymity or p.country]
    without_meta = [p for p in raw if not p.anonymity and not p.country]
    random.shuffle(with_meta)
    random.shuffle(without_meta)
    shuffled = with_meta + without_meta

    # Validate
    valid = await validate_proxies(
        shuffled,
        count=args.count,
        timeout=args.timeout,
        concurrency=args.concurrency,
        anonymous_only=args.anonymous,
        quiet=args.quiet,
    )

    if not valid:
        print(
            "No valid proxies found. Try: --timeout 15, --fast, or different filters.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Cache results
    set_cached(valid, protocol, country, args.anonymous)

    # Output
    if not args.quiet:
        print(file=sys.stderr)
    print(FORMATTERS[args.format](valid))


def main():
    parser = argparse.ArgumentParser(
        description="Find and validate free proxies - standalone agent tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                              Find 5 best proxies
  %(prog)s -n 10 -t socks5              10 SOCKS5 proxies
  %(prog)s -c us -f json                US proxies as JSON
  %(prog)s --fast -n 3                   Quick mode, 3 proxies
  %(prog)s -f env                        Export as shell env vars
  %(prog)s -f curl                       curl commands ready to paste
  %(prog)s -f python                     Python requests snippet
  %(prog)s -f proxychains                proxychains.conf format
  %(prog)s --no-validate -n 50 -f plain  Raw list, no validation
  %(prog)s --anonymous -t socks5         Anonymous SOCKS5 only

output formats:
  table         Human-readable table (default)
  json          JSON array of proxy objects
  plain         ip:port per line (pipe-friendly)
  url           protocol://ip:port per line
  curl          Ready-to-use curl commands
  env           Shell env var exports (HTTP_PROXY, etc.)
  python        Python requests code snippet
  proxychains   proxychains.conf format
""",
    )
    parser.add_argument(
        "-t", "--type",
        choices=["http", "https", "socks4", "socks5"],
        help="protocol type filter",
    )
    parser.add_argument(
        "-c", "--country",
        help="country code, e.g. us, uk, jp, de",
    )
    parser.add_argument(
        "-n", "--count",
        type=int, default=5,
        help="number of proxies to return (default: 5)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=FORMATTERS.keys(), default="table",
        help="output format (default: table)",
    )
    parser.add_argument(
        "--timeout",
        type=int, default=8,
        help="validation timeout in seconds (default: 8)",
    )
    parser.add_argument(
        "--concurrency",
        type=int, default=100,
        help="max concurrent validations (default: 100)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="skip validation, return raw proxy list",
    )
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help="only return anonymous/elite proxies",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="fast mode: fewer sources, quicker results",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignore cache, fetch fresh proxies",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="suppress progress output (stderr)",
    )

    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
