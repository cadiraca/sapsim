"""
SAP SIM — pytest conftest.py
Phase: 7.8
Purpose: Shared fixtures for the comprehensive API test suite.
         - In-memory SQLite test DB via init_persistence
         - FastAPI TestClient via httpx.AsyncClient + ASGITransport
         - DB teardown after each test
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# pytest-asyncio configuration (strict mode is the default in 1.x)
# ---------------------------------------------------------------------------

pytest_plugins = ("pytest_asyncio",)


# ---------------------------------------------------------------------------
# Event-loop: use a session-scoped loop so fixtures share the same loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Temp DB path fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a fresh temp-file path for an isolated test database."""
    return tmp_path / "test_sapsim.db"


# ---------------------------------------------------------------------------
# init/close persistence around every test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def reset_persistence(tmp_path: Path, tmp_db_path: Path):
    """
    Initialise a clean in-memory-backed persistence layer for every test,
    then close and reset it afterwards.

    Also patches PROJECTS_BASE so filesystem writes go to a temp dir
    instead of the real ``projects/`` directory.
    """
    from utils import persistence
    import simulation.engine as _eng_module

    # Ensure no stale state from prior tests
    if persistence._db is not None:
        await persistence.close_persistence()
    persistence._db = None

    # Reset the engine singleton so each test starts with a blank engine.
    # Without this, projects registered by earlier tests pollute later ones.
    _eng_module._engine_instance = None

    # Redirect PROJECTS_BASE to a temp dir so tests don't pollute the real one
    original_projects_base = persistence.PROJECTS_BASE
    test_projects_base = tmp_path / "projects"
    test_projects_base.mkdir(exist_ok=True)
    persistence.PROJECTS_BASE = test_projects_base

    # Also patch the module-level reference used by routes.py
    try:
        import api.routes as _routes_module
        _routes_module.PROJECTS_BASE = test_projects_base
    except Exception:
        pass

    await persistence.init_persistence(tmp_db_path)
    yield
    await persistence.close_persistence()
    persistence._db = None

    # Restore originals
    persistence.PROJECTS_BASE = original_projects_base
    try:
        import api.routes as _routes_module
        _routes_module.PROJECTS_BASE = original_projects_base
    except Exception:
        pass

    # Clean up engine after test too
    _eng_module._engine_instance = None


# ---------------------------------------------------------------------------
# FastAPI async test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """
    Return an httpx AsyncClient wired to the FastAPI app.
    Uses ASGITransport so no real server is started.
    The lifespan is NOT used here — persistence is managed by reset_persistence.
    """
    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Convenience: create a project and return its name
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def project(client: AsyncClient) -> str:
    """Create a default test project and return its name."""
    name = "test-project"
    resp = await client.post("/api/projects", json={"name": name})
    assert resp.status_code == 201, resp.text
    return name
