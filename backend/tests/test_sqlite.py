"""
SAP SIM — SQLite Functional Test Suite
Phase: 7.7
Purpose: Functional / integration tests for the SQLite persistence layer.
         Tests operate on a real (temporary) SQLite database — no mocking.

Coverage:
  1. init_db — schema bootstrap, idempotency
  2. Database class — project CRUD (save / load / list)
  3. Database class — feed events (append / query / filter)
  4. Database class — agent state (save / load)
  5. Database class — memory summaries (save / load)
  6. utils.persistence high-level API (init_persistence → save/load wrappers)
  7. Edge cases — missing data returns None, not raises

Run:
    cd backend
    source venv/bin/activate
    python -m pytest tests/test_sqlite.py -v
  or directly:
    python tests/test_sqlite.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio  # noqa: F401 — registers the asyncio marker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_db() -> Path:
    """Return a unique temp-file path for each test (no auto-cleanup needed — tmp)."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    return Path(tf.name)


# ---------------------------------------------------------------------------
# 1. init_db — schema bootstrap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_db_creates_tables() -> None:
    """init_db should create all expected tables without error."""
    from db.schema import init_db, TABLE_DEFINITIONS, INDEX_DEFINITIONS
    import aiosqlite

    db_path = _tmp_db()
    await init_db(db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cur:
            rows = await cur.fetchall()
        table_names = {r[0] for r in rows}

    expected = {"projects", "agents", "feed_events", "meetings",
                "decisions", "tools", "test_cases", "lessons", "memory_summaries"}
    assert expected.issubset(table_names), (
        f"Missing tables: {expected - table_names}"
    )
    assert len(TABLE_DEFINITIONS) == 9, (
        f"Expected 9 table definitions, got {len(TABLE_DEFINITIONS)}"
    )
    assert len(INDEX_DEFINITIONS) == 11, (
        f"Expected 11 index definitions, got {len(INDEX_DEFINITIONS)}"
    )


@pytest.mark.asyncio
async def test_init_db_is_idempotent() -> None:
    """Calling init_db twice on the same path must not raise."""
    from db.schema import init_db

    db_path = _tmp_db()
    await init_db(db_path)
    await init_db(db_path)  # second call — should be a no-op


@pytest.mark.asyncio
async def test_init_db_wal_mode() -> None:
    """Database should be in WAL journal mode after init_db."""
    from db.schema import init_db
    import aiosqlite

    db_path = _tmp_db()
    await init_db(db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
    assert row[0] == "wal", f"Expected WAL, got {row[0]}"


# ---------------------------------------------------------------------------
# 2. Database class — project CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_save_and_load_project() -> None:
    """Save a project, load it back, verify all fields round-trip correctly."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        project = {
            "id":            "proj-001",
            "name":          "TestSAPProject",
            "status":        "active",
            "config":        {"litellm_base_url": "http://localhost:4000", "tier": 1},
            "current_phase": "Explore",
            "current_day":   7,
        }
        await db.save_project(project)
        loaded = await db.load_project("TestSAPProject")

        assert loaded is not None, "load_project returned None"
        assert loaded["id"]            == "proj-001"
        assert loaded["name"]          == "TestSAPProject"
        assert loaded["status"]        == "active"
        assert loaded["current_phase"] == "Explore"
        assert loaded["current_day"]   == 7
        # Config should be deserialised back to a dict
        assert isinstance(loaded["config"], dict)
        assert loaded["config"]["tier"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_load_project_returns_none_when_missing() -> None:
    """Loading a non-existent project must return None, not raise."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        result = await db.load_project("does-not-exist")
        assert result is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_save_project_upsert() -> None:
    """Saving the same project twice should update, not duplicate."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        project = {"id": "proj-002", "name": "UpsertTest",
                   "status": "active", "current_phase": "Prepare", "current_day": 1}
        await db.save_project(project)

        # Update the project
        project["current_phase"] = "Realize"
        project["current_day"]   = 42
        await db.save_project(project)

        loaded = await db.load_project("UpsertTest")
        assert loaded is not None
        assert loaded["current_phase"] == "Realize"
        assert loaded["current_day"]   == 42

        # list_projects should have exactly 1 entry
        all_projects = await db.list_projects()
        assert len(all_projects) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_list_projects() -> None:
    """list_projects should return all saved projects in order."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        for i in range(3):
            await db.save_project({
                "id": f"p{i}", "name": f"Project{i}",
                "status": "active", "current_phase": "Prepare", "current_day": i + 1,
            })

        projects = await db.list_projects()
        assert len(projects) == 3
        names = [p["name"] for p in projects]
        assert "Project0" in names
        assert "Project1" in names
        assert "Project2" in names
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 3. Feed events — append / query / filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_append_and_query_events() -> None:
    """Appended events should be retrievable in order."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        # Minimal project needed for FK
        await db.save_project({"id": "proj-ev", "name": "EventProject",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})

        events_to_save = [
            {"event_type": "agent_action", "agent_id": "PM_ALEX", "phase": "Prepare", "day": 1,
             "content": "Alex opened the kickoff meeting."},
            {"event_type": "agent_thought", "agent_id": "ARCH_SARA", "phase": "Prepare", "day": 1,
             "content": "Sara reviewed the architecture scope."},
            {"event_type": "system",       "agent_id": None,       "phase": "Prepare", "day": 2,
             "content": "Simulation tick: day advanced to 2."},
        ]
        for ev in events_to_save:
            await db.append_event("proj-ev", ev)

        # Retrieve all
        loaded = await db.get_events("proj-ev")
        assert len(loaded) == 3, f"Expected 3 events, got {len(loaded)}"

        # Check content round-trip
        assert loaded[0]["event_type"] == "agent_action"
        assert loaded[0]["content"]    == "Alex opened the kickoff meeting."
        assert loaded[1]["agent_id"]   == "ARCH_SARA"
        assert loaded[2]["event_type"] == "system"

        # Filter by event_type
        actions = await db.get_events("proj-ev", event_type="agent_action")
        assert len(actions) == 1
        assert actions[0]["agent_id"] == "PM_ALEX"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_get_events_pagination() -> None:
    """get_events limit/offset should page correctly."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "pg-proj", "name": "PaginationProject",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})
        for i in range(10):
            await db.append_event("pg-proj", {"event_type": "tick", "day": i + 1, "seq": i})

        page1 = await db.get_events("pg-proj", limit=4, offset=0)
        page2 = await db.get_events("pg-proj", limit=4, offset=4)
        page3 = await db.get_events("pg-proj", limit=4, offset=8)

        assert len(page1) == 4
        assert len(page2) == 4
        assert len(page3) == 2
        assert page1[0]["seq"] == 0
        assert page2[0]["seq"] == 4
        assert page3[0]["seq"] == 8
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 4. Agent state — save / load
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_save_and_load_agent() -> None:
    """Agent state should persist and round-trip faithfully."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "ag-proj", "name": "AgentProject",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})

        state = {
            "id":        "PM_ALEX",
            "codename":  "PM_ALEX",
            "role":      "Project Manager",
            "status":    "active",
            "memory":    ["Kickoff held on day 1", "Risks: timeline pressure"],
            "turn_count": 3,
            "last_response": "I've aligned the team on sprint 1 objectives.",
        }
        await db.save_agent("ag-proj", "PM_ALEX", state)
        loaded = await db.load_agent("ag-proj", "PM_ALEX")

        assert loaded is not None
        assert loaded["codename"]     == "PM_ALEX"
        assert loaded["role"]         == "Project Manager"
        assert loaded["turn_count"]   == 3
        assert isinstance(loaded["memory"], list)
        assert len(loaded["memory"])  == 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_load_agent_returns_none_when_missing() -> None:
    """Loading an agent that was never saved must return None."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "ag-proj2", "name": "AgentProject2",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})
        result = await db.load_agent("ag-proj2", "GHOST_AGENT")
        assert result is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_agent_upsert() -> None:
    """Saving the same agent twice should update, not duplicate."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "ag-proj3", "name": "AgentProject3",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})

        await db.save_agent("ag-proj3", "ARCH_SARA", {"id": "ARCH_SARA",
                                                       "turn_count": 1, "role": "Architect"})
        await db.save_agent("ag-proj3", "ARCH_SARA", {"id": "ARCH_SARA",
                                                       "turn_count": 5, "role": "Architect"})

        loaded = await db.load_agent("ag-proj3", "ARCH_SARA")
        assert loaded is not None
        assert loaded["turn_count"] == 5

        agents = await db.list_agents("ag-proj3")
        assert len(agents) == 1
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 5. Memory summaries — save / load
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_save_and_load_memory() -> None:
    """Memory summary should persist and be returned as a string."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "mem-proj", "name": "MemoryProject",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})

        summary = (
            "## PM_ALEX Memory Summary\n"
            "- Kickoff completed Day 1; 30 agents introduced.\n"
            "- Risk: customer key users are unavailable on Fridays.\n"
            "- Next: Blueprint workshop scheduled for Day 5.\n"
        )
        await db.save_memory("mem-proj", "PM_ALEX", summary)
        loaded = await db.load_memory("mem-proj", "PM_ALEX")

        assert loaded is not None
        assert "Kickoff completed" in loaded
        assert "Blueprint workshop" in loaded
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_load_memory_returns_none_when_missing() -> None:
    """Loading memory for an agent with no summary must return None."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "mem-proj2", "name": "MemoryProject2",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})
        result = await db.load_memory("mem-proj2", "NOBODY")
        assert result is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_memory_upsert() -> None:
    """Saving memory twice for the same agent should overwrite, not duplicate."""
    from db.repository import Database

    db = Database(_tmp_db())
    await db.connect()
    try:
        await db.save_project({"id": "mem-proj3", "name": "MemoryProject3",
                               "status": "active", "current_phase": "Prepare", "current_day": 1})

        await db.save_memory("mem-proj3", "FI_CHEN", "Initial summary.")
        await db.save_memory("mem-proj3", "FI_CHEN", "Updated summary with more detail.")

        loaded = await db.load_memory("mem-proj3", "FI_CHEN")
        assert loaded == "Updated summary with more detail."

        # Verify no duplicates in the table
        import aiosqlite
        async with aiosqlite.connect(str(db._db_path)) as raw:
            async with raw.execute(
                "SELECT COUNT(*) FROM memory_summaries WHERE project_id='mem-proj3' AND codename='FI_CHEN'"
            ) as cur:
                row = await cur.fetchone()
        assert row[0] == 1, f"Expected 1 row, got {row[0]}"
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 6. utils.persistence high-level API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persistence_full_lifecycle() -> None:
    """
    Full round-trip via the utils.persistence module-level API:
      init_persistence → save_project_state → load_project_state (verify)
      → append_feed_event → save_agent_state → load_agent_state (verify)
      → save_memory_summary → load_memory_summary (verify)
      → close_persistence
    """
    from utils import persistence  # noqa: PLC0415

    # Reset module-level state (needed when running multiple tests in same process)
    persistence._db = None

    db_path = _tmp_db()
    await persistence.init_persistence(db_path)
    try:
        project_state = {
            "status":        "active",
            "current_phase": "Explore",
            "simulated_day": 5,
            "litellm_base_url": "http://localhost:4000",
            "agents_initialised": True,
        }
        await persistence.save_project_state("p7-smoke-test", project_state)

        loaded_state = await persistence.load_project_state("p7-smoke-test")
        assert loaded_state is not None, "load_project_state returned None"
        assert loaded_state["current_phase"] == "Explore"
        assert loaded_state["simulated_day"] == 5

        # Feed event
        await persistence.append_feed_event("p7-smoke-test", {
            "event_type": "agent_action",
            "agent_id":   "PM_ALEX",
            "phase":      "Explore",
            "day":        5,
            "content":    "Alex facilitated the fit-gap workshop.",
        })

        # Retrieve event through Database directly
        db = persistence.get_db()
        events = await db.get_events("p7-smoke-test")
        assert len(events) == 1
        assert events[0]["agent_id"] == "PM_ALEX"

        # Agent state
        await persistence.save_agent_state("p7-smoke-test", "PM_ALEX", {
            "id":       "PM_ALEX",
            "codename": "PM_ALEX",
            "role":     "Project Manager",
            "turn_count": 10,
        })
        agent = await persistence.load_agent_state("p7-smoke-test", "PM_ALEX")
        assert agent is not None
        assert agent["turn_count"] == 10

        # Memory
        await persistence.save_memory_summary("p7-smoke-test", "PM_ALEX",
                                              "Summary: Alex managed sprint 2 successfully.")
        mem = await persistence.load_memory_summary("p7-smoke-test", "PM_ALEX")
        assert mem is not None
        assert "sprint 2" in mem

    finally:
        await persistence.close_persistence()
        persistence._db = None  # cleanup module state


@pytest.mark.asyncio
async def test_persistence_load_returns_none_on_missing_project() -> None:
    """Loading a project that was never saved must return None."""
    from utils import persistence

    persistence._db = None
    db_path = _tmp_db()
    await persistence.init_persistence(db_path)
    try:
        result = await persistence.load_project_state("no-such-project")
        assert result is None
    finally:
        await persistence.close_persistence()
        persistence._db = None


@pytest.mark.asyncio
async def test_persistence_get_db_raises_when_not_initialised() -> None:
    """get_db() must raise RuntimeError when called before init_persistence."""
    from utils import persistence

    persistence._db = None  # ensure not initialised
    with pytest.raises(RuntimeError, match="Persistence not initialised"):
        persistence.get_db()


# ---------------------------------------------------------------------------
# Entry-point for running directly: python tests/test_sqlite.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    sys.exit(result.returncode)
