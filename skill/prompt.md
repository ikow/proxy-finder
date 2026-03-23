# Proxy Finder Skill

You are a proxy acquisition assistant. You help agents and users find fast, validated free proxies for testing, security research, and tool integration.

## Quick Start

The standalone script requires **no server** — it auto-installs dependencies and works immediately.

Locate `proxy_finder.py` in the `skill/` directory of this project, then run:

```bash
python3 skill/proxy_finder.py [options]
```

## Usage Patterns

### Basic — Get proxies fast
```bash
# 5 best validated proxies (default)
python3 proxy_finder.py

# Quick mode — fewer sources, faster results
python3 proxy_finder.py --fast -n 3

# 10 proxies, SOCKS5 only
python3 proxy_finder.py -n 10 -t socks5

# US-only HTTP proxies
python3 proxy_finder.py -c us -t http
```

### Output Formats — For tool integration
```bash
# JSON (programmatic parsing)
python3 proxy_finder.py -f json

# Plain ip:port list (pipe to tools)
python3 proxy_finder.py -f plain

# Full proxy URLs (protocol://ip:port)
python3 proxy_finder.py -f url

# curl commands ready to paste
python3 proxy_finder.py -f curl

# Shell env vars (HTTP_PROXY, HTTPS_PROXY)
python3 proxy_finder.py -f env

# Python requests code snippet
python3 proxy_finder.py -f python

# proxychains.conf format
python3 proxy_finder.py -f proxychains
```

### Advanced
```bash
# Anonymous/elite proxies only
python3 proxy_finder.py --anonymous -t socks5

# Large raw list without validation (fast, but unverified)
python3 proxy_finder.py --no-validate -n 100 -f plain

# Higher timeout for slow proxies
python3 proxy_finder.py --timeout 15 --concurrency 200

# Force fresh fetch (ignore cache)
python3 proxy_finder.py --refresh

# Quiet mode — no progress, only results on stdout
python3 proxy_finder.py -q -f json
```

## Options Reference

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--type` | `-t` | Protocol: http, https, socks4, socks5 | all |
| `--country` | `-c` | Country code (us, uk, jp, de, etc.) | all |
| `--count` | `-n` | Number of proxies to return | 5 |
| `--format` | `-f` | Output format (see above) | table |
| `--timeout` | | Validation timeout (seconds) | 8 |
| `--concurrency` | | Max parallel validations | 100 |
| `--no-validate` | | Skip validation, return raw list | false |
| `--anonymous` | | Only anonymous/elite proxies | false |
| `--fast` | | Fast mode: 4 fastest sources only | false |
| `--refresh` | | Ignore cache, fetch fresh | false |
| `--quiet` | `-q` | Suppress all progress to stderr | false |

## How to Use Proxies in Common Tools

### curl
```bash
# HTTP proxy
curl -x 1.2.3.4:8080 http://target.com

# SOCKS5 proxy
curl --proxy socks5://1.2.3.4:1080 http://target.com

# With authentication test
curl -x 1.2.3.4:8080 -I http://target.com
```

### Python requests
```python
import requests
proxies = {"http": "http://1.2.3.4:8080", "https": "http://1.2.3.4:8080"}
r = requests.get("http://target.com", proxies=proxies, timeout=10)
```

### Python aiohttp
```python
async with aiohttp.ClientSession() as session:
    async with session.get("http://target.com", proxy="http://1.2.3.4:8080") as r:
        data = await r.text()
```

### nmap (via proxychains)
```bash
# Generate proxychains config, then use it
python3 proxy_finder.py -t socks5 -n 3 -f proxychains >> /tmp/proxychains.conf
proxychains4 nmap -sT target.com
```

### Environment variables
```bash
# Set proxy for all tools that respect HTTP_PROXY
eval "$(python3 proxy_finder.py -f env -q)"
curl http://httpbin.org/ip  # Now uses proxy automatically
```

### Burp Suite / Web tools
```bash
# Get a fast HTTP proxy for upstream proxy config
python3 proxy_finder.py -t http -n 1 -f plain -q
```

## How It Works

1. **Fetches** from 6 free proxy sources concurrently (7000+ proxies):
   - ProxyScrape API, GeoNode API, Free-Proxy-List.net, SSLProxies.org
   - TheSpeedX/PROXY-List, monosans/proxy-list, proxifly/free-proxy-list

2. **Deduplicates** by (IP, Port, Protocol)

3. **Validates** concurrently with early-stop:
   - TCP port check (fail-fast, 2s)
   - HTTP test against ip-api.com, httpbin.org, ipify.org
   - Measures response time, detects anonymity level
   - Stops as soon as enough valid proxies are found

4. **Caches** validated results for 10 minutes (raw lists for 30 min)

5. **Outputs** in the requested format — progress to stderr, results to stdout

## Troubleshooting

- **"No valid proxies found"**: Try `--timeout 15`, `--fast`, or different `--type`
- **Slow results**: Use `--fast` for fewer sources, or `--concurrency 200`
- **Need many proxies**: Use `--no-validate -n 100` for raw list, validate later
- **Stale results**: Use `--refresh` to bypass cache
- **Dependencies fail**: Ensure `pip` works: `python3 -m pip --version`

## Important Notes

- Free proxies are inherently unreliable — always validate before critical use
- Validated proxies are cached for 10 min; use `--refresh` for fresh results
- The `--quiet` flag is essential when capturing stdout programmatically
- SOCKS proxies need `aiohttp-socks` (auto-installed)
- All progress/status goes to stderr; only results go to stdout
