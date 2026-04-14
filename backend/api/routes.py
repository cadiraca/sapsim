"""
SAP SIM — API Routes (Phase 5.1 — Pydantic Models + Wired Engine)
Phase: 5.1
Purpose: All FastAPI endpoints for project management, simulation control,
         settings, live feed, agents, artifacts, stakeholder view, and admin.
         Simulation control routes call the real SimulationEngine singleton.
         Artifact routes use real DecisionBoard / ToolRegistry / LessonsCollector /
         TestStrategy objects for live data access.
Dependencies: FastAPI, Pydantic v2, config, utils.persistence, api.sse,
              simulation.engine, artifacts.*
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import aiofiles
import aiofiles.os
from fastapi import APIRouter, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from api.models import (
    AdminHealthResponse,
    AdminHighlightsResponse,
    AgentDetailResponse,
    AgentPersonality,
    AgentResponse,
    ArtifactReportRequest,
    ArtifactResponse,
    CreateProjectRequest,
    DecisionResponse,
    FeedPageResponse,
    LessonEntry,
    LessonResponse,
    MeetingDetailResponse,
    MeetingResponse,
    PhaseProgress,
    ProjectListResponse,
    ProjectResponse,
    ProposeDecisionRequest,
    RerollRequest,
    SettingsResponse,
    SettingsUpdateRequest,
    SimulationStatusResponse,
    StakeholderView,
    StartSimulationRequest,
    TestCaseResponse,
    TestSettingsRequest,
    TestSettingsResponse,
    TokenBudgetRequest,
    TokenUsageResponse,
    ToolResponse,
)
from api.sse import get_bus
from config import ProjectSettings, load_settings, save_settings
from simulation.engine import get_engine
from utils.persistence import (
    PROJECTS_BASE,
    _ensure_dir,
    _project_dir,
    append_feed_event,
    count_feed_events,
    delete_project_state,
    get_feed_events,
    list_project_names,
    load_project_state,
    save_project_state,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Artifact factory helpers (lazy-import to avoid circular deps at module load)
# ---------------------------------------------------------------------------

def _get_decision_board(project_name: str):
    from artifacts.decision_board import DecisionBoard as ArtifactDecisionBoard
    # BUG-001 FIX: DecisionBoard.__init__ does not accept 'projects_root'; removed.
    return ArtifactDecisionBoard(project_name=project_name)


def _get_tool_registry(project_name: str):
    from artifacts.tool_registry import ToolRegistry
    return ToolRegistry(project_name=project_name)


def _get_lessons_collector(project_name: str):
    from artifacts.lessons_learned import LessonsCollector
    # BUG-008 FIX: LessonsCollector has no .load() classmethod; just instantiate directly.
    return LessonsCollector(project_name)


def _get_test_strategy(project_name: str):
    from artifacts.test_strategy import TestStrategy
    # BUG-009 FIX: TestStrategy has no .load() classmethod; just instantiate directly.
    return TestStrategy(project_name)


def _get_meeting_logger(project_name: str):
    """Build a MeetingLogger hydrated from on-disk meeting JSON files."""
    from artifacts.meeting_logger import MeetingLog, MeetingLogger, TranscriptTurn

    # BUG-006 FIX: MeetingLogger.__init__ requires project_name argument.
    ml = MeetingLogger(project_name)
    meetings_dir = _project_dir(project_name) / "meetings"
    if not meetings_dir.exists():
        return ml
    for fp in sorted(meetings_dir.glob("*.json")):
        try:
            import json as _json
            data = _json.loads(fp.read_text(encoding="utf-8"))
            meeting_id = data.get("id", fp.stem)
            log = MeetingLog(
                meeting_id=meeting_id,
                title=data.get("title", ""),
                meeting_type=data.get("meeting_type", data.get("type", "ad_hoc")),
                phase=data.get("phase", ""),
                participants=data.get("participants", []),
                agenda_items=data.get("agenda", []),
                simulated_day=data.get("simulated_day", 0),
                duration_minutes=data.get("duration_minutes"),
                is_finalised=True,
            )
            for turn in data.get("transcript", []):
                if isinstance(turn, dict):
                    log.transcript.append(
                        TranscriptTurn(
                            speaker=turn.get("speaker", ""),
                            text=turn.get("text", turn.get("content", "")),
                        )
                    )
            log.decisions_made = data.get("decisions", [])
            log.action_items = data.get("action_items", [])
            # Register directly into archive (skip start_log/finalize_log lifecycle)
            ml._archive[meeting_id] = log
        except Exception as exc:
            logger.warning("_get_meeting_logger: skipping %s — %s", fp.name, exc)
    return ml


# ---------------------------------------------------------------------------
# SAP Activate default phases (mirrors state_machine.py when fully built)
# ---------------------------------------------------------------------------

SAP_ACTIVATE_PHASES = [
    {"id": "discover",  "name": "Discover",  "duration_days": 14},
    {"id": "prepare",   "name": "Prepare",   "duration_days": 21},
    {"id": "explore",   "name": "Explore",   "duration_days": 35},
    {"id": "realize",   "name": "Realize",   "duration_days": 60},
    {"id": "deploy",    "name": "Deploy",    "duration_days": 21},
    {"id": "run",       "name": "Run",       "duration_days": 14},
]

TOTAL_SIM_DAYS = sum(p["duration_days"] for p in SAP_ACTIVATE_PHASES)

# Valid simulation statuses
STATUS_IDLE      = "IDLE"
STATUS_RUNNING   = "RUNNING"
STATUS_PAUSED    = "PAUSED"
STATUS_COMPLETED = "COMPLETED"
STATUS_STOPPED   = "STOPPED"

# (mirrored from state_machine for route-level guards)



# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SERVER_START = time.monotonic()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_phase_progress() -> list[PhaseProgress]:
    return [
        PhaseProgress(
            phase_id=p["id"],
            phase_name=p["name"],
            percentage=0.0,
            is_current=(i == 0),
            is_completed=False,
        )
        for i, p in enumerate(SAP_ACTIVATE_PHASES)
    ]


def _build_default_state(project_name: str, industry: str, scope: str,
                          methodology: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "project_name": project_name,
        "status": STATUS_IDLE,
        "current_phase": SAP_ACTIVATE_PHASES[0]["id"],
        "simulated_day": 0,
        "total_days": TOTAL_SIM_DAYS,
        "phase_progress": [p.model_dump() for p in _default_phase_progress()],
        "active_agents": [],
        "pending_decisions": [],
        "active_meetings": [],
        "milestones": [],
        "industry": industry,
        "scope": scope,
        "methodology": methodology,
        "created_at": now,
        "last_updated": now,
    }


async def _require_project(project_name: str) -> dict[str, Any]:
    """Load project state, raising 404 if it doesn't exist."""
    state = await load_project_state(project_name)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_name}' not found",
        )
    return state


