"""
SAP SIM — Phase Manager
Phase: 3.2
Purpose: SAP Activate phase progression, objectives, completion checks, and methodology loading.
         Manages transitions between Discover → Prepare → Explore → Realize → Deploy → Run.
Dependencies: simulation.state_machine, utils.persistence
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from simulation.state_machine import (
    PHASES,
    PHASES_BY_ID,
    ProjectState,
    save_state,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Projects base directory (resolved relative to backend package root)
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECTS_DIR = _BACKEND_DIR.parent / "projects"


# ---------------------------------------------------------------------------
# SAP Activate — hardcoded phase objectives
# (used when no custom methodology.md is provided)
# ---------------------------------------------------------------------------

_SAP_ACTIVATE_OBJECTIVES: dict[str, list[str]] = {
    "discover": [
        "Define project vision, goals, and success criteria",
        "Identify key stakeholders and obtain executive sponsorship",
        "Review SAP Best Practices and pre-configured solution content",
        "Assess organisational readiness and change impact",
        "Produce and sign the Project Charter",
        "Agree on project governance model and escalation path",
        "Confirm project scope boundaries (in-scope / out-of-scope modules)",
        "Conduct value discovery workshop with business owners",
    ],
    "prepare": [
        "Establish system landscape (DEV / QAS / PRD) and transport routes",
        "Set up project infrastructure: VPN, S-User IDs, SAP Support Portal access",
        "Onboard full project team and confirm RACI matrix",
        "Baseline and publish detailed project plan with phase milestones",
        "Configure project standards: naming conventions, object naming, change management tooling",
        "Establish project communication cadence (standup, weekly status, steering committee)",
        "Deploy SAP Activate accelerators and Best Practice content to DEV client",
        "Complete risk register and mitigation planning",
    ],
    "explore": [
        "Execute fit-to-standard workshops for all in-scope modules (FI, CO, MM, SD, PP, WM)",
        "Map current-state (AS-IS) business processes to SAP standard functionality",
        "Identify and document all gaps requiring configuration delta or RICEFW development",
        "Produce signed RICEFW inventory with effort estimates and priorities",
        "Capture business process master list (BPML) and obtain business owner sign-off",
        "Run integration design sessions and document all interface touchpoints",
        "Complete data migration scoping: objects, volumes, cleansing rules, source systems",
        "Define security and authorisation concept",
        "Produce solution blueprint document and obtain steering committee approval",
        "Agree on testing strategy (unit, integration, UAT, performance, regression)",
    ],
    "realize": [
        "Configure SAP system according to approved blueprint (IMG activities)",
        "Develop all approved RICEFW objects (Reports, Interfaces, Conversions, Enhancements, Forms, Workflows)",
        "Complete data migration programmes (LTMC / BAPI) and execute at least one dry run",
        "Execute unit testing for all configuration and custom development objects",
        "Perform integration testing cycles (at least two rounds) and resolve all Priority-1 defects",
        "Complete security role design, build SU24 authorisation objects, resolve SoD conflicts",
        "Conduct performance testing for critical transaction loads",
        "Complete technical documentation (functional specs, technical specs, test scripts)",
        "Obtain quality gate sign-off from QA_CLAIRE before exiting Realize",
        "Update cutover plan with sequenced steps, owners, and time estimates",
    ],
    "deploy": [
        "Execute User Acceptance Testing (UAT) with key users from each business area",
        "Resolve all open UAT defects; obtain business sign-off on UAT completion",
        "Conduct final cutover rehearsal (at least two dress rehearsals)",
        "Execute end-user training programme across all roles",
        "Complete go-live readiness checklist (technical, functional, operational)",
        "Finalise hypercare model: team roster, war room setup, escalation contacts",
        "Perform production system validation and system copy from QAS",
        "Obtain written go-live authorisation from EXEC_VICTOR and steering committee",
        "Execute cutover and go-live activities per approved cutover plan",
    ],
    "run": [
        "Monitor production system health and resolve go-live incidents (hypercare period)",
        "Support key users and end-users during initial production use",
        "Conduct formal lessons-learned session with full project team",
        "Produce and distribute project closure report",
        "Hand over system to BAU operations team with full documentation",
        "Archive all project artefacts to document management system",
        "Complete final financial reconciliation and project sign-off",
        "Celebrate project completion and recognise team contributions",
    ],
}


# ---------------------------------------------------------------------------
# SAP Activate — typical activities and deliverables per phase
# (used by load_methodology to return rich phase configs)
# ---------------------------------------------------------------------------

_PHASE_CONFIGS: dict[str, dict[str, Any]] = {
    "discover": {
        "typical_activities": [
            "Value discovery workshop",
            "Stakeholder mapping and RACI definition",
            "SAP Best Practices review and demo",
            "Business case validation",
            "Readiness assessment",
        ],
        "deliverables": [
            "Project Charter",
            "Stakeholder Register",
            "Scope Statement",
            "High-Level Project Plan",
            "Risk Register (initial)",
        ],
        "meeting_types": [
            "Kick-off Meeting",
            "Executive Alignment Session",
            "SAP Best Practices Demo",
            "Project Charter Review",
        ],
        "key_roles": [
            "PM_ALEX", "EXEC_VICTOR", "ARCH_SARA", "CUST_PM_OMAR", "PMO_NIKO",
        ],
        "success_criteria": [
            "Signed Project Charter",
            "Confirmed executive sponsorship",
            "Agreed scope boundaries",
        ],
    },
    "prepare": {
        "typical_activities": [
            "System landscape setup and baseline client configuration",
            "Transport management system (TMS) configuration",
            "Project team onboarding and tool access provisioning",
            "SAP Activate accelerator deployment",
            "Communication plan and reporting cadence establishment",
        ],
        "deliverables": [
            "System Landscape Document",
            "Project Plan (detailed)",
            "Team Onboarding Confirmation",
            "Communication Plan",
            "Initial Risk Log Update",
        ],
        "meeting_types": [
            "System Landscape Design Review",
            "Team Onboarding Session",
            "Methodology and Standards Workshop",
            "Kick-off with Full Project Team",
        ],
        "key_roles": [
            "BASIS_KURT", "IT_MGR_HELEN", "PM_ALEX", "ARCH_SARA", "PMO_NIKO",
        ],
        "success_criteria": [
            "DEV system available and accessible to all consultants",
            "All team members onboarded with S-User IDs",
            "Project plan baselined and shared",
        ],
    },
    "explore": {
        "typical_activities": [
            "Fit-to-standard (BBP) workshops per module — run in SAP standard system",
            "Business Process Master List (BPML) construction",
            "Gap analysis and RICEFW identification",
            "Data migration scoping and source system mapping",
            "Integration landscape design",
            "Security and authorisation concept definition",
            "Solution Blueprint authoring",
        ],
        "deliverables": [
            "Business Process Master List (BPML)",
            "Solution Blueprint",
            "RICEFW Inventory with estimates",
            "Integration Design Document",
            "Data Migration Scope Document",
            "Security Concept Document",
            "Testing Strategy",
        ],
        "meeting_types": [
            "Fit-to-Standard Workshop: FI/CO",
            "Fit-to-Standard Workshop: MM/SD",
            "Fit-to-Standard Workshop: PP/WM",
            "Integration Design Session",
            "Data Migration Scoping Workshop",
            "Security Design Workshop",
            "Blueprint Sign-off Session",
        ],
        "key_roles": [
            "FI_CHEN", "CO_MARTA", "MM_RAVI", "SD_ISLA", "PP_JONAS", "WM_FATIMA",
            "INT_MARCO", "SEC_DIANA", "DM_FELIX", "ARCH_SARA",
            "FI_KU_ROSE", "CO_KU_BJORN", "MM_KU_GRACE", "SD_KU_TONY",
        ],
        "success_criteria": [
            "BPML signed by business process owners",
            "Solution Blueprint approved by steering committee",
            "RICEFW inventory agreed with effort estimates",
        ],
    },
    "realize": {
        "typical_activities": [
            "IMG configuration per blueprint (enterprise structure, master data, process config)",
            "Custom ABAP development: BADIs, user exits, OData services, RICEFW objects",
            "Data migration programme development and dry runs (LTMC, BAPI, LSMW)",
            "Unit testing of all configuration and development objects",
            "Integration testing cycles — at least two full rounds",
            "Security role build, SU24 maintenance, SoD conflict resolution (GRC)",
            "Performance and load testing of critical transactions",
            "Sprint-based iterative build with regular sprint reviews",
            "Defect management via test management tool",
        ],
        "deliverables": [
            "Configured DEV and QAS systems",
            "All RICEFW objects (functional/technical specs + built + unit tested)",
            "Integration Test Results (rounds 1 and 2)",
            "Data Migration Dry Run Results",
            "Security Role Concept (approved)",
            "Updated Cutover Plan",
            "Test Scripts Library",
        ],
        "meeting_types": [
            "Sprint Review (biweekly)",
            "Integration Test Kick-off",
            "Data Migration Design Review",
            "Security Design Review",
            "Defect Triage Meeting",
            "Realize Phase Gate Review",
        ],
        "key_roles": [
            "DEV_PRIYA", "DEV_LEON", "FI_CHEN", "CO_MARTA", "MM_RAVI",
            "SD_ISLA", "PP_JONAS", "WM_FATIMA", "INT_MARCO", "SEC_DIANA",
            "DM_FELIX", "BI_SAM", "QA_CLAIRE",
            "BA_CUST_JAMES", "FI_KU_ROSE", "IT_MGR_HELEN",
        ],
        "success_criteria": [
            "All Priority-1 and Priority-2 integration defects resolved",
            "Data migration dry run pass rate ≥ 95%",
            "Security design approved by customer IT and audit",
            "Quality gate passed with QA_CLAIRE sign-off",
        ],
    },
    "deploy": {
        "typical_activities": [
            "User Acceptance Testing (UAT) — key users execute test scripts in QAS",
            "UAT defect resolution and re-test cycles",
            "Cutover rehearsals (minimum two dress rehearsals)",
            "End-user training delivery (role-based, classroom and e-learning)",
            "Go-live readiness checklist completion",
            "Production system preparation: system copy, authorisation transport",
            "Cutover execution: legacy system freeze, data loads, go-live validation",
            "Hypercare model preparation: war room, on-call rota, escalation contacts",
        ],
        "deliverables": [
            "UAT Sign-off Document",
            "Cutover Plan (final)",
            "Cutover Rehearsal Results",
            "Training Materials (role-based)",
            "Go-Live Readiness Checklist (all items green)",
            "Hypercare Plan",
            "Go-Live Authorisation from EXEC_VICTOR",
        ],
        "meeting_types": [
            "UAT Kick-off",
            "UAT Defect Triage",
            "Cutover Planning Workshop",
            "Go-Live Readiness Review",
            "Hypercare Preparation Session",
            "Final Steering Committee (go/no-go decision)",
        ],
        "key_roles": [
            "PM_ALEX", "CUST_PM_OMAR", "EXEC_VICTOR", "QA_CLAIRE",
            "DM_FELIX", "BASIS_KURT", "CHG_NADIA",
            "FI_KU_ROSE", "MM_KU_GRACE", "SD_KU_TONY", "CHAMP_LEILA",
        ],
        "success_criteria": [
            "UAT signed off by all business process owners",
            "Go/no-go decision confirmed by steering committee",
            "Cutover executed within approved window",
        ],
    },
    "run": {
        "typical_activities": [
            "Production support and hypercare monitoring (24×7 first two weeks)",
            "Incident triage and P1/P2 resolution",
            "Knowledge transfer to BAU operations team",
            "Lessons-learned facilitation",
            "Project closure activities: financials, artefact archiving, contract wrap-up",
            "System optimisation based on early usage patterns",
        ],
        "deliverables": [
            "Hypercare Report",
            "Lessons Learned Register",
            "Project Closure Report",
            "BAU Handover Documentation",
            "Final Financial Statement",
        ],
        "meeting_types": [
            "Daily Hypercare Stand-up",
            "Hypercare Review (weekly)",
            "Lessons Learned Session",
            "Project Closure Meeting",
        ],
        "key_roles": [
            "PM_ALEX", "EXEC_VICTOR", "PMO_NIKO", "BASIS_KURT",
            "IT_MGR_HELEN", "CHAMP_LEILA", "QA_CLAIRE",
        ],
        "success_criteria": [
            "No open P1 incidents at end of hypercare",
            "Lessons-learned session completed and report distributed",
            "Signed project closure document from EXEC_VICTOR",
        ],
    },
}

# ---------------------------------------------------------------------------
# Default methodology text (returned when no methodology.md exists)
# ---------------------------------------------------------------------------

_DEFAULT_METHODOLOGY_TEXT = """# SAP Activate Methodology

