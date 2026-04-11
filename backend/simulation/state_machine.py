"""
SAP SIM — Project State Machine
Phase: 3.1
Purpose: ProjectState dataclass, status constants, SAP Activate phase definitions,
         and save/load helpers backed by the persistence layer.
Dependencies: utils.persistence, dataclasses, datetime
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from utils.persistence import save_project_state, load_project_state

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project-level status constants
# ---------------------------------------------------------------------------

STATUS_IDLE = "IDLE"
STATUS_RUNNING = "RUNNING"
STATUS_PAUSED = "PAUSED"
STATUS_COMPLETED = "COMPLETED"
STATUS_STOPPED = "STOPPED"

VALID_STATUSES = {STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_COMPLETED, STATUS_STOPPED}

# ---------------------------------------------------------------------------
# SAP Activate phase definitions (default methodology)
# ---------------------------------------------------------------------------

PHASES: list[dict[str, Any]] = [
    {
        "id": "discover",
        "name": "Discover",
        "duration_days": 14,
        "description": (
            "Establish project vision and value proposition. "
            "Align stakeholders on scope, objectives, and success criteria. "
            "Review SAP Best Practices and pre-configured solutions."
        ),
    },
    {
        "id": "prepare",
        "name": "Prepare",
        "duration_days": 21,
        "description": (
            "Set up the project environment, infrastructure, and governance. "
            "Onboard the project team, define roles, and baseline the project plan. "
            "Configure system landscape and transport routes."
        ),
    },
    {
        "id": "explore",
        "name": "Explore",
        "duration_days": 35,
        "description": (
            "Run fit-to-standard workshops to map business processes to SAP standard. "
            "Identify gaps requiring configuration or development (RICEFW). "
            "Produce the solution blueprint and obtain sign-off."
        ),
    },
    {
        "id": "realize",
        "name": "Realize",
        "duration_days": 60,
        "description": (
            "Implement the solution: configure, develop custom objects, migrate data. "
            "Execute iterative integration testing and defect resolution. "
            "Complete security design, authorizations, and interface testing."
        ),
    },
    {
        "id": "deploy",
        "name": "Deploy",
        "duration_days": 21,
        "description": (
            "Execute user acceptance testing (UAT) and final performance testing. "
            "Perform cutover rehearsals and finalize go-live readiness checklist. "
            "Train end-users and prepare hypercare support model."
        ),
    },
    {
        "id": "run",
        "name": "Run",
        "duration_days": 14,
        "description": (
            "Go-live and hypercare support. Monitor system stability and resolve incidents. "
            "Conduct lessons-learned session and hand over to BAU operations. "
            "Produce project closure report."
        ),
    },
]

# Derived lookup: phase_id → phase dict
PHASES_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in PHASES}

# Total project duration from default phases
TOTAL_DAYS: int = sum(p["duration_days"] for p in PHASES)  # 165


# ---------------------------------------------------------------------------
# Milestone definitions per phase
# ---------------------------------------------------------------------------

DEFAULT_MILESTONES: list[dict[str, Any]] = [
    {"id": "M01", "name": "Project Charter Signed",            "phase": "discover",  "completed": False},
    {"id": "M02", "name": "System Landscape Ready",            "phase": "prepare",   "completed": False},
    {"id": "M03", "name": "Team Onboarding Complete",          "phase": "prepare",   "completed": False},
    {"id": "M04", "name": "Fit-to-Standard Workshops Done",    "phase": "explore",   "completed": False},
    {"id": "M05", "name": "Solution Blueprint Approved",       "phase": "explore",   "completed": False},
    {"id": "M06", "name": "RICEFW Inventory Signed Off",       "phase": "explore",   "completed": False},
    {"id": "M07", "name": "Integration Test Complete",         "phase": "realize",   "completed": False},
    {"id": "M08", "name": "Data Migration Dry Run Passed",     "phase": "realize",   "completed": False},
    {"id": "M09", "name": "Security & Auth Design Approved",   "phase": "realize",   "completed": False},
    {"id": "M10", "name": "UAT Sign-off Obtained",             "phase": "deploy",    "completed": False},
    {"id": "M11", "name": "Go-Live Readiness Confirmed",       "phase": "deploy",    "completed": False},
    {"id": "M12", "name": "Cutover Executed",                  "phase": "deploy",    "completed": False},
    {"id": "M13", "name": "Hypercare Period Complete",         "phase": "run",       "completed": False},
    {"id": "M14", "name": "Project Closure Report Issued",     "phase": "run",       "completed": False},
]


# ---------------------------------------------------------------------------
# ProjectState dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProjectState:
    """Complete, serialisable snapshot of a simulation project.

    All mutable collections are default-factory to avoid shared-state bugs.

    Attributes:
        project_name:       Unique project identifier (used as directory name).
        status:             One of IDLE / RUNNING / PAUSED / COMPLETED / STOPPED.
        current_phase:      ID of the active SAP Activate phase (e.g. ``"discover"``).
        simulated_day:      How many simulated project days have elapsed.
        total_days:         Total planned project duration in simulated days.
        phase_progress:     Mapping of phase_id → completion percentage (0–100).
        active_agents:      Codenames of agents currently processing a turn.
        pending_decisions:  List of decision dicts awaiting resolution.
        active_meetings:    List of meeting dicts currently in progress.
        milestones:         List of milestone dicts with ``completed`` flag.
        created_at:         ISO-8601 timestamp of when the project was created.
        last_updated:       ISO-8601 timestamp of the most recent state save.
    """

    project_name: str
    status: str = STATUS_IDLE
    current_phase: str = "discover"
    simulated_day: int = 0
    total_days: int = TOTAL_DAYS

    # Progress tracking
    phase_progress: dict[str, float] = field(
        default_factory=lambda: {p["id"]: 0.0 for p in PHASES}
    )

    # Live activity lists — populated and cleared by the Conductor
    active_agents: list[str] = field(default_factory=list)
    pending_decisions: list[dict[str, Any]] = field(default_factory=list)
    active_meetings: list[dict[str, Any]] = field(default_factory=list)

    # Milestones — pre-populated from DEFAULT_MILESTONES on creation
    milestones: list[dict[str, Any]] = field(
        default_factory=lambda: [m.copy() for m in DEFAULT_MILESTONES]
    )

    # Timestamps
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # -----------------------------------------------------------------------
    # Validation helpers
    # -----------------------------------------------------------------------

    def validate_status(self, new_status: str) -> None:
        """Raise ValueError if *new_status* is not a recognised project status."""
        if new_status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of {sorted(VALID_STATUSES)}."
            )

    def validate_phase(self, phase_id: str) -> None:
        """Raise ValueError if *phase_id* is not a recognised SAP Activate phase."""
        if phase_id not in PHASES_BY_ID:
            raise ValueError(
                f"Invalid phase id '{phase_id}'. Must be one of {list(PHASES_BY_ID.keys())}."
            )

    # -----------------------------------------------------------------------
    # Mutation helpers
    # -----------------------------------------------------------------------

    def transition_status(self, new_status: str) -> None:
        """Validate and apply a status transition, updating ``last_updated``.

        Args:
            new_status: The target status string.

        Raises:
            ValueError: If the transition is not permitted from the current state.
        """
        self.validate_status(new_status)

        allowed: dict[str, set[str]] = {
            STATUS_IDLE:      {STATUS_RUNNING},
            STATUS_RUNNING:   {STATUS_PAUSED, STATUS_COMPLETED, STATUS_STOPPED},
            STATUS_PAUSED:    {STATUS_RUNNING, STATUS_STOPPED},
            STATUS_COMPLETED: set(),
            STATUS_STOPPED:   set(),
        }
        if new_status not in allowed.get(self.status, set()):
            raise ValueError(
                f"Cannot transition from '{self.status}' to '{new_status}'. "
                f"Allowed: {sorted(allowed.get(self.status, set()))}."
            )

        logger.info(
            "Project '%s' status: %s → %s",
            self.project_name, self.status, new_status,
        )
        self.status = new_status
        self.touch()

    def advance_day(self) -> None:
        """Increment ``simulated_day`` by one and update ``last_updated``."""
        self.simulated_day += 1
        self.touch()

    def set_phase(self, phase_id: str) -> None:
        """Move to a new SAP Activate phase and reset its progress counter.

        Args:
            phase_id: ID of the target phase.
        """
        self.validate_phase(phase_id)
        self.current_phase = phase_id
        self.phase_progress[phase_id] = 0.0
        self.touch()
        logger.info("Project '%s' entered phase: %s", self.project_name, phase_id)

    def update_phase_progress(self, phase_id: str, percentage: float) -> None:
        """Set the completion percentage for a specific phase.

        Args:
            phase_id:   ID of the phase to update.
            percentage: Value between 0.0 and 100.0 (clamped automatically).
        """
        self.validate_phase(phase_id)
        self.phase_progress[phase_id] = max(0.0, min(100.0, percentage))
        self.touch()

    def complete_milestone(self, milestone_id: str) -> bool:
        """Mark a milestone as completed.

        Args:
            milestone_id: The ``id`` field of the target milestone.

        Returns:
            True if the milestone was found and updated; False if not found.
        """
        for milestone in self.milestones:
            if milestone["id"] == milestone_id:
                milestone["completed"] = True
                milestone["completed_day"] = self.simulated_day
                self.touch()
                logger.info(
                    "Project '%s' milestone completed: %s (%s)",
                    self.project_name, milestone["name"], milestone_id,
                )
                return True
        logger.warning(
            "Milestone id '%s' not found in project '%s'.",
            milestone_id, self.project_name,
        )
        return False

    def touch(self) -> None:
        """Refresh ``last_updated`` to the current UTC time."""
        self.last_updated = datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------------------------------
    # Computed properties
    # -----------------------------------------------------------------------

    @property
    def current_phase_info(self) -> dict[str, Any]:
        """Return the full phase definition dict for the active phase."""
        return PHASES_BY_ID[self.current_phase]

    @property
    def overall_progress(self) -> float:
        """Weighted overall project completion percentage (0–100).

        Each phase is weighted by its ``duration_days`` relative to ``total_days``.
        """
        if self.total_days == 0:
            return 0.0
        weighted = sum(
            self.phase_progress.get(p["id"], 0.0) * p["duration_days"]
            for p in PHASES
        )
        return round(weighted / self.total_days, 2)

    @property
    def next_phase(self) -> dict[str, Any] | None:
        """Return the next SAP Activate phase dict, or None if on the last phase."""
        ids = [p["id"] for p in PHASES]
        try:
            idx = ids.index(self.current_phase)
        except ValueError:
            return None
        if idx + 1 < len(ids):
            return PHASES_BY_ID[ids[idx + 1]]
        return None

    @property
    def completed_milestones(self) -> list[dict[str, Any]]:
        """Return only milestones that have been completed."""
        return [m for m in self.milestones if m.get("completed")]

    @property
    def pending_milestones(self) -> list[dict[str, Any]]:
        """Return milestones not yet completed for the current phase."""
        return [
            m for m in self.milestones
            if not m.get("completed") and m.get("phase") == self.current_phase
        ]

    # -----------------------------------------------------------------------
    # Serialisation
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable dict snapshot of this state.

        Includes computed properties so API consumers get them without extra
        round-trips.
        """
        return {
            "project_name": self.project_name,
            "status": self.status,
            "current_phase": self.current_phase,
            "current_phase_info": self.current_phase_info,
            "simulated_day": self.simulated_day,
            "total_days": self.total_days,
            "phase_progress": dict(self.phase_progress),
            "overall_progress": self.overall_progress,
            "active_agents": list(self.active_agents),
            "pending_decisions": list(self.pending_decisions),
            "active_meetings": list(self.active_meetings),
            "milestones": [m.copy() for m in self.milestones],
            "completed_milestones_count": len(self.completed_milestones),
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        """Reconstruct a ProjectState from a serialised dict.

        Args:
            data: Dict as produced by :meth:`to_dict` or loaded from ``project.json``.

        Returns:
            A fully initialised :class:`ProjectState` instance.
        """
        state = cls(project_name=data["project_name"])
        state.status = data.get("status", STATUS_IDLE)
        state.current_phase = data.get("current_phase", "discover")
        state.simulated_day = data.get("simulated_day", 0)
        state.total_days = data.get("total_days", TOTAL_DAYS)
        state.phase_progress = data.get(
            "phase_progress", {p["id"]: 0.0 for p in PHASES}
        )
        state.active_agents = data.get("active_agents", [])
        state.pending_decisions = data.get("pending_decisions", [])
        state.active_meetings = data.get("active_meetings", [])
        state.milestones = data.get(
            "milestones", [m.copy() for m in DEFAULT_MILESTONES]
        )
        state.created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())
        state.last_updated = data.get("last_updated", datetime.now(timezone.utc).isoformat())
        return state


