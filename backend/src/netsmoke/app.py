from contextlib import asynccontextmanager

from fastapi import FastAPI

from netsmoke.api.routes import router
from netsmoke.db.init import initialize_database
from netsmoke.services.targets import sync_config_targets
from netsmoke.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    await sync_config_targets()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router, prefix='/api')
