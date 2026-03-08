from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from netsmoke.api.routes import router
from netsmoke.collector.service import CollectorService
from netsmoke.db.init import initialize_database
from netsmoke.services.targets import sync_config_targets
from netsmoke.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    await sync_config_targets()

    collector_task: asyncio.Task[None] | None = None
    if settings.collector_enabled:
        collector_task = asyncio.create_task(CollectorService().run_forever())

    try:
        yield
    finally:
        if collector_task is not None:
            collector_task.cancel()
            with suppress(asyncio.CancelledError):
                await collector_task


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router, prefix='/api')
