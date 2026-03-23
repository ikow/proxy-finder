# CLAUDE.md - AI Agent Guide for proxy-finder

## What is this project?

A free proxy aggregation and validation toolkit with three interfaces:
1. **Standalone CLI** (`skill/proxy_finder.py`) - Zero-setup, self-contained proxy finder for agents
2. **REST API** (`backend/`) - FastAPI service with SQLite storage and 7 proxy sources
3. **Web UI** (`frontend/`) - React dashboard for browsing and managing proxies

## Quick Commands

### Standalone CLI (recommended for agents)
```bash
# Find 5 best validated proxies
python3 skill/proxy_finder.py

# Fast mode, 3 SOCKS5 proxies as JSON
python3 skill/proxy_finder.py --fast -n 3 -t socks5 -f json -q

# Get a proxy for curl
PROXY=$(python3 skill/proxy_finder.py -n 1 -f plain -q)
curl -x $PROXY http://httpbin.org/ip
```

### Backend API
```bash
cd backend && pip install -r requirements.txt && python run.py
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

### Frontend
```bash
cd frontend && npm install && npm run dev
# UI at http://localhost:5173
```

## Project Structure

```
proxy-finder/
├── skill/                    # Standalone agent skill (START HERE)
│   ├── proxy_finder.py       # Self-contained CLI tool, auto-installs deps
│   ├── prompt.md             # Agent skill instructions
│   └── SKILL.toml            # Skill manifest
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── config.py         # Settings (DB, validation, CORS)
│   │   ├── database.py       # SQLAlchemy async + SQLite
│   │   ├── models.py         # Proxy ORM model
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── routers/proxies.py # All API endpoints
│   │   ├── services/
│   │   │   ├── fetcher.py    # Multi-source proxy fetcher
│   │   │   └── validator.py  # Concurrent proxy validator
│   │   └── sources/          # Proxy source implementations
│   │       ├── base.py       # ProxySource ABC + RawProxy dataclass
│   │       ├── proxyscrape.py
│   │       ├── geonode.py
│   │       ├── freeproxy.py  # Free-Proxy-List + SSLProxies
│   │       ├── github_speedx.py
│   │       ├── github_monosans.py
│   │       └── github_proxifly.py
│   ├── requirements.txt
│   └── run.py                # Uvicorn launcher
└── frontend/                 # React + TypeScript web UI
    ├── src/
    │   ├── components/       # Dashboard, ProxyTable, Filters, etc.
    │   ├── pages/            # ProxyBrowser page
    │   ├── services/api.ts   # Axios API client
    │   └── App.tsx
    ├── package.json
    └── vite.config.ts
```

## Key Architecture Decisions

- **Async everywhere**: Backend uses `asyncio` + `aiohttp` for concurrent fetching/validation
- **7 proxy sources**: ProxyScrape, GeoNode, Free-Proxy-List, SSLProxies, SpeedX, monosans, proxifly
- **Validation strategy**: TCP check (fail-fast) -> HTTP test (3 endpoints) -> first success wins
- **Scoring**: Speed (0-40) + Stability (0-30) + Anonymity (0-30) = 0-100 score
- **SOCKS support**: via `aiohttp-socks` library for SOCKS4/SOCKS5 proxies
- **Standalone skill**: `skill/proxy_finder.py` duplicates core logic intentionally to be zero-dependency portable

## Code Conventions

- Python: async/await, type hints, dataclasses
- Frontend: TypeScript, React Query, Tailwind CSS
- All proxy sources implement `ProxySource` ABC from `backend/app/sources/base.py`
- Status/progress output goes to stderr, results to stdout (in CLI tool)

## Adding a New Proxy Source

1. Create `backend/app/sources/your_source.py` extending `ProxySource`
2. Implement `async def fetch(self, protocol, country) -> list[RawProxy]`
3. Register in `backend/app/services/fetcher.py` sources list
4. Add matching fetcher function in `skill/proxy_finder.py` source registry

## Testing

```bash
# Test standalone CLI
python3 skill/proxy_finder.py --fast -n 2

# Test backend
cd backend && python -c "from app.main import app; print('OK')"

# Test frontend build
cd frontend && npm run build
```
