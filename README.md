# netsmoke

Modern SmokePing-style network monitoring with a Python backend and React frontend.

## Scaffold status

This repository now contains:

- `backend/`: FastAPI service scaffold, SQLAlchemy models, config loader, graphing utilities, tests
- `frontend/`: React + TypeScript + Vite scaffold with a tree/detail layout and SVG graph preview
- `compose.yaml`: local development stack for backend and frontend
- `config/netsmoke.yaml`: example runtime config in YAML

## Run locally

1. Start Docker or `colima start` if Docker is not already running.
2. Run `docker compose up --build`.
3. Open `http://localhost:5173`.

## Current state

- The backend now runs as a long-lived FastAPI service that loads YAML config, syncs targets into SQLite, collects ICMP samples with `fping`, stores measurement rounds plus raw ping samples, and renders SmokePing-style SVG graphs from persisted data.
- The frontend now shows the configured target tree, target detail, graph range selector, collector status, and recent measurement rounds, with automatic refresh during development.
- `docker compose up --build` remains the expected local development entrypoint.

## Known caveats

- Under Colima on macOS, ICMP latency values gathered inside the container do not match host-network RTTs. The app is functioning, but the measured RTT reflects the Colima/container networking environment rather than trustworthy host-level Internet latency.
- SQLite table creation is currently driven directly from SQLAlchemy metadata at startup. Alembic is scaffolded, but real schema migrations are still pending.
