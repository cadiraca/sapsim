"""
SAP SIM — SQLite Repository Layer
Phase: 7.2
Purpose: Provides the ``Database`` class — a thin async wrapper around
         ``aiosqlite`` that implements all CRUD operations for the SAP SIM
         simulation engine.

Design principles:
  - All queries use parameterised placeholders (no string interpolation).
  - JSON columns are transparently serialised/deserialised by this layer.
  - All public methods return plain Python dicts (never aiosqlite Row objects).
  - A single persistent connection is managed via ``connect()`` / ``close()``
    with WAL mode enabled for concurrent read/write access.
  - ``init_db()`` from the schema module is called on ``connect()`` so the
    caller never has to think about schema bootstrapping.

Typical usage::

    db = Database("projects/my_project/sapsim.db")
    await db.connect()
    try:
        await db.save_project({"id": "...", "name": "MySAPProject", ...})
        project = await db.load_project("MySAPProject")
    finally:
        await db.close()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite

from backend.db.schema import init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dumps(value: Any) -> str:
    """Serialise *value* to a JSON string (handles non-serialisable types via str)."""
    return json.dumps(value, default=str)


def _loads(raw: str | None) -> Any:
    """Deserialise a JSON string; returns ``None`` if *raw* is None or empty."""
    if raw is None:
        return None
    return json.loads(raw)


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert an :class:`aiosqlite.Row` (sqlite3.Row) to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class Database:
    """
    Async SQLite repository for SAP SIM.

    Parameters
    ----------
    db_path:
        Path (string or :class:`~pathlib.Path`) to the SQLite database file.
        Parent directories are created automatically on :meth:`connect`.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path: Path = Path(db_path).expanduser().resolve()
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the database connection, enable WAL mode, and bootstrap the schema."""
        if self._db is not None:
            logger.warning("Database.connect() called while already connected — ignored.")
            return

        logger.info("Opening database at %s", self._db_path)
        self._db = await aiosqlite.connect(str(self._db_path))
        # Return rows as sqlite3.Row objects so _row_to_dict works.
        self._db.row_factory = aiosqlite.Row

        # Enable foreign keys and WAL for this connection.
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.execute("PRAGMA journal_mode = WAL")

        # Bootstrap tables / indexes (idempotent).
        await init_db(self._db_path)

        logger.info("Database ready.")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is None:
            return
        await self._db.close()
        self._db = None
        logger.info("Database connection closed.")

    # ------------------------------------------------------------------
    # Internal guard
    # ------------------------------------------------------------------

    @property
    def _conn(self) -> aiosqlite.Connection:
        """Return the active connection or raise if not connected."""
        if self._db is None:
            raise RuntimeError(
                "Database is not connected. Call await db.connect() first."
            )
        return self._db

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    async def save_project(self, project_dict: dict[str, Any]) -> None:
        """
        Insert or replace a project record.

        The dict should contain at minimum ``id`` and ``name``.  Optional keys
        (``status``, ``config``, ``current_phase``, ``current_day``) are written
        if present; absent keys fall back to the schema defaults.

        Parameters
        ----------
        project_dict:
            Full project state dict.  ``config`` may be a nested dict — it will
            be JSON-serialised automatically.
        """
        config_json = _dumps(project_dict.get("config", {}))
        await self._conn.execute(
            """
            INSERT INTO projects (id, name, status, config, current_phase, current_day, updated_at)
            VALUES (:id, :name, :status, :config, :current_phase, :current_day, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                status        = excluded.status,
                config        = excluded.config,
                current_phase = excluded.current_phase,
                current_day   = excluded.current_day,
                updated_at    = datetime('now')
            """,
            {
                "id":            project_dict["id"],
                "name":          project_dict["name"],
                "status":        project_dict.get("status", "active"),
                "config":        config_json,
                "current_phase": project_dict.get("current_phase", "Prepare"),
                "current_day":   project_dict.get("current_day", 1),
            },
        )
        await self._conn.commit()
        logger.debug("Saved project '%s'.", project_dict.get("name"))

    async def load_project(self, name: str) -> dict[str, Any] | None:
        """
        Load a project by its unique *name*.

        Returns
        -------
        dict | None
            Plain dict with ``config`` already deserialised, or ``None`` if no
            project with that name exists.
        """
        async with self._conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        result = _row_to_dict(row)
        result["config"] = _loads(result.get("config"))
        return result

    async def list_projects(self) -> list[dict[str, Any]]:
        """
        Return all projects ordered by creation time (oldest first).

        Returns
        -------
        list[dict]
            Each item is a plain dict with ``config`` deserialised.
        """
        async with self._conn.execute(
            "SELECT * FROM projects ORDER BY created_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _row_to_dict(row)
            item["config"] = _loads(item.get("config"))
            results.append(item)
        return results

    # ------------------------------------------------------------------
    # Agent CRUD
    # ------------------------------------------------------------------

    async def save_agent(
        self,
        project_id: str,
        codename: str,
        state_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace an agent record for *project_id* / *codename*.

        The full agent state is stored in the JSON ``state`` column.  The
        ``role`` and ``status`` convenience columns are also extracted from
        *state_dict* if present so they can be queried without JSON parsing.

        Parameters
        ----------
        project_id:
            The project's UUID/string ID (FK → ``projects.id``).
        codename:
            Agent unique identifier within the project (e.g. ``PM_ALEX``).
        state_dict:
            Full agent state snapshot.  Must include at minimum ``id``.
        """
        state_json = _dumps(state_dict)
        # Derive a row-level ID: prefer state_dict["id"], fall back to
        # "<project_id>:<codename>" to guarantee uniqueness.
        row_id = state_dict.get("id") or f"{project_id}:{codename}"
        await self._conn.execute(
            """
            INSERT INTO agents (id, project_id, codename, role, status, state, updated_at)
            VALUES (:id, :project_id, :codename, :role, :status, :state, datetime('now'))
            ON CONFLICT(project_id, codename) DO UPDATE SET
                role       = excluded.role,
                status     = excluded.status,
                state      = excluded.state,
                updated_at = datetime('now')
            """,
            {
                "id":         row_id,
                "project_id": project_id,
                "codename":   codename,
                "role":       state_dict.get("role", ""),
                "status":     state_dict.get("status", "active"),
                "state":      state_json,
            },
        )
        await self._conn.commit()
        logger.debug("Saved agent '%s' for project '%s'.", codename, project_id)

    async def load_agent(
        self, project_id: str, codename: str
    ) -> dict[str, Any] | None:
        """
        Load an agent by project + codename.

        Returns
        -------
        dict | None
            The full ``state`` dict (not the table row) so callers receive the
            same structure they passed to :meth:`save_agent`.  Returns ``None``
            if the agent has not been saved yet.
        """
        async with self._conn.execute(
            "SELECT state FROM agents WHERE project_id = ? AND codename = ?",
            (project_id, codename),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return _loads(row["state"])

    async def list_agents(self, project_id: str) -> list[dict[str, Any]]:
        """
        Return all agents for *project_id*, ordered by codename.

        Returns
        -------
        list[dict]
            Each item is the deserialised agent state dict (same shape as what
            was passed to :meth:`save_agent`).
        """
        async with self._conn.execute(
            "SELECT state FROM agents WHERE project_id = ? ORDER BY codename ASC",
            (project_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [_loads(row["state"]) for row in rows]

    # ------------------------------------------------------------------
    # Feed events (append-only)
    # ------------------------------------------------------------------

    async def append_event(
        self,
        project_id: str,
        event_dict: dict[str, Any],
    ) -> None:
        """
        Append a single event to the feed log for *project_id*.

        Convenience columns (``event_type``, ``agent_id``, ``phase``, ``day``)
        are extracted from *event_dict* when present so they can be filtered
        efficiently.  The full dict is also stored in ``payload``.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        event_dict:
            JSON-serialisable event payload.  Common keys: ``event_type``,
            ``agent_id``, ``phase``, ``day``.
        """
        payload_json = _dumps(event_dict)
        await self._conn.execute(
            """
            INSERT INTO feed_events
                (project_id, event_type, agent_id, phase, day, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                event_dict.get("event_type", ""),
                event_dict.get("agent_id"),
                event_dict.get("phase"),
                event_dict.get("day"),
                payload_json,
            ),
        )
        await self._conn.commit()
        logger.debug(
            "Appended '%s' event for project '%s'.",
            event_dict.get("event_type"),
            project_id,
        )

    async def get_events(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve feed events for *project_id* in chronological order.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        limit:
            Maximum number of rows to return.
        offset:
            Number of rows to skip (for pagination).
        event_type:
            When provided, only events whose ``event_type`` column matches this
            value are returned.

        Returns
        -------
        list[dict]
            Each item is the deserialised ``payload`` dict plus a synthetic
            ``_row_id`` key carrying the auto-increment primary key and a
            ``_created_at`` timestamp from the database row.
        """
        if event_type is not None:
            query = """
                SELECT id, payload, created_at
                FROM   feed_events
                WHERE  project_id = ? AND event_type = ?
                ORDER  BY id ASC
                LIMIT  ? OFFSET ?
            """
            params = (project_id, event_type, limit, offset)
        else:
            query = """
                SELECT id, payload, created_at
                FROM   feed_events
                WHERE  project_id = ?
                ORDER  BY id ASC
                LIMIT  ? OFFSET ?
            """
            params = (project_id, limit, offset)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _loads(row["payload"]) or {}
            # Inject DB metadata without overwriting existing payload keys.
            item.setdefault("_row_id", row["id"])
            item.setdefault("_created_at", row["created_at"])
            results.append(item)
        return results

    # ------------------------------------------------------------------
    # Memory summaries (per-agent compressed context)
    # ------------------------------------------------------------------

    async def save_memory(
        self,
        project_id: str,
        codename: str,
        text: str,
    ) -> None:
        """
        Upsert the memory summary for *codename* within *project_id*.

        The summary is stored as plain text (Markdown).  Each call overwrites
        the previous summary — only the latest version is retained.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        codename:
            Agent codename (e.g. ``PM_ALEX``).
        text:
            LLM-compressed memory summary in plain text / Markdown.
        """
        await self._conn.execute(
            """
            INSERT INTO memory_summaries (project_id, codename, summary_text, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(project_id, codename) DO UPDATE SET
                summary_text = excluded.summary_text,
                updated_at   = datetime('now')
            """,
            (project_id, codename, text),
        )
        await self._conn.commit()
        logger.debug("Saved memory for agent '%s' in project '%s'.", codename, project_id)

    async def load_memory(
        self,
        project_id: str,
        codename: str,
    ) -> str | None:
        """
        Load the latest memory summary for *codename* in *project_id*.

        Returns
        -------
        str | None
            The plain-text summary, or ``None`` if no summary has been saved.
        """
        async with self._conn.execute(
            """
            SELECT summary_text
            FROM   memory_summaries
            WHERE  project_id = ? AND codename = ?
            """,
            (project_id, codename),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return row["summary_text"]
