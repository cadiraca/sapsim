"""
SAP SIM — JSON-to-SQLite Migration Tool
Phase: 7.6
Purpose: One-time migration utility that reads legacy JSON/JSONL data from the
         projects/ directory and imports it into the SQLite database.

Scans each project sub-directory for:
  - project.json       → projects table (via save_project)
  - agents/<name>.json → agents table  (via save_agent)
  - feed/events.jsonl  → feed_events table (via append_event)
  - memory/<codename>.md → memory_summaries table (via save_memory)

CLI usage::

    cd backend
    python -m db.migrate                         # default paths
    python -m db.migrate --projects ../projects --db ../projects/sapsim.db

Programmatic usage::

    import asyncio
    from db.migrate import migrate_json_to_sqlite

    asyncio.run(migrate_json_to_sqlite("../projects", "../projects/sapsim.db"))
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    """Load a JSON file; return ``None`` on parse errors."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping %s — could not parse: %s", path, exc)
        return None


def _iter_jsonl(path: Path):
    """Yield parsed dicts from a JSONL file, skipping blank or malformed lines."""
    try:
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping line %d in %s: %s", lineno, path, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Core migration function
# ---------------------------------------------------------------------------


async def migrate_json_to_sqlite(
    projects_dir: str | Path,
    db_path: str | Path,
) -> dict[str, int]:
    """Migrate legacy JSON/JSONL project data into a SQLite database.

    Idempotent: uses ``INSERT OR IGNORE`` / ``ON CONFLICT DO UPDATE`` so it is
    safe to run multiple times.  Existing DB rows are updated with the latest
    values from the file system.

    Parameters
    ----------
    projects_dir:
        Root directory that contains one sub-directory per project (e.g.
        ``projects/admin-test/``).
    db_path:
        Destination SQLite file.  Created automatically if absent.

    Returns
    -------
    dict
        Migration counts::

            {
                "projects": int,
                "agents":   int,
                "events":   int,
                "memories": int,
            }
    """
    projects_dir = Path(projects_dir).expanduser().resolve()
    db_path = Path(db_path).expanduser().resolve()

    if not projects_dir.exists():
        raise FileNotFoundError(f"projects_dir not found: {projects_dir}")

    # Bootstrap DB: initialise schema first (creates the file + tables), then
    # open the repository connection.  We call init_db in a separate step so
    # its internal aiosqlite connection is fully closed before Database.connect()
    # opens its own connection — this prevents a WAL-mode locking conflict that
    # occurs when two connections both try to set PRAGMA journal_mode=WAL
    # simultaneously on a freshly created database file.
    from db.repository import Database  # noqa: PLC0415
    from db.schema import init_db  # noqa: PLC0415

    # Step 1: initialise schema (opens + closes its own connection)
    await init_db(db_path)

    # Step 2: open the persistent repository connection (skips re-init since
    # Database.connect() calls init_db again, but schema already exists so
    # all CREATE TABLE IF NOT EXISTS statements are no-ops; the WAL PRAGMA
    # call succeeds because no other connection is open).
    db = Database(db_path)
    await db.connect()

    counts = {"projects": 0, "agents": 0, "events": 0, "memories": 0}

    try:
        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue

            project_name = project_dir.name
            logger.info("Migrating project: %s", project_name)

            # ------------------------------------------------------------------
            # 1. project.json → projects table
            # ------------------------------------------------------------------
            project_json = project_dir / "project.json"
            project_id = project_name  # use directory name as canonical ID

            if project_json.exists():
                state = _load_json(project_json)
                if isinstance(state, dict):
                    record: dict[str, Any] = {
                        "id":            project_id,
                        "name":          project_name,
                        "status":        state.get("status", "active"),
                        "config":        state,
                        "current_phase": state.get("current_phase", "discover"),
                        "current_day":   state.get("simulated_day", 1),
                    }
                    await db.save_project(record)
                    counts["projects"] += 1
                    logger.debug("  → project saved: %s", project_name)
            else:
                # Create a minimal stub so FK constraints are satisfied for
                # any agents/events we find.
                stub: dict[str, Any] = {
                    "id":     project_id,
                    "name":   project_name,
                    "status": "unknown",
                    "config": {},
                }
                await db.save_project(stub)
                counts["projects"] += 1
                logger.debug("  → project stub created: %s", project_name)

            # ------------------------------------------------------------------
            # 2. agents/<codename>.json → agents table
            # ------------------------------------------------------------------
            agents_dir = project_dir / "agents"
            if agents_dir.is_dir():
                for agent_file in sorted(agents_dir.glob("*.json")):
                    agent_state = _load_json(agent_file)
                    if not isinstance(agent_state, dict):
                        continue
                    codename = agent_file.stem
                    await db.save_agent(project_id, codename, agent_state)
                    counts["agents"] += 1
                    logger.debug("  → agent saved: %s / %s", project_name, codename)

            # ------------------------------------------------------------------
            # 3. feed/events.jsonl → feed_events table
            # ------------------------------------------------------------------
            feed_file = project_dir / "feed" / "events.jsonl"
            if feed_file.exists():
                for event in _iter_jsonl(feed_file):
                    if not isinstance(event, dict):
                        continue
                    # Normalise event_type: legacy files may use "type" key.
                    if "event_type" not in event and "type" in event:
                        event = {**event, "event_type": event["type"]}
                    await db.append_event(project_id, event)
                    counts["events"] += 1

                logger.debug(
                    "  → %d events migrated for: %s",
                    counts["events"],
                    project_name,
                )

            # ------------------------------------------------------------------
            # 4. memory/<codename>.md → memory_summaries table
            # ------------------------------------------------------------------
            memory_dir = project_dir / "memory"
            if memory_dir.is_dir():
                for mem_file in sorted(memory_dir.glob("*.md")):
                    codename = mem_file.stem
                    try:
                        text = mem_file.read_text(encoding="utf-8").strip()
                        if text:
                            await db.save_memory(project_id, codename, text)
                            counts["memories"] += 1
                            logger.debug(
                                "  → memory saved: %s / %s", project_name, codename
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "  Skipping memory file %s: %s", mem_file, exc
                        )

    finally:
        await db.close()

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m db.migrate",
        description=(
            "One-time migration: import SAP SIM JSON/JSONL project data "
            "into a SQLite database."
        ),
    )
    default_projects = (
        Path(__file__).resolve().parent.parent.parent / "projects"
    )
    default_db = default_projects / "sapsim.db"

    parser.add_argument(
        "--projects",
        default=str(default_projects),
        metavar="DIR",
        help=f"Root projects directory (default: {default_projects})",
    )
    parser.add_argument(
        "--db",
        default=str(default_db),
        metavar="PATH",
        help=f"Target SQLite database file (default: {default_db})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser


async def _run_migration(projects_dir: str, db_path: str) -> None:
    counts = await migrate_json_to_sqlite(projects_dir, db_path)
    print(
        f"\nMigration complete:\n"
        f"  {counts['projects']:>6} project(s)\n"
        f"  {counts['agents']:>6} agent(s)\n"
        f"  {counts['events']:>6} event(s)\n"
        f"  {counts['memories']:>6} memory summary/summaries\n"
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(name)s  %(message)s",
    )

    asyncio.run(_run_migration(args.projects, args.db))


if __name__ == "__main__":
    main()
