from netsmoke.db.base import Base
from netsmoke.db.session import get_engine
from netsmoke import models  # noqa: F401


async def initialize_database() -> None:
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
