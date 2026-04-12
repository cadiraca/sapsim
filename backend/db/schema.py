"""
SAP SIM — SQLite Database Schema
Phase: 7.1
Purpose: Defines the full SQLite schema for all simulation data and provides
         the ``init_db`` async function that bootstraps the database on first run.

Design decisions:
  - All structured/variable-length data (config, state, votes, participants,
    transcript, etc.) is stored as JSON TEXT columns for flexibility and
    forward-compatibility.
  - Timestamps use ISO-8601 TEXT (SQLite has no native DATETIME type).
  - Foreign key constraints are declared but SQLite enforces them only when
    ``PRAGMA foreign_keys = ON`` is set per-connection — callers should do this.
  - All CREATE TABLE statements use IF NOT EXISTS so the function is idempotent
    and safe to call on every startup.

Tables
------
  projects          — one row per simulation run / project
  agents            — participating AI agents and their runtime state
  feed_events       — append-only event log (replaces feed/events.jsonl)
  meetings          — meeting records (replaces MeetingLogger JSON artefact)
  decisions         — project decisions and votes (replaces decisions.json)
  tools             — SAP tool landscape (replaces tools.json)
  test_cases        — test strategy items (replaces test_strategy.json)
  lessons           — lessons learned (replaces lessons.json)
  memory_summaries  — compressed per-agent memory (replaces memory/*.md)

Usage::

    import asyncio
    from backend.db.schema import init_db

    asyncio.run(init_db("projects/my_project/sapsim.db"))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema SQL — one CREATE TABLE per simulation data domain
# ---------------------------------------------------------------------------

# Each statement is stored in a module-level list so callers can inspect the
# schema definitions without having to parse the function body.

TABLE_DEFINITIONS: list[str] = [
    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS projects (
        id            TEXT    PRIMARY KEY,
        name          TEXT    NOT NULL UNIQUE,
        status        TEXT    NOT NULL DEFAULT 'active',
        config        TEXT    NOT NULL DEFAULT '{}',   -- JSON: ProjectConfig dict
        current_phase TEXT    NOT NULL DEFAULT 'Prepare',
        current_day   INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ------------------------------------------------------------------
    # agents
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS agents (
        id          TEXT    PRIMARY KEY,
        project_id  TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        codename    TEXT    NOT NULL,
        role        TEXT    NOT NULL,
        status      TEXT    NOT NULL DEFAULT 'active',
        state       TEXT    NOT NULL DEFAULT '{}',   -- JSON: full agent state snapshot
        updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE (project_id, codename)
    )
    """,

    # ------------------------------------------------------------------
    # feed_events  (append-only; replaces feed/events.jsonl)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS feed_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id  TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        event_type  TEXT    NOT NULL,
        agent_id    TEXT,                             -- nullable (system events have no agent)
        phase       TEXT,
        day         INTEGER,
        payload     TEXT    NOT NULL DEFAULT '{}',   -- JSON: event-type-specific data
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ------------------------------------------------------------------
    # meetings  (replaces MeetingLogger artefact)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS meetings (
        id           TEXT    PRIMARY KEY,
        project_id   TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title        TEXT    NOT NULL,
        meeting_type TEXT    NOT NULL,                -- kickoff / blueprint / steering / ad_hoc
        phase        TEXT    NOT NULL,
        participants TEXT    NOT NULL DEFAULT '[]',   -- JSON: list[str]
        transcript   TEXT    NOT NULL DEFAULT '[]',   -- JSON: list[{speaker, text, timestamp}]
        decisions    TEXT    NOT NULL DEFAULT '[]',   -- JSON: list[str]
        actions      TEXT    NOT NULL DEFAULT '[]',   -- JSON: list[{owner, task, due_day, notes}]
        duration     REAL,                            -- minutes (null until finalised)
        day          INTEGER NOT NULL DEFAULT 1,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ------------------------------------------------------------------
    # decisions  (replaces decision_board.py decisions.json)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS decisions (
        id           TEXT    PRIMARY KEY,
        project_id   TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title        TEXT    NOT NULL,
        description  TEXT    NOT NULL DEFAULT '',
        category     TEXT    NOT NULL,                -- technical / functional / organizational / budget
        proposed_by  TEXT    NOT NULL,
        status       TEXT    NOT NULL DEFAULT 'proposed',
        votes        TEXT    NOT NULL DEFAULT '{}',   -- JSON: {agent_id: {vote, reasoning}}
        rationale    TEXT    NOT NULL DEFAULT '',
        impact       TEXT    NOT NULL DEFAULT '',     -- maps to impact_assessment in DecisionBoard
        meeting_id   TEXT    REFERENCES meetings(id) ON DELETE SET NULL,
        proposed_day INTEGER NOT NULL DEFAULT 1,
        resolved_day INTEGER                          -- null until approved/rejected/deferred
    )
    """,

    # ------------------------------------------------------------------
    # tools  (replaces tool_registry.py tools.json)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS tools (
        id            TEXT    PRIMARY KEY,
        project_id    TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name          TEXT    NOT NULL,
        category      TEXT    NOT NULL,               -- config / dev / test / data / security / reporting
        description   TEXT    NOT NULL DEFAULT '',
        sap_module    TEXT    NOT NULL DEFAULT '',
        tcodes        TEXT    NOT NULL DEFAULT '[]',  -- JSON: list[str]
        tables        TEXT    NOT NULL DEFAULT '[]',  -- JSON: list[str]
        announced_by  TEXT    NOT NULL DEFAULT '',
        status        TEXT    NOT NULL DEFAULT 'announced',
        usage_count   INTEGER NOT NULL DEFAULT 0,
        announced_day INTEGER NOT NULL DEFAULT 1
    )
    """,

    # ------------------------------------------------------------------
    # test_cases  (replaces test_strategy.py test_strategy.json)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS test_cases (
        id              TEXT    PRIMARY KEY,
        project_id      TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title           TEXT    NOT NULL,
        module          TEXT    NOT NULL,
        type            TEXT    NOT NULL,             -- unit / integration / uat / regression / performance
        status          TEXT    NOT NULL DEFAULT 'planned',
        assigned_to     TEXT    NOT NULL DEFAULT '',
        priority        INTEGER NOT NULL DEFAULT 1,
        steps           TEXT    NOT NULL DEFAULT '[]', -- JSON: list[str]
        expected_result TEXT    NOT NULL DEFAULT '',
        actual_result   TEXT    NOT NULL DEFAULT '',
        defect_id       TEXT                           -- null unless a defect is linked
    )
    """,

    # ------------------------------------------------------------------
    # lessons  (replaces lessons_learned.py lessons.json)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS lessons (
        id              TEXT    PRIMARY KEY,
        project_id      TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title           TEXT    NOT NULL,
        description     TEXT    NOT NULL DEFAULT '',
        category        TEXT    NOT NULL DEFAULT '',
        phase           TEXT    NOT NULL DEFAULT '',
        reported_by     TEXT    NOT NULL DEFAULT '',
        impact          TEXT    NOT NULL DEFAULT 'MEDIUM', -- HIGH / MEDIUM / LOW
        recommendation  TEXT    NOT NULL DEFAULT '',
        reported_day    INTEGER NOT NULL DEFAULT 1
    )
    """,

    # ------------------------------------------------------------------
    # memory_summaries  (replaces memory/<codename>_summary.md files)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS memory_summaries (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id   TEXT    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        codename     TEXT    NOT NULL,
        summary_text TEXT    NOT NULL DEFAULT '',
        updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE (project_id, codename)
    )
    """,
]

# Indexes improve query performance for the most common access patterns.
INDEX_DEFINITIONS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_agents_project        ON agents(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_feed_project_day      ON feed_events(project_id, day)",
    "CREATE INDEX IF NOT EXISTS idx_feed_event_type       ON feed_events(project_id, event_type)",
    "CREATE INDEX IF NOT EXISTS idx_meetings_project      ON meetings(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_project     ON decisions(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_status      ON decisions(project_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_tools_project         ON tools(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_test_cases_project    ON test_cases(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_test_cases_status     ON test_cases(project_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_lessons_project       ON lessons(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_project        ON memory_summaries(project_id)",
]


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


async def init_db(db_path: Union[str, Path]) -> None:
    """
    Initialise the SQLite database at *db_path*, creating all tables and
    indexes if they do not already exist.

    This function is **idempotent**: it is safe to call on every application
    startup.  Existing data is never modified.

    Parameters
    ----------
    db_path:
        Filesystem path to the SQLite database file.
        Parent directories are created automatically if missing.

    Example
    -------
    ::

        import asyncio
        from backend.db.schema import init_db

        asyncio.run(init_db("projects/my_project/sapsim.db"))
    """
    db_path = Path(db_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initialising SAP SIM database at %s", db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        # Enable foreign key enforcement for this connection.
        await db.execute("PRAGMA foreign_keys = ON")

        # Use WAL journal mode for better concurrent read/write performance.
        await db.execute("PRAGMA journal_mode = WAL")

        # Create tables
        for stmt in TABLE_DEFINITIONS:
            await db.execute(stmt)

        # Create indexes
        for stmt in INDEX_DEFINITIONS:
            await db.execute(stmt)

        await db.commit()

    logger.info(
        "Database ready: %d table(s), %d index(es) verified.",
        len(TABLE_DEFINITIONS),
        len(INDEX_DEFINITIONS),
    )
