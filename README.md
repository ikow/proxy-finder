# Proxy Finder

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Claude Code Skill](https://img.shields.io/badge/Claude_Code-Skill-blueviolet.svg)](skill/)

A free proxy aggregation and validation toolkit designed for **AI agents** and **security researchers**. Fetches 10,000+ proxies from 7 sources, validates them concurrently, and outputs in 8 formats ready for direct tool integration.

## Three Ways to Use

| Interface | Use Case | Setup |
|-----------|----------|-------|
| **Standalone CLI** | Agents, scripts, quick proxy grab | `python3 skill/proxy_finder.py` (zero setup) |
| **REST API** | Persistent service, database, scheduling | `cd backend && python run.py` |
| **Web UI** | Visual browsing, filtering, export | `cd frontend && npm run dev` |

## Quick Start

### Standalone CLI (Recommended for Agents)

Zero setup. Auto-installs dependencies. Works immediately.

```bash
# Find 5 best validated proxies
python3 skill/proxy_finder.py

# 10 SOCKS5 proxies as JSON
python3 skill/proxy_finder.py -n 10 -t socks5 -f json

# Quick proxy for curl (quiet mode, stdout only)
PROXY=$(python3 skill/proxy_finder.py -n 1 -f plain -q)
curl -x $PROXY http://httpbin.org/ip

# Set proxy env vars for all tools
eval "$(python3 skill/proxy_finder.py -f env -q)"

# Generate proxychains config
python3 skill/proxy_finder.py -t socks5 -n 5 -f proxychains
```

### Full Stack (API + Web UI)

```bash
# Backend
cd backend
pip install -r requirements.txt
python run.py
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Web UI: http://localhost:5173
```

## CLI Reference

```
python3 skill/proxy_finder.py [options]
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--type` | `-t` | Protocol: `http`, `https`, `socks4`, `socks5` | all |
| `--country` | `-c` | Country code: `us`, `uk`, `jp`, `de`, etc. | all |
| `--count` | `-n` | Number of proxies to return | 5 |
| `--format` | `-f` | Output format (see below) | table |
| `--timeout` | | Validation timeout (seconds) | 8 |
| `--concurrency` | | Max parallel validations | 100 |
| `--no-validate` | | Skip validation, return raw list | false |
| `--anonymous` | | Only anonymous/elite proxies | false |
| `--fast` | | Fast mode: 4 fastest sources | false |
| `--refresh` | | Ignore cache, fetch fresh | false |
| `--quiet` | `-q` | No progress output (stderr) | false |

### Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `table` | Human-readable table | Terminal display |
| `json` | JSON array with full metadata | Programmatic parsing |
| `plain` | `ip:port` per line | Pipe to tools |
| `url` | `protocol://ip:port` per line | Direct proxy URLs |
| `curl` | Ready-to-paste curl commands | Quick testing |
| `env` | `HTTP_PROXY`/`HTTPS_PROXY` exports | Shell env setup |
| `python` | `requests` library code snippet | Python scripts |
| `proxychains` | `proxychains.conf` format | Proxychains / nmap |

## Tool Integration Examples

### curl
```bash
curl -x $(python3 skill/proxy_finder.py -n1 -f plain -q) http://target.com
```

### Python requests
```python
import subprocess, json
proxies_json = subprocess.check_output([
    "python3", "skill/proxy_finder.py", "-n", "1", "-f", "json", "-q"
])
proxy = json.loads(proxies_json)[0]
import requests
r = requests.get("http://target.com", proxies={"http": proxy["url"], "https": proxy["url"]})
```

### Proxychains + nmap
```bash
python3 skill/proxy_finder.py -t socks5 -n 3 -f proxychains > /tmp/pc.conf
proxychains4 -f /tmp/pc.conf nmap -sT target.com
```

### Environment variables
```bash
eval "$(python3 skill/proxy_finder.py -f env -q)"
wget http://target.com   # Uses proxy automatically
```

## Claude Code Skill

Install as a [Claude Code](https://claude.ai/code) skill for `/proxy-finder` command:

```
/proxy-finder                    # 5 best proxies
/proxy-finder -t socks5 -n 10   # 10 SOCKS5 proxies
/proxy-finder -c us -f json     # US proxies as JSON
```

## Proxy Sources

| Source | Type | Data Quality | Update Frequency |
|--------|------|-------------|-----------------|
| [ProxyScrape](https://proxyscrape.com) | API | IP:Port | Real-time |
| [GeoNode](https://geonode.com) | API | Full metadata | Real-time |
| [Free-Proxy-List](https://free-proxy-list.net) | Scrape | With geolocation | ~15 min |
| [SSLProxies](https://sslproxies.org) | Scrape | HTTPS only | ~15 min |
| [TheSpeedX](https://github.com/TheSpeedX/PROXY-List) | GitHub | Large lists | Hourly |
| [monosans](https://github.com/monosans/proxy-list) | GitHub | JSON + geo | Hourly |
| [proxifly](https://github.com/proxifly/free-proxy-list) | GitHub | JSON + geo | ~5 min |

## Architecture

```
                    ┌─────────────────────────────────┐
                    │     7 Free Proxy Sources         │
                    │  (APIs, GitHub, Web Scraping)    │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      Concurrent Fetcher          │
                    │   (async, dedup, 10k+ proxies)   │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │     Concurrent Validator          │
                    │  TCP check → HTTP test → Score   │
                    │  (100+ concurrent, early-stop)   │
                    └──────────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
   ┌──────────▼─────────┐ ┌───────▼────────┐ ┌─────────▼────────┐
   │   CLI Tool          │ │  REST API      │ │   Web UI         │
   │ (8 output formats)  │ │ (FastAPI)      │ │ (React+TS)       │
   │  Agents / Scripts   │ │  + SQLite DB   │ │  Dashboard       │
   └─────────────────────┘ └────────────────┘ └──────────────────┘
```

## API Endpoints

All endpoints prefixed with `/api`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/proxies` | List proxies with filters & pagination |
| `GET` | `/proxies/best?limit=10` | Top proxies by score |
| `GET` | `/proxies/by-country/{code}` | Proxies by country |
| `GET` | `/proxies/stats` | Aggregate statistics |
| `POST` | `/proxies/refresh` | Fetch from all sources |
| `POST` | `/proxies/validate` | Bulk validation |
| `POST` | `/proxies/validate/stream` | SSE streaming validation |

**Query params**: `protocol`, `country`, `anonymity`, `min_score`, `is_active`, `sort_by`, `sort_order`, `page`, `page_size`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-source`)
3. Add your proxy source in `backend/app/sources/` and `skill/proxy_finder.py`
4. Test with `python3 skill/proxy_finder.py --fast -n 3`
5. Submit a Pull Request

See [CLAUDE.md](CLAUDE.md) for detailed architecture and code conventions.

## Disclaimer

This tool is intended for **authorized security testing**, **research**, and **educational purposes**. Free proxies are inherently unreliable and may expose your traffic. Always:

- Validate proxies before critical use
- Respect target systems' terms of service
- Use responsibly and in compliance with applicable laws
- Never use for unauthorized access or malicious activities

## License

[MIT](LICENSE) - Qi Deng
