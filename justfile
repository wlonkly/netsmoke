config := "config.example.yaml"
db     := "netsmoke.db"
host   := "0.0.0.0"
port   := "8000"

piddir := ".pids"

# Show service status (default)
default:
    @just status

# Show whether backend and frontend are running
status:
    #!/usr/bin/env bash
    _check() {
        local name=$1 pidfile=$2 url=$3
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                echo "$name  UP   pid=$pid  $url"
            else
                echo "$name  DOWN (stale pidfile)"
            fi
        else
            echo "$name  DOWN"
        fi
    }
    _check "backend   " "{{piddir}}/backend.pid"  "http://localhost:{{port}}"
    _check "frontend  " "{{piddir}}/frontend.pid" "http://localhost:5173"

# Start backend + frontend together (both with auto-reload)
dev:
    #!/usr/bin/env bash
    set -e
    root=$(pwd)
    mkdir -p "{{piddir}}"

    cleanup() {
        kill 0
        rm -f "{{piddir}}/backend.pid" "{{piddir}}/frontend.pid"
    }
    trap cleanup EXIT INT TERM

    (cd "$root/backend" && uv run netsmoke \
        --config "$root/{{config}}" \
        --host {{host}} --port {{port}} \
        --reload) &
    echo $! > "{{piddir}}/backend.pid"

    (cd "$root/frontend" && npm run dev) &
    echo $! > "{{piddir}}/frontend.pid"

    wait

# Stop running services
stop:
    #!/usr/bin/env bash
    _stop() {
        local name=$1 pidfile=$2
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" && echo "stopped $name (pid=$pid)"
            else
                echo "$name not running (stale pidfile)"
            fi
            rm -f "$pidfile"
        else
            echo "$name not running"
        fi
    }
    _stop backend  "{{piddir}}/backend.pid"
    _stop frontend "{{piddir}}/frontend.pid"

# Start only the backend (with file-watch reload)
backend:
    cd backend && uv run netsmoke \
        --config ../{{config}} \
        --host {{host}} --port {{port}} \
        --reload

# Start only the frontend dev server (Vite HMR)
frontend:
    cd frontend && npm run dev

# Run the full application (collector + API, no reload)
run:
    cd backend && uv run netsmoke --config ../{{config}} --db ../{{db}}

# Run backend tests
test *args:
    cd backend && uv run pytest {{args}}

# Run backend tests, re-run on file changes
test-watch:
    cd backend && uv run pytest-watch -- -q

# Run frontend tests
test-frontend:
    cd frontend && npm test

# Run frontend tests, re-run on file changes
test-frontend-watch:
    cd frontend && npm run test:watch

# Build the frontend for production
build:
    cd frontend && npm run build

# Install / sync all dependencies
install:
    cd backend && uv sync --all-groups
    cd frontend && npm install

# Import SmokePing RRD data directory into netsmoke
import-smokeping data_dir targets_file db="netsmoke.db" config="config.yaml":
    cd importer && uv run smokeping-import \
        --data-dir "{{data_dir}}" \
        --targets-file "{{targets_file}}" \
        --db "../{{db}}" \
        --config "../{{config}}"
