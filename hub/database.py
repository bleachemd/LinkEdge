from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def init_db() -> None:
    from models import telemetry, device  # noqa: F401 — registers mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Convert telemetry_readings into a TimescaleDB hypertable (idempotent)
        await conn.execute(
            text(
                "SELECT create_hypertable("
                "  'telemetry_readings', 'time',"
                "  if_not_exists => TRUE,"
                "  migrate_data => TRUE"
                ")"
            )
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
