from functools import lru_cache
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from netsmoke.settings import settings



def _resolve_sqlite_url(database_url: str) -> str:
    prefix = 'sqlite+aiosqlite:///'
    if not database_url.startswith(prefix):
        return database_url

    raw_path = database_url.removeprefix(prefix)
    sqlite_path = Path(raw_path)
    if sqlite_path.parent.exists():
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f'{prefix}{sqlite_path}'

    search_roots = [Path.cwd(), *Path(__file__).resolve().parents]
    for root in search_roots:
        data_dir = root / 'data'
        if data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            return f'{prefix}{(data_dir / sqlite_path.name).resolve()}'

    fallback_dir = (Path.cwd() / 'data').resolve()
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return f'{prefix}{fallback_dir / sqlite_path.name}'



def get_database_url() -> str:
    return _resolve_sqlite_url(settings.database_url)


@lru_cache(maxsize=4)
def get_engine(database_url: str | None = None) -> AsyncEngine:
    return create_async_engine(database_url or get_database_url(), echo=False)


@lru_cache(maxsize=4)
def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(database_url), expire_on_commit=False, class_=AsyncSession)
