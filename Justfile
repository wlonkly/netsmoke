set shell := ["bash", "-cu"]

pid_dir := "tmp/dev"
backend_pid := pid_dir + "/backend.pid"
frontend_pid := pid_dir + "/frontend.pid"
backend_log := pid_dir + "/backend.log"
frontend_log := pid_dir + "/frontend.log"

_default:
    @just --list

ensure-dirs:
    @mkdir -p {{pid_dir}} data

setup: ensure-dirs
    @cd backend && uv sync --extra dev
    @cd frontend && npm ci
    @echo "local development dependencies installed"

backend-start: ensure-dirs
    @if [ -f {{backend_pid}} ] && kill -0 "$(cat {{backend_pid}})" 2>/dev/null; then \
        echo "backend already running (pid $(cat {{backend_pid}}))"; \
    else \
        rm -f {{backend_pid}}; \
        cd backend; \
        nohup env NETSMOKE_COLLECTOR_ENABLED=true uv run uvicorn netsmoke.app:app --reload --host 127.0.0.1 --port 8000 > ../{{backend_log}} 2>&1 & \
        echo $! > ../{{backend_pid}}; \
        echo "backend started (pid $(cat ../{{backend_pid}}))"; \
    fi

frontend-start: ensure-dirs
    @if [ -f {{frontend_pid}} ] && kill -0 "$(cat {{frontend_pid}})" 2>/dev/null; then \
        echo "frontend already running (pid $(cat {{frontend_pid}}))"; \
    else \
        rm -f {{frontend_pid}}; \
        cd frontend; \
        nohup npm run dev -- --host 127.0.0.1 --port 5173 > ../{{frontend_log}} 2>&1 & \
        echo $! > ../{{frontend_pid}}; \
        echo "frontend started (pid $(cat ../{{frontend_pid}}))"; \
    fi

start: backend-start frontend-start
    @echo "local development started"
    @echo "backend log: {{backend_log}}"
    @echo "frontend log: {{frontend_log}}"

backend-stop:
    @if [ -f {{backend_pid}} ] && kill -0 "$(cat {{backend_pid}})" 2>/dev/null; then \
        kill "$(cat {{backend_pid}})"; \
        rm -f {{backend_pid}}; \
        echo "backend stopped"; \
    else \
        rm -f {{backend_pid}}; \
        echo "backend not running"; \
    fi

frontend-stop:
    @if [ -f {{frontend_pid}} ] && kill -0 "$(cat {{frontend_pid}})" 2>/dev/null; then \
        kill "$(cat {{frontend_pid}})"; \
        rm -f {{frontend_pid}}; \
        echo "frontend stopped"; \
    else \
        rm -f {{frontend_pid}}; \
        echo "frontend not running"; \
    fi

stop: frontend-stop backend-stop
    @echo "local development stopped"

restart: stop start

status:
    @if [ -f {{backend_pid}} ] && kill -0 "$(cat {{backend_pid}})" 2>/dev/null; then \
        echo "backend: running (pid $(cat {{backend_pid}}))"; \
    else \
        echo "backend: stopped"; \
    fi
    @if [ -f {{frontend_pid}} ] && kill -0 "$(cat {{frontend_pid}})" 2>/dev/null; then \
        echo "frontend: running (pid $(cat {{frontend_pid}}))"; \
    else \
        echo "frontend: stopped"; \
    fi

logs:
    @echo "== backend log =="
    @tail -n 20 {{backend_log}} 2>/dev/null || true
    @echo
    @echo "== frontend log =="
    @tail -n 20 {{frontend_log}} 2>/dev/null || true
