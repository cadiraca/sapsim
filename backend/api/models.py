"""
SAP SIM — Pydantic v2 Response & Request Models
Phase: 5.1
Purpose: All public-facing API models (request bodies and response shapes)
         used by api.routes and api.admin.  Importing from one place keeps
         route code clean and ensures consistent serialisation across the API.

All models use Pydantic v2 BaseModel.  Field aliases, validators, and
model_config are added where useful for JSON serialisation compatibility.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error shape returned by all error paths."""

    error: str
    detail: str
    code: str


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


class PhaseInfo(BaseModel):
    """SAP Activate phase descriptor."""

    id: str
    name: str
    duration_days: int


class PhaseProgress(BaseModel):
    """Progress state for a single SAP Activate phase."""

    phase_id: str
    phase_name: str
    percentage: float = 0.0
    is_current: bool = False
    is_completed: bool = False


# ---------------------------------------------------------------------------
# Project models
# ---------------------------------------------------------------------------


class ProjectResponse(BaseModel):
    """Full project state — returned by detail + mutation endpoints."""

    project_name: str
    status: str
    current_phase: str
    simulated_day: int
    total_days: int
    phase_progress: list[PhaseProgress]
    active_agents: list[str]
    pending_decisions: list[dict[str, Any]]
    active_meetings: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    industry: Optional[str] = None
    scope: Optional[str] = None
    methodology: Optional[str] = None
    created_at: str
    last_updated: str


class ProjectListResponse(BaseModel):
    """Lightweight project list entry."""

    name: str
    status: str
    current_phase: str
    simulated_day: int
    total_days: int
    industry: Optional[str] = None
    created_at: str
    last_updated: str


# ---------------------------------------------------------------------------
# Simulation status
# ---------------------------------------------------------------------------


class SimulationStatusResponse(BaseModel):
    """Engine-level simulation status — enriches the project state with engine metrics."""

    project_name: str
    status: str
    current_phase: str
    simulated_day: int
    total_days: int
    overall_progress: float = Field(ge=0.0, le=100.0, description="0-100 overall progress")
    phase_progress: dict[str, float] = Field(default_factory=dict, description="phase_id → %")
    active_agents: list[str] = Field(default_factory=list)
    tick_count: int = 0
    tick_interval_seconds: float = 5.0
    loop_running: bool = False
    pending_decisions: list[dict[str, Any]] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    injected_failures: list[dict[str, Any]] = Field(default_factory=list)
    last_updated: float = 0.0


# ---------------------------------------------------------------------------
# Agent models
# ---------------------------------------------------------------------------


