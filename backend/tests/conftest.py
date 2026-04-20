"""Shared pytest fixtures.

Most tests in this suite operate on services in isolation and don't need a
real DB. The fixtures here are opt-in via explicit use in specific tests
(see test_api_routers.py) so they don't slow the default suite.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from promptarmor.config import settings
from promptarmor.database import init_db
from promptarmor.middleware import rate_limit


@pytest_asyncio.fixture
async def empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Path]:
    """Point settings at a fresh empty SQLite DB for the duration of the test."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(settings, "database_path", str(db_file))
    await init_db()
    yield db_file


@pytest_asyncio.fixture
async def api_client(empty_db: Path) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the FastAPI app with a fresh empty DB."""
    # Import here so the monkeypatched settings take effect first.
    from promptarmor.main import app

    rate_limit._reset_default_limiter()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    rate_limit._reset_default_limiter()