async def _require_status(
    project_name: str,
    allowed: list[str],
    action: str,
) -> dict[str, Any]:
    """Load state and validate its status allows *action*."""
    state = await _require_project(project_name)
    if state["status"] not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot {action} project '{project_name}' "
                f"(status={state['status']}). "
                f"Allowed statuses: {allowed}"
            ),
        )
    return state


def _parse_phase_progress(state: dict[str, Any]) -> list[PhaseProgress]:
    """Convert phase_progress from state (dict or list) into PhaseProgress models."""
    raw = state.get("phase_progress", {})
    current_phase = state.get("current_phase", "")

    # Format A: dict like {"discover": 7.14, "prepare": 0.0, ...}
    if isinstance(raw, dict):
        phases = ["discover", "prepare", "explore", "realize", "deploy", "run"]
        result = []
        for phase in phases:
            pct = raw.get(phase, 0.0)
            result.append(PhaseProgress(
                phase_id=phase,
                phase_name=phase.capitalize(),
                percentage=pct,
                is_current=(phase == current_phase),
                is_completed=(pct >= 100.0),
            ))
        return result

    # Format B: list of PhaseProgress-like dicts
    if isinstance(raw, list):
        return [PhaseProgress(**p) if isinstance(p, dict) else p for p in raw]

    return []


def _state_to_model(state: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        project_name=state["project_name"],
        status=state["status"],
        current_phase=state["current_phase"],
        simulated_day=state["simulated_day"],
        total_days=state["total_days"],
        phase_progress=_parse_phase_progress(state),
        active_agents=state.get("active_agents", []),
        pending_decisions=state.get("pending_decisions", []),
        active_meetings=state.get("active_meetings", []),
        milestones=state.get("milestones", []),
        industry=state.get("industry"),
        scope=state.get("scope"),
        methodology=state.get("methodology"),
        created_at=state["created_at"],
        last_updated=state["last_updated"],
    )


async def _list_project_names() -> list[str]:
    # BUG-004 FIX: Use DB-backed list instead of filesystem scan.
    # The old implementation scanned for 'project.json' files which are never
    # written (state is stored exclusively in SQLite since Phase 7).
    return await list_project_names()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", tags=["health"])
async def health() -> dict:
    """Health check — always returns 200 while the service is up."""
    return {"status": "ok", "service": "sapsim-backend"}


# ---------------------------------------------------------------------------
# Project Management
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["projects"],
    summary="Create a new simulation project",
)
async def create_project(req: CreateProjectRequest) -> ProjectResponse:
    """Create a new SAP SIM project with the given name, industry, scope and methodology.

    - Initialises ``project.json`` with IDLE status and SAP Activate phase scaffold.
    - Writes ``methodology.md`` (custom text or 'SAP Activate') and ``scope.md``.
    - Applies default ``settings.json``.
    - Returns the freshly created project state.

    Raises:
        409: If a project with that name already exists.
    """
    existing = await load_project_state(req.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project '{req.name}' already exists.",
        )

    methodology_text = req.methodology or "SAP Activate"
    scope_text = req.scope or ""
    state = _build_default_state(req.name, req.industry or "Manufacturing",
                                  scope_text, methodology_text)
    await save_project_state(req.name, state)

    # Write auxiliary text files
    project_dir = _project_dir(req.name)
    await _ensure_dir(project_dir)
    async with aiofiles.open(str(project_dir / "methodology.md"), "w") as fh:
        await fh.write(methodology_text)
    async with aiofiles.open(str(project_dir / "scope.md"), "w") as fh:
        await fh.write(scope_text)

    # Default settings
    save_settings(req.name, ProjectSettings())

    # BUG-011 FIX: Do NOT call engine.create_project() here.
    # Conductor.initialize_simulation() transitions state IDLE → RUNNING and
    # overwrites the DB record, so when start_simulation later checks
    # _require_status(allowed=[IDLE, STOPPED]) it sees RUNNING → 409.
    # Engine registration is deferred to start_simulation where it belongs.

    # Announce creation event to the bus (non-blocking)
    bus = get_bus(req.name)
    await bus.publish("PROJECT_CREATED", {"project_name": req.name, "industry": req.industry})

    logger.info("Project '%s' created.", req.name)
    return _state_to_model(state)


@router.get(
    "/api/projects",
    response_model=list[ProjectListResponse],
    tags=["projects"],
    summary="List all projects",
)
async def list_projects() -> list[ProjectListResponse]:
    """Return a lightweight summary for every project in the ``projects/`` folder."""
    names = await _list_project_names()
    summaries: list[ProjectListResponse] = []
    for name in names:
        state = await load_project_state(name)
        if state:
            summaries.append(
                ProjectListResponse(
                    name=state["project_name"],
                    status=state["status"],
                    current_phase=state["current_phase"],
                    simulated_day=state["simulated_day"],
                    total_days=state["total_days"],
                    industry=state.get("industry"),
                    created_at=state["created_at"],
                    last_updated=state["last_updated"],
                )
            )
    return summaries


@router.get(
    "/api/projects/{project_name}",
    response_model=ProjectResponse,
    tags=["projects"],
    summary="Get full project state",
)
async def get_project(project_name: str) -> ProjectResponse:
    """Return the full project state for *project_name*."""
    state = await _require_project(project_name)
    return _state_to_model(state)


@router.delete(
    "/api/projects/{project_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["projects"],
    summary="Delete a project and all its data",
)
async def delete_project(project_name: str) -> None:
    """Permanently delete the project folder and all simulation data.

    A running or paused simulation is force-stopped before deletion.

    Raises:
        404: Project not found.
    """
    await _require_project(project_name)  # ensures it exists
    # BUG-002 FIX: Also remove the project record from SQLite DB.
    # Previously only the filesystem directory was removed, leaving the DB record
    # intact so subsequent 404-expected calls returned 204 instead.
    await delete_project_state(project_name)
    project_dir = _project_dir(project_name)
    shutil.rmtree(str(project_dir), ignore_errors=True)
    logger.info("Project '%s' deleted.", project_name)


# ---------------------------------------------------------------------------
# Simulation Control
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects/{project_name}/start",
    response_model=ProjectResponse,
    tags=["simulation"],
    summary="Start the simulation",
)
async def start_simulation(
    project_name: str,
    req: StartSimulationRequest = StartSimulationRequest(),
) -> ProjectResponse:
    """Start the simulation for *project_name*.

    Transitions status from IDLE or STOPPED → RUNNING.
    Stubs the Conductor integration — full engine wiring is in Phase 6.

    Raises:
        404: Project not found.
        409: Already running or completed.
    """
    state = await _require_status(
        project_name,
        allowed=[STATUS_IDLE, STATUS_STOPPED],
        action="start",
    )

    settings = load_settings(project_name)
    if req.max_parallel_agents:
        settings.max_parallel_agents = req.max_parallel_agents
        save_settings(project_name, settings)

    # --- Engine integration: create project if not registered, then start loop ---
    engine = get_engine()
    if not engine.is_registered(project_name):
        try:
            cfg: dict[str, Any] = {
                "litellm_base_url": settings.litellm_base_url,
                "litellm_api_key":  settings.litellm_api_key,
                "litellm_model":    settings.litellm_model,
            }
            if req.tick_interval_seconds:
                cfg["tick_interval_seconds"] = req.tick_interval_seconds
            await engine.create_project(project_name, config=cfg)
        except Exception as exc:
            logger.warning(
                "Engine.create_project failed for '%s' (non-fatal): %s", project_name, exc
            )
    try:
        await engine.start(project_name)
    except Exception as exc:
        logger.warning("Engine.start failed for '%s' (non-fatal): %s", project_name, exc)

    state["status"] = STATUS_RUNNING
    state["last_updated"] = _now_iso()
    await save_project_state(project_name, state)

    bus = get_bus(project_name)
    await bus.publish("SIMULATION_STARTED", {
        "project_name": project_name,
        "simulated_day": state["simulated_day"],
        "current_phase": state["current_phase"],
    })
    await append_feed_event(project_name, {
        "type": "SIMULATION_STARTED",
        "data": {"project_name": project_name},
        "timestamp": state["last_updated"],
    })

    logger.info("Simulation '%s' started.", project_name)
    return _state_to_model(state)


