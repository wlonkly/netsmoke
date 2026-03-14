# netsmoke

Modern SmokePing-style network monitoring with a Python backend and React frontend.

## Scaffold status

This repository now contains:

- `backend/`: FastAPI service scaffold, SQLAlchemy models, config loader, graphing utilities, tests
- `frontend/`: React + TypeScript + Vite scaffold with a tree/detail layout and SVG graph preview
- `compose.yaml`: optional local Docker stack for backend and frontend
- `config/netsmoke.yaml`: example runtime config in YAML
- `Justfile`: local development helpers for starting and stopping the host-based stack

## Run locally

For accurate ICMP latency on this Mac, run the backend directly on macOS instead of inside Colima/Docker.

1. Install `fping` on the host.
2. Install dependencies from the repo root:
   - `just setup`
3. Start both services from the repo root:
   - `just start`
4. Open `http://localhost:5173`.
5. Stop both services when finished:
   - `just stop`

Useful helpers:

- `just setup` runs `uv sync --extra dev` in `backend/` and `npm ci` in `frontend/`.
- `just status` shows whether the backend and frontend are running.
- `just logs` prints the last lines from `tmp/dev/backend.log` and `tmp/dev/frontend.log`.
- `just restart` restarts both services.

The backend runs with `NETSMOKE_COLLECTOR_ENABLED=true`, auto-resolves the repo config at `config/netsmoke.yaml`, and stores SQLite data under `data/` when the container-style defaults are not present.

## Docker development

`docker compose up --build` still works for general UI/API development. The frontend now proxies to `http://backend:8000` only when running in Compose; local `npm run dev` defaults to `http://127.0.0.1:8000`.

## Current state

- The backend now runs as a long-lived FastAPI service that loads YAML config, syncs targets into SQLite, collects ICMP samples with `fping`, stores measurement rounds plus raw ping samples, and renders SmokePing-style SVG graphs from persisted data.
- The frontend now shows the configured target tree, target detail, Day/Week/Month/Year graph range selector, collector status, and recent measurement rounds, with automatic refresh during development.
- Local macOS backend development is now the recommended path for trustworthy latency measurements on this machine.

## Known caveats

- Under Colima on macOS, ICMP latency values gathered inside the container do not match host-network RTTs. The app is functioning, but the measured RTT reflects the Colima/container networking environment rather than trustworthy host-level Internet latency.
- SQLite table creation is currently driven directly from SQLAlchemy metadata at startup. Alembic is scaffolded, but real schema migrations are still pending.
