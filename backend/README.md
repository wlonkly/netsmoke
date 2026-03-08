# netsmoke backend

FastAPI service, collector loop, persistence, and graph rendering for netsmoke.

## Local development

Run the backend on macOS when you need real ICMP RTTs instead of Colima-distorted timings.

- `uv sync --extra dev`
- `NETSMOKE_COLLECTOR_ENABLED=true uv run uvicorn netsmoke.app:app --reload --host 127.0.0.1 --port 8000`

With the default settings, the app will discover `../config/netsmoke.yaml` and place SQLite data in `../data/` when `/app/...` paths are absent.