@router.post(
    "/api/projects/{project_name}/pause",
    response_model=ProjectResponse,
    tags=["simulation"],
    summary="Pause the simulation",
)
async def pause_simulation(project_name: str) -> ProjectResponse:
    """Pause a running simulation, preserving all in-progress state.

    Raises:
        404: Project not found.
        409: Not currently running.
    """
    state = await _require_status(
        project_name,
        allowed=[STATUS_RUNNING],
        action="pause",
    )

    # --- Engine integration ---
    engine = get_engine()
    if engine.is_registered(project_name):
        try:
            engine.pause(project_name)
        except Exception as exc:
            logger.warning("Engine.pause failed for '%s' (non-fatal): %s", project_name, exc)

    state["status"] = STATUS_PAUSED
    state["last_updated"] = _now_iso()
    await save_project_state(project_name, state)

    bus = get_bus(project_name)
    await bus.publish("SIMULATION_PAUSED", {
        "project_name": project_name,
        "simulated_day": state["simulated_day"],
    })
    await append_feed_event(project_name, {
        "type": "SIMULATION_PAUSED",
        "data": {"project_name": project_name},
        "timestamp": state["last_updated"],
    })

    logger.info("Simulation '%s' paused.", project_name)
    return _state_to_model(state)


@router.post(
    "/api/projects/{project_name}/resume",
    response_model=ProjectResponse,
    tags=["simulation"],
    summary="Resume a paused simulation",
)
async def resume_simulation(project_name: str) -> ProjectResponse:
    """Resume a previously paused simulation.

    Raises:
        404: Project not found.
        409: Not currently paused.
    """
    state = await _require_status(
        project_name,
        allowed=[STATUS_PAUSED],
        action="resume",
    )

    # --- Engine integration ---
    engine = get_engine()
    if engine.is_registered(project_name):
        try:
            await engine.resume(project_name)
        except Exception as exc:
            logger.warning("Engine.resume failed for '%s' (non-fatal): %s", project_name, exc)

    state["status"] = STATUS_RUNNING
    state["last_updated"] = _now_iso()
    await save_project_state(project_name, state)

    bus = get_bus(project_name)
    await bus.publish("SIMULATION_RESUMED", {
        "project_name": project_name,
        "simulated_day": state["simulated_day"],
    })
    await append_feed_event(project_name, {
        "type": "SIMULATION_RESUMED",
        "data": {"project_name": project_name},
        "timestamp": state["last_updated"],
    })

    logger.info("Simulation '%s' resumed.", project_name)
    return _state_to_model(state)


@router.post(
    "/api/projects/{project_name}/stop",
    response_model=ProjectResponse,
    tags=["simulation"],
    summary="Stop (and save) the simulation",
)
async def stop_simulation(project_name: str) -> ProjectResponse:
    """Gracefully stop the simulation. State is saved, agents are frozen.

    Raises:
        404: Project not found.
        409: Already idle, completed, or stopped.
    """
    state = await _require_status(
        project_name,
        allowed=[STATUS_RUNNING, STATUS_PAUSED],
        action="stop",
    )

    # --- Engine integration ---
    engine = get_engine()
    if engine.is_registered(project_name):
        try:
            await engine.stop(project_name)
        except Exception as exc:
            logger.warning("Engine.stop failed for '%s' (non-fatal): %s", project_name, exc)

    state["status"] = STATUS_STOPPED
    state["last_updated"] = _now_iso()
    await save_project_state(project_name, state)

    bus = get_bus(project_name)
    await bus.publish("SIMULATION_STOPPED", {
        "project_name": project_name,
        "simulated_day": state["simulated_day"],
        "final_phase": state["current_phase"],
    })
    await append_feed_event(project_name, {
        "type": "SIMULATION_STOPPED",
        "data": {"project_name": project_name},
        "timestamp": state["last_updated"],
    })

    logger.info("Simulation '%s' stopped.", project_name)
    return _state_to_model(state)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Engine Status endpoint (Phase 5.1 addition)
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_name}/simulation/status",
    response_model=SimulationStatusResponse,
    tags=["simulation"],
    summary="Engine-level simulation status (tick metrics, loop state)",
)
async def get_simulation_status(project_name: str) -> SimulationStatusResponse:
    """Return live engine metrics for *project_name* if the engine has it registered.

    Falls back gracefully to the persisted project state if the engine has not
    yet initialised this project (e.g. after a server restart).
    """
    state = await _require_project(project_name)
    engine = get_engine()
    if engine.is_registered(project_name):
        try:
            eng_status = engine.get_status(project_name)
            return SimulationStatusResponse(
                project_name=project_name,
                status=eng_status["status"],
                current_phase=eng_status["current_phase"],
                simulated_day=eng_status["simulated_day"],
                total_days=eng_status["total_days"],
                overall_progress=eng_status["overall_progress"],
                phase_progress=eng_status["phase_progress"],
                active_agents=eng_status["active_agents"],
                tick_count=eng_status["tick_count"],
                tick_interval_seconds=eng_status["tick_interval_seconds"],
                loop_running=eng_status["loop_running"],
                pending_decisions=eng_status["pending_decisions"],
                milestones=eng_status["milestones"],
                injected_failures=eng_status["injected_failures"],
                last_updated=eng_status["last_updated"],
            )
        except Exception as exc:
            logger.warning("Engine.get_status failed for '%s': %s", project_name, exc)
    # Fallback: derive from persisted state
    simulated_day = state["simulated_day"]
    total_days = state["total_days"]
    return SimulationStatusResponse(
        project_name=project_name,
        status=state["status"],
        current_phase=state["current_phase"],
        simulated_day=simulated_day,
        total_days=total_days,
        overall_progress=round(simulated_day / total_days * 100, 2) if total_days else 0.0,
        phase_progress={},
        active_agents=state.get("active_agents", []),
        tick_count=0,
        tick_interval_seconds=5.0,
        loop_running=False,
        pending_decisions=state.get("pending_decisions", []),
        milestones=state.get("milestones", []),
        injected_failures=[],
        last_updated=time.time(),
    )