class AgentPersonality(BaseModel):
    """Psychographic axes for customer/crossfunctional agents."""

    engagement: int = Field(ge=1, le=5)
    trust: int = Field(ge=1, le=5)
    risk_tolerance: int = Field(ge=1, le=5)
    archetype: str
    history: list[dict[str, Any]] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Summary card for a single agent."""

    codename: str
    role: str
    side: str               # "consultant" | "customer" | "crossfunctional"
    tier: str               # "strategic" | "senior" | "operational" | "basic"
    model: str
    status: str             # "idle" | "thinking" | "speaking" | "in_meeting"
    current_task: Optional[str] = None
    personality: Optional[AgentPersonality] = None


class AgentDetailResponse(AgentResponse):
    """Full agent detail including memory and recent activity."""

    skills: list[str] = Field(default_factory=list)
    memory_turns: int = 0
    memory_summary: Optional[str] = None
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    """List of agent summary cards."""

    agents: list[AgentResponse]
    total: int


# ---------------------------------------------------------------------------
# Meeting models
# ---------------------------------------------------------------------------


class MeetingResponse(BaseModel):
    """Summary of a single meeting log."""

    id: str
    title: str
    phase: str
    simulated_day: int
    facilitator: str
    participants: list[str]
    duration_turns: int
    decisions_count: int


class MeetingDetailResponse(MeetingResponse):
    """Full meeting log including transcript, decisions, and action items."""

    agenda: list[str] = Field(default_factory=list)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[dict[str, Any]] = Field(default_factory=list)
    markdown_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Decision models
# ---------------------------------------------------------------------------


class DecisionResponse(BaseModel):
    """Decision board grouped by lifecycle status."""

    pending: list[dict[str, Any]] = Field(default_factory=list)
    approved: list[dict[str, Any]] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    deferred: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Tool registry models
# ---------------------------------------------------------------------------


class ToolResponse(BaseModel):
    """Tool registry — catalogue of all SAP tools declared during the simulation."""

    tools: list[dict[str, Any]]
    total: int


# ---------------------------------------------------------------------------
# Test strategy models
# ---------------------------------------------------------------------------


class TestCaseResponse(BaseModel):
    """Test strategy document summary."""

    scope: list[str] = Field(default_factory=list)
    test_types: list[dict[str, Any]] = Field(default_factory=list)
    uat_plan: dict[str, Any] = Field(default_factory=dict)
    defect_process: str = ""
    overall_progress: float = 0.0
    last_updated: Optional[str] = None
    # Coverage report from the live TestStrategy object
    coverage: Optional[dict[str, Any]] = None
    tests: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Lessons learned models
# ---------------------------------------------------------------------------


class LessonEntry(BaseModel):
    """A single lessons-learned entry."""

    id: str
    raised_by: str
    phase: str
    day: int
    category: str
    lesson: str
    validation_count: int = 0
    validated_by: list[str] = Field(default_factory=list)


class LessonResponse(BaseModel):
    """Lessons learned log with total count."""

    lessons: list[LessonEntry]
    total: int


# ---------------------------------------------------------------------------
# Feed / SSE models
# ---------------------------------------------------------------------------


class FeedEventResponse(BaseModel):
    """A single feed event entry."""

    type: str
    data: dict[str, Any]
    timestamp: str


class FeedPageResponse(BaseModel):
    """Paginated historical feed response."""

    events: list[dict[str, Any]]
    total: int
    page: int
    limit: int
    has_more: bool


# ---------------------------------------------------------------------------
# Artifact models
# ---------------------------------------------------------------------------


class ArtifactResponse(BaseModel):
    """Generic artifact file response (e.g. final report)."""

    project_name: str
    content: str
    generated: bool = False


# ---------------------------------------------------------------------------
# Settings models
# ---------------------------------------------------------------------------


class SettingsResponse(BaseModel):
    """Project settings — LiteLLM and simulation tunables."""

    litellm_base_url: str
    litellm_api_key: str
    litellm_model: str
    max_parallel_agents: int
    memory_compression_interval: str
    webhook_url: Optional[str] = None
    max_token_budget: Optional[int] = None


# ---------------------------------------------------------------------------
# Request bodies (kept here for single-source-of-truth)
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Request body for POST /api/projects."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique project identifier (alphanumeric, hyphens, underscores)",
    )
    industry: Optional[str] = Field(default="Manufacturing")
    scope: Optional[str] = Field(default=None)
    methodology: Optional[str] = Field(default=None)


class StartSimulationRequest(BaseModel):
    """Optional config override when starting a simulation."""

    max_parallel_agents: Optional[int] = Field(default=None, ge=1, le=30)
    tick_interval_seconds: Optional[float] = Field(default=None, gt=0.0)


class SettingsUpdateRequest(BaseModel):
    """Body for PUT /api/projects/{project_name}/settings."""

    litellm_base_url: Optional[str] = None
    litellm_api_key: Optional[str] = None
    litellm_model: Optional[str] = None
    max_parallel_agents: Optional[int] = Field(default=None, ge=1, le=30)
    memory_compression_interval: Optional[str] = None
    webhook_url: Optional[str] = None
    max_token_budget: Optional[int] = None


class TestSettingsRequest(BaseModel):
    """Body for POST /api/settings/test — test any LiteLLM endpoint."""

    litellm_base_url: str
    litellm_api_key: str
    litellm_model: str


class TestSettingsResponse(BaseModel):
    """Result of a settings connectivity test."""

    success: bool
    latency_ms: Optional[float] = None
    model_used: Optional[str] = None
    error: Optional[str] = None


class RerollRequest(BaseModel):
    """Body for POST /agents/reroll — optionally target a specific agent."""

    codename: Optional[str] = Field(
        default=None,
        description="Codename to re-roll; omit to re-roll all customers",
    )


class ProposeDecisionRequest(BaseModel):
    """Body for POST /api/projects/{project_name}/decisions — propose a new decision."""

    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1)
    category: str = Field(
        default="technical",
        description="One of: technical, functional, organizational, budget",
    )
    proposed_by: str = Field(..., description="Codename or name of the proposing agent/user")
    proposed_at_day: int = Field(default=0, ge=0)
    rationale: Optional[str] = Field(default="")
    impact_assessment: Optional[str] = Field(default="")
    related_meeting_id: Optional[str] = Field(default=None)


class ArtifactReportRequest(BaseModel):
    """Body for POST /api/projects/{project_name}/artifacts/report — trigger report generation."""

    force_regenerate: bool = Field(
        default=False,
        description="When True, overwrite any existing report on disk.",
    )


class TokenBudgetRequest(BaseModel):
    """Body for POST /api/admin/token-budget."""

    project_name: str
    max_tokens: Optional[int] = None


class TokenUsageResponse(BaseModel):
    """Token usage breakdown by agent and tier."""

    project_name: str
    total_used: int
    budget: Optional[int] = None
    remaining: Optional[int] = None
    by_agent: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Admin / operator models
# ---------------------------------------------------------------------------


class AdminHealthResponse(BaseModel):
    """Aggregate backend health for operator monitoring."""

    status: str
    active_projects: int
    active_agents: int
    tokens_per_minute: float
    total_tokens_used: int
    phase_summaries: list[dict[str, Any]] = Field(default_factory=list)
    uptime_seconds: float


class AdminHighlightsResponse(BaseModel):
    """Last N significant simulation events."""

    highlights: list[dict[str, Any]]
    total: int


# ---------------------------------------------------------------------------
# Stakeholder / executive view
# ---------------------------------------------------------------------------


class StakeholderView(BaseModel):
    """Curated executive summary for the stakeholder dashboard panel."""

    project_name: str
    status: str
    health_score: float = Field(ge=0, le=100, description="0-100 overall project health")
    current_phase: str
    phase_progress_pct: float
    simulated_day: int
    total_days: int
    active_agent_count: int
    pending_escalations: list[dict[str, Any]] = Field(default_factory=list)
    top_decisions: list[dict[str, Any]] = Field(default_factory=list)
    latest_milestone: Optional[dict[str, Any]] = None
    agent_leaderboard: list[dict[str, Any]] = Field(default_factory=list)
    phase_breakdown: list[PhaseProgress] = Field(default_factory=list)
    last_updated: str
