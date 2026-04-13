"""
SAP SIM — Persistence Utilities
Phase: 7.4
Purpose: Async persistence for all project data backed by SQLite via the
         Database class from ``backend.db.repository``.  All public function
         signatures are unchanged from the Phase 1.5 file-based implementation
         so no callers need to be updated.

Dependencies: backend.db.repository.Database, pathlib
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from db.repository import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers — kept for backward compatibility with callers that import them
# ---------------------------------------------------------------------------

# Base directory for all project data (relative to repo root)
PROJECTS_BASE = Path(__file__).resolve().parent.parent.parent / "projects"


def _project_dir(project_name: str) -> Path:
    """Return the root directory for a project, without creating it."""
    return PROJECTS_BASE / project_name


async def _ensure_dir(path: Path) -> None:
    """Create *path* (and parents) if it does not exist."""
    import aiofiles.os  # noqa: PLC0415 — lazy to avoid hard dep at import time
    await aiofiles.os.makedirs(str(path), exist_ok=True)


# ---------------------------------------------------------------------------
# Module-level database instance
# ---------------------------------------------------------------------------

# Resolved lazily by init_persistence(); all public helpers guard against None.
# Type annotation uses a string forward reference to avoid importing Database at
# module load time (aiosqlite may not be installed in all environments).
_db: "Database | None" = None

# Default database path (relative to repo root)
_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "projects" / "sapsim.db"
)


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def init_persistence(db_path: str | Path | None = None) -> None:
    """Initialise the module-level :class:`~backend.db.repository.Database`.

    Creates and opens the SQLite database at *db_path* (defaulting to
    ``projects/sapsim.db`` relative to the repo root).  Idempotent: calling
    this a second time while already connected is a no-op.

    Args:
        db_path: Path to the SQLite file.  Parent directories are created
                 automatically by the ``Database`` class.  Defaults to
                 ``projects/sapsim.db``.
    """
    global _db
    if _db is not None:
        logger.debug("init_persistence: already initialised — skipped.")
        return

    # Lazy import so that aiosqlite is not required at module-load time
    # (e.g. in test environments where it may not be installed).
    from db.repository import Database  # noqa: PLC0415

    resolved = Path(db_path).expanduser().resolve() if db_path else _DEFAULT_DB_PATH
    _db = Database(resolved)
    await _db.connect()
    logger.info("Persistence layer initialised at %s", resolved)


async def close_persistence() -> None:
    """Close the module-level database connection cleanly.

    Safe to call even if the database was never opened.
    """
    global _db
    if _db is None:
        return
    await _db.close()
    _db = None
    logger.info("Persistence layer closed.")


def get_db() -> "Database":
    """Return the active :class:`~backend.db.repository.Database` instance.

    Useful for callers that need direct access to advanced repository methods
    (meetings, decisions, tools, test cases, lessons, etc.).

    Raises:
        RuntimeError: If :func:`init_persistence` has not been called yet.
    """
    if _db is None:
        raise RuntimeError(
            "Persistence not initialised. Call await init_persistence() first."
        )
    return _db


def _require_db() -> "Database":
    """Internal guard — same as :func:`get_db` but with a more descriptive error."""
    if _db is None:
        raise RuntimeError(
            "Database not ready. Ensure init_persistence() has been awaited "
            "before calling persistence helpers."
        )
    return _db


# ---------------------------------------------------------------------------
# Project state
# ---------------------------------------------------------------------------


async def save_project_state(project_name: str, state_dict: dict[str, Any]) -> None:
    """Persist the full project state dict.

    Delegates to :meth:`~backend.db.repository.Database.save_project`.
    The ``project_name`` is used as both ``id`` and ``name`` since the
    project state dict does not carry a separate ``id`` field.

    Args:
        project_name: The unique project identifier.
        state_dict:   Serialisable dict representing the current project state.
    """
    db = _require_db()

    # Build a record compatible with Database.save_project which expects
    # at minimum "id" and "name".
    record: dict[str, Any] = {
        "id":            project_name,
        "name":          project_name,
        "status":        state_dict.get("status", "active"),
        "config":        state_dict,          # store full state as config blob
        "current_phase": state_dict.get("current_phase", "discover"),
        "current_day":   state_dict.get("simulated_day", 1),
    }
    await db.save_project(record)
    logger.debug("Saved project state for '%s'", project_name)


async def load_project_state(project_name: str) -> dict[str, Any] | None:
    """Load the persisted project state dict.

    Returns:
        The state dict as originally passed to :func:`save_project_state`,
        or ``None`` if the project has never been saved.
    """
    db = _require_db()
    row = await db.load_project(project_name)
    if row is None:
        return None
    # The full state dict was stored inside the "config" JSON column.
    config = row.get("config")
    if isinstance(config, dict):
        return config
    # Fallback: return the raw row minus internal DB metadata.
    return row


# ---------------------------------------------------------------------------
# Feed events  (append-only)
# ---------------------------------------------------------------------------


async def append_feed_event(project_name: str, event_dict: dict[str, Any]) -> None:
    """Append a single event to the feed log.

    Delegates to :meth:`~backend.db.repository.Database.append_event`.

    Args:
        project_name: The unique project identifier (used as ``project_id``).
        event_dict:   JSON-serialisable event payload.
    """
    db = _require_db()
    await db.append_event(project_name, event_dict)


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------


async def save_agent_state(
    project_name: str, codename: str, state_dict: dict[str, Any]
) -> None:
    """Persist an agent's state dict.

    Delegates to :meth:`~backend.db.repository.Database.save_agent`.

    Args:
        project_name: The unique project identifier.
        codename:     Agent's unique codename (e.g. ``PM_ALEX``).
        state_dict:   Serialisable snapshot of the agent's current state.
    """
    db = _require_db()
    await db.save_agent(project_name, codename, state_dict)
    logger.debug("Saved agent state for %s / %s", project_name, codename)


async def load_agent_state(
    project_name: str, codename: str
) -> dict[str, Any] | None:
    """Load an agent's persisted state.

    Delegates to :meth:`~backend.db.repository.Database.load_agent`.

    Returns:
        The state dict, or ``None`` if no state has been saved yet.
    """
    db = _require_db()
    return await db.load_agent(project_name, codename)


# ---------------------------------------------------------------------------
# Memory summaries
# ---------------------------------------------------------------------------


async def save_memory_summary(
    project_name: str, codename: str, summary_text: str
) -> None:
    """Write a compressed memory summary for an agent.

    Delegates to :meth:`~backend.db.repository.Database.save_memory`.
    Each call overwrites the previous summary (only latest is retained).

    Args:
        project_name:  The unique project identifier.
        codename:      Agent's unique codename.
        summary_text:  Plain-text (Markdown) summary produced by LLM compression.
    """
    db = _require_db()
    await db.save_memory(project_name, codename, summary_text)
    logger.debug("Saved memory summary for %s / %s", project_name, codename)


async def load_memory_summary(project_name: str, codename: str) -> str | None:
    """Load an agent's memory summary.

    Delegates to :meth:`~backend.db.repository.Database.load_memory`.

    Returns:
        The raw Markdown text, or ``None`` if no summary has been saved.
    """
    db = _require_db()
    return await db.load_memory(project_name, codename)