@router.get(
    "/api/projects/{project_name}/settings",
    response_model=SettingsResponse,
    tags=["settings"],
    summary="Get LiteLLM and simulation settings",
)
async def get_settings(project_name: str) -> SettingsResponse:
    """Return the current settings for *project_name*."""
    await _require_project(project_name)
    s = load_settings(project_name)
    return SettingsResponse(
        litellm_base_url=s.litellm_base_url,
        litellm_api_key=s.litellm_api_key,
        litellm_model=s.litellm_model,
        max_parallel_agents=s.max_parallel_agents,
        memory_compression_interval=s.memory_compression_interval,
        webhook_url=s.webhook_url,
        max_token_budget=s.max_token_budget,
    )


@router.put(
    "/api/projects/{project_name}/settings",
    response_model=SettingsResponse,
    tags=["settings"],
    summary="Update LiteLLM and simulation settings",
)
async def update_settings(
    project_name: str,
    req: SettingsUpdateRequest,
) -> SettingsResponse:
    """Patch and persist settings for *project_name*.

    Only fields present in the request body are updated.
    """
    await _require_project(project_name)
    s = load_settings(project_name)

    if req.litellm_base_url is not None:
        s.litellm_base_url = req.litellm_base_url
    if req.litellm_api_key is not None:
        s.litellm_api_key = req.litellm_api_key
    if req.litellm_model is not None:
        s.litellm_model = req.litellm_model
    if req.max_parallel_agents is not None:
        s.max_parallel_agents = req.max_parallel_agents
    if req.memory_compression_interval is not None:
        s.memory_compression_interval = req.memory_compression_interval
    if req.webhook_url is not None:
        s.webhook_url = req.webhook_url
    if req.max_token_budget is not None:
        s.max_token_budget = req.max_token_budget

    save_settings(project_name, s)

    return SettingsResponse(
        litellm_base_url=s.litellm_base_url,
        litellm_api_key=s.litellm_api_key,
        litellm_model=s.litellm_model,
        max_parallel_agents=s.max_parallel_agents,
        memory_compression_interval=s.memory_compression_interval,
        webhook_url=s.webhook_url,
        max_token_budget=s.max_token_budget,
    )


