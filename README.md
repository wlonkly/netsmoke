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

## Notes

- The current graph endpoint serves a deterministic demo SVG so we can iterate on visuals before wiring real measurements.
- The collector and `fping` integration are scaffolded but not implemented yet.
- SQLite is the initial datastore; schema evolution is set up with Alembic scaffolding.
