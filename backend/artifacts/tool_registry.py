"""
SAP SIM — Tool Registry Artifact
Phase: 4.3
Purpose: Tracks the SAP tool landscape within a simulation — which tools have
         been announced, who is using them, and how frequently they are accessed.

A "tool" in SAP context means anything an agent interacts with: custom reports,
ABAP programs, BAPIs, Fiori apps, batch jobs, etc.  The registry captures
metadata (module, T-codes, tables) and live usage so the simulation can model
realistic tool adoption dynamics.

Lifecycle:
    announced → in_use → (deprecated)

Key operations:
    ToolRegistry.announce_tool(tool)               – agent declares a new tool
    ToolRegistry.use_tool(tool_id, agent_id, ctx)  – record a tool interaction
    ToolRegistry.get_tools(**filters)              – query the catalogue
    ToolRegistry.get_usage_stats()                 – summary statistics
    ToolRegistry.save() / ToolRegistry.load()      – JSON persistence

Persistence::

    projects/<project_name>/tools.json

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

    registry.use_tool(t.id, agent_id="Sara", context="Monthly AR close")
    registry.save()
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

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
    # Serialisation helpers (for JSON round-trips)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulatedTool":
        """Reconstruct a SimulatedTool from a plain dict (e.g. loaded JSON)."""
        # Deserialise nested usage_history list
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

    Provides CRUD-style access, usage tracking, and JSON persistence under
    ``projects/<project_name>/tools.json``.
    """

    PROJECTS_ROOT: Path = Path(__file__).parent.parent.parent / "projects"

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self._tools: Dict[str, SimulatedTool] = {}
        self._load_if_exists()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @property
    def _tools_path(self) -> Path:
        return self.PROJECTS_ROOT / self.project_name / "tools.json"

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def announce_tool(self, tool: SimulatedTool) -> SimulatedTool:
        """
        Register a new tool in the catalogue.

        An agent calls this to declare that a tool exists and will be used
        during the project.  The tool is assigned a unique ID (if not already
        set) and stored with ``status='announced'``.

        Args:
            tool: A :class:`SimulatedTool` instance (id may be pre-set or left
                  as the default UUID).

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

        # Ensure status starts at 'announced'
        tool.status = "announced"
        self._tools[tool.id] = tool

        logger.info(
            "Tool announced: %s by %s on day %s",
            tool.name,
            tool.announced_by,
            tool.announced_at_day,
        )
        return tool

    def use_tool(
        self,
        tool_id: str,
        agent_id: str,
        context: str,
        day: int = 0,
    ) -> SimulatedTool:
        """
        Record that an agent used a tool during the simulation.

        Increments ``usage_count``, updates ``last_used_day``, appends a
        :class:`ToolUsageEvent` to the tool's history, and promotes the tool's
        status from ``'announced'`` to ``'in_use'`` on first recorded usage.

        Args:
            tool_id:  ID of the tool being used.
            agent_id: ID of the agent making the call.
            context:  Short description of why/how the tool is being used.
            day:      Current simulation day (defaults to 0 if not provided).

        Returns:
            The updated :class:`SimulatedTool`.

        Raises:
            KeyError:  If *tool_id* is not in the registry.
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
        Mark a tool as deprecated.  No further usage will be allowed.

        Args:
            tool_id: ID of the tool to deprecate.
            reason:  Optional human-readable reason appended to notes.

        Returns:
            The updated :class:`SimulatedTool`.
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
        """Return a single tool by id, or None if not found."""
        return self._tools.get(tool_id)

    def get_tools(
        self,
        *,
        category: Optional[ToolCategory] = None,
        sap_module: Optional[str] = None,
        status: Optional[ToolStatus] = None,
        announced_by: Optional[str] = None,
        tag: Optional[str] = None,
        tcode: Optional[str] = None,
        table: Optional[str] = None,
    ) -> List[SimulatedTool]:
        """
        Return tools matching all supplied filter criteria.

        All filters are optional and applied with AND semantics.

        Args:
            category:     Filter by :attr:`SimulatedTool.category`.
            sap_module:   Filter by :attr:`SimulatedTool.sap_module` (case-insensitive).
            status:       Filter by :attr:`SimulatedTool.status`.
            announced_by: Filter by the agent who announced the tool.
            tag:          Filter tools that include this tag.
            tcode:        Filter tools that include this T-code.
            table:        Filter tools that include this database table.

        Returns:
            A sorted list of :class:`SimulatedTool` instances (by name).
        """
        results = list(self._tools.values())

        if category is not None:
            results = [t for t in results if t.category == category]
        if sap_module is not None:
            results = [t for t in results if t.sap_module.upper() == sap_module.upper()]
        if status is not None:
            results = [t for t in results if t.status == status]
        if announced_by is not None:
            results = [t for t in results if t.announced_by == announced_by]
        if tag is not None:
            results = [t for t in results if tag in t.tags]
        if tcode is not None:
            results = [t for t in results if tcode in t.tcodes]
        if table is not None:
            results = [t for t in results if table in t.tables]

        return sorted(results, key=lambda t: t.name.lower())

    def get_all_tools(self) -> List[SimulatedTool]:
        """Return all tools sorted by name."""
        return sorted(self._tools.values(), key=lambda t: t.name.lower())

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Compute and return a summary of tool usage across the registry.

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

        # Counts by status
        by_status: Dict[str, int] = {}
        for t in all_tools:
            by_status[t.status] = by_status.get(t.status, 0) + 1

        # Counts by category
        by_category: Dict[str, int] = {}
        for t in all_tools:
            by_category[t.category] = by_category.get(t.category, 0) + 1

        # Counts by SAP module
        by_module: Dict[str, int] = {}
        for t in all_tools:
            mod = t.sap_module.upper()
            by_module[mod] = by_module.get(mod, 0) + 1

        # Total usages
        total_usages = sum(t.usage_count for t in all_tools)

        # Most-used tools
        most_used = sorted(all_tools, key=lambda t: t.usage_count, reverse=True)[:5]
        most_used_list = [
            {"id": t.id, "name": t.name, "usage_count": t.usage_count}
            for t in most_used
        ]

        # Most-active agents
        agent_counts: Dict[str, int] = {}
        for t in all_tools:
            for ev in t.usage_history:
                agent_counts[ev.agent_id] = agent_counts.get(ev.agent_id, 0) + 1
        most_active = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        most_active_agents = [
            {"agent_id": aid, "event_count": cnt} for aid, cnt in most_active
        ]

        # Never-used tools
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
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """
        Serialise the registry to ``projects/<project_name>/tools.json``.

        Creates the project directory if it does not exist.
        """
        self._tools_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "project": self.project_name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "tools": [t.to_dict() for t in self._tools.values()],
        }

        with self._tools_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

        logger.info(
            "ToolRegistry saved: %d tools → %s",
            len(self._tools),
            self._tools_path,
        )

    def load(self) -> None:
        """
        Load / reload the registry from ``projects/<project_name>/tools.json``.

        Replaces the current in-memory state.  Silently returns if the file
        does not exist (fresh project).
        """
        if not self._tools_path.exists():
            logger.debug("No tools.json found for project '%s'.", self.project_name)
            return

        with self._tools_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        self._tools = {}
        for raw in payload.get("tools", []):
            tool = SimulatedTool.from_dict(raw)
            self._tools[tool.id] = tool

        logger.info(
            "ToolRegistry loaded: %d tools from %s",
            len(self._tools),
            self._tools_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_if_exists(self) -> None:
        """Called at construction time to hydrate from disk if available."""
        self.load()

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
