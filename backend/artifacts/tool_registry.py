"""
SAP SIM — Tool Registry Artifact
Phase: 7.5
Purpose: Tracks the SAP tool landscape within a simulation — which tools have
         been announced, who is using them, and how frequently they are accessed.

A "tool" in SAP context means anything an agent interacts with: custom reports,
ABAP programs, BAPIs, Fiori apps, batch jobs, etc.  The registry captures
metadata (module, T-codes, tables) and live usage so the simulation can model
realistic tool adoption dynamics.

Lifecycle:
    announced → in_use → (deprecated)

Key operations:
    ToolRegistry.announce_tool(tool)               – agent declares a new tool; persists to DB
    ToolRegistry.use_tool(tool_id, agent_id, ctx)  – record a tool interaction; increments DB counter
    ToolRegistry.get_tools(**filters)              – query the DB catalogue
    ToolRegistry.get_usage_stats()                 – summary statistics

Persistence: SQLite via utils.persistence.get_db() (db.save_tool / db.update_tool_usage).

Usage::

    registry = ToolRegistry(project_name="my-sap-project")

    t = registry.announce_tool(SimulatedTool(
        name="ZFIN_OPEN_ITEMS",
        category="reporting",
        description="Custom open-item ageing report for AR.",
        sap_module="FI",
        tcodes=["ZFI001"],
        tables=["BSID", "KNA1"],
        announced_by="Leila",
        announced_at_day=2,
    ))
    await registry.persist_tool(t)

    await registry.use_tool(t.id, agent_id="Sara", context="Monthly AR close")
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from utils.persistence import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ToolCategory = Literal["config", "dev", "test", "data", "security", "reporting"]
ToolStatus   = Literal["announced", "in_use", "deprecated"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ToolUsageEvent:
    """A single recorded usage of a tool by an agent."""

    agent_id: str
    day: int
    context: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SimulatedTool:
    """
    Represents one tool in the SAP tool landscape.

    Required fields must be supplied at construction.  All other fields are
    populated by :class:`ToolRegistry` as the simulation progresses.
    """

    # --- Core identity (required at construction) ---
    name: str
    category: ToolCategory
    description: str
    sap_module: str              # e.g. "FI", "MM", "SD", "Basis", "ABAP"
    tcodes: List[str]            # SAP transaction codes, e.g. ["SE38", "ZFI001"]
    tables: List[str]            # Database tables accessed, e.g. ["BKPF", "BSEG"]
    announced_by: str            # agent_id of the agent who announced the tool
    announced_at_day: int        # simulation day when the tool was announced

    # --- Auto-populated ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ToolStatus = "announced"
    usage_count: int = 0
    last_used_day: Optional[int] = None
    usage_history: List[ToolUsageEvent] = field(default_factory=list)

    # --- Optional enrichment ---
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """One-line human-readable summary."""
        tcode_str = ", ".join(self.tcodes) if self.tcodes else "—"
        return (
            f"[{self.id[:8]}] {self.name} ({self.category}/{self.sap_module}) "
            f"| status={self.status} | uses={self.usage_count} "
            f"| tcodes={tcode_str}"
        )

    # ------------------------------------------------------------------
    # Serialisation helpers (for internal use)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulatedTool":
        """Reconstruct a SimulatedTool from a plain dict."""
        raw_history = data.pop("usage_history", [])
        tool = cls(**data)
        tool.usage_history = [ToolUsageEvent(**e) for e in raw_history]
        return tool


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """
    Central catalogue of tools used throughout a SAP simulation project.

    Provides CRUD-style access and usage tracking backed by SQLite.

    Parameters
    ----------
    project_name:
        Project identifier used as ``project_id`` in all DB calls.
    """

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self._tools: Dict[str, SimulatedTool] = {}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def announce_tool(self, tool: SimulatedTool) -> SimulatedTool:
        """
        Register a new tool in the in-memory catalogue.

        An agent calls this to declare that a tool exists and will be used
        during the project.  The tool is assigned a unique ID (if not already
        set) and stored with ``status='announced'``.

        .. note::
            Call :meth:`persist_tool` immediately after to write to the DB.

        Args:
            tool: A :class:`SimulatedTool` instance.

        Returns:
            The stored :class:`SimulatedTool` (same object, with id confirmed).

        Raises:
            ValueError: If a tool with the same id is already registered.
        """
        if tool.id in self._tools:
            raise ValueError(
                f"Tool '{tool.id}' is already registered. "
                "Use a new id or call use_tool() to record usage."
            )

        tool.status = "announced"
        self._tools[tool.id] = tool

        logger.info(
            "Tool announced: %s by %s on day %s",
            tool.name,
            tool.announced_by,
            tool.announced_at_day,
        )
        return tool

    async def persist_tool(self, tool: SimulatedTool) -> None:
        """Persist *tool* to SQLite via db.save_tool()."""
        db = get_db()
        await db.save_tool(self.project_name, tool.to_dict())
        logger.debug("ToolRegistry: persisted tool '%s' to SQLite", tool.name)

    async def use_tool(
        self,
        tool_id: str,
        agent_id: str,
        context: str,
        day: int = 0,
    ) -> SimulatedTool:
        """
        Record that an agent used a tool during the simulation.

        Increments ``usage_count`` in-memory and in the DB via
        :meth:`~backend.db.repository.Database.update_tool_usage`, updates
        ``last_used_day``, appends a :class:`ToolUsageEvent`, and promotes the
        tool's status from ``'announced'`` to ``'in_use'`` on first recorded usage.

        Args:
            tool_id:  ID of the tool being used.
            agent_id: ID of the agent making the call.
            context:  Short description of why/how the tool is being used.
            day:      Current simulation day (defaults to 0 if not provided).

        Returns:
            The updated :class:`SimulatedTool`.

        Raises:
            KeyError:   If *tool_id* is not in the in-memory registry.
            ValueError: If the tool has been deprecated.
        """
        tool = self._get_tool_or_raise(tool_id)

        if tool.status == "deprecated":
            raise ValueError(
                f"Tool '{tool.name}' ({tool_id}) is deprecated and cannot be used."
            )

        event = ToolUsageEvent(agent_id=agent_id, day=day, context=context)
        tool.usage_history.append(event)
        tool.usage_count += 1
        tool.last_used_day = day

        if tool.status == "announced":
            tool.status = "in_use"
            logger.info("Tool '%s' transitioned to in_use.", tool.name)

        # Persist the usage increment to the DB
        db = get_db()
        await db.update_tool_usage(tool_id)

        logger.debug(
            "Tool used: %s by %s on day %s — %s",
            tool.name,
            agent_id,
            day,
            context,
        )
        return tool

    def deprecate_tool(self, tool_id: str, reason: str = "") -> SimulatedTool:
        """
        Mark a tool as deprecated in-memory.  No further usage will be allowed.

        Args:
            tool_id: ID of the tool to deprecate.
            reason:  Optional human-readable reason appended to notes.

        Returns:
            The updated :class:`SimulatedTool`.

        .. note::
            Call :meth:`persist_tool` after this to sync the status to the DB.
        """
        tool = self._get_tool_or_raise(tool_id)
        tool.status = "deprecated"
        if reason:
            tool.notes = (tool.notes + f"\n[deprecated] {reason}").strip()
        logger.info("Tool deprecated: %s — %s", tool.name, reason)
        return tool

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_tool(self, tool_id: str) -> Optional[SimulatedTool]:
        """Return a single tool from in-memory cache by id, or None if not found."""
        return self._tools.get(tool_id)

    async def get_tools(
        self,
        category: Optional[ToolCategory] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the database for tools belonging to this project.

        Args:
            category: When supplied, only tools in this category are returned.

        Returns:
            A list of tool dicts as returned by
            :meth:`~backend.db.repository.Database.get_tools`, sorted by name.
        """
        db = get_db()
        return await db.get_tools(self.project_name, category=category)

    def get_all_tools_local(self) -> List[SimulatedTool]:
        """Return all in-memory tools sorted by name."""
        return sorted(self._tools.values(), key=lambda t: t.name.lower())

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Compute and return a summary of tool usage from the in-memory registry.

        Returns a dict with the following keys:

        - ``total_tools``       – total number of registered tools
        - ``by_status``         – count per :data:`ToolStatus`
        - ``by_category``       – count per :data:`ToolCategory`
        - ``by_module``         – count per SAP module
        - ``total_usages``      – sum of all ``usage_count`` values
        - ``most_used``         – top-5 tools by ``usage_count`` (list of dicts)
        - ``most_active_agents``– top-5 agents by number of usage events
        - ``never_used``        – ids of announced tools with zero usages
        """
        all_tools = list(self._tools.values())

        by_status: Dict[str, int] = {}
        for t in all_tools:
            by_status[t.status] = by_status.get(t.status, 0) + 1

        by_category: Dict[str, int] = {}
        for t in all_tools:
            by_category[t.category] = by_category.get(t.category, 0) + 1

        by_module: Dict[str, int] = {}
        for t in all_tools:
            mod = t.sap_module.upper()
            by_module[mod] = by_module.get(mod, 0) + 1

        total_usages = sum(t.usage_count for t in all_tools)

        most_used = sorted(all_tools, key=lambda t: t.usage_count, reverse=True)[:5]
        most_used_list = [
            {"id": t.id, "name": t.name, "usage_count": t.usage_count}
            for t in most_used
        ]

        agent_counts: Dict[str, int] = {}
        for t in all_tools:
            for ev in t.usage_history:
                agent_counts[ev.agent_id] = agent_counts.get(ev.agent_id, 0) + 1
        most_active = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        most_active_agents = [
            {"agent_id": aid, "event_count": cnt} for aid, cnt in most_active
        ]

        never_used = [t.id for t in all_tools if t.usage_count == 0]

        return {
            "total_tools": len(all_tools),
            "by_status": by_status,
            "by_category": by_category,
            "by_module": by_module,
            "total_usages": total_usages,
            "most_used": most_used_list,
            "most_active_agents": most_active_agents,
            "never_used": never_used,
        }

    def get_tool_timeline(self, tool_id: str) -> List[Dict[str, Any]]:
        """
        Return the full usage timeline for a single tool, sorted chronologically.

        Each entry has: ``day``, ``agent_id``, ``context``, ``timestamp``.
        """
        tool = self._get_tool_or_raise(tool_id)
        return sorted(
            [asdict(ev) for ev in tool.usage_history],
            key=lambda e: (e["day"], e["timestamp"]),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_tool_or_raise(self, tool_id: str) -> SimulatedTool:
        """Return the tool or raise a descriptive KeyError."""
        tool = self._tools.get(tool_id)
        if tool is None:
            raise KeyError(
                f"Tool '{tool_id}' not found in registry for project "
                f"'{self.project_name}'. Did you call announce_tool() first?"
            )
        return tool

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return (
            f"ToolRegistry(project={self.project_name!r}, "
            f"tools={len(self._tools)})"
        )
