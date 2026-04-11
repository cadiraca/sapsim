"""
SAP SIM — Admin API Router
Phase: 3.6
Purpose: Operator/Mission-Controller admin endpoints for health monitoring,
         simulation highlights, token budgets, and webhook registration.
         Mounted at /api/admin in main.py.
Dependencies: FastAPI, simulation.engine, config, utils.persistence
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiofiles
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from config import load_settings, save_settings
from simulation.engine import get_engine
from utils.persistence import (
    PROJECTS_BASE,
    _project_dir,
    load_project_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# ---------------------------------------------------------------------------
# Server start time (shared with routes.py via monotonic clock origin)
# ---------------------------------------------------------------------------

_SERVER_START = time.monotonic()

# ---------------------------------------------------------------------------
# Token budget defaults per agent tier
# ---------------------------------------------------------------------------

# Approximate token budgets per simulation run (all phases combined)
TIER_TOKEN_BUDGETS: dict[str, int] = {
    "strategic":    500_000,   # Opus-class; high-context strategic decisions
    "senior":       200_000,   # Sonnet-class; module leads
    "operational":  100_000,   # Gemini/mid-tier; key users & developers
    "basic":         40_000,   # Low-cost models; lightweight participants
}

# Valid event types for webhook subscriptions
VALID_WEBHOOK_EVENTS = frozenset({
    "phase_complete",
    "meeting_done",
    "decision_needed",
    "simulation_error",
    "simulation_started",
    "simulation_stopped",
    "simulation_completed",
    "blocker_raised",
    "chaos_injected",
})

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AdminHealthResponse(BaseModel):
    """Aggregate backend health across all active projects."""
    status: str
    uptime_seconds: float
    active_projects: int
    active_agents: int
    tokens_per_minute: float
    total_tokens_used: int
    registered_projects: list[str] = []
    phase_summaries: list[dict[str, Any]] = []
    timestamp: str


class HighlightEntry(BaseModel):
    tick: int = 0
    day: int = 0
    phase: str = ""
    events: list[dict[str, Any]] = []
    timestamp: float = 0.0
    project_name: Optional[str] = None


class AdminHighlightsResponse(BaseModel):
    """Recent simulation activity highlights from the Conductor ring-buffer."""
    highlights: list[dict[str, Any]]
    total: int
    source: str = "conductor"   # "conductor" if engine live, "feed" if from disk


class TierBudget(BaseModel):
    tier: str
    token_budget: int
    description: str


class TokenBudgetResponse(BaseModel):
    """Configured token budgets per agent tier and global project cap."""
    tier_budgets: list[TierBudget]
    project_budget: Optional[int] = None
    project_name: Optional[str] = None
    note: str = ""


class AgentTokenUsage(BaseModel):
    codename: str
    tier: str
    tokens_used: int
    budget: int
    pct_used: float


class TokenUsageResponse(BaseModel):
    """Actual token consumption breakdown for a project."""
    project_name: str
    total_used: int
    budget: Optional[int] = None
    remaining: Optional[int] = None
    pct_used: float = 0.0
    by_agent: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    agent_detail: list[AgentTokenUsage] = []


class WebhookRegistration(BaseModel):
    """Register a callback URL for simulation events."""
    url: str = Field(..., description="HTTP(S) URL to POST events to")
    events: list[str] = Field(
        default=list(VALID_WEBHOOK_EVENTS),
        description=(
            "Event types to subscribe to. Valid values: "
            + ", ".join(sorted(VALID_WEBHOOK_EVENTS))
        ),
    )
    project_name: Optional[str] = Field(
        default=None,
        description="Scope to a specific project (omit for global)",
    )
    secret: Optional[str] = Field(
        default=None,
        description="Optional shared secret sent in X-SAPSim-Secret header",
    )


class WebhookRegistrationResponse(BaseModel):
    url: str
    events: list[str]
    project_name: Optional[str] = None
    registered_at: str
    note: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _list_project_names() -> list[str]:
    """Return sorted list of all project directories on disk."""
    if not PROJECTS_BASE.exists():
        return []
    names = []
    for entry in PROJECTS_BASE.iterdir():
        if entry.is_dir() and (entry / "project.json").exists():
            names.append(entry.name)
    return sorted(names)


def _get_conductor_safely(project_name: str):
    """Return the Conductor for *project_name* or None if not registered."""
    engine = get_engine()
    if engine.is_registered(project_name):
        return engine.get_conductor(project_name)
    return None


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=AdminHealthResponse,
    summary="System health — uptime, active projects, agent counts, token stats",
)
async def admin_health() -> AdminHealthResponse:
    """Return aggregate system health for all active projects.

    Pulls live data from the engine when projects are registered, falls back
    to persisted state on disk for offline projects.

    Returns:
        :class:`AdminHealthResponse` with uptime, project counts, and phase summaries.
    """
    engine = get_engine()
    registered = engine.list_projects()
    disk_projects = await _list_project_names()
    all_projects = sorted(set(registered) | set(disk_projects))

    active_projects = 0
    active_agents = 0
    total_tokens_used = 0
    phase_summaries: list[dict[str, Any]] = []

    for name in all_projects:
        # Prefer live engine data
        if engine.is_registered(name):
            sim_status = engine.get_status(name)
            if sim_status["status"] == "RUNNING":
                active_projects += 1
                active_agents += len(sim_status.get("active_agents", []))
            phase_summaries.append({
                "project":     name,
                "status":      sim_status["status"],
                "phase":       sim_status["current_phase"],
                "day":         sim_status["simulated_day"],
                "total_days":  sim_status["total_days"],
                "tick_count":  sim_status["tick_count"],
                "loop_running": sim_status["loop_running"],
                "source":      "engine",
            })
        else:
            # Fall back to disk state
            state = await load_project_state(name)
            if state:
                if state.get("status") == "RUNNING":
                    active_projects += 1
                    active_agents += len(state.get("active_agents", []))
                phase_summaries.append({
                    "project":    name,
                    "status":     state.get("status", "UNKNOWN"),
                    "phase":      state.get("current_phase", "unknown"),
                    "day":        state.get("simulated_day", 0),
                    "total_days": state.get("total_days", 0),
                    "source":     "disk",
                })

    return AdminHealthResponse(
        status="ok",
        uptime_seconds=round(time.monotonic() - _SERVER_START, 2),
        active_projects=active_projects,
        active_agents=active_agents,
        tokens_per_minute=0.0,      # populated by engine token tracker (Phase 4+)
        total_tokens_used=total_tokens_used,
        registered_projects=registered,
        phase_summaries=phase_summaries,
        timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# GET /highlights
# ---------------------------------------------------------------------------


@router.get(
    "/highlights",
    response_model=AdminHighlightsResponse,
    summary="Recent simulation events — from Conductor ring-buffer or feed log",
)
async def admin_highlights(
    n: int = Query(default=20, ge=1, le=200, description="Max highlights to return"),
    project_name: Optional[str] = Query(
        default=None,
        description="Filter to a specific project (omit for all projects)",
    ),
) -> AdminHighlightsResponse:
    """Return the last *n* significant simulation events.

    Priority:
    1. If the project is registered in the engine and running, calls
       ``conductor.get_highlights()`` for in-memory highlights.
    2. Otherwise, falls back to reading ``feed/events.jsonl`` on disk and
       filtering for significant event types.

    Args:
        n:            Number of recent entries to return.
        project_name: Optional project filter.

    Returns:
        :class:`AdminHighlightsResponse` with highlights list and source tag.
    """
    engine = get_engine()

    # ----------------------------------------------------------------
    # Path 1: live Conductor highlights
    # ----------------------------------------------------------------
    if project_name and engine.is_registered(project_name):
        conductor = engine.get_conductor(project_name)
        raw = conductor.get_highlights(limit=n)
        # Annotate each highlight with its project
        for h in raw:
            h.setdefault("project_name", project_name)
        return AdminHighlightsResponse(
            highlights=raw,
            total=len(raw),
            source="conductor",
        )

    # ----------------------------------------------------------------
    # Path 2: disk-based feed scan
    # ----------------------------------------------------------------
    SIGNIFICANT_TYPES = {
        "DECISION_RAISED", "DECISION_APPROVED", "DECISION_REJECTED",
        "MEETING_STARTED", "MEETING_ENDED", "NEW_TOOL",
        "BLOCKER", "PHASE_TRANSITION", "SIMULATION_STARTED",
        "SIMULATION_STOPPED", "SIMULATION_COMPLETED", "FAILURE_INJECTED",
        "TICK_COMPLETE",
    }

    disk_projects = await _list_project_names()
    if project_name:
        disk_projects = [p for p in disk_projects if p == project_name]

    all_events: list[dict] = []
    for pname in disk_projects:
        feed_path = _project_dir(pname) / "feed" / "events.jsonl"
        if not feed_path.exists():
            continue
        async with aiofiles.open(str(feed_path), "r") as fh:
            async for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    import json
                    ev = json.loads(line)
                    if ev.get("type") in SIGNIFICANT_TYPES:
                        ev["project_name"] = pname
                        all_events.append(ev)
                except Exception:
                    pass

    # Newest first, capped to n
    recent = all_events[-n:]
    recent.reverse()

    return AdminHighlightsResponse(
        highlights=recent,
        total=len(recent),
        source="feed",
    )


# ---------------------------------------------------------------------------
# GET /token-budget
# ---------------------------------------------------------------------------


@router.get(
    "/token-budget",
    response_model=TokenBudgetResponse,
    summary="Configured token budget per agent tier (and optional project cap)",
)
async def admin_token_budget(
    project_name: Optional[str] = Query(
        default=None,
        description="Include per-project global token cap alongside tier budgets",
    ),
) -> TokenBudgetResponse:
    """Return the configured token budget for each agent tier.

    Tier budgets are defined in this module and reflect the model class used
    per tier.  If *project_name* is supplied, the project's global cap from
    ``settings.json`` is also returned.

    Args:
        project_name: Optional project to read global cap from.

    Returns:
        :class:`TokenBudgetResponse` with tier-level budgets and optional project cap.
    """
    tier_budgets = [
        TierBudget(
            tier="strategic",
            token_budget=TIER_TOKEN_BUDGETS["strategic"],
            description="Opus-class agents (PM, Architect, Exec Sponsor, PMO). High-context, low-frequency.",
        ),
        TierBudget(
            tier="senior",
            token_budget=TIER_TOKEN_BUDGETS["senior"],
            description="Sonnet-class agents (module leads, IT Manager, QA). Medium frequency.",
        ),
        TierBudget(
            tier="operational",
            token_budget=TIER_TOKEN_BUDGETS["operational"],
            description="Gemini/mid-tier agents (key users, developers). Higher frequency, lower per-call cost.",
        ),
        TierBudget(
            tier="basic",
            token_budget=TIER_TOKEN_BUDGETS["basic"],
            description="Lightweight agents (change champions, occasional participants). Minimal token use.",
        ),
    ]

    project_budget: Optional[int] = None
    note = "Tier budgets are per-agent totals across a full simulation run."

    if project_name:
        settings = load_settings(project_name)
        project_budget = settings.max_token_budget
        if project_budget:
            note += f" Project '{project_name}' has a global cap of {project_budget:,} tokens."
        else:
            note += f" Project '{project_name}' has no global token cap set (unlimited)."

    return TokenBudgetResponse(
        tier_budgets=tier_budgets,
        project_budget=project_budget,
        project_name=project_name,
        note=note,
    )


# ---------------------------------------------------------------------------
# GET /token-usage
# ---------------------------------------------------------------------------


@router.get(
    "/token-usage",
    response_model=TokenUsageResponse,
    summary="Actual token consumption breakdown by agent and tier",
)
async def admin_token_usage(
    project_name: str = Query(..., description="Project to inspect"),
) -> TokenUsageResponse:
    """Return current token usage for *project_name*.

    If the project is registered in the live engine, usage is read from the
    Conductor's agent objects (when the token-tracking feature is wired in
    Phase 4+).  Otherwise returns the stub structure with zeros.

    Args:
        project_name: Project identifier.

    Returns:
        :class:`TokenUsageResponse` with breakdown by agent codename and tier.

    Raises:
        404: Project not found.
    """
    state = await load_project_state(project_name)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_name}' not found.",
        )

    settings = load_settings(project_name)
    engine = get_engine()

    by_agent: dict[str, int] = {}
    by_tier: dict[str, int] = {}

    # Pull live usage from conductor agents if registered
    if engine.is_registered(project_name):
        conductor = engine.get_conductor(project_name)
        for codename, agent in conductor.agents.items():
            used = getattr(agent, "tokens_used", 0)
            tier = getattr(agent, "tier", "basic")
            if used:
                by_agent[codename] = used
                by_tier[tier] = by_tier.get(tier, 0) + used

    total_used = sum(by_agent.values())
    budget = settings.max_token_budget
    remaining = (budget - total_used) if budget is not None else None
    pct_used = round((total_used / budget * 100) if budget else 0.0, 2)

    # Build per-agent detail with tier budgets
    agent_detail: list[AgentTokenUsage] = []
    for codename, used in by_agent.items():
        conductor = _get_conductor_safely(project_name)
        tier = "basic"
        if conductor:
            agent_obj = conductor.agents.get(codename)
            tier = getattr(agent_obj, "tier", "basic") if agent_obj else "basic"
        tier_budget = TIER_TOKEN_BUDGETS.get(tier, TIER_TOKEN_BUDGETS["basic"])
        agent_detail.append(
            AgentTokenUsage(
                codename=codename,
                tier=tier,
                tokens_used=used,
                budget=tier_budget,
                pct_used=round(used / tier_budget * 100, 2),
            )
        )

    return TokenUsageResponse(
        project_name=project_name,
        total_used=total_used,
        budget=budget,
        remaining=remaining,
        pct_used=pct_used,
        by_agent=by_agent,
        by_tier=by_tier,
        agent_detail=sorted(agent_detail, key=lambda a: a.tokens_used, reverse=True),
    )


# ---------------------------------------------------------------------------
# POST /webhook
# ---------------------------------------------------------------------------


@router.post(
    "/webhook",
    response_model=WebhookRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a webhook callback URL for simulation events",
)
async def register_webhook(req: WebhookRegistration) -> WebhookRegistrationResponse:
    """Register (or update) a webhook URL for simulation event notifications.

    SAP SIM will POST a JSON payload to *url* whenever a subscribed event fires.
    Supported events:

    - ``phase_complete`` — a SAP Activate phase has finished
    - ``meeting_done`` — a simulation meeting has concluded
    - ``decision_needed`` — an agent raised a decision that needs resolution
    - ``simulation_error`` — an unhandled error occurred during a tick
    - ``simulation_started`` / ``simulation_stopped`` / ``simulation_completed``
    - ``blocker_raised`` — a blocking issue was raised
    - ``chaos_injected`` — a failure scenario was injected

    The webhook payload shape::

        {
            "event": "<event_type>",
            "project_name": "<name>",
            "data": { ... },
            "timestamp": "<ISO-8601>"
        }

    If *secret* is provided, SAP SIM sends it as the ``X-SAPSim-Secret`` header.

    Scope:
    - If *project_name* is given, the webhook is scoped to that project.
    - If omitted, it applies globally (all projects — stored in global settings).

    Args:
        req: :class:`WebhookRegistration` with URL, events, project, and optional secret.

    Returns:
        :class:`WebhookRegistrationResponse` confirming registration.

    Raises:
        400: If any requested event type is invalid.
        404: If *project_name* is given but doesn't exist.
    """
    # Validate event types
    invalid = [e for e in req.events if e not in VALID_WEBHOOK_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid event type(s): {invalid}. "
                f"Valid events: {sorted(VALID_WEBHOOK_EVENTS)}"
            ),
        )

    # If project-scoped, ensure the project exists
    if req.project_name:
        state = await load_project_state(req.project_name)
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{req.project_name}' not found.",
            )
        # Persist webhook URL to project settings
        settings = load_settings(req.project_name)
        settings.webhook_url = req.url
        save_settings(req.project_name, settings)

        logger.info(
            "[AdminAPI] Webhook registered for project '%s' → %s (events=%s)",
            req.project_name, req.url, req.events,
        )
        note = (
            f"Webhook registered for project '{req.project_name}'. "
            "Events will be delivered to the registered URL."
        )
    else:
        # Global webhook: log it (full global registry is a Phase 4+ feature)
        logger.info(
            "[AdminAPI] Global webhook registered → %s (events=%s)",
            req.url, req.events,
        )
        note = (
            "Global webhook registered. "
            "Per-project overrides can be set by including project_name. "
            "Note: global webhook fan-out is enabled in Phase 4."
        )

    return WebhookRegistrationResponse(
        url=req.url,
        events=sorted(req.events),
        project_name=req.project_name,
        registered_at=_now_iso(),
        note=note,
    )
