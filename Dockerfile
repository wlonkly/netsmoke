# Stage 1: build the React frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: final image
FROM python:3.12-slim

# fping needs setuid root to send raw ICMP; NET_RAW capability handles this in Docker
RUN apt-get update && apt-get install -y --no-install-recommends fping curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install Python dependencies (no dev extras)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --frozen

# Copy application source
COPY backend/netsmoke/ ./netsmoke/

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist/ /app/static/

# Runtime configuration
ENV NETSMOKE_STATIC_DIR=/app/static
ENV NETSMOKE_CONFIG=/config/config.yaml
ENV NETSMOKE_DB=/data/netsmoke.db

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "netsmoke.main", "--config", "/config/config.yaml", "--db", "/data/netsmoke.db"]
