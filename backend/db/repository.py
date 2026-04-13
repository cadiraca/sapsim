"""
SAP SIM — SQLite Repository Layer
Phase: 7.3
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

from db.schema import init_db

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

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    async def save_meeting(
        self,
        project_id: str,
        meeting_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace a meeting record for *project_id*.

        The dict should mirror the :class:`~backend.artifacts.meeting_logger.MeetingLog`
        shape (or any superset thereof).  JSON-valued fields (``participants``,
        ``transcript``, ``decisions``, ``actions``) are serialised automatically.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        meeting_dict:
            Meeting state dict.  Must include ``id``, ``title``, ``meeting_type``,
            ``phase``, and ``day`` (or ``simulated_day``).
        """
        # Normalise day key: MeetingLog uses ``simulated_day``; schema uses ``day``.
        day = meeting_dict.get("day") or meeting_dict.get("simulated_day", 1)

        # Normalise decisions key: MeetingLog calls it ``decisions_made``.
        decisions = meeting_dict.get("decisions") or meeting_dict.get("decisions_made", [])

        # Normalise actions key: MeetingLog calls it ``action_items``.
        actions = meeting_dict.get("actions") or meeting_dict.get("action_items", [])

        await self._conn.execute(
            """
            INSERT INTO meetings
                (id, project_id, title, meeting_type, phase,
                 participants, transcript, decisions, actions,
                 duration, day)
            VALUES
                (:id, :project_id, :title, :meeting_type, :phase,
                 :participants, :transcript, :decisions, :actions,
                 :duration, :day)
            ON CONFLICT(id) DO UPDATE SET
                title        = excluded.title,
                meeting_type = excluded.meeting_type,
                phase        = excluded.phase,
                participants = excluded.participants,
                transcript   = excluded.transcript,
                decisions    = excluded.decisions,
                actions      = excluded.actions,
                duration     = excluded.duration,
                day          = excluded.day
            """,
            {
                "id":           meeting_dict["id"],
                "project_id":   project_id,
                "title":        meeting_dict.get("title", ""),
                "meeting_type": meeting_dict.get("meeting_type", "ad_hoc"),
                "phase":        meeting_dict.get("phase", ""),
                "participants": _dumps(meeting_dict.get("participants", [])),
                "transcript":   _dumps(meeting_dict.get("transcript", [])),
                "decisions":    _dumps(decisions),
                "actions":      _dumps(actions),
                "duration":     meeting_dict.get("duration_minutes") or meeting_dict.get("duration"),
                "day":          day,
            },
        )
        await self._conn.commit()
        logger.debug(
            "Saved meeting '%s' for project '%s'.",
            meeting_dict.get("id"),
            project_id,
        )

    async def get_meetings(
        self,
        project_id: str,
        phase: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retrieve meetings for *project_id* in chronological order.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        phase:
            When supplied, only meetings in this SAP ACTIVATE phase are returned.
        limit:
            Maximum number of rows to return (default 50).

        Returns
        -------
        list[dict]
            Each item is a plain dict with all JSON columns deserialised.
        """
        if phase is not None:
            query = """
                SELECT *
                FROM   meetings
                WHERE  project_id = ? AND phase = ?
                ORDER  BY day ASC, created_at ASC
                LIMIT  ?
            """
            params: tuple[Any, ...] = (project_id, phase, limit)
        else:
            query = """
                SELECT *
                FROM   meetings
                WHERE  project_id = ?
                ORDER  BY day ASC, created_at ASC
                LIMIT  ?
            """
            params = (project_id, limit)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _row_to_dict(row)
            item["participants"] = _loads(item.get("participants")) or []
            item["transcript"]   = _loads(item.get("transcript"))   or []
            item["decisions"]    = _loads(item.get("decisions"))    or []
            item["actions"]      = _loads(item.get("actions"))      or []
            results.append(item)
        return results

    async def get_meeting(
        self,
        meeting_id: str,
    ) -> dict[str, Any] | None:
        """
        Fetch a single meeting by its primary-key ID.

        Returns
        -------
        dict | None
            Plain dict with JSON columns deserialised, or ``None`` if not found.
        """
        async with self._conn.execute(
            "SELECT * FROM meetings WHERE id = ?",
            (meeting_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        item = _row_to_dict(row)
        item["participants"] = _loads(item.get("participants")) or []
        item["transcript"]   = _loads(item.get("transcript"))   or []
        item["decisions"]    = _loads(item.get("decisions"))    or []
        item["actions"]      = _loads(item.get("actions"))      or []
        return item

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    async def save_decision(
        self,
        project_id: str,
        decision_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace a decision record for *project_id*.

        The dict should mirror the :class:`~backend.artifacts.decision_board.Decision`
        shape.  The ``votes`` dict and ``impact_assessment`` alias are handled
        automatically.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        decision_dict:
            Decision state dict.  Must include ``id``, ``title``, ``category``,
            and ``proposed_by``.
        """
        # Normalise field name: Decision uses ``proposed_at_day``; schema uses ``proposed_day``.
        proposed_day = (
            decision_dict.get("proposed_day")
            or decision_dict.get("proposed_at_day", 1)
        )
        resolved_day = (
            decision_dict.get("resolved_day")
            or decision_dict.get("resolved_at_day")
        )

        # Normalise impact alias: Decision uses ``impact_assessment``.
        impact = decision_dict.get("impact") or decision_dict.get("impact_assessment", "")

        # Normalise meeting_id alias: Decision uses ``related_meeting_id``.
        meeting_id = (
            decision_dict.get("meeting_id")
            or decision_dict.get("related_meeting_id")
        )

        await self._conn.execute(
            """
            INSERT INTO decisions
                (id, project_id, title, description, category,
                 proposed_by, status, votes, rationale, impact,
                 meeting_id, proposed_day, resolved_day)
            VALUES
                (:id, :project_id, :title, :description, :category,
                 :proposed_by, :status, :votes, :rationale, :impact,
                 :meeting_id, :proposed_day, :resolved_day)
            ON CONFLICT(id) DO UPDATE SET
                title        = excluded.title,
                description  = excluded.description,
                category     = excluded.category,
                proposed_by  = excluded.proposed_by,
                status       = excluded.status,
                votes        = excluded.votes,
                rationale    = excluded.rationale,
                impact       = excluded.impact,
                meeting_id   = excluded.meeting_id,
                proposed_day = excluded.proposed_day,
                resolved_day = excluded.resolved_day
            """,
            {
                "id":           decision_dict["id"],
                "project_id":   project_id,
                "title":        decision_dict.get("title", ""),
                "description":  decision_dict.get("description", ""),
                "category":     decision_dict.get("category", ""),
                "proposed_by":  decision_dict.get("proposed_by", ""),
                "status":       decision_dict.get("status", "proposed"),
                "votes":        _dumps(decision_dict.get("votes", {})),
                "rationale":    decision_dict.get("rationale", ""),
                "impact":       impact,
                "meeting_id":   meeting_id,
                "proposed_day": proposed_day,
                "resolved_day": resolved_day,
            },
        )
        await self._conn.commit()
        logger.debug(
            "Saved decision '%s' for project '%s'.",
            decision_dict.get("id"),
            project_id,
        )

    async def update_decision(
        self,
        decision_id: str,
        updates: dict[str, Any],
    ) -> None:
        """
        Apply a partial update to an existing decision row.

        Only the keys present in *updates* are written.  Supported keys match
        the ``decisions`` table columns: ``status``, ``votes``, ``rationale``,
        ``impact``, ``meeting_id``, ``resolved_day``, ``title``,
        ``description``, ``category``.

        Parameters
        ----------
        decision_id:
            Primary key of the decision to update.
        updates:
            Dict of column → new value.  ``votes`` may be a dict (it will be
            JSON-serialised automatically).

        Raises
        ------
        ValueError
            If *updates* is empty or contains no recognised column names.
        """
        _ALLOWED = {
            "status", "votes", "rationale", "impact", "meeting_id",
            "resolved_day", "title", "description", "category",
        }
        filtered = {k: v for k, v in updates.items() if k in _ALLOWED}
        if not filtered:
            raise ValueError(
                f"update_decision: no recognised columns in updates dict. "
                f"Allowed: {_ALLOWED}"
            )

        # JSON-serialise the votes column if present.
        if "votes" in filtered and not isinstance(filtered["votes"], str):
            filtered["votes"] = _dumps(filtered["votes"])

        set_clause = ", ".join(f"{col} = :{col}" for col in filtered)
        filtered["_id"] = decision_id

        await self._conn.execute(
            f"UPDATE decisions SET {set_clause} WHERE id = :_id",
            filtered,
        )
        await self._conn.commit()
        logger.debug("Updated decision '%s' (fields: %s).", decision_id, list(filtered.keys()))

    async def get_decisions(
        self,
        project_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve decisions for *project_id*, optionally filtered by *status*.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        status:
            When supplied, only decisions with this status value are returned
            (e.g. ``"proposed"``, ``"approved"``, ``"rejected"``).

        Returns
        -------
        list[dict]
            Ordered by ``proposed_day`` ASC then ``id`` ASC.  The ``votes``
            column is deserialised to a dict.
        """
        if status is not None:
            query = """
                SELECT *
                FROM   decisions
                WHERE  project_id = ? AND status = ?
                ORDER  BY proposed_day ASC, id ASC
            """
            params: tuple[Any, ...] = (project_id, status)
        else:
            query = """
                SELECT *
                FROM   decisions
                WHERE  project_id = ?
                ORDER  BY proposed_day ASC, id ASC
            """
            params = (project_id,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _row_to_dict(row)
            item["votes"] = _loads(item.get("votes")) or {}
            results.append(item)
        return results

    async def get_decision(
        self,
        decision_id: str,
    ) -> dict[str, Any] | None:
        """
        Fetch a single decision by its primary-key ID.

        Returns
        -------
        dict | None
            Plain dict with ``votes`` deserialised, or ``None`` if not found.
        """
        async with self._conn.execute(
            "SELECT * FROM decisions WHERE id = ?",
            (decision_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        item = _row_to_dict(row)
        item["votes"] = _loads(item.get("votes")) or {}
        return item

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def save_tool(
        self,
        project_id: str,
        tool_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace a tool record for *project_id*.

        The dict should mirror the :class:`~backend.artifacts.tool_registry.SimulatedTool`
        shape.  JSON-valued fields (``tcodes``, ``tables``) are serialised
        automatically.  ``usage_history`` and ``tags`` / ``notes`` from
        SimulatedTool are accepted but the column-level convenience fields
        (``usage_count``, ``announced_day``) take priority.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        tool_dict:
            Tool state dict.  Must include ``id``, ``name``, ``category``.
        """
        # Normalise announced_day alias: SimulatedTool uses ``announced_at_day``.
        announced_day = (
            tool_dict.get("announced_day")
            or tool_dict.get("announced_at_day", 1)
        )

        await self._conn.execute(
            """
            INSERT INTO tools
                (id, project_id, name, category, description,
                 sap_module, tcodes, tables, announced_by,
                 status, usage_count, announced_day)
            VALUES
                (:id, :project_id, :name, :category, :description,
                 :sap_module, :tcodes, :tables, :announced_by,
                 :status, :usage_count, :announced_day)
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                category      = excluded.category,
                description   = excluded.description,
                sap_module    = excluded.sap_module,
                tcodes        = excluded.tcodes,
                tables        = excluded.tables,
                announced_by  = excluded.announced_by,
                status        = excluded.status,
                usage_count   = excluded.usage_count,
                announced_day = excluded.announced_day
            """,
            {
                "id":            tool_dict["id"],
                "project_id":    project_id,
                "name":          tool_dict.get("name", ""),
                "category":      tool_dict.get("category", ""),
                "description":   tool_dict.get("description", ""),
                "sap_module":    tool_dict.get("sap_module", ""),
                "tcodes":        _dumps(tool_dict.get("tcodes", [])),
                "tables":        _dumps(tool_dict.get("tables", [])),
                "announced_by":  tool_dict.get("announced_by", ""),
                "status":        tool_dict.get("status", "announced"),
                "usage_count":   tool_dict.get("usage_count", 0),
                "announced_day": announced_day,
            },
        )
        await self._conn.commit()
        logger.debug(
            "Saved tool '%s' for project '%s'.",
            tool_dict.get("name"),
            project_id,
        )

    async def update_tool_usage(
        self,
        tool_id: str,
    ) -> None:
        """
        Atomically increment the ``usage_count`` counter for *tool_id* and
        promote its status from ``announced`` to ``in_use`` if it was
        previously un-used.

        This is a lightweight operation designed to be called every time an
        agent records a tool interaction without requiring a full save cycle.

        Parameters
        ----------
        tool_id:
            Primary key of the tool to update.
        """
        await self._conn.execute(
            """
            UPDATE tools
            SET
                usage_count = usage_count + 1,
                status      = CASE
                                  WHEN status = 'announced' THEN 'in_use'
                                  ELSE status
                              END
            WHERE id = ?
            """,
            (tool_id,),
        )
        await self._conn.commit()
        logger.debug("Incremented usage_count for tool '%s'.", tool_id)

    async def get_tools(
        self,
        project_id: str,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve tools for *project_id*, optionally filtered by *category*.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        category:
            When supplied, only tools in this category are returned
            (e.g. ``"config"``, ``"dev"``, ``"test"``, ``"data"``,
            ``"security"``, ``"reporting"``).

        Returns
        -------
        list[dict]
            Sorted alphabetically by ``name``.  The ``tcodes`` and ``tables``
            columns are deserialised to lists.
        """
        if category is not None:
            query = """
                SELECT *
                FROM   tools
                WHERE  project_id = ? AND category = ?
                ORDER  BY name ASC
            """
            params: tuple[Any, ...] = (project_id, category)
        else:
            query = """
                SELECT *
                FROM   tools
                WHERE  project_id = ?
                ORDER  BY name ASC
            """
            params = (project_id,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _row_to_dict(row)
            item["tcodes"] = _loads(item.get("tcodes")) or []
            item["tables"] = _loads(item.get("tables")) or []
            results.append(item)
        return results

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    async def save_test_case(
        self,
        project_id: str,
        test_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace a test-case record for *project_id*.

        The dict should mirror the
        :class:`~backend.artifacts.test_strategy.TestCase` shape.
        The ``steps`` list is JSON-serialised automatically.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        test_dict:
            Test-case state dict.  Must include ``id``, ``title``, ``module``,
            and ``type``.
        """
        # TestCase.type / .status may be Enum instances — coerce to string.
        tc_type   = test_dict.get("type", "unit")
        tc_status = test_dict.get("status", "planned")
        if hasattr(tc_type, "value"):
            tc_type = tc_type.value
        if hasattr(tc_status, "value"):
            tc_status = tc_status.value

        await self._conn.execute(
            """
            INSERT INTO test_cases
                (id, project_id, title, module, type, status,
                 assigned_to, priority, steps, expected_result,
                 actual_result, defect_id)
            VALUES
                (:id, :project_id, :title, :module, :type, :status,
                 :assigned_to, :priority, :steps, :expected_result,
                 :actual_result, :defect_id)
            ON CONFLICT(id) DO UPDATE SET
                title           = excluded.title,
                module          = excluded.module,
                type            = excluded.type,
                status          = excluded.status,
                assigned_to     = excluded.assigned_to,
                priority        = excluded.priority,
                steps           = excluded.steps,
                expected_result = excluded.expected_result,
                actual_result   = excluded.actual_result,
                defect_id       = excluded.defect_id
            """,
            {
                "id":              test_dict["id"],
                "project_id":      project_id,
                "title":           test_dict.get("title", ""),
                "module":          test_dict.get("module", ""),
                "type":            tc_type,
                "status":          tc_status,
                "assigned_to":     test_dict.get("assigned_to", ""),
                "priority":        test_dict.get("priority", 1),
                "steps":           _dumps(test_dict.get("steps", [])),
                "expected_result": test_dict.get("expected_result", ""),
                "actual_result":   test_dict.get("actual_result", ""),
                "defect_id":       test_dict.get("defect_id"),
            },
        )
        await self._conn.commit()
        logger.debug(
            "Saved test case '%s' for project '%s'.",
            test_dict.get("id"),
            project_id,
        )

    async def update_test_status(
        self,
        test_id: str,
        status: str,
        result: str = "",
    ) -> None:
        """
        Update the ``status`` (and optionally ``actual_result``) of a test case.

        *status* may be a :class:`~backend.artifacts.test_strategy.TestStatus`
        enum value or a plain string (e.g. ``"passed"``, ``"failed"``,
        ``"blocked"``).

        Parameters
        ----------
        test_id:
            Primary key of the test case to update.
        status:
            New status string.
        result:
            Optional actual-result text to record alongside the status change.
        """
        # Coerce Enum to string.
        if hasattr(status, "value"):
            status = status.value

        await self._conn.execute(
            """
            UPDATE test_cases
            SET status        = ?,
                actual_result = CASE WHEN ? != '' THEN ? ELSE actual_result END
            WHERE id = ?
            """,
            (status, result, result, test_id),
        )
        await self._conn.commit()
        logger.debug("Updated test case '%s' → status='%s'.", test_id, status)

    async def get_test_cases(
        self,
        project_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve test cases for *project_id*, optionally filtered by *status*.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        status:
            When supplied, only test cases with this status are returned
            (e.g. ``"planned"``, ``"in_progress"``, ``"passed"``,
            ``"failed"``, ``"blocked"``).

        Returns
        -------
        list[dict]
            Sorted by ``priority`` ASC then ``id`` ASC.  The ``steps`` column
            is deserialised to a list.
        """
        if status is not None:
            query = """
                SELECT *
                FROM   test_cases
                WHERE  project_id = ? AND status = ?
                ORDER  BY priority ASC, id ASC
            """
            params: tuple[Any, ...] = (project_id, status)
        else:
            query = """
                SELECT *
                FROM   test_cases
                WHERE  project_id = ?
                ORDER  BY priority ASC, id ASC
            """
            params = (project_id,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            item = _row_to_dict(row)
            item["steps"] = _loads(item.get("steps")) or []
            results.append(item)
        return results

    async def get_coverage_stats(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Compute test-coverage statistics for *project_id* using SQL aggregation.

        Returns a dict modelled on
        :meth:`~backend.artifacts.test_strategy.TestStrategy.get_coverage_report`:

        .. code-block:: python

            {
                "total": int,
                "by_status": {status: count, ...},
                "by_type": {type: count, ...},
                "by_module": {module: {"total": n, <status>: n, ...}, ...},
                "pass_rate": float,        # 0.0 – 1.0
                "defect_count": int,
            }

        Returns
        -------
        dict
            Coverage statistics; empty counters for projects with no tests.
        """
        # --- Counts by status ---
        async with self._conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM   test_cases
            WHERE  project_id = ?
            GROUP  BY status
            """,
            (project_id,),
        ) as cursor:
            status_rows = await cursor.fetchall()

        by_status: dict[str, int] = {
            s: 0 for s in ("planned", "in_progress", "passed", "failed", "blocked")
        }
        total = 0
        for row in status_rows:
            key = row["status"]
            by_status[key] = by_status.get(key, 0) + row["cnt"]
            total += row["cnt"]

        # --- Counts by type ---
        async with self._conn.execute(
            """
            SELECT type, COUNT(*) AS cnt
            FROM   test_cases
            WHERE  project_id = ?
            GROUP  BY type
            """,
            (project_id,),
        ) as cursor:
            type_rows = await cursor.fetchall()

        by_type: dict[str, int] = {
            t: 0
            for t in ("unit", "integration", "uat", "regression", "performance")
        }
        for row in type_rows:
            key = row["type"]
            by_type[key] = by_type.get(key, 0) + row["cnt"]

        # --- Counts by module/status (per-module breakdown) ---
        async with self._conn.execute(
            """
            SELECT module, status, COUNT(*) AS cnt
            FROM   test_cases
            WHERE  project_id = ?
            GROUP  BY module, status
            """,
            (project_id,),
        ) as cursor:
            module_rows = await cursor.fetchall()

        by_module: dict[str, dict[str, int]] = {}
        for row in module_rows:
            mod = row["module"]
            if mod not in by_module:
                by_module[mod] = {
                    s: 0
                    for s in ("planned", "in_progress", "passed", "failed", "blocked")
                }
                by_module[mod]["total"] = 0
            by_module[mod][row["status"]] = (
                by_module[mod].get(row["status"], 0) + row["cnt"]
            )
            by_module[mod]["total"] += row["cnt"]

        # --- Defect count ---
        async with self._conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM   test_cases
            WHERE  project_id = ? AND defect_id IS NOT NULL AND defect_id != ''
            """,
            (project_id,),
        ) as cursor:
            defect_row = await cursor.fetchone()
        defect_count = defect_row["cnt"] if defect_row else 0

        # --- Pass rate ---
        executed = by_status["passed"] + by_status["failed"]
        pass_rate = round(by_status["passed"] / executed, 4) if executed > 0 else 0.0

        return {
            "total":        total,
            "by_status":    by_status,
            "by_type":      by_type,
            "by_module":    by_module,
            "pass_rate":    pass_rate,
            "defect_count": defect_count,
        }

    # ------------------------------------------------------------------
    # Lessons learned
    # ------------------------------------------------------------------

    async def save_lesson(
        self,
        project_id: str,
        lesson_dict: dict[str, Any],
    ) -> None:
        """
        Insert or replace a lessons-learned record for *project_id*.

        The dict should mirror the
        :class:`~backend.artifacts.lessons_learned.Lesson` shape.  The field
        ``reported_at_day`` is accepted as an alias for ``reported_day``.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        lesson_dict:
            Lesson state dict.  Must include ``id``, ``title``, ``phase``,
            and ``reported_by``.
        """
        # Normalise day alias: Lesson uses ``reported_at_day``.
        reported_day = (
            lesson_dict.get("reported_day")
            or lesson_dict.get("reported_at_day", 1)
        )

        await self._conn.execute(
            """
            INSERT INTO lessons
                (id, project_id, title, description, category,
                 phase, reported_by, impact, recommendation, reported_day)
            VALUES
                (:id, :project_id, :title, :description, :category,
                 :phase, :reported_by, :impact, :recommendation, :reported_day)
            ON CONFLICT(id) DO UPDATE SET
                title          = excluded.title,
                description    = excluded.description,
                category       = excluded.category,
                phase          = excluded.phase,
                reported_by    = excluded.reported_by,
                impact         = excluded.impact,
                recommendation = excluded.recommendation,
                reported_day   = excluded.reported_day
            """,
            {
                "id":             lesson_dict["id"],
                "project_id":     project_id,
                "title":          lesson_dict.get("title", ""),
                "description":    lesson_dict.get("description", ""),
                "category":       lesson_dict.get("category", ""),
                "phase":          lesson_dict.get("phase", ""),
                "reported_by":    lesson_dict.get("reported_by", ""),
                "impact":         lesson_dict.get("impact", "MEDIUM"),
                "recommendation": lesson_dict.get("recommendation", ""),
                "reported_day":   reported_day,
            },
        )
        await self._conn.commit()
        logger.debug(
            "Saved lesson '%s' for project '%s'.",
            lesson_dict.get("id"),
            project_id,
        )

    async def get_lessons(
        self,
        project_id: str,
        phase: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve lessons for *project_id*, optionally filtered by *phase*.

        Parameters
        ----------
        project_id:
            FK → ``projects.id``.
        phase:
            When supplied, only lessons from this SAP ACTIVATE phase are
            returned (case-sensitive match against the ``phase`` column).

        Returns
        -------
        list[dict]
            Sorted by ``reported_day`` ASC then ``id`` ASC.  All columns are
            plain scalars — no JSON deserialisation needed for this table.
        """
        if phase is not None:
            query = """
                SELECT *
                FROM   lessons
                WHERE  project_id = ? AND phase = ?
                ORDER  BY reported_day ASC, id ASC
            """
            params: tuple[Any, ...] = (project_id, phase)
        else:
            query = """
                SELECT *
                FROM   lessons
                WHERE  project_id = ?
                ORDER  BY reported_day ASC, id ASC
            """
            params = (project_id,)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [_row_to_dict(row) for row in rows]
