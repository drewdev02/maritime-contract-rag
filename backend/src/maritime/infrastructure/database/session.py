from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, Pool

from maritime.core.telemetry.tracer import instrument_engine
from maritime.infrastructure.config import settings


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


def create_engine(
    database_url: str = settings.DATABASE_URL,
    poolclass: type[Pool] | None = None,
) -> AsyncEngine:
    """Creates an asynchronous SQLAlchemy engine."""
    kwargs: dict[str, Any] = {"echo": False, "future": True}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
    created = create_async_engine(database_url, **kwargs)
    instrument_engine(created.sync_engine)
    return created


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Creates an async sessionmaker bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def create_worker_session_factory(
    database_url: str = settings.DATABASE_URL,
) -> async_sessionmaker[AsyncSession]:
    """Creates an async session factory using NullPool for background workers.

    Celery prefork workers invoke asyncio.run() repeatedly. NullPool guarantees
    that connections are never shared across different event loops in the same worker process.
    """
    worker_engine = create_engine(database_url=database_url, poolclass=NullPool)
    return create_session_factory(worker_engine)


# Default engine & sessionmaker
engine = create_engine()
async_session_factory = create_session_factory(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to yield an active database session."""
    async with async_session_factory() as session:
        yield session
