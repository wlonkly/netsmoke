# netsmoke

SmokePing-inspired network latency monitor. Sends batched pings to configured targets, stores round-trip times in SQLite, and renders smoke-band graphs via a React frontend backed by a FastAPI server.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | ≥ 3.12 | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package/venv manager |
| Node.js | ≥ 18 | Frontend build |
| npm | ≥ 9 | Frontend package manager |
| [just](https://github.com/casey/just) | latest | Task runner |
| fping | any | Underlying ping tool used by collector |

---

## Quick start

```bash
# 1. Install dependencies
just install

# 2. Copy and edit the config
cp config.example.yaml config.yaml
$EDITOR config.yaml

# 3. Start backend + frontend with hot-reload
just dev
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

`just dev` runs both processes under a single shell; `Ctrl-C` stops both.

---

## Configuration

`config.yaml` controls targets and collection settings:

```yaml
settings:
  ping_count: 20       # pings per measurement (determines smoke band width)
  ping_interval: 60    # seconds between measurements

targets:
  - name: "Google DNS"
    host: "8.8.8.8"
  - folder: "CDNs"        # folders can be nested arbitrarily
    targets:
      - name: "Cloudflare"
        host: "1.1.1.1"
```

The config is loaded once at startup. Change it and restart the backend to pick up new targets. Existing data for removed targets is retained in the database but no longer collected.

---

## Docker

The included `Dockerfile` builds a single image containing the compiled frontend and the Python backend. The backend serves the frontend as static files, so one container on port 8000 is all you need.

### Quick start with Docker Compose

```bash
# 1. Copy and edit the config
cp config.example.yaml config.yaml
$EDITOR config.yaml

# 2. Build and start
docker compose up --build
```

Open http://localhost:8000. The React frontend loads from the same origin, so no CORS configuration is needed.

### Data persistence

By default `docker-compose.yml` uses a named Docker volume (`netsmoke-data`) for `/data` inside the container. The SQLite database lives at `/data/netsmoke.db`.

To use a host directory instead (e.g. for direct file access), replace the volume entry in `docker-compose.yml`:

```yaml
volumes:
  - ./data:/data          # bind-mount host ./data to /data in container
  # - netsmoke-data:/data  # (remove or comment out the named volume line)
```

### NET_RAW capability

fping sends raw ICMP packets, which requires the `NET_RAW` Linux capability. The compose file adds it via `cap_add: [NET_RAW]`. Without it the collector will fail to ping any host. If your container runtime restricts capabilities, you may need to grant it explicitly or run the container with `--cap-add NET_RAW`.

### Building and running manually

```bash
# Build
docker build -t netsmoke .

# Run (named volume for DB, read-only config bind-mount)
docker run -d \
  --name netsmoke \
  -p 8000:8000 \
  --cap-add NET_RAW \
  -v netsmoke-data:/data \
  -v "$(pwd)/config.yaml":/config/config.yaml:ro \
  netsmoke
```

---

## Task runner (`just`)

| Command | What it does |
|---------|-------------|
| `just dev` | Start backend + frontend with hot-reload |
| `just stop` | Stop both services |
| `just status` | Check whether services are running |
| `just backend` | Backend only (with `--reload`) |
| `just frontend` | Frontend only (Vite HMR) |
| `just run` | Production-style run (no reload) |
| `just test` | Run backend test suite |
| `just test-watch` | Re-run tests on file change |
| `just build` | Production frontend build into `frontend/dist/` |
| `just install` | Sync all backend + frontend dependencies |

---

## Project layout

```
backend/
  netsmoke/
    main.py        # CLI entry point (argparse + uvicorn)
    api.py         # FastAPI app, routes, lifespan
    collector.py   # Background task: runs pinger on interval
    pinger.py      # fping wrapper + output parser
    db.py          # aiosqlite helpers (open, insert, query, prune)
    graph.py       # matplotlib smoke-graph renderer
    config.py      # YAML config loader + target tree
  tests/           # pytest test suite (async, uses httpx ASGI transport)
  pyproject.toml   # dependencies, build config, pytest config

frontend/
  src/
    main.jsx         # React entry point
    App.jsx          # Root: layout, active target, zoom state
    App.css          # All styles (CSS variables, dark sidebar / light main)
    api.js           # Thin fetch wrappers (graphUrl, graphUrlWindow, fetchStats, …)
    components/
      Sidebar.jsx          # Hierarchical target tree
      GraphView.jsx        # 4-panel graph view with drag-to-zoom overlay
      ZoomView.jsx         # Single-graph zoom view (editable time range)
  vite.config.js     # Vite + React plugin config; proxies /api → :8000 in dev

config.example.yaml  # Sample config
justfile             # Task runner recipes
```

---

## Backend

### Running directly

```bash
cd backend
uv run netsmoke --config ../config.yaml --db ../netsmoke.db
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--config` / `-c` | `config.yaml` | Path to YAML config |
| `--db` | `netsmoke.db` | Path to SQLite database |
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Bind port |
| `--reload` | off | Auto-reload on Python file changes |
| `--log-level` | `info` | `debug` / `info` / `warning` / `error` |

### API endpoints

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `GET` | `/api/targets` | — | Target tree as JSON |
| `GET` | `/api/graph/{path}` | `range=3h\|2d\|1mo\|1y` | PNG smoke graph (named range) |
| `GET` | `/api/graph/{path}` | `start=<unix>&end=<unix>` | PNG smoke graph (exact window) |
| `GET` | `/api/targets/{path}/stats` | `window=<60-86400>` | `{median_ms, loss_pct, sample_count}` |

When both `start` and `end` are present on the graph endpoint, `range` is ignored.

### Testing

```bash
just test              # run all tests
just test -x -q        # stop on first failure, quiet output
just test tests/test_graph.py  # specific file
just test-watch        # re-run on file change
```

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. API tests create a full FastAPI app instance via `httpx.AsyncClient` + `ASGITransport` — no real server required. DB fixtures use `tmp_path` so tests never touch the live database.

---

## Frontend

### Development

Vite proxies all `/api` and `/health` requests to `http://localhost:8000`, so the frontend dev server (`localhost:5173`) works without CORS issues. See `vite.config.js`.

### Production build

```bash
just build
# Output: frontend/dist/
```

Serve `frontend/dist/` from any static file host (or configure the backend to serve it directly).

### Zoom / time-selection

Drag across any graph panel to select a time range. This opens a single-graph **zoom view** with:
- Editable start/end datetime inputs — change them to re-render the graph
- **Zoom out** — doubles the displayed duration, centered on the current midpoint
- Drag-to-zoom — same interaction works within the zoom view for further drill-down
- **Back** — returns to the 4-panel view

Clicking a different target in the sidebar while in zoom view resets back to the 4-panel view.

---

## Data retention

The backend prunes samples older than 365 days on startup. There is no per-target quota.
