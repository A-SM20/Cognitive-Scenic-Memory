"""
Async SQLAlchemy database configuration for Cognitive Scene Memory.

Uses aiosqlite for non-blocking SQLite access. All database operations
throughout the project use async session management.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def _get_async_url(url: str) -> str:
    """Convert a standard sqlite URL to an async aiosqlite URL."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


# These are initialized lazily via init_db() so that settings are
# fully resolved (including path resolution) before engine creation.
engine = None
AsyncSessionLocal = None


async def init_db() -> None:
    """
    Initialize the async database engine and create all tables.

    Must be called once at application startup (e.g., in a FastAPI
    lifespan handler). Creates the engine, session factory, and
    issues CREATE TABLE IF NOT EXISTS for every registered model.
    """
    global engine, AsyncSessionLocal

    settings = get_settings()
    async_url = _get_async_url(settings.database_url)

    logger.info("Initializing database: %s", async_url.split("///")[-1])

    engine = create_async_engine(
        async_url,
        echo=False,
        future=True,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import all models so they register with Base.metadata
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that yields an async database session.

    Usage in a route::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Dispose of the database engine on shutdown."""
    global engine
    if engine is not None:
        await engine.dispose()
        logger.info("Database connection closed")
