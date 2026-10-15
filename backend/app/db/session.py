from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def configure(url: str | None = None) -> None:
    """Create the engine. Called once at startup, and by tests with their own URL."""
    global _engine, _factory
    url = url or get_settings().database_url
    kwargs = {} if url.startswith("sqlite") else {"pool_pre_ping": True, "pool_size": 10}
    _engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys unless asked, so cascades would silently
        # not happen in tests while they do in Postgres.
        @event.listens_for(_engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    _factory = async_sessionmaker(_engine, expire_on_commit=False)


def engine() -> AsyncEngine:
    if _engine is None:
        configure()
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _factory is None:
        configure()
    return _factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
