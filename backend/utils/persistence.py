"""
SAP SIM — Persistence Utilities
Phase: 1.5
Purpose: Async file I/O for all project data: project state, agent state,
         feed events (JSONL), and memory summaries. Auto-creates directories.
Dependencies: aiofiles, pathlib, json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

logger = logging.getLogger(__name__)

# Base directory for all project data (relative to repo root)
PROJECTS_BASE = Path(__file__).resolve().parent.parent.parent / "projects"


def _project_dir(project_name: str) -> Path:
    """Return the root directory for a project, without creating it."""
    return PROJECTS_BASE / project_name


async def _ensure_dir(path: Path) -> None:
    """Create *path* (and parents) if it does not exist."""
    await aiofiles.os.makedirs(str(path), exist_ok=True)


# ---------------------------------------------------------------------------
# Project state  — projects/{name}/project.json
# ---------------------------------------------------------------------------


async def save_project_state(project_name: str, state_dict: dict[str, Any]) -> None:
    """Persist the full project state dict to ``project.json``.

    Args:
        project_name: The unique project identifier.
        state_dict:   Serialisable dict representing the current project state.
    """
    project_dir = _project_dir(project_name)
    await _ensure_dir(project_dir)
    target = project_dir / "project.json"
    async with aiofiles.open(str(target), "w", encoding="utf-8") as fh:
        await fh.write(json.dumps(state_dict, indent=2, default=str))
    logger.debug("Saved project state for '%s'", project_name)


async def load_project_state(project_name: str) -> dict[str, Any] | None:
    """Load ``project.json`` for the given project.

    Returns:
        The state dict, or ``None`` if the file does not exist yet.
    """
    target = _project_dir(project_name) / "project.json"
    if not target.exists():
        return None
    async with aiofiles.open(str(target), "r", encoding="utf-8") as fh:
        raw = await fh.read()
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Feed events  — projects/{name}/feed/events.jsonl  (append-only)
# ---------------------------------------------------------------------------


async def append_feed_event(project_name: str, event_dict: dict[str, Any]) -> None:
    """Append a single event to the JSONL feed log.

    The file is opened in append mode so each call adds exactly one line.

    Args:
        project_name: The unique project identifier.
        event_dict:   JSON-serialisable event payload.
    """
    feed_dir = _project_dir(project_name) / "feed"
    await _ensure_dir(feed_dir)
    target = feed_dir / "events.jsonl"
    line = json.dumps(event_dict, default=str) + "\n"
    async with aiofiles.open(str(target), "a", encoding="utf-8") as fh:
        await fh.write(line)


# ---------------------------------------------------------------------------
# Agent state  — projects/{name}/agents/{codename}.json
# ---------------------------------------------------------------------------


async def save_agent_state(
    project_name: str, codename: str, state_dict: dict[str, Any]
) -> None:
    """Persist an agent's state dict.

    Args:
        project_name: The unique project identifier.
        codename:     Agent's unique codename (e.g. ``PM_ALEX``).
        state_dict:   Serialisable snapshot of the agent's current state.
    """
    agents_dir = _project_dir(project_name) / "agents"
    await _ensure_dir(agents_dir)
    target = agents_dir / f"{codename}.json"
    async with aiofiles.open(str(target), "w", encoding="utf-8") as fh:
        await fh.write(json.dumps(state_dict, indent=2, default=str))
    logger.debug("Saved agent state for %s / %s", project_name, codename)


async def load_agent_state(
    project_name: str, codename: str
) -> dict[str, Any] | None:
    """Load an agent's persisted state.

    Returns:
        The state dict, or ``None`` if no state file exists yet.
    """
    target = _project_dir(project_name) / "agents" / f"{codename}.json"
    if not target.exists():
        return None
    async with aiofiles.open(str(target), "r", encoding="utf-8") as fh:
        raw = await fh.read()
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Memory summary  — projects/{name}/memory/{codename}_summary.md
# ---------------------------------------------------------------------------


async def save_memory_summary(
    project_name: str, codename: str, summary_text: str
) -> None:
    """Write a compressed memory summary for an agent.

    The file is overwritten on each call (always the latest summary).

    Args:
        project_name:  The unique project identifier.
        codename:      Agent's unique codename.
        summary_text:  Plain-text (Markdown) summary produced by LLM compression.
    """
    memory_dir = _project_dir(project_name) / "memory"
    await _ensure_dir(memory_dir)
    target = memory_dir / f"{codename}_summary.md"
    async with aiofiles.open(str(target), "w", encoding="utf-8") as fh:
        await fh.write(summary_text)
    logger.debug("Saved memory summary for %s / %s", project_name, codename)


async def load_memory_summary(project_name: str, codename: str) -> str | None:
    """Load an agent's memory summary.

    Returns:
        The raw Markdown text, or ``None`` if no summary file exists.
    """
    target = _project_dir(project_name) / "memory" / f"{codename}_summary.md"
    if not target.exists():
        return None
    async with aiofiles.open(str(target), "r", encoding="utf-8") as fh:
        return await fh.read()
