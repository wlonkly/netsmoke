"""
FastAPI application and route definitions.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from netsmoke.config import Config, load_config, tree_to_json, target_full_path
from netsmoke.db import open_db, prune_old_data, query_latest_stats
from netsmoke.graph import render_graph_for_target, RANGE_SECONDS

logger = logging.getLogger(__name__)

# Module-level state
_config: Config | None = None
_db: aiosqlite.Connection | None = None


def set_state(config: Config, db: aiosqlite.Connection) -> None:
    """
    Inject shared state directly (used by tests and by main.py in no-reload mode).
    When called before app startup, the lifespan will skip env-var initialization.
    """
    global _config, _db
    _config = config
    _db = db


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("DB not initialized")
    return _db


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle.

    If state was pre-injected via set_state() (tests, no-reload main.py),
    the lifespan is a pass-through.  When invoked by uvicorn --reload (or
    `uvicorn netsmoke.api:create_app --factory`), it reads env vars to
    initialize config, db, and the collector.
    """
    from netsmoke.collector import run_collector

    collector_task = None
    owns_db = False

    if _config is None or _db is None:
        config_path = os.environ.get("NETSMOKE_CONFIG", "config.yaml")
        db_path = os.environ.get("NETSMOKE_DB", "netsmoke.db")

        logger.info("Lifespan: loading config from %s", config_path)
        config = load_config(config_path)
        db = await open_db(db_path)

        pruned = await prune_old_data(db)
        if pruned:
            logger.info("Pruned %d old samples", pruned)

        set_state(config, db)
        owns_db = True

        collector_task = asyncio.create_task(
            run_collector(config, db), name="collector"
        )
        logger.info(
            "Collector started: %d targets, interval=%ds",
            len(config.all_targets),
            config.ping_interval,
        )

    yield

    if collector_task:
        collector_task.cancel()
        try:
            await collector_task
        except asyncio.CancelledError:
            pass
    if owns_db and _db is not None:
        await _db.close()
        logger.info("Database closed.")


def create_app() -> FastAPI:
    app = FastAPI(title="netsmoke", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/targets")
    async def get_targets() -> list[dict[str, Any]]:
        config = get_config()
        return tree_to_json(config.tree)

    @app.get("/api/graph/{target_path:path}")
    async def get_graph(
        target_path: str,
        range: str = Query(default="3h", pattern="^(3h|2d|1mo|1y)$"),
    ) -> Response:
        config = get_config()
        db = get_db()

        valid_paths = {target_full_path(t) for t in config.all_targets}
        if target_path not in valid_paths:
            raise HTTPException(status_code=404, detail=f"Target not found: {target_path}")

        png_bytes = await render_graph_for_target(
            db, target_path, range, num_pings=config.ping_count
        )
        return Response(content=png_bytes, media_type="image/png")

    @app.get("/api/targets/{target_path:path}/stats")
    async def get_stats(
        target_path: str,
        window: int = Query(default=300, ge=60, le=86400),
    ) -> dict[str, Any]:
        config = get_config()
        db = get_db()

        valid_paths = {target_full_path(t) for t in config.all_targets}
        if target_path not in valid_paths:
            raise HTTPException(status_code=404, detail=f"Target not found: {target_path}")

        stats = await query_latest_stats(db, target_path, window_seconds=window)
        return {"target": target_path, **stats}

    return app
