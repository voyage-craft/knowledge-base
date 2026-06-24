import pytest
import pytest_asyncio
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# CRITICAL: Set test database BEFORE importing any app modules
# This ensures tests never touch the production database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_knowledge.db"
os.environ["ADMIN_INITIAL_PASSWORD"] = "test-admin-password-123"
os.environ["INTERNAL_API_SECRET"] = "test-internal-secret-for-testing"

from app.main import app
from app.core.database import Base
from app.api.auth import ensure_admin_user
# Ensure all models are imported so their tables are registered
from app.models import user, document, export_job, graph, import_batch  # noqa: F401

# Create a separate test engine (uses the test database URL)
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)
TestAsyncSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Test admin credentials
TEST_ADMIN_PASSWORD = "test-admin-password-123"


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA cache_size=-64000"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        await ensure_admin_user(session)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
