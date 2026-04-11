"""
SAP SIM — Meeting Scheduler
Phase: 3.3
Purpose: Hybrid scheduled + organic meeting management.  Maintains the canonical
         list of standard meetings per SAP Activate phase (SCHEDULED_MEETINGS),
         an organic meeting queue for unplanned requests, turn-based dialogue
         execution for every meeting, and structured Markdown logging.
Dependencies: state_machine, api.sse (EventBus), agents.base_agent, utils.persistence
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import aiofiles
import aiofiles.os

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent
    from api.sse import EventBus
    from simulation.state_machine import ProjectState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Projects base dir (mirroring persistence.py)
# ---------------------------------------------------------------------------

PROJECTS_BASE = Path(__file__).resolve().parent.parent.parent / "projects"


# ---------------------------------------------------------------------------
# Meeting types and status constants
# ---------------------------------------------------------------------------

class MeetingStatus(str, Enum):
    PENDING   = "pending"     # queued, not yet started
    ACTIVE    = "active"      # in progress
    COMPLETED = "completed"   # finished, log saved
    CANCELLED = "cancelled"   # dropped (e.g. key participant unavailable)


class MeetingUrgency(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ---------------------------------------------------------------------------
# Standard meetings per SAP Activate phase
# ---------------------------------------------------------------------------

SCHEDULED_MEETINGS: dict[str, list[dict[str, Any]]] = {
    "discover": [
        {
            "title": "Kick-off Meeting",
            "agenda": [
                "Welcome and introductions",
                "Project vision and value proposition",
                "High-level scope and objectives",
                "Team roles and responsibilities",
                "Communication and governance model",
                "Next steps and actions",
            ],
            "default_participants": [
                "PM_ALEX", "ARCH_SARA", "EXEC_VICTOR", "CUST_PM_OMAR",
                "IT_MGR_HELEN", "PMO_NIKO", "CHG_NADIA",
            ],
            "duration_hours": 2.0,
            "facilitator": "PM_ALEX",
        },
        {
            "title": "Project Charter Review",
            "agenda": [
                "Review draft project charter",
                "Confirm project scope boundaries",
                "Agree on success criteria and KPIs",
                "Sign-off on governance structure",
                "Budget and resource alignment",
            ],
            "default_participants": [
                "PM_ALEX", "EXEC_VICTOR", "CUST_PM_OMAR", "PMO_NIKO", "ARCH_SARA",
            ],
            "duration_hours": 1.5,
            "facilitator": "PMO_NIKO",
        },
    ],
    "prepare": [
        {
            "title": "System Landscape Design",
            "agenda": [
                "Review proposed 3-system landscape (DEV/QAS/PRD)",
                "Transport route configuration",
                "Client strategy and number ranges",
                "System access provisioning approach",
                "Infrastructure sizing and cloud hosting",
            ],
            "default_participants": [
                "BASIS_KURT", "ARCH_SARA", "IT_MGR_HELEN", "INT_MARCO", "PM_ALEX",
            ],
            "duration_hours": 2.0,
            "facilitator": "BASIS_KURT",
        },
        {
            "title": "Team Onboarding",
            "agenda": [
                "Project tooling and collaboration platform walkthrough",
                "Working norms and meeting cadence",
                "Access credentials and system setup",
                "SAP Activate methodology overview",
                "Phase deliverables and milestone plan",
                "Team Q&A",
            ],
            "default_participants": [
                "PM_ALEX", "CHG_NADIA", "PMO_NIKO", "CUST_PM_OMAR", "IT_MGR_HELEN",
                "BA_CUST_JAMES", "CHAMP_LEILA",
            ],
            "duration_hours": 2.5,
            "facilitator": "CHG_NADIA",
        },
    ],
    "explore": [
        {
            "title": "Fit-to-Standard Workshop: FI",
            "agenda": [
                "Current-state FI process walkthrough (by customer)",
                "SAP S/4HANA Finance best practice demo",
                "Gap identification: G/L, AP, AR, Asset Accounting",
                "Configuration decisions and delta design",
                "RICEFW objects scoped from FI",
                "Open items and action list",
            ],
            "default_participants": [
                "FI_CHEN", "FI_KU_ROSE", "CO_MARTA", "CO_KU_BJORN",
                "ARCH_SARA", "PM_ALEX", "BA_CUST_JAMES",
            ],
            "duration_hours": 4.0,
            "facilitator": "FI_CHEN",
        },
        {
            "title": "Fit-to-Standard Workshop: MM",
            "agenda": [
                "Current procurement and inventory processes",
                "SAP MM best practice walkthrough (PR/PO/GR/IR cycle)",
                "Gap analysis: purchasing org, storage locations, MRP",
                "Inventory management configuration decisions",
                "Vendor master data requirements",
                "RICEFW items from MM",
            ],
            "default_participants": [
                "MM_RAVI", "MM_KU_GRACE", "WM_FATIMA", "WM_KU_ELENA",
                "PP_JONAS", "PP_KU_IBRAHIM", "PM_ALEX",
            ],
            "duration_hours": 4.0,
            "facilitator": "MM_RAVI",
        },
        {
            "title": "Fit-to-Standard Workshop: SD",
            "agenda": [
                "Order-to-cash process mapping",
                "Sales organisation and distribution channel design",
                "Pricing procedure requirements",
                "Credit management and billing configuration",
                "Customer master data strategy",
                "SD-MM-FI integration touchpoints",
            ],
            "default_participants": [
                "SD_ISLA", "SD_KU_TONY", "FI_CHEN", "MM_RAVI",
                "INT_MARCO", "BA_CUST_JAMES", "PM_ALEX",
            ],
            "duration_hours": 4.0,
            "facilitator": "SD_ISLA",
        },
        {
            "title": "Integration Design Session",
            "agenda": [
                "Interface inventory review (all inbound/outbound interfaces)",
                "Integration platform selection (API vs iDoc vs middleware)",
                "Error handling and monitoring approach",
                "Interface testing strategy",
                "Data volume and frequency analysis",
                "Open integration risks",
            ],
            "default_participants": [
                "INT_MARCO", "ARCH_SARA", "BASIS_KURT", "DEV_PRIYA",
                "IT_MGR_HELEN", "PM_ALEX",
            ],
            "duration_hours": 3.0,
            "facilitator": "INT_MARCO",
        },
        {
            "title": "Blueprint Sign-off",
            "agenda": [
                "Solution blueprint summary by workstream",
                "RICEFW inventory review and effort sign-off",
                "Open gaps and risk register review",
                "Data migration scope confirmation",
                "Test strategy overview",
                "Blueprint approval and phase gate sign-off",
            ],
            "default_participants": [
                "PM_ALEX", "ARCH_SARA", "EXEC_VICTOR", "CUST_PM_OMAR",
                "PMO_NIKO", "QA_CLAIRE", "DM_FELIX",
            ],
            "duration_hours": 2.0,
            "facilitator": "PM_ALEX",
        },
    ],
    "realize": [
        {
            "title": "Sprint Review 1",
            "agenda": [
                "Demo: FI configuration completed in Sprint 1",
                "Demo: MM baseline configuration",
                "Integration test results overview",
                "Defects raised and resolutions",
                "Sprint 2 scope and priorities",
                "Customer feedback and acceptance",
            ],
            "default_participants": [
                "PM_ALEX", "CUST_PM_OMAR", "FI_CHEN", "FI_KU_ROSE",
                "MM_RAVI", "MM_KU_GRACE", "QA_CLAIRE", "EXEC_VICTOR",
            ],
            "duration_hours": 2.0,
            "facilitator": "PM_ALEX",
        },
        {
            "title": "Sprint Review 2",
            "agenda": [
                "Demo: SD and PP configuration",
                "Demo: Custom developments (ABAP/RICEFW)",
                "Integration test wave 2 results",
                "Data migration dry-run status",
                "Defect burndown progress",
                "Sprint 3 scope and re-prioritization",
            ],
            "default_participants": [
                "PM_ALEX", "CUST_PM_OMAR", "SD_ISLA", "SD_KU_TONY",
                "PP_JONAS", "DEV_PRIYA", "DEV_LEON", "QA_CLAIRE", "DM_FELIX",
            ],
            "duration_hours": 2.0,
            "facilitator": "PM_ALEX",
        },
        {
            "title": "Integration Test Planning",
            "agenda": [
                "End-to-end test scenario inventory",
                "Test data requirements and preparation",
                "Integration test wave schedule",
                "Roles and responsibilities for test execution",
                "Defect management process walkthrough",
                "Entry and exit criteria",
            ],
            "default_participants": [
                "QA_CLAIRE", "INT_MARCO", "PM_ALEX", "DEV_PRIYA",
                "FI_CHEN", "MM_RAVI", "SD_ISLA",
            ],
            "duration_hours": 2.5,
            "facilitator": "QA_CLAIRE",
        },
        {
            "title": "Data Migration Design",
            "agenda": [
                "Migration object list (master data + open items)",
                "Source system extraction approach",
                "Transformation and cleansing rules",
                "LTMC/LSMW/BAPI tooling decisions",
                "Migration cutover timeline and dress rehearsal plan",
                "Data quality validation strategy",
            ],
            "default_participants": [
                "DM_FELIX", "FI_KU_ROSE", "MM_KU_GRACE", "IT_MGR_HELEN",
                "DEV_PRIYA", "PM_ALEX",
            ],
            "duration_hours": 3.0,
            "facilitator": "DM_FELIX",
        },
        {
            "title": "Security Design Review",
            "agenda": [
                "Role concept design walkthrough",
                "Segregation of Duties (SoD) conflict matrix",
                "Critical authorizations and emergency access",
                "GRC configuration approach",
                "Audit and compliance requirements",
                "Security testing plan",
            ],
            "default_participants": [
                "SEC_DIANA", "IT_MGR_HELEN", "BASIS_KURT", "PM_ALEX",
                "FI_CHEN", "MM_RAVI",
            ],
            "duration_hours": 2.5,
            "facilitator": "SEC_DIANA",
        },
    ],
    "deploy": [
        {
            "title": "UAT Kick-off",
            "agenda": [
                "UAT scope, objectives, and exit criteria",
                "Test scenario assignments to key users",
                "UAT environment readiness confirmation",
                "Defect management and triage process",
                "UAT schedule and checkpoints",
                "Key user Q&A",
            ],
            "default_participants": [
                "QA_CLAIRE", "CUST_PM_OMAR", "PM_ALEX", "FI_KU_ROSE",
                "MM_KU_GRACE", "SD_KU_TONY", "PP_KU_IBRAHIM", "CHAMP_LEILA",
            ],
            "duration_hours": 2.0,
            "facilitator": "QA_CLAIRE",
        },
        {
            "title": "Go-Live Readiness Review",
            "agenda": [
                "Go-live readiness checklist review (technical + functional)",
                "Outstanding defect status (P1/P2 open items)",
                "Cutover plan walkthrough",
                "Hypercare support model confirmation",
                "Go / No-go decision",
                "Communication plan for go-live",
            ],
            "default_participants": [
                "PM_ALEX", "EXEC_VICTOR", "CUST_PM_OMAR", "ARCH_SARA",
                "BASIS_KURT", "QA_CLAIRE", "PMO_NIKO",
            ],
            "duration_hours": 2.0,
            "facilitator": "PM_ALEX",
        },
        {
            "title": "Cutover Planning",
            "agenda": [
                "Cutover weekend task list and sequence",
                "System freeze and blackout window confirmation",
                "Data migration final run plan",
                "Rollback criteria and decision tree",
                "Cutover team assignments and contact list",
                "Dress rehearsal debrief and open items",
            ],
            "default_participants": [
                "PM_ALEX", "BASIS_KURT", "DM_FELIX", "INT_MARCO",
                "CUST_PM_OMAR", "IT_MGR_HELEN", "QA_CLAIRE",
            ],
            "duration_hours": 3.0,
            "facilitator": "PM_ALEX",
        },
    ],
    "run": [
        {
            "title": "Hypercare Review",
            "agenda": [
                "Incident summary since go-live",
                "Open defects and workarounds",
                "Performance metrics vs baselines",
                "User adoption indicators",
                "Hypercare exit criteria assessment",
                "Escalation items requiring management attention",
            ],
            "default_participants": [
                "PM_ALEX", "EXEC_VICTOR", "CUST_PM_OMAR", "IT_MGR_HELEN",
                "BASIS_KURT", "QA_CLAIRE",
            ],
            "duration_hours": 1.5,
            "facilitator": "PM_ALEX",
        },
        {
            "title": "Lessons Learned Session",
            "agenda": [
                "What went well (keep doing)",
                "What could have been better (change next time)",
                "Key risks that materialised vs those that didn't",
                "Team recognition and shout-outs",
                "Lessons to capture for future projects",
                "Knowledge transfer and BAU handover",
            ],
            "default_participants": [
                "PM_ALEX", "PMO_NIKO", "ARCH_SARA", "CHG_NADIA",
                "CUST_PM_OMAR", "EXEC_VICTOR", "QA_CLAIRE",
            ],
            "duration_hours": 2.0,
            "facilitator": "PMO_NIKO",
        },
        {
            "title": "Project Closure",
            "agenda": [
                "Final project report presentation",
                "Financial reconciliation overview",
                "Outstanding obligations and warranty period",
                "Contract closure confirmation",
                "Team disbanding and resource release",
                "Formal project closure sign-off",
            ],
            "default_participants": [
                "PM_ALEX", "EXEC_VICTOR", "CUST_PM_OMAR", "PMO_NIKO",
            ],
            "duration_hours": 1.5,
            "facilitator": "PM_ALEX",
        },
    ],
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Meeting:
    """Complete record of a simulation meeting (scheduled or organic).

    Attributes:
        id:               Unique meeting identifier (UUID4-based).
        type:             ``"scheduled"`` or ``"organic"``.
        title:            Human-readable meeting title.
        phase:            SAP Activate phase id when the meeting occurs.
        participants:     Codenames of all invited agents.
        agenda:           Ordered list of agenda items.
        status:           Current lifecycle status (MeetingStatus).
        scheduled_day:    Simulated project day on which the meeting is planned.
        actual_day:       Simulated day on which it actually ran (set on execute).
        duration_hours:   Planned duration in hours.
        log:              Turn-by-turn dialogue captured during execution.
                          Each entry: {codename, content, timestamp, turn_number}.
        decisions:        Key decisions captured during the meeting.
        action_items:     Follow-up tasks: {description, owner, due_phase}.
        facilitator:      Codename of the agent running the meeting.
        urgency:          Organic meetings only — ``"low"``/``"medium"``/``"high"``.
        requested_by:     Organic meetings only — codename of requesting agent.
        request_reason:   Organic meetings only — why the meeting was requested.
    """

    id: str = field(default_factory=lambda: f"MTG-{uuid.uuid4().hex[:8].upper()}")
    type: str = "scheduled"                # "scheduled" | "organic"
    title: str = ""
    phase: str = ""
    participants: list[str] = field(default_factory=list)
    agenda: list[str] = field(default_factory=list)
    status: str = MeetingStatus.PENDING.value
    scheduled_day: int = 0
    actual_day: Optional[int] = None
    duration_hours: float = 1.0
    log: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[dict[str, Any]] = field(default_factory=list)
    facilitator: str = "PM_ALEX"
    urgency: str = MeetingUrgency.MEDIUM.value    # only used for organic meetings
    requested_by: str = ""
    request_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict snapshot."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "phase": self.phase,
            "participants": self.participants,
            "agenda": self.agenda,
            "status": self.status,
            "scheduled_day": self.scheduled_day,
            "actual_day": self.actual_day,
            "duration_hours": self.duration_hours,
            "log": self.log,
            "decisions": self.decisions,
            "action_items": self.action_items,
            "facilitator": self.facilitator,
            "urgency": self.urgency,
            "requested_by": self.requested_by,
            "request_reason": self.request_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Meeting":
        """Reconstruct a Meeting from a serialised dict."""
        m = cls()
        for key, val in data.items():
            if hasattr(m, key):
                setattr(m, key, val)
        return m


# ---------------------------------------------------------------------------
# MeetingScheduler
# ---------------------------------------------------------------------------

class MeetingScheduler:
    """Hybrid scheduled + organic meeting manager for SAP SIM.

    Responsibilities:
    - Tracks which scheduled meetings remain for the current phase.
    - Maintains an organic meeting request queue.
    - On each simulation tick, decides whether to start a new meeting.
    - Orchestrates turn-based dialogue between participants via their
      ``generate_response()`` (or ``think()``) methods.
    - Persists structured Markdown logs to
      ``projects/{project_name}/meetings/``.

    Typical usage inside the Conductor's main loop::

        scheduler = MeetingScheduler(project_name, event_bus)
        scheduler.load_phase_meetings("discover")
        # ... each tick:
        await scheduler.tick(project_state, agents_dict)
    """

    # How many turns each participant gets per meeting (min/max)
    MIN_TURNS_PER_PARTICIPANT = 3
    MAX_TURNS_PER_PARTICIPANT = 8

    # Organic meeting: how many agents must independently request the same
    # topic before it is auto-approved (used when urgency < HIGH)
    ORGANIC_APPROVAL_THRESHOLD = 2

    # Delay in simulated ticks between scheduling and executing a meeting
    MEETING_RAMP_TICKS = 1

    def __init__(
        self,
        project_name: str,
        event_bus: "EventBus",
    ) -> None:
        """Initialise the scheduler for a project.

        Args:
            project_name: Unique project identifier (directory name).
            event_bus:    The project's EventBus for broadcasting events.
        """
        self.project_name = project_name
        self.event_bus = event_bus

        # Meetings scheduled for the current phase that haven't started yet
        self._pending_scheduled: list[Meeting] = []

        # Organic meeting request queue — any agent can push here
        self._organic_queue: list[Meeting] = []

        # Fully completed meeting IDs (avoid re-running)
        self._completed_ids: set[str] = set()

        # Topic → count of organic requests (for threshold logic)
        self._organic_topic_counts: dict[str, int] = {}

        # Meetings currently active (running concurrently is intentionally
        # NOT supported — meetings are sequential to keep dialogue coherent)
        self._active_meeting: Optional[Meeting] = None

        logger.info("[MeetingScheduler] Initialised for project '%s'", project_name)

    # -----------------------------------------------------------------------
    # Phase management
    # -----------------------------------------------------------------------

    def load_phase_meetings(self, phase_id: str) -> None:
        """Populate the pending-scheduled queue for a SAP Activate phase.

        Any previous pending meetings for the old phase are cleared.  Completed
        meeting IDs are preserved so the same meeting is never run twice.

        Args:
            phase_id: SAP Activate phase id (e.g. ``"explore"``).
        """
        phase_meeting_defs = SCHEDULED_MEETINGS.get(phase_id, [])
        self._pending_scheduled = []

        for defn in phase_meeting_defs:
            meeting = Meeting(
                type="scheduled",
                title=defn["title"],
                phase=phase_id,
                participants=list(defn.get("default_participants", [])),
                agenda=list(defn.get("agenda", [])),
                duration_hours=defn.get("duration_hours", 1.5),
                facilitator=defn.get("facilitator", "PM_ALEX"),
                status=MeetingStatus.PENDING.value,
            )
            self._pending_scheduled.append(meeting)

        logger.info(
            "[MeetingScheduler] Loaded %d scheduled meetings for phase '%s'",
            len(self._pending_scheduled), phase_id,
        )

    def get_meetings_for_phase(self, phase_id: str) -> list[Meeting]:
        """Return Meeting objects for all standard meetings in a given phase.

        These are freshly constructed from SCHEDULED_MEETINGS and do NOT carry
        any runtime state — use for inspection/planning only.

        Args:
            phase_id: SAP Activate phase identifier.

        Returns:
            List of Meeting instances (status=pending, no log).
        """
        meetings: list[Meeting] = []
        for defn in SCHEDULED_MEETINGS.get(phase_id, []):
            meetings.append(
                Meeting(
                    type="scheduled",
                    title=defn["title"],
                    phase=phase_id,
                    participants=list(defn.get("default_participants", [])),
                    agenda=list(defn.get("agenda", [])),
                    duration_hours=defn.get("duration_hours", 1.5),
                    facilitator=defn.get("facilitator", "PM_ALEX"),
                )
            )
        return meetings

    # -----------------------------------------------------------------------
    # Scheduling helpers
    # -----------------------------------------------------------------------

    def schedule_meeting(self, meeting: Meeting) -> None:
        """Add an already-constructed Meeting to the appropriate queue.

        Scheduled meetings go into ``_pending_scheduled``; organic ones
        go into ``_organic_queue``.

        Args:
            meeting: A Meeting instance to enqueue.
        """
        if meeting.type == "organic":
            self._organic_queue.append(meeting)
            # Track topic popularity for auto-approval logic
            topic_key = meeting.title.lower().strip()
            self._organic_topic_counts[topic_key] = (
                self._organic_topic_counts.get(topic_key, 0) + 1
            )
            logger.info(
                "[MeetingScheduler] Organic meeting enqueued: '%s' (urgency=%s, requested_by=%s)",
                meeting.title, meeting.urgency, meeting.requested_by,
            )
        else:
            self._pending_scheduled.append(meeting)
            logger.info(
                "[MeetingScheduler] Scheduled meeting enqueued: '%s' (phase=%s)",
                meeting.title, meeting.phase,
            )

    def trigger_organic_meeting(
        self,
        reason: str,
        participants: list[str],
        requested_by: str = "",
        title: str = "",
        agenda: Optional[list[str]] = None,
        urgency: str = MeetingUrgency.MEDIUM.value,
        facilitator: str = "PM_ALEX",
        phase: str = "",
    ) -> Meeting:
        """Create and enqueue an unplanned (organic) meeting.

        Organic meetings are auto-approved when urgency == HIGH or when the
        same topic has been requested ≥ ORGANIC_APPROVAL_THRESHOLD times.

        Args:
            reason:       The triggering reason (used as description + default title).
            participants: Codenames of required attendees.
            requested_by: Codename of the requesting agent.
            title:        Override title (defaults to a short form of *reason*).
            agenda:       Agenda items; defaults to a single item derived from *reason*.
            urgency:      ``"low"``/``"medium"``/``"high"``.
            facilitator:  Codename of the meeting facilitator.
            phase:        Phase id (defaults to whatever the scheduler sees as current).

        Returns:
            The newly created and enqueued Meeting.
        """
        if not title:
            # Truncate reason to a meeting-title length
            title = reason[:80].strip()

        meeting = Meeting(
            type="organic",
            title=title,
            phase=phase,
            participants=list(participants),
            agenda=agenda or [reason],
            duration_hours=1.0,
            facilitator=facilitator,
            urgency=urgency,
            requested_by=requested_by,
            request_reason=reason,
            status=MeetingStatus.PENDING.value,
        )

        self.schedule_meeting(meeting)
        return meeting

    # -----------------------------------------------------------------------
    # Tick — called each simulation step
    # -----------------------------------------------------------------------

    async def tick(
        self,
        state: "ProjectState",
        agents_dict: dict[str, "BaseAgent"],
    ) -> None:
        """Advance the meeting scheduler by one simulation tick.

        Logic:
        1. If a meeting is already active, return (meetings are sequential).
        2. Check scheduled meetings for the current phase — run the next one.
        3. If no scheduled meeting is pending, check the organic queue.
        4. Approved organic meetings (high urgency or threshold met) run next.

        Args:
            state:       Current project state (supplies simulated_day, phase).
            agents_dict: Dict mapping codename → BaseAgent instance.
        """
        if self._active_meeting is not None:
            # A meeting is running; wait for it to finish
            return

        current_phase = state.current_phase
        current_day = state.simulated_day

        # --- 1. Run next scheduled meeting for this phase ---
        next_scheduled = self._pick_next_scheduled(current_phase)
        if next_scheduled is not None:
            next_scheduled.scheduled_day = current_day
            next_scheduled.phase = current_phase
            await self._run_meeting(next_scheduled, state, agents_dict)
            return

        # --- 2. Run approved organic meeting ---
        approved_organic = self._pick_approved_organic()
        if approved_organic is not None:
            approved_organic.scheduled_day = current_day
            if not approved_organic.phase:
                approved_organic.phase = current_phase
            await self._run_meeting(approved_organic, state, agents_dict)

    def _pick_next_scheduled(self, phase_id: str) -> Optional[Meeting]:
        """Return (and remove) the next pending scheduled meeting for *phase_id*."""
        for i, meeting in enumerate(self._pending_scheduled):
            if meeting.phase == phase_id and meeting.id not in self._completed_ids:
                self._pending_scheduled.pop(i)
                return meeting
        return None

    def _pick_approved_organic(self) -> Optional[Meeting]:
        """Return (and remove) the next organic meeting that should run.

        Approval criteria:
        - urgency == HIGH → immediate approval
        - Same topic requested ≥ ORGANIC_APPROVAL_THRESHOLD times → approved
        """
        for i, meeting in enumerate(self._organic_queue):
            if meeting.id in self._completed_ids:
                self._organic_queue.pop(i)
                return None  # re-check from start

            is_high = meeting.urgency == MeetingUrgency.HIGH.value
            topic_count = self._organic_topic_counts.get(
                meeting.title.lower().strip(), 1
            )
            is_threshold = topic_count >= self.ORGANIC_APPROVAL_THRESHOLD

            if is_high or is_threshold:
                self._organic_queue.pop(i)
                return meeting

        return None

    # -----------------------------------------------------------------------
    # Meeting execution
    # -----------------------------------------------------------------------

    async def _run_meeting(
        self,
        meeting: Meeting,
        state: "ProjectState",
        agents_dict: dict[str, "BaseAgent"],
    ) -> None:
        """Orchestrate a full meeting from start to finish.

        Steps:
        1. Mark meeting as ACTIVE; publish MEETING_STARTED.
        2. Mark participant agents as in_meeting.
        3. Execute turn-based dialogue (facilitator opens, round-robin turns,
           facilitator closes).
        4. Extract decisions and action items from the transcript.
        5. Restore agent statuses; mark meeting COMPLETED.
        6. Save Markdown log; publish MEETING_ENDED; update project state.

        Args:
            meeting:     The meeting to run.
            state:       Current project state.
            agents_dict: Dict of available agents.
        """
        meeting.status = MeetingStatus.ACTIVE.value
        meeting.actual_day = state.simulated_day
        self._active_meeting = meeting

        # Resolve actual attendees (intersection with available agents)
        available_participants = [
            p for p in meeting.participants if p in agents_dict
        ]
        if not available_participants:
            logger.warning(
                "[MeetingScheduler] No available agents for meeting '%s' — cancelling.",
                meeting.title,
            )
            meeting.status = MeetingStatus.CANCELLED.value
            self._active_meeting = None
            return

        # Ensure facilitator is in the list
        facilitator = meeting.facilitator
        if facilitator not in agents_dict:
            facilitator = available_participants[0]
            meeting.facilitator = facilitator
        if facilitator not in available_participants:
            available_participants.insert(0, facilitator)

        logger.info(
            "[MeetingScheduler] Starting meeting '%s' (phase=%s, day=%d, %d participants)",
            meeting.title, meeting.phase, meeting.actual_day, len(available_participants),
        )

        # Publish MEETING_STARTED
        await self.event_bus.publish(
            "MEETING_STARTED",
            {
                "meeting_id": meeting.id,
                "title": meeting.title,
                "phase": meeting.phase,
                "participants": available_participants,
                "agenda": meeting.agenda,
                "facilitator": facilitator,
                "simulated_day": meeting.actual_day,
                "timestamp": time.time(),
            },
        )

        # Mark all participant agents as in_meeting
        for codename in available_participants:
            if codename in agents_dict:
                agents_dict[codename].status = "in_meeting"

        try:
            await self.execute_meeting(meeting, agents_dict)
        except Exception as exc:
            logger.error(
                "[MeetingScheduler] Error during meeting '%s': %s",
                meeting.title, exc,
            )
        finally:
            # Restore agent statuses
            for codename in available_participants:
                if codename in agents_dict:
                    agents_dict[codename].status = "idle"

            meeting.status = MeetingStatus.COMPLETED.value
            self._completed_ids.add(meeting.id)
            self._active_meeting = None

            # Publish MEETING_ENDED
            await self.event_bus.publish(
                "MEETING_ENDED",
                {
                    "meeting_id": meeting.id,
                    "title": meeting.title,
                    "phase": meeting.phase,
                    "participants": available_participants,
                    "decisions": meeting.decisions,
                    "action_items": meeting.action_items,
                    "turns": len(meeting.log),
                    "simulated_day": meeting.actual_day,
                    "timestamp": time.time(),
                },
            )

            # Persist the meeting log
            try:
                await self.save_meeting_log(meeting)
            except Exception as exc:
                logger.error(
                    "[MeetingScheduler] Failed to save log for '%s': %s",
                    meeting.title, exc,
                )

            logger.info(
                "[MeetingScheduler] Completed meeting '%s': %d turns, %d decisions, %d actions",
                meeting.title, len(meeting.log), len(meeting.decisions), len(meeting.action_items),
            )

    async def execute_meeting(
        self,
        meeting: Meeting,
        agents_dict: dict[str, "BaseAgent"],
    ) -> None:
        """Run the turn-based dialogue for a meeting.

        Turn order:
          1. Facilitator opens the meeting (intro + first agenda item).
          2. Each non-facilitator participant speaks in round-robin order.
             The number of rounds is proportional to the meeting's duration.
          3. Facilitator closes (summarises decisions, assigns action items).

        Each turn calls ``agent.generate_response(context)`` if available,
        otherwise falls back to ``agent.think(context)``.  This makes the
        method compatible with both the minimal BaseAgent interface and any
        richer role-specific overrides.

        Captured decisions (lines matching ``[DECISION]:`` or ``DECISION:`` prefix)
        and action items (``[ACTION]:`` or ``ACTION:`` prefix) are extracted from
        every turn and aggregated into ``meeting.decisions`` / ``meeting.action_items``.

        Args:
            meeting:     The active Meeting being run (mutated in-place).
            agents_dict: Dict mapping codename → BaseAgent.
        """
        available = [p for p in meeting.participants if p in agents_dict]
        if not available:
            return

        facilitator = meeting.facilitator
        non_facilitators = [p for p in available if p != facilitator]

        # Determine rounds: 1 round ≈ 0.5 h of meeting, clamped to [1, 3]
        rounds = min(3, max(1, int(meeting.duration_hours / 0.5)))

        # --- Opening turn (facilitator) ---
        opening_context = self._build_meeting_context(
            meeting=meeting,
            turn_type="opening",
            speaker=facilitator,
            prior_log=meeting.log,
            extra={
                "instruction": (
                    f"You are facilitating the '{meeting.title}' meeting. "
                    "Open the meeting: welcome attendees, state the objectives, "
                    "and introduce the first agenda item. Be crisp and professional."
                ),
            },
        )
        opening_response = await self._get_agent_response(
            agents_dict[facilitator], opening_context, meeting
        )
        self._record_turn(meeting, facilitator, opening_response, turn_type="opening")

        # --- Round-robin discussion turns ---
        for round_num in range(1, rounds + 1):
            for codename in non_facilitators:
                if codename not in agents_dict:
                    continue

                # Determine which agenda item this round covers
                agenda_idx = min(round_num - 1, len(meeting.agenda) - 1)
                current_agenda_item = meeting.agenda[agenda_idx] if meeting.agenda else "General discussion"

                context = self._build_meeting_context(
                    meeting=meeting,
                    turn_type="discussion",
                    speaker=codename,
                    prior_log=meeting.log,
                    extra={
                        "current_agenda_item": current_agenda_item,
                        "round": round_num,
                        "instruction": (
                            f"You are participating in the '{meeting.title}' meeting. "
                            f"Current agenda item: '{current_agenda_item}'. "
                            "Contribute your perspective. "
                            "If you have a decision to propose, prefix it with [DECISION]: "
                            "If you have an action item, prefix it with [ACTION]: <description> | owner: <codename>"
                        ),
                    },
                )
                response = await self._get_agent_response(
                    agents_dict[codename], context, meeting
                )
                self._record_turn(meeting, codename, response, turn_type="discussion")

            # Facilitator mid-meeting summary after each round (except opening)
            if round_num < rounds and facilitator in agents_dict:
                summary_context = self._build_meeting_context(
                    meeting=meeting,
                    turn_type="facilitation",
                    speaker=facilitator,
                    prior_log=meeting.log,
                    extra={
                        "instruction": (
                            f"Briefly summarise what was discussed in round {round_num} "
                            f"of the '{meeting.title}' meeting. "
                            "Acknowledge key points, note any emerging decisions, "
                            "and introduce the next agenda item."
                        ),
                    },
                )
                summary_response = await self._get_agent_response(
                    agents_dict[facilitator], summary_context, meeting
                )
                self._record_turn(meeting, facilitator, summary_response, turn_type="facilitation")

        # --- Closing turn (facilitator) ---
        closing_context = self._build_meeting_context(
            meeting=meeting,
            turn_type="closing",
            speaker=facilitator,
            prior_log=meeting.log,
            extra={
                "instruction": (
                    f"Close the '{meeting.title}' meeting. "
                    "Summarise ALL decisions made during this meeting — prefix each with [DECISION]: "
                    "List ALL action items — prefix each with [ACTION]: <description> | owner: <codename> | due_phase: <phase> "
                    "Thank attendees and formally close the meeting."
                ),
            },
        )
        closing_response = await self._get_agent_response(
            agents_dict.get(facilitator), closing_context, meeting
        )
        self._record_turn(meeting, facilitator, closing_response, turn_type="closing")

    # -----------------------------------------------------------------------
    # Internal helpers — agent responses
    # -----------------------------------------------------------------------

    async def _get_agent_response(
        self,
        agent: Optional["BaseAgent"],
        context: dict[str, Any],
        meeting: Meeting,
    ) -> str:
        """Call the agent's response method, preferring generate_response() if present.

        Falls back gracefully to think() if generate_response() is not defined,
        and returns a placeholder if the agent is unavailable.

        Args:
            agent:   The agent to call.
            context: Meeting context dict passed as the prompt.
            meeting: The active meeting (used for logging).

        Returns:
            The agent's text response.
        """
        if agent is None:
            return "[Agent unavailable — no response]"

        try:
            agent.status = "speaking"
            # Prefer generate_response() if the subclass provides it
            if hasattr(agent, "generate_response") and callable(agent.generate_response):
                response: str = await agent.generate_response(context)  # type: ignore[attr-defined]
            else:
                response = await agent.think(context)
            return response
        except Exception as exc:
            logger.error(
                "[MeetingScheduler] Agent %s failed to respond in meeting '%s': %s",
                agent.codename, meeting.title, exc,
            )
            return f"[{agent.codename} was unable to respond: {exc}]"
        finally:
            if agent.status == "speaking":
                agent.status = "in_meeting"

    # -----------------------------------------------------------------------
    # Internal helpers — context builders
    # -----------------------------------------------------------------------

    def _build_meeting_context(
        self,
        meeting: Meeting,
        turn_type: str,
        speaker: str,
        prior_log: list[dict[str, Any]],
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Build the context dict passed to an agent for a meeting turn.

        Args:
            meeting:    The active meeting.
            turn_type:  ``"opening"`` | ``"discussion"`` | ``"facilitation"`` | ``"closing"``.
            speaker:    Codename of the agent taking this turn.
            prior_log:  All prior turns recorded so far.
            extra:      Additional keys merged into the context.

        Returns:
            Context dict ready for ``agent.think(context)``.
        """
        # Format recent transcript (last 10 turns) to keep context manageable
        recent_transcript = prior_log[-10:] if prior_log else []
        transcript_text = "\n".join(
            f"**{t['codename']}** (turn {t['turn_number']}): {t['content'][:300]}"
            for t in recent_transcript
        )

        context: dict[str, Any] = {
            "meeting_id": meeting.id,
            "meeting_title": meeting.title,
            "phase": meeting.phase,
            "agenda": meeting.agenda,
            "participants": meeting.participants,
            "facilitator": meeting.facilitator,
            "turn_type": turn_type,
            "your_codename": speaker,
            "transcript_so_far": transcript_text,
            "decisions_so_far": meeting.decisions,
            "action_items_so_far": meeting.action_items,
        }

        if extra:
            context.update(extra)

        return context

    def _record_turn(
        self,
        meeting: Meeting,
        codename: str,
        content: str,
        turn_type: str = "discussion",
    ) -> None:
        """Append a turn to the meeting log and extract decisions/actions.

        Args:
            meeting:    The active meeting (mutated in-place).
            codename:   Speaker's codename.
            content:    The agent's response text.
            turn_type:  Turn classification for logging.
        """
        turn_number = len(meeting.log) + 1
        turn: dict[str, Any] = {
            "codename": codename,
            "content": content,
            "timestamp": time.time(),
            "turn_number": turn_number,
            "turn_type": turn_type,
        }
        meeting.log.append(turn)

        # Extract decisions
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("[DECISION]:") or stripped.upper().startswith("DECISION:"):
                decision_text = re.sub(r"^\[?DECISION\]?:\s*", "", stripped, flags=re.IGNORECASE).strip()
                if decision_text and decision_text not in meeting.decisions:
                    meeting.decisions.append(decision_text)

        # Extract action items
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("[ACTION]:") or stripped.upper().startswith("ACTION:"):
                action_text = re.sub(r"^\[?ACTION\]?:\s*", "", stripped, flags=re.IGNORECASE).strip()
                if action_text:
                    # Try to parse "description | owner: X | due_phase: Y"
                    action_item = self._parse_action_item(action_text, codename)
                    meeting.action_items.append(action_item)

    @staticmethod
    def _parse_action_item(raw: str, default_owner: str) -> dict[str, Any]:
        """Parse a raw action item string into a structured dict.

        Expected format (flexible):
            ``description | owner: CODENAME | due_phase: phase_id``

        Falls back gracefully if parts are missing.

        Args:
            raw:           Raw action text extracted from transcript.
            default_owner: Fallback owner if none found in the string.

        Returns:
            Dict: {description, owner, due_phase}
        """
        description = raw
        owner = default_owner
        due_phase = "realize"  # sensible default

        # Split on pipe
        parts = [p.strip() for p in raw.split("|")]
        if parts:
            description = parts[0]
        for part in parts[1:]:
            lower = part.lower()
            if lower.startswith("owner:"):
                owner = part.split(":", 1)[1].strip().upper()
            elif lower.startswith("due_phase:") or lower.startswith("due phase:"):
                due_phase = part.split(":", 1)[1].strip().lower()

        return {"description": description, "owner": owner, "due_phase": due_phase}

    # -----------------------------------------------------------------------
    # Meeting log persistence
    # -----------------------------------------------------------------------

    async def save_meeting_log(self, meeting: Meeting) -> None:
        """Persist a completed meeting as structured Markdown.

        Output path: ``projects/{project_name}/meetings/{id}_meeting.md``

        Format::

            # {title}
            **Phase**: {phase} | **Day**: {day} | **Facilitator**: {facilitator}
            **Participants**: {comma-separated codenames}

            ## Agenda
            1. ...

            ## Transcript
            **CODENAME** (turn N): ...

            ## Decisions Made
            1. ...

            ## Action Items
            | # | Description | Owner | Due Phase |
            ...

        Args:
            meeting: The completed Meeting to serialise.
        """
        meetings_dir = PROJECTS_BASE / self.project_name / "meetings"
        await aiofiles.os.makedirs(str(meetings_dir), exist_ok=True)

        filename = f"{meeting.id}_meeting.md"
        filepath = meetings_dir / filename

        lines: list[str] = []

        # --- Header ---
        lines.append(f"# {meeting.title}")
        lines.append("")
        lines.append(
            f"**Phase**: {meeting.phase.upper()} | "
            f"**Day**: {meeting.actual_day} | "
            f"**Facilitator**: {meeting.facilitator}"
        )
        if meeting.type == "organic":
            lines.append(
                f"**Type**: Organic | "
                f"**Urgency**: {meeting.urgency.upper()} | "
                f"**Requested by**: {meeting.requested_by}"
            )
            if meeting.request_reason:
                lines.append(f"**Reason**: {meeting.request_reason}")
        else:
            lines.append(f"**Type**: Scheduled")

        participants_str = ", ".join(meeting.participants)
        lines.append(f"**Participants**: {participants_str}")
        lines.append(f"**Duration (planned)**: {meeting.duration_hours}h")
        lines.append(f"**Status**: {meeting.status.upper()}")
        lines.append("")

        # --- Agenda ---
        lines.append("## Agenda")
        lines.append("")
        for idx, item in enumerate(meeting.agenda, start=1):
            lines.append(f"{idx}. {item}")
        lines.append("")

        # --- Transcript ---
        lines.append("## Transcript")
        lines.append("")
        for turn in meeting.log:
            codename = turn.get("codename", "?")
            turn_num = turn.get("turn_number", "?")
            content = turn.get("content", "")
            # Format timestamp as relative if available
            ts = turn.get("timestamp")
            ts_str = f" | ts: {ts:.0f}" if ts else ""
            lines.append(f"**{codename}** (turn {turn_num}{ts_str}):")
            lines.append("")
            # Indent the content block slightly for readability
            for content_line in content.splitlines():
                lines.append(f"> {content_line}" if content_line.strip() else ">")
            lines.append("")

        # --- Decisions ---
        lines.append("## Decisions Made")
        lines.append("")
        if meeting.decisions:
            for idx, decision in enumerate(meeting.decisions, start=1):
                lines.append(f"{idx}. {decision}")
        else:
            lines.append("_No formal decisions were recorded._")
        lines.append("")

        # --- Action Items ---
        lines.append("## Action Items")
        lines.append("")
        if meeting.action_items:
            lines.append("| # | Description | Owner | Due Phase |")
            lines.append("|---|---|---|---|")
            for idx, item in enumerate(meeting.action_items, start=1):
                desc = item.get("description", "")
                owner = item.get("owner", "")
                due = item.get("due_phase", "")
                lines.append(f"| {idx} | {desc} | {owner} | {due} |")
        else:
            lines.append("_No action items were recorded._")
        lines.append("")

        # --- Footer ---
        lines.append("---")
        lines.append(f"*Meeting ID: `{meeting.id}` — auto-generated by SAP SIM*")

        content_str = "\n".join(lines)

        async with aiofiles.open(str(filepath), "w", encoding="utf-8") as fh:
            await fh.write(content_str)

        logger.info(
            "[MeetingScheduler] Meeting log saved: %s",
            filepath,
        )

    # -----------------------------------------------------------------------
    # Introspection / state
    # -----------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        """Total number of pending meetings (scheduled + organic)."""
        return len(self._pending_scheduled) + len(self._organic_queue)

    @property
    def completed_count(self) -> int:
        """Number of meetings completed in this session."""
        return len(self._completed_ids)

    @property
    def active_meeting(self) -> Optional[Meeting]:
        """The currently executing meeting, or None."""
        return self._active_meeting

    def get_pending_organic(self) -> list[Meeting]:
        """Return a copy of the organic meeting queue."""
        return list(self._organic_queue)

    def get_pending_scheduled(self) -> list[Meeting]:
        """Return a copy of the pending scheduled meeting queue."""
        return list(self._pending_scheduled)

    def to_dict(self) -> dict[str, Any]:
        """Serialise scheduler state for project state snapshots."""
        return {
            "pending_scheduled": [m.to_dict() for m in self._pending_scheduled],
            "organic_queue": [m.to_dict() for m in self._organic_queue],
            "completed_ids": list(self._completed_ids),
            "active_meeting": self._active_meeting.to_dict() if self._active_meeting else None,
            "pending_count": self.pending_count,
            "completed_count": self.completed_count,
        }

    def __repr__(self) -> str:
        return (
            f"<MeetingScheduler project='{self.project_name}' "
            f"pending={self.pending_count} completed={self.completed_count} "
            f"active={self._active_meeting.title if self._active_meeting else None!r}>"
        )
