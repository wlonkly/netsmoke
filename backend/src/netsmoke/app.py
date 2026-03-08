from contextlib import asynccontextmanager

from fastapi import FastAPI

from netsmoke.api.routes import router
from netsmoke.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(router, prefix="/api")
