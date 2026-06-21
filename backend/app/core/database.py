from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from app.core.config import get_settings
import os
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")), exist_ok=True)

# SQLite uses StaticPool by default; pool_size/max_overflow are not applicable.
# For production scale, migrate to PostgreSQL for true connection pooling.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Use this in API endpoints via: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a standalone database session for background tasks and services.

    This should ONLY be used where FastAPI dependency injection is unavailable:
    - Background tasks (BackgroundTasks.add_task)
    - Service layer internal operations
    - CLI utilities

    For API endpoints, always use: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _migrate_columns(conn):
    """Add missing columns to existing tables (SQLite ALTER TABLE)."""
    migrations = [
        ("api_endpoints", "protocol_mode", "VARCHAR(20) NOT NULL DEFAULT 'auto'"),
    ]
    for table, column, col_type in migrations:
        try:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]
            if column not in columns:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                logger.info("Migration: added %s.%s", table, column)
        except Exception as e:
            logger.debug("Migration check for %s.%s: %s", table, column, e)


async def init_db():
    """Initialize database with WAL mode and optimized settings."""
    async with engine.begin() as conn:
        # Enable WAL mode for better concurrent read performance
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        # Set synchronous mode to NORMAL for better performance
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        # Increase cache size to 64MB
        await conn.execute(text("PRAGMA cache_size=-64000"))
        # Enable foreign keys
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        # Set busy timeout to 5 seconds
        await conn.execute(text("PRAGMA busy_timeout=5000"))

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

        # Run column migrations for existing tables
        await _migrate_columns(conn)

    logger.info("Database initialized with WAL mode and optimized settings")