SAP Activate is SAP's prescriptive implementation methodology combining SAP Best Practices
(pre-configured content), guided configuration, and agile delivery principles.

## Phases

### Discover
Establish the business case, align stakeholders, and agree on project scope and success criteria.
Key artefact: Project Charter.

### Prepare
Set up the technical landscape, onboard the project team, and baseline the project plan.
Key artefacts: System Landscape Document, Detailed Project Plan.

### Explore
Run fit-to-standard workshops (BBP sessions) to map business processes to SAP standard.
Identify and log all gaps as RICEFW items. Produce the Solution Blueprint.
Key artefacts: BPML, Solution Blueprint, RICEFW Inventory.

### Realize
Configure and build the solution iteratively in sprints. Execute integration testing,
data migration dry runs, and security role build.
Key artefacts: Configured systems, test results, updated cutover plan.

### Deploy
Execute UAT, deliver end-user training, run cutover rehearsals, and go live.
Key artefacts: UAT Sign-off, Go-Live Readiness Checklist, Cutover Plan.

### Run
Provide hypercare support post go-live, conduct lessons learned, and hand over to BAU.
Key artefacts: Hypercare Report, Lessons Learned, Project Closure Report.
"""


# ---------------------------------------------------------------------------
# PhaseManager class
# ---------------------------------------------------------------------------

class PhaseManager:
    """Manages SAP Activate phase progression for a SAP SIM project.

    Responsibilities:
    - Determine the current phase from project state
    - Advance the simulation to the next phase
    - Return phase-specific objectives (from custom methodology or SAP Activate defaults)
    - Evaluate whether a phase is complete based on milestones and progress
    - Load and expose the full methodology configuration (phases, activities, deliverables)

    Usage::

        pm = PhaseManager(project_name="acme-s4-rollout")
        current = pm.get_current_phase(state)
        if pm.is_phase_complete(state, "explore"):
            state = await pm.advance_phase(state)
    """

    def __init__(self, project_name: str) -> None:
        """Initialise the PhaseManager.

        Args:
            project_name: Unique project identifier (used to locate methodology.md).
        """
        self.project_name = project_name
        self._methodology_cache: dict[str, Any] | None = None

    # -----------------------------------------------------------------------
    # Public API — phase inspection
    # -----------------------------------------------------------------------

    def get_current_phase(self, state: ProjectState) -> dict[str, Any]:
        """Return the full phase configuration for the project's active phase.

        Combines the static SAP Activate phase definition from state_machine with
        the richer activity/deliverable/meeting-type config from this module.

        Args:
            state: Current project state.

        Returns:
            A dict with keys: id, name, duration_days, description,
            typical_activities, deliverables, meeting_types, key_roles,
            success_criteria, progress (0–100), objectives (list[str]).
        """
        phase_id = state.current_phase
        base = PHASES_BY_ID.get(phase_id, PHASES_BY_ID["discover"])
        extra = _PHASE_CONFIGS.get(phase_id, {})

        return {
            **base,
            **extra,
            "progress": state.phase_progress.get(phase_id, 0.0),
            "objectives": self.get_phase_objectives(phase_id),
            "simulated_day_in_phase": self._day_within_phase(state),
        }

    def get_phase_objectives(self, phase_name: str) -> list[str]:
        """Return the list of objectives for the given phase.

        If the project has a custom ``methodology.md``, objectives are parsed from it
        under the matching phase heading.  Falls back to the hardcoded SAP Activate
        objectives when no custom file exists or the phase section is not found.

        Args:
            phase_name: Phase ID (e.g. ``"explore"``) or display name (e.g. ``"Explore"``).

        Returns:
            List of objective strings.
        """
        # Normalise to lowercase id form
        phase_id = phase_name.lower()
        if phase_id not in PHASES_BY_ID:
            # Try matching by display name
            for p in PHASES:
                if p["name"].lower() == phase_id:
                    phase_id = p["id"]
                    break
            else:
                logger.warning("Unknown phase name '%s', returning empty objectives.", phase_name)
                return []

        # Attempt to parse from custom methodology file
        custom_objectives = self._parse_objectives_from_methodology(phase_id)
        if custom_objectives:
            return custom_objectives

        # Fall back to SAP Activate defaults
        return list(_SAP_ACTIVATE_OBJECTIVES.get(phase_id, []))

    def is_phase_complete(self, state: ProjectState, phase_name: str | None = None) -> bool:
        """Determine whether a phase is complete.

        Completion is assessed on three criteria (all must pass):

        1. **Progress threshold** — ``phase_progress`` for the phase must be ≥ 90%.
        2. **Milestone completion** — all milestones belonging to the phase are marked done.
        3. **Phase duration** — the simulated day has reached or exceeded the planned end day
           for the phase.

        Criterion 3 uses a *soft* check: if progress and milestones are satisfied, the phase
        is considered complete even if slightly ahead of schedule.  This prevents the
        simulation from stalling on simulated-day accounting.

        Args:
            state:       Current project state.
            phase_name:  Phase to evaluate.  Defaults to ``state.current_phase``.

        Returns:
            True if the phase should be considered complete.
        """
        phase_id = (phase_name or state.current_phase).lower()
        if phase_id not in PHASES_BY_ID:
            logger.warning("is_phase_complete called with unknown phase '%s'.", phase_id)
            return False

        # 1. Progress threshold
        progress = state.phase_progress.get(phase_id, 0.0)
        if progress < 90.0:
            logger.debug(
                "Phase '%s' not complete: progress %.1f%% < 90%%.", phase_id, progress
            )
            return False

        # 2. Milestone completion
        phase_milestones = [m for m in state.milestones if m.get("phase") == phase_id]
        incomplete = [m for m in phase_milestones if not m.get("completed", False)]
        if incomplete:
            names = [m["name"] for m in incomplete]
            logger.debug(
                "Phase '%s' not complete: %d milestone(s) pending: %s",
                phase_id, len(incomplete), names,
            )
            return False

        # 3. Simulated duration (soft) — we check that we've passed the phase start day
        phase_start_day = self._phase_start_day(phase_id)
        phase_info = PHASES_BY_ID[phase_id]
        planned_end = phase_start_day + phase_info["duration_days"]

        # Allow early completion if progress and milestones are met but day is close (>= 80% of planned)
        soft_threshold = phase_start_day + int(phase_info["duration_days"] * 0.8)
        if state.simulated_day < soft_threshold:
            logger.debug(
                "Phase '%s' not complete: simulated_day %d < soft threshold %d.",
                phase_id, state.simulated_day, soft_threshold,
            )
            return False

        logger.info(
            "Phase '%s' complete: progress=%.1f%%, milestones=%d/%d, day=%d (planned_end=%d).",
            phase_id, progress, len(phase_milestones), len(phase_milestones),
            state.simulated_day, planned_end,
        )
        return True

    # -----------------------------------------------------------------------
    # Public API — phase transitions
    # -----------------------------------------------------------------------

    async def advance_phase(self, state: ProjectState) -> ProjectState:
        """Transition the project to the next SAP Activate phase.

        Steps performed:
        1. Mark the current phase progress as 100%.
        2. Determine the next phase in the SAP Activate sequence.
        3. If there is a next phase, call ``state.set_phase()`` to transition.
        4. If there is no next phase (Run is complete), mark the project COMPLETED.
        5. Persist the updated state.

        Args:
            state: Current project state (mutated in place).

        Returns:
            The updated :class:`~simulation.state_machine.ProjectState`.
        """
        current_id = state.current_phase
        state.update_phase_progress(current_id, 100.0)

        next_phase = state.next_phase
        if next_phase is None:
            # Completed the last phase (Run)
            logger.info(
                "Project '%s' completed all SAP Activate phases.", state.project_name
            )
            state.transition_status("COMPLETED")
        else:
            logger.info(
                "Project '%s' advancing: %s → %s (day %d).",
                state.project_name, current_id, next_phase["id"], state.simulated_day,
            )
            state.set_phase(next_phase["id"])

        # Invalidate methodology cache so the next phase picks up fresh config
        self._methodology_cache = None

        await save_state(state)
        return state

    # -----------------------------------------------------------------------
    # Public API — methodology loading
    # -----------------------------------------------------------------------

    def load_methodology(self) -> dict[str, Any]:
        """Return the full methodology configuration.

        If a ``methodology.md`` file exists at
        ``projects/{project_name}/methodology.md``, it is read and stored
        alongside the static phase configs.  Otherwise the SAP Activate default
        content is used.

        The returned dict has the following top-level structure::

            {
                "name": "SAP Activate" | "<custom name>",
                "source": "default" | "custom",
                "raw_text": "<full methodology markdown>",
                "phases": {
                    "<phase_id>": {
                        "id", "name", "duration_days", "description",
                        "typical_activities", "deliverables", "meeting_types",
                        "key_roles", "success_criteria", "objectives"
                    },
                    ...
                }
            }

        The result is cached for the lifetime of this :class:`PhaseManager` instance.

        Returns:
            Full methodology configuration dict.
        """
        if self._methodology_cache is not None:
            return self._methodology_cache

        raw_text, source = self._read_methodology_file()

        phases_out: dict[str, dict[str, Any]] = {}
        for phase in PHASES:
            pid = phase["id"]
            phases_out[pid] = {
                **phase,
                **_PHASE_CONFIGS.get(pid, {}),
                "objectives": self.get_phase_objectives(pid),
            }

        methodology_name = "SAP Activate"
        if source == "custom":
            # Try to extract a name from the first heading of the custom file
            for line in raw_text.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    methodology_name = line.lstrip("# ").strip()
                    break

        self._methodology_cache = {
            "name": methodology_name,
            "source": source,
            "raw_text": raw_text,
            "phases": phases_out,
        }
        logger.info(
            "Methodology loaded for project '%s': '%s' (source=%s).",
            self.project_name, methodology_name, source,
        )
        return self._methodology_cache

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _read_methodology_file(self) -> tuple[str, str]:
        """Read ``methodology.md`` for the project.

        Returns:
            Tuple of (text, source) where source is ``"custom"`` or ``"default"``.
        """
        methodology_path = _PROJECTS_DIR / self.project_name / "methodology.md"
        if methodology_path.exists():
            try:
                text = methodology_path.read_text(encoding="utf-8")
                logger.debug(
                    "Loaded custom methodology from '%s'.", methodology_path
                )
                return text, "custom"
            except OSError as exc:
                logger.warning(
                    "Could not read methodology.md for '%s': %s. Using default.",
                    self.project_name, exc,
                )
        return _DEFAULT_METHODOLOGY_TEXT, "default"

    def _parse_objectives_from_methodology(self, phase_id: str) -> list[str]:
        """Parse phase objectives from a custom methodology.md file.

        Looks for a heading matching the phase display name (e.g. ``## Explore``)
        and collects bullet-point lines (``-`` or ``*`` prefixed) until the next heading.

        Args:
            phase_id: Lowercase phase ID.

        Returns:
            List of objective strings, or empty list if not found / no custom file.
        """
        raw_text, source = self._read_methodology_file()
        if source != "custom":
            return []

        phase_display = PHASES_BY_ID[phase_id]["name"]  # e.g. "Explore"
        objectives: list[str] = []
        inside_phase = False

        for line in raw_text.splitlines():
            stripped = line.strip()

            # Detect phase section heading (## Explore or ### Explore)
            if stripped.lstrip("#").strip().lower() == phase_display.lower() and stripped.startswith("#"):
                inside_phase = True
                continue

            # Stop at the next heading of same or higher level
            if inside_phase and stripped.startswith("#"):
                break

            # Collect bullet-point objectives
            if inside_phase and (stripped.startswith("- ") or stripped.startswith("* ")):
                obj = stripped[2:].strip()
                if obj:
                    objectives.append(obj)

        return objectives

    def _phase_start_day(self, phase_id: str) -> int:
        """Calculate the planned start day (simulated) for a given phase.

        Args:
            phase_id: Lowercase phase ID.

        Returns:
            The cumulative simulated day on which the phase begins.
        """
        start = 0
        for phase in PHASES:
            if phase["id"] == phase_id:
                return start
            start += phase["duration_days"]
        return 0

    def _day_within_phase(self, state: ProjectState) -> int:
        """Return how many simulated days have elapsed within the current phase.

        Args:
            state: Current project state.

        Returns:
            Days elapsed since the phase start (0-indexed).
        """
        phase_start = self._phase_start_day(state.current_phase)
        return max(0, state.simulated_day - phase_start)