@router.post(
    "/api/settings/test",
    response_model=TestSettingsResponse,
    tags=["settings"],
    summary="Test a LiteLLM connection",
)
async def test_settings(req: TestSettingsRequest) -> TestSettingsResponse:
    """Test the provided LiteLLM endpoint by making a minimal completion call.

    Returns latency in milliseconds and the model actually used.
    """
    try:
        import httpx
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{req.litellm_base_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {req.litellm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": req.litellm_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
        latency_ms = (time.monotonic() - t0) * 1000

        if resp.status_code == 200:
            body = resp.json()
            model_used = body.get("model", req.litellm_model)
            return TestSettingsResponse(
                success=True,
                latency_ms=round(latency_ms, 2),
                model_used=model_used,
            )
        else:
            return TestSettingsResponse(
                success=False,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

    except Exception as exc:  # noqa: BLE001
        return TestSettingsResponse(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Live Feed — SSE
# ---------------------------------------------------------------------------


@router.get(
    "/api/stream/{project_name}",
    tags=["feed"],
    summary="SSE stream of live simulation events",
)
async def stream_project_events(
    project_name: str,
    request: Request,
) -> EventSourceResponse:
    """Server-Sent Events stream for *project_name*.

    Sends a ``CONNECTED`` ping immediately, then forwards every event published
    on the project's ``EventBus``.  Closes when the client disconnects.
    """
    bus = get_bus(project_name)

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {
            "event": "CONNECTED",
            "data": json.dumps({"project": project_name, "message": "Stream connected"}),
        }

        async for envelope in bus.subscribe():
            if await request.is_disconnected():
                logger.info("SSE client disconnected from '%s'", project_name)
                break
            yield {
                "event": envelope["type"],
                "data": json.dumps(envelope["data"], default=str),
            }

    return EventSourceResponse(event_generator())


@router.get(
    "/api/projects/{project_name}/feed",
    response_model=FeedPageResponse,
    tags=["feed"],
    summary="Paginated historical feed",
)
async def get_feed(
    project_name: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
) -> FeedPageResponse:
    """Return paginated events from the database.

    Filter by ``event_type`` to narrow results (e.g. ``AGENT_MSG``, ``MEETING_STARTED``).

    .. note::
       BUG-003 FIX: Previously read from a filesystem JSONL file that was never
       written (events are stored in SQLite via append_feed_event). Now uses the
       DB-backed get_feed_events / count_feed_events helpers.
    """
    await _require_project(project_name)
    offset = (page - 1) * limit
    events = await get_feed_events(
        project_name, limit=limit, offset=offset, event_type=event_type
    )
    total = await count_feed_events(project_name)
    return FeedPageResponse(
        events=events,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(events)) < total,
    )


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

# Minimal agent roster — full agent objects come from agents/ when Phase 2 is complete.
_AGENT_ROSTER: list[dict[str, Any]] = [
    # ── Consultant side ──────────────────────────────────────────────────
    {"codename": "PM_ALEX",    "role": "Project Manager",          "side": "consultant",     "tier": "strategic",   "model": "claude-4-6-opus",    "skills": ["project_management", "change_management"]},
    {"codename": "ARCH_SARA",  "role": "Solution Architect",       "side": "consultant",     "tier": "strategic",   "model": "claude-4-6-opus",    "skills": ["sap_activate", "integration_pi", "abap_development"]},
    {"codename": "PMO_NIKO",   "role": "PMO Lead",                 "side": "consultant",     "tier": "strategic",   "model": "claude-4-6-opus",    "skills": ["project_management", "testing_strategy"]},
    {"codename": "BASIS_KURT", "role": "Basis Administrator",      "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["basis_admin", "security_auth"]},
    {"codename": "FI_CHEN",    "role": "FI Lead",                  "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["fi_accounting", "co_controlling"]},
    {"codename": "CO_MARTA",   "role": "CO Lead",                  "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["co_controlling", "fi_accounting"]},
    {"codename": "MM_RAVI",    "role": "MM Lead",                  "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["mm_procurement", "wm_warehouse"]},
    {"codename": "SD_ISLA",    "role": "SD Lead",                  "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["sd_sales", "fi_accounting"]},
    {"codename": "PP_JONAS",   "role": "PP Lead",                  "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["pp_production", "mm_procurement"]},
    {"codename": "WM_FATIMA",  "role": "WM/EWM Lead",              "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["wm_warehouse", "mm_procurement"]},
    {"codename": "INT_MARCO",  "role": "Integration Lead",         "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["integration_pi", "abap_development"]},
    {"codename": "SEC_DIANA",  "role": "Security Lead",            "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["security_auth", "basis_admin"]},
    {"codename": "BI_SAM",     "role": "BI/Analytics Lead",        "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["bi_analytics", "fi_accounting"]},
    {"codename": "CHG_NADIA",  "role": "Change Management Lead",   "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["change_management", "testing_strategy"]},
    {"codename": "DM_FELIX",   "role": "Data Migration Lead",      "side": "consultant",     "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["data_migration", "abap_development"]},
    {"codename": "DEV_PRIYA",  "role": "Developer",                "side": "consultant",     "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["abap_development", "integration_pi"]},
    {"codename": "DEV_LEON",   "role": "Developer",                "side": "consultant",     "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["abap_development", "bi_analytics"]},
    # ── Customer side ────────────────────────────────────────────────────
    {"codename": "EXEC_VICTOR",   "role": "Executive Sponsor",         "side": "customer",   "tier": "strategic",   "model": "claude-4-6-opus",    "skills": ["project_management"]},
    {"codename": "IT_MGR_HELEN",  "role": "IT Manager",                "side": "customer",   "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["basis_admin", "security_auth"]},
    {"codename": "CUST_PM_OMAR",  "role": "Customer Project Manager",  "side": "customer",   "tier": "senior",      "model": "claude-4-6-sonnet",  "skills": ["project_management"]},
    {"codename": "QA_CLAIRE",     "role": "QA Lead",                   "side": "crossfunctional", "tier": "senior", "model": "claude-4-6-sonnet",  "skills": ["testing_strategy"]},
    {"codename": "FI_KU_ROSE",    "role": "FI Key User",               "side": "customer",   "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["fi_accounting"]},
    {"codename": "CO_KU_BJORN",   "role": "CO Key User",               "side": "customer",   "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["co_controlling"]},
    {"codename": "MM_KU_GRACE",   "role": "MM Key User",               "side": "customer",   "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["mm_procurement"]},
    {"codename": "SD_KU_TONY",    "role": "SD Key User",               "side": "customer",   "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["sd_sales"]},
    {"codename": "BA_CUST_JAMES", "role": "Business Analyst",          "side": "customer",   "tier": "operational", "model": "gemini-2.5-pro",     "skills": ["sap_activate", "data_migration"]},
    {"codename": "WM_KU_ELENA",   "role": "WM Key User",               "side": "customer",   "tier": "basic",       "model": "qwen3.6-plus",       "skills": ["wm_warehouse"]},
    {"codename": "PP_KU_IBRAHIM", "role": "PP Key User",               "side": "customer",   "tier": "basic",       "model": "qwen3.6-plus",       "skills": ["pp_production"]},
    {"codename": "HR_KU_SOPHIE",  "role": "HR Key User",               "side": "customer",   "tier": "basic",       "model": "qwen3.6-plus",       "skills": []},
    {"codename": "CHAMP_LEILA",   "role": "Change Champion",           "side": "customer",   "tier": "basic",       "model": "qwen3.6-plus",       "skills": ["change_management"]},
]


async def _load_agent_file(project_name: str, codename: str) -> dict[str, Any] | None:
    agent_file = _project_dir(project_name) / "agents" / f"{codename}.json"
    if not agent_file.exists():
        return None
    async with aiofiles.open(str(agent_file), "r") as fh:
        return json.loads(await fh.read())


def _agent_summary(
    roster_entry: dict[str, Any],
    live_state: dict[str, Any] | None,
) -> AgentResponse:
    codename = roster_entry["codename"]
    side = roster_entry["side"]
    personality = None
    if side in ("customer", "crossfunctional") and live_state:
        p = live_state.get("personality")
        if p:
            personality = AgentPersonality(**p)
    return AgentResponse(
        codename=codename,
        role=roster_entry["role"],
        side=side,
        tier=roster_entry["tier"],
        model=roster_entry["model"],
        status=live_state.get("status", "idle") if live_state else "idle",
        current_task=live_state.get("current_task") if live_state else None,
        personality=personality,
    )


@router.get(
    "/api/projects/{project_name}/agents",
    response_model=list[AgentResponse],
    tags=["agents"],
    summary="List all 30 agents with current status",
)
async def list_agents(project_name: str) -> list[AgentResponse]:
    """Return status cards for all 30 agents.

    Enriches agent status from the live Conductor when the engine has the
    project registered (i.e. simulation is running).
    """
    await _require_project(project_name)

    # Try to pull live agent state from the engine's Conductor
    engine = get_engine()
    live_agent_map: dict[str, Any] = {}
    if engine.is_registered(project_name):
        try:
            conductor = engine.get_conductor(project_name)
            for codename_key, agent_obj in conductor.agents.items():
                live_agent_map[codename_key] = {
                    "status": getattr(agent_obj, "status", "idle"),
                    "current_task": getattr(agent_obj, "current_task", None),
                    "personality": getattr(agent_obj, "personality", None),
                    "recent_activity": getattr(agent_obj, "recent_activity", []),
                }
        except Exception as exc:
            logger.debug("Could not pull live agent state from engine: %s", exc)

    results: list[AgentResponse] = []
    for entry in _AGENT_ROSTER:
        codename_upper = entry["codename"]
        if codename_upper in live_agent_map:
            live = live_agent_map[codename_upper]
        else:
            live = await _load_agent_file(project_name, codename_upper)
        results.append(_agent_summary(entry, live))
    return results


@router.get(
    "/api/projects/{project_name}/agents/{codename}",
    response_model=AgentDetailResponse,
    tags=["agents"],
    summary="Agent detail — state, memory, personality, activity",
)
async def get_agent(project_name: str, codename: str) -> AgentDetailResponse:
    """Return full detail for a single agent."""
    await _require_project(project_name)
    codename_upper = codename.upper()
    roster_entry = next(
        (a for a in _AGENT_ROSTER if a["codename"] == codename_upper), None
    )
    if roster_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent codename '{codename}'",
        )

    # Try to get live state from engine conductor first
    live: dict[str, Any] | None = None
    engine = get_engine()
    if engine.is_registered(project_name):
        try:
            conductor = engine.get_conductor(project_name)
            agent_obj = conductor.agents.get(codename_upper)
            if agent_obj:
                live = {
                    "status": getattr(agent_obj, "status", "idle"),
                    "current_task": getattr(agent_obj, "current_task", None),
                    "personality": getattr(agent_obj, "personality", None),
                    "memory_turns_count": len(getattr(agent_obj, "_memory", []) or []),
                    "recent_activity": getattr(agent_obj, "recent_activity", []),
                }
        except Exception as exc:
            logger.debug("Could not pull live agent '%s' from engine: %s", codename_upper, exc)

    if live is None:
        live = await _load_agent_file(project_name, codename_upper)

    agent_summary = _agent_summary(roster_entry, live)
    memory_file = _project_dir(project_name) / "memory" / f"{codename_upper}_summary.md"
    memory_summary = None
    if memory_file.exists():
        async with aiofiles.open(str(memory_file), "r") as fh:
            memory_summary = await fh.read()

    return AgentDetailResponse(
        **agent_summary.model_dump(),
        skills=roster_entry.get("skills", []),
        memory_turns=live.get("memory_turns_count", 0) if live else 0,
        memory_summary=memory_summary,
        recent_activity=live.get("recent_activity", []) if live else [],
    )


@router.post(
    "/api/projects/{project_name}/agents/reroll",
    response_model=list[AgentResponse],
    tags=["agents"],
    summary="Re-roll customer agent personalities",
)
async def reroll_personalities(
    project_name: str,
    req: RerollRequest = RerollRequest(),
) -> list[AgentResponse]:
    """Re-roll personality axes for customer agents.

    Only allowed while the simulation is IDLE (pre-start).
    If ``req.codename`` is provided, only that agent is re-rolled.
    """
    state = await _require_status(
        project_name,
        allowed=[STATUS_IDLE],
        action="reroll personalities for",
    )

    import random

    ARCHETYPES = {
        "The Skeptic":           {"engagement": (3, 5), "trust": (1, 2), "risk_tolerance": (1, 3)},
        "The Absent Sponsor":    {"engagement": (1, 2), "trust": (3, 4), "risk_tolerance": (2, 4)},
        "The Spreadsheet Hoarder": {"engagement": (2, 4), "trust": (2, 3), "risk_tolerance": (1, 2)},
        "The Reluctant Champion": {"engagement": (3, 4), "trust": (2, 3), "risk_tolerance": (2, 3)},
        "The Power User":        {"engagement": (4, 5), "trust": (4, 5), "risk_tolerance": (3, 5)},
        "The Escalator":         {"engagement": (4, 5), "trust": (1, 2), "risk_tolerance": (1, 2)},
        "The Ghost":             {"engagement": (1, 2), "trust": (3, 5), "risk_tolerance": (2, 4)},
        "The Overloader":        {"engagement": (5, 5), "trust": (4, 5), "risk_tolerance": (4, 5)},
    }

    customer_codenames = [
        a["codename"] for a in _AGENT_ROSTER
        if a["side"] in ("customer", "crossfunctional")
    ]

    if req.codename:
        codename_upper = req.codename.upper()
        if codename_upper not in customer_codenames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{req.codename}' is not a customer agent or doesn't exist.",
            )
        targets = [codename_upper]
    else:
        targets = customer_codenames

    agents_dir = _project_dir(project_name) / "agents"
    await _ensure_dir(agents_dir)

    for codename_target in targets:
        archetype = random.choice(list(ARCHETYPES.keys()))
        ranges = ARCHETYPES[archetype]
        personality = {
            "engagement": random.randint(*ranges["engagement"]),
            "trust": random.randint(*ranges["trust"]),
            "risk_tolerance": random.randint(*ranges["risk_tolerance"]),
            "archetype": archetype,
            "history": [],
        }
        agent_file = agents_dir / f"{codename_target}.json"
        existing: dict = {}
        if agent_file.exists():
            async with aiofiles.open(str(agent_file), "r") as fh:
                existing = json.loads(await fh.read())
        existing["personality"] = personality
        existing["status"] = existing.get("status", "idle")
        async with aiofiles.open(str(agent_file), "w") as fh:
            await fh.write(json.dumps(existing, indent=2))

    # Return fresh list
    results = []
    for entry in _AGENT_ROSTER:
        live = await _load_agent_file(project_name, entry["codename"])
        results.append(_agent_summary(entry, live))
    return results


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_name}/meetings",
    response_model=list[MeetingResponse],
    tags=["artifacts"],
    summary="List all meeting logs",
)
async def list_meetings(project_name: str) -> list[MeetingResponse]:
    """Return a list of all meetings recorded for this project.

    Uses :class:`~artifacts.meeting_logger.MeetingLogger` to load and
    enumerate archived meeting logs from the project's ``meetings/`` folder.
    Returns an empty list if no meetings have been logged yet.
    """
    await _require_project(project_name)
    meeting_logger = await asyncio.get_event_loop().run_in_executor(
        None, _get_meeting_logger, project_name
    )
    archived_ids = meeting_logger.list_archived()
    if not archived_ids:
        return []

    summaries: list[MeetingResponse] = []
    for mid in archived_ids:
        log = meeting_logger.get_log(mid)
        if log is None:
            continue
        summaries.append(
            MeetingResponse(
                id=log.meeting_id,
                title=log.title,
                phase=log.phase,
                simulated_day=log.simulated_day,
                facilitator=(
                    log.participants[0] if log.participants else ""
                ),
                participants=log.participants,
                duration_turns=len(log.transcript),
                decisions_count=len(log.decisions_made),
            )
        )
    return summaries


@router.get(
    "/api/projects/{project_name}/meetings/{meeting_id}",
    response_model=MeetingDetailResponse,
    tags=["artifacts"],
    summary="Full meeting log",
)
async def get_meeting(project_name: str, meeting_id: str) -> MeetingDetailResponse:
    """Return the full meeting transcript, decisions, and action items."""
    await _require_project(project_name)
    meeting_file = _project_dir(project_name) / "meetings" / f"{meeting_id}.json"
    if not meeting_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found in project '{project_name}'",
        )
    async with aiofiles.open(str(meeting_file), "r") as fh:
        data = json.loads(await fh.read())
    md_path = _project_dir(project_name) / "meetings" / f"{meeting_id}_meeting.md"
    return MeetingDetailResponse(
        id=data.get("id", meeting_id),
        title=data.get("title", ""),
        phase=data.get("phase", ""),
        simulated_day=data.get("simulated_day", 0),
        facilitator=data.get("facilitator", ""),
        participants=data.get("participants", []),
        duration_turns=data.get("duration_turns", 0),
        decisions_count=len(data.get("decisions", [])),
        agenda=data.get("agenda", []),
        transcript=data.get("transcript", []),
        decisions=data.get("decisions", []),
        action_items=data.get("action_items", []),
        markdown_path=str(md_path) if md_path.exists() else None,
    )


@router.get(
    "/api/projects/{project_name}/decisions",
    response_model=DecisionResponse,
    tags=["artifacts"],
    summary="Decision board grouped by status",
)
async def get_decisions(project_name: str) -> DecisionResponse:
    """Return all decisions grouped by status (pending/approved/rejected/deferred).

    BUG-005 FIX: Previously attempted to call `DecisionBoard.get_board()` (an async
    method) without awaiting it inside a thread executor — producing a coroutine
    object instead of results.  Now queries the DB directly via persistence helpers.
    """
    from utils.persistence import get_decisions as _get_decisions_from_db
    await _require_project(project_name)
    all_decisions = await _get_decisions_from_db(project_name)
    board = DecisionResponse(total=len(all_decisions))
    for d in all_decisions:
        s = d.get("status", "proposed")
        if s == "approved":
            board.approved.append(d)
        elif s == "rejected":
            board.rejected.append(d)
        elif s == "deferred":
            board.deferred.append(d)
        else:
            board.pending.append(d)
    return board


@router.post(
    "/api/projects/{project_name}/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["artifacts"],
    summary="Propose a new decision",
)
async def propose_decision(
    project_name: str,
    req: ProposeDecisionRequest,
) -> DecisionResponse:
    """Propose a new decision and add it to the Decision Board.

    The decision starts with status ``proposed``.  Use the DecisionBoard's
    vote/resolve cycle (driven by the simulation engine) to progress it.

    Raises:
        404: Project not found.
        409: A decision with an identical title proposed by the same agent
             on the same day already exists (duplicate guard).
    """
    # BUG-005 / BUG-010 FIX: Replaced broken thread-executor + unawaited coroutine pattern
    # with direct async DB access via persistence helpers.
    from utils.persistence import get_decisions as _get_decisions_from_db
    from utils.persistence import save_decision as _save_decision
    import uuid as _uuid

    await _require_project(project_name)

    # Duplicate guard: same title + proposer + day
    existing = await _get_decisions_from_db(project_name)
    for d in existing:
        if (
            d.get("title", "").strip().lower() == req.title.strip().lower()
            and d.get("proposed_by") == req.proposed_by
            and d.get("proposed_day") == req.proposed_at_day
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A decision titled '{req.title}' proposed by '{req.proposed_by}' "
                    f"on day {req.proposed_at_day} already exists."
                ),
            )

    decision_id = str(_uuid.uuid4())
    decision_dict = {
        "id":              decision_id,
        "title":           req.title,
        "description":     req.description,
        "category":        req.category or "general",
        "proposed_by":     req.proposed_by,
        "proposed_at_day": req.proposed_at_day,
        "status":          "proposed",
        "rationale":       req.rationale or "",
        "impact_assessment": req.impact_assessment or "",
        "related_meeting_id": req.related_meeting_id,
        "votes":           {},
    }
    await _save_decision(project_name, decision_dict)

    # Return the full board state
    all_decisions = await _get_decisions_from_db(project_name)
    board = DecisionResponse(total=len(all_decisions))
    for d in all_decisions:
        s = d.get("status", "proposed")
        if s == "approved":
            board.approved.append(d)
        elif s == "rejected":
            board.rejected.append(d)
        elif s == "deferred":
            board.deferred.append(d)
        else:
            board.pending.append(d)
    return board


@router.get(
    "/api/projects/{project_name}/tools",
    response_model=ToolResponse,
    tags=["artifacts"],
    summary="Tool registry",
)
async def get_tools(project_name: str) -> ToolResponse:
    """Return the tool registry — all tools invented by agents during the simulation."""
    await _require_project(project_name)
    registry = await asyncio.get_event_loop().run_in_executor(
        None, _get_tool_registry, project_name
    )
    # BUG-007 FIX: ToolRegistry has no 'get_all_tools' method; renamed to 'get_all_tools_local'.
    all_tools = registry.get_all_tools_local()
    return ToolResponse(
        tools=[t.to_dict() for t in all_tools],
        total=len(all_tools),
    )


@router.get(
    "/api/projects/{project_name}/test-strategy",
    response_model=TestCaseResponse,
    tags=["artifacts"],
    summary="Current test strategy",
)
async def get_test_strategy(project_name: str) -> TestCaseResponse:
    """Return the live test strategy document."""
    await _require_project(project_name)
    # BUG-009 FIX: TestStrategy.get_coverage_report() is async; must be awaited.
    # Also run instantiation in thread executor then await the async method in the
    # main event loop.
    ts = await asyncio.get_event_loop().run_in_executor(
        None, _get_test_strategy, project_name
    )
    coverage = await ts.get_coverage_report()
    return TestCaseResponse(
        tests=[tc.to_dict() for tc in ts.all_tests()],
        overall_progress=float(coverage.get("pass_rate", 0.0)) * 100,
        coverage=coverage,
    )


@router.get(
    "/api/projects/{project_name}/lessons",
    response_model=LessonResponse,
    tags=["artifacts"],
    summary="Lessons learned log",
)
async def get_lessons(project_name: str) -> LessonResponse:
    """Return all lessons learned, with validation counts."""
    await _require_project(project_name)
    collector = await asyncio.get_event_loop().run_in_executor(
        None, _get_lessons_collector, project_name
    )
    all_lessons = collector.all_lessons()
    entries: list[LessonEntry] = []
    for l in all_lessons:
        entries.append(
            LessonEntry(
                id=l.id,
                raised_by=l.reported_by,
                phase=l.phase,
                day=l.reported_at_day,
                category=l.category,
                lesson=l.description,
                validation_count=0,
                validated_by=[],
            )
        )
    return LessonResponse(lessons=entries, total=len(entries))


@router.get(
    "/api/projects/{project_name}/report",
    tags=["artifacts"],
    summary="Generate and return the final report",
)
async def get_report(project_name: str) -> dict:
    """Return the final simulation report (generates it if it doesn't exist yet)."""
    await _require_project(project_name)
    report_file = _project_dir(project_name) / "artifacts" / "final_report.md"
    if report_file.exists():
        async with aiofiles.open(str(report_file), "r") as fh:
            content = await fh.read()
        return {"project_name": project_name, "content": content, "generated": False}

    # Stub: generate minimal report from project state
    state = await load_project_state(project_name)
    now = _now_iso()
    report = (
        f"# SAP SIM — Project Final Report\n\n"
        f"**Project:** {state['project_name']}\n"
        f"**Status:** {state['status']}\n"
        f"**Generated:** {now}\n\n"
        f"## Project Overview\n"
        f"- Industry: {state.get('industry', 'N/A')}\n"
        f"- Simulated day: {state['simulated_day']} / {state['total_days']}\n"
        f"- Current phase: {state['current_phase']}\n\n"
        f"## Scope\n{state.get('scope') or '_No scope provided._'}\n\n"
        f"## Methodology\n{state.get('methodology') or 'SAP Activate'}\n\n"
        f"_Full report will be generated automatically when the simulation completes._\n"
    )
    artifacts_dir = _project_dir(project_name) / "artifacts"
    await _ensure_dir(artifacts_dir)
    async with aiofiles.open(str(report_file), "w") as fh:
        await fh.write(report)
    return {"project_name": project_name, "content": report, "generated": True}


@router.post(
    "/api/projects/{project_name}/artifacts/report",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["artifacts"],
    summary="Trigger full report generation via FinalReportGenerator",
)
async def generate_artifact_report(
    project_name: str,
    req: ArtifactReportRequest = ArtifactReportRequest(),
) -> ArtifactResponse:
    """Trigger :class:`~artifacts.final_report.FinalReportGenerator` to compile
    all project artifacts into a comprehensive Markdown report.

    The report is written to ``projects/<project_name>/final_report.md`` and
    also returned inline in the response body.

    - If a report already exists and ``force_regenerate`` is ``False``, the
      cached copy is returned without re-generating.
    - Set ``force_regenerate=True`` to always rebuild from current artifact state.

    Raises:
        404: Project not found.
    """
    await _require_project(project_name)

    report_file = _project_dir(project_name) / "artifacts" / "final_report.md"

    if report_file.exists() and not req.force_regenerate:
        async with aiofiles.open(str(report_file), "r") as fh:
            content = await fh.read()
        return ArtifactResponse(
            project_name=project_name,
            content=content,
            generated=False,
        )

    def _run_generator() -> str:
        from artifacts.final_report import FinalReportGenerator
        from utils.persistence import PROJECTS_BASE

        gen = FinalReportGenerator(
            project_name=project_name,
            projects_root=str(PROJECTS_BASE),
        )
        report_text = gen.generate_report(project_name)
        gen.save_report(report_text, project_name)
        return report_text

    try:
        content = await asyncio.get_event_loop().run_in_executor(None, _run_generator)
    except Exception as exc:
        logger.error(
            "FinalReportGenerator failed for '%s': %s", project_name, exc, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {exc}",
        ) from exc

    return ArtifactResponse(
        project_name=project_name,
        content=content,
        generated=True,
    )


# ---------------------------------------------------------------------------
# Stakeholder View
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_name}/stakeholder",
    response_model=StakeholderView,
    tags=["stakeholder"],
    summary="Curated executive summary",
)
async def get_stakeholder_view(project_name: str) -> StakeholderView:
    """Return the executive summary used by the stakeholder panel on the dashboard.

    Includes: health gauge, active escalations, phase progress, top decisions,
    agent leaderboard, and latest milestone.
    """
    state = await _require_project(project_name)

    # Derive health score from status + simulated progress
    status_val = state["status"]
    sim_day = state["simulated_day"]
    total_days = state["total_days"]
    progress_pct = (sim_day / total_days * 100) if total_days else 0

    if status_val == STATUS_RUNNING:
        health = max(60.0, 100.0 - len(state.get("pending_decisions", [])) * 5)
    elif status_val == STATUS_PAUSED:
        health = 50.0
    elif status_val == STATUS_COMPLETED:
        health = 100.0
    elif status_val == STATUS_STOPPED:
        health = 30.0
    else:
        health = 70.0

    phase_progress = _parse_phase_progress(state)

    # Top decisions (first 5 pending)
    top_decisions = state.get("pending_decisions", [])[:5]

    # Latest milestone
    milestones = state.get("milestones", [])
    latest_milestone = milestones[-1] if milestones else None

    # Agent leaderboard (stub — replaced with real activity when Phase 2 runs)
    leaderboard: list[dict] = []

    return StakeholderView(
        project_name=project_name,
        status=status_val,
        health_score=round(health, 1),
        current_phase=state["current_phase"],
        phase_progress_pct=round(progress_pct, 1),
        simulated_day=sim_day,
        total_days=total_days,
        active_agent_count=len(state.get("active_agents", [])),
        pending_escalations=[
            d for d in state.get("pending_decisions", [])
            if d.get("impact") == "critical"
        ],
        top_decisions=top_decisions,
        latest_milestone=latest_milestone,
        agent_leaderboard=leaderboard,
        phase_breakdown=phase_progress,
        last_updated=state["last_updated"],
    )


# ---------------------------------------------------------------------------
# Admin API (localhost-only, King Charly co-operator)
# ---------------------------------------------------------------------------


@router.get(
    "/api/admin/health",
    response_model=AdminHealthResponse,
    tags=["admin"],
    summary="Detailed backend health for operator monitoring",
)
async def admin_health() -> AdminHealthResponse:
    """Return aggregate health metrics for all active projects."""
    names = await _list_project_names()
    active_projects = 0
    active_agents = 0
    phase_summaries = []

    engine = get_engine()
    for name in names:
        state = await load_project_state(name)
        if state and state["status"] == STATUS_RUNNING:
            active_projects += 1
            # Prefer engine-reported active agents when available
            if engine.is_registered(name):
                try:
                    eng_status = engine.get_status(name)
                    active_agents += len(eng_status["active_agents"])
                except Exception:
                    active_agents += len(state.get("active_agents", []))
            else:
                active_agents += len(state.get("active_agents", []))
            phase_summaries.append({
                "project": name,
                "phase": state["current_phase"],
                "day": state["simulated_day"],
            })

    return AdminHealthResponse(
        status="ok",
        active_projects=active_projects,
        active_agents=active_agents,
        tokens_per_minute=0.0,    # populated by engine telemetry in later phase
        total_tokens_used=0,
        phase_summaries=phase_summaries,
        uptime_seconds=round(time.monotonic() - _SERVER_START, 1),
    )


@router.get(
    "/api/admin/highlights",
    response_model=AdminHighlightsResponse,
    tags=["admin"],
    summary="Last N significant simulation events",
)
async def admin_highlights(
    n: int = Query(default=20, ge=1, le=200),
    project_name: Optional[str] = Query(default=None),
) -> AdminHighlightsResponse:
    """Return the last *n* significant events across all (or one) project(s).

    Significant events include: decisions, tools invented, meetings started/ended,
    blockers raised, phase transitions, and go-live rehearsals.
    """
    SIGNIFICANT_TYPES = {
        "DECISION_RAISED", "DECISION_APPROVED", "DECISION_REJECTED",
        "MEETING_STARTED", "MEETING_ENDED", "NEW_TOOL",
        "BLOCKER", "PHASE_TRANSITION", "SIMULATION_STARTED",
        "SIMULATION_STOPPED", "SIMULATION_COMPLETED",
    }

    names = await _list_project_names()
    if project_name:
        names = [p for p in names if p == project_name]

    all_events: list[dict] = []
    for pname in names:
        feed_path = _project_dir(pname) / "feed" / "events.jsonl"
        if not feed_path.exists():
            continue
        async with aiofiles.open(str(feed_path), "r") as fh:
            async for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if ev.get("type") in SIGNIFICANT_TYPES:
                        ev["_project"] = pname
                        all_events.append(ev)
                except json.JSONDecodeError:
                    pass

    # Most recent first
    all_events = all_events[-n:]
    all_events.reverse()
    return AdminHighlightsResponse(highlights=all_events, total=len(all_events))


@router.post(
    "/api/admin/token-budget",
    tags=["admin"],
    summary="Set max token budget for a project",
)
async def set_token_budget(req: TokenBudgetRequest) -> dict:
    """Set or clear the max token budget for a project run."""
    await _require_project(req.project_name)
    s = load_settings(req.project_name)
    s.max_token_budget = req.max_tokens
    save_settings(req.project_name, s)
    return {"project_name": req.project_name, "max_token_budget": req.max_tokens}


@router.get(
    "/api/admin/token-usage",
    response_model=TokenUsageResponse,
    tags=["admin"],
    summary="Token usage breakdown by agent and tier",
)
async def get_token_usage(
    project_name: str = Query(..., description="Project to inspect"),
) -> TokenUsageResponse:
    """Return current token usage for a project (stub — real data from engine)."""
    await _require_project(project_name)
    s = load_settings(project_name)
    # Token usage populated by the engine in Phase 3; stub returns zeros.
    return TokenUsageResponse(
        project_name=project_name,
        total_used=0,
        budget=s.max_token_budget,
        remaining=s.max_token_budget,
        by_agent={},
        by_tier={},
    )