# ---------------------------------------------------------------------------
# Async save / load helpers  (thin wrappers over persistence layer)
# ---------------------------------------------------------------------------


async def save_state(state: ProjectState) -> None:
    """Persist a :class:`ProjectState` to ``projects/{name}/project.json``.

    Args:
        state: The project state to save.
    """
    state.touch()
    await save_project_state(state.project_name, state.to_dict())
    logger.debug("ProjectState saved for '%s'", state.project_name)


async def load_state(project_name: str) -> ProjectState | None:
    """Load a :class:`ProjectState` from ``projects/{name}/project.json``.

    Args:
        project_name: The unique project identifier.

    Returns:
        A reconstructed :class:`ProjectState`, or ``None`` if no file exists.
    """
    data = await load_project_state(project_name)
    if data is None:
        logger.debug("No saved state found for project '%s'.", project_name)
        return None
    state = ProjectState.from_dict(data)
    logger.debug(
        "Loaded ProjectState for '%s': status=%s, phase=%s, day=%d",
        project_name, state.status, state.current_phase, state.simulated_day,
    )
    return state


async def create_new_state(project_name: str) -> ProjectState:
    """Create and immediately persist a fresh :class:`ProjectState`.

    Initialises phase_progress for all phases to 0.0 and sets status to IDLE.

    Args:
        project_name: The unique project identifier.

    Returns:
        The newly created :class:`ProjectState` (already saved to disk).
    """
    state = ProjectState(project_name=project_name)
    await save_state(state)
    logger.info("Created new ProjectState for '%s'.", project_name)
    return state
