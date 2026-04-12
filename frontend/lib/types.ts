/**
 * SAP SIM — TypeScript Interfaces
 * Phase: 6.1
 * Purpose: Typed interfaces matching backend Pydantic models (api/models.py).
 *          Import these everywhere instead of using `any` or inline shapes.
 */

// ---------------------------------------------------------------------------
// Shared enums / primitives
// ---------------------------------------------------------------------------

export type SimulationStatus = 'IDLE' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'STOPPED'

export type AgentSide = 'consultant' | 'customer' | 'crossfunctional'

export type AgentTier = 'strategic' | 'senior' | 'operational' | 'basic'

export type AgentStatus = 'idle' | 'thinking' | 'speaking' | 'in_meeting'

export type DecisionStatus = 'pending' | 'proposed' | 'approved' | 'rejected' | 'deferred'

export type DecisionImpact = 'Low' | 'Medium' | 'High' | 'Critical'

export type LessonCategory = 'Process' | 'Technical' | 'People' | 'Tools'

export type SapActivatePhase =
  | 'discover'
  | 'prepare'
  | 'explore'
  | 'realize'
  | 'deploy'
  | 'run'
  | 'Discover'
  | 'Prepare'
  | 'Explore'
  | 'Realize'
  | 'Deploy'
  | 'Run'

// ---------------------------------------------------------------------------
// Phase helpers
// ---------------------------------------------------------------------------

export interface PhaseInfo {
  id: string
  name: string
  duration_days: number
}

export interface PhaseProgress {
  phase_id: string
  phase_name: string
  percentage: number
  is_current: boolean
  is_completed: boolean
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export interface ErrorResponse {
  error: string
  detail: string
  code: string
}

// ---------------------------------------------------------------------------
// Project
// ---------------------------------------------------------------------------

export interface ProjectResponse {
  project_name: string
  status: SimulationStatus
  current_phase: string
  simulated_day: number
  total_days: number
  phase_progress: PhaseProgress[]
  active_agents: string[]
  pending_decisions: Record<string, unknown>[]
  active_meetings: Record<string, unknown>[]
  milestones: Record<string, unknown>[]
  industry: string | null
  scope: string | null
  methodology: string | null
  created_at: string
  last_updated: string
}

export interface ProjectListResponse {
  name: string
  status: SimulationStatus
  current_phase: string
  simulated_day: number
  total_days: number
  industry: string | null
  created_at: string
  last_updated: string
}

export interface CreateProjectRequest {
  name: string
  industry?: string
  scope?: string
  methodology?: string
}

// ---------------------------------------------------------------------------
// Simulation status
// ---------------------------------------------------------------------------

export interface SimulationStatusResponse {
  project_name: string
  status: SimulationStatus
  current_phase: string
  simulated_day: number
  total_days: number
  overall_progress: number
  phase_progress: Record<string, number>
  active_agents: string[]
  tick_count: number
  tick_interval_seconds: number
  loop_running: boolean
  pending_decisions: Record<string, unknown>[]
  milestones: Record<string, unknown>[]
  injected_failures: Record<string, unknown>[]
  last_updated: number
}

export interface StartSimulationRequest {
  max_parallel_agents?: number
  tick_interval_seconds?: number
}

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

export interface AgentPersonality {
  engagement: number   // 1–5
  trust: number        // 1–5
  risk_tolerance: number  // 1–5
  archetype: string
  history: Record<string, unknown>[]
}

export interface Agent {
  codename: string
  role: string
  side: AgentSide
  tier: AgentTier
  model: string
  status: AgentStatus
  current_task: string | null
  personality: AgentPersonality | null
}

/** Alias for list context */
export type AgentResponse = Agent

export interface AgentDetailResponse extends Agent {
  skills: string[]
  memory_turns: number
  memory_summary: string | null
  recent_activity: Record<string, unknown>[]
}

export interface AgentListResponse {
  agents: Agent[]
  total: number
}

export interface RerollRequest {
  codename?: string
}

// ---------------------------------------------------------------------------
// Meeting
// ---------------------------------------------------------------------------

export interface TranscriptTurn {
  speaker: string
  text: string
}

export interface Meeting {
  id: string
  title: string
  phase: string
  simulated_day: number
  facilitator: string
  participants: string[]
  duration_turns: number
  decisions_count: number
}

export type MeetingResponse = Meeting

export interface MeetingDetailResponse extends Meeting {
  agenda: string[]
  transcript: TranscriptTurn[]
  decisions: string[]
  action_items: Record<string, unknown>[]
  markdown_path: string | null
}

// ---------------------------------------------------------------------------
// Decision
// ---------------------------------------------------------------------------

/** Raw decision dict shape (items inside DecisionResponse lists) */
export interface DecisionItem {
  id: string
  title: string
  description: string
  category: string
  proposed_by: string
  proposed_at_day: number
  status: DecisionStatus
  rationale?: string
  impact_assessment?: string
  related_meeting_id?: string | null
  [key: string]: unknown
}

export interface DecisionResponse {
  pending: DecisionItem[]
  approved: DecisionItem[]
  rejected: DecisionItem[]
  deferred: DecisionItem[]
  total: number
}

export interface ProposeDecisionRequest {
  title: string
  description: string
  category?: string
  proposed_by: string
  proposed_at_day?: number
  rationale?: string
  impact_assessment?: string
  related_meeting_id?: string | null
}

// ---------------------------------------------------------------------------
// Tool registry
// ---------------------------------------------------------------------------

export interface ToolItem {
  id: string
  name: string
  description: string
  created_by: string
  created_at_day?: number
  used_by?: string[]
  [key: string]: unknown
}

export interface ToolResponse {
  tools: ToolItem[]
  total: number
}

// ---------------------------------------------------------------------------
// Test strategy / test cases
// ---------------------------------------------------------------------------

export interface TestCase {
  id: string
  name: string
  description?: string
  status?: string
  module?: string
  [key: string]: unknown
}

export interface TestCaseResponse {
  scope: string[]
  test_types: Record<string, unknown>[]
  uat_plan: Record<string, unknown>
  defect_process: string
  overall_progress: number
  last_updated: string | null
  coverage: Record<string, unknown> | null
  tests: TestCase[]
}

// ---------------------------------------------------------------------------
// Lessons learned
// ---------------------------------------------------------------------------

export interface Lesson {
  id: string
  raised_by: string
  phase: string
  day: number
  category: string
  lesson: string
  validation_count: number
  validated_by: string[]
}

/** Alias used in some places */
export type LessonEntry = Lesson

export interface LessonResponse {
  lessons: Lesson[]
  total: number
}

// ---------------------------------------------------------------------------
// Feed / SSE
// ---------------------------------------------------------------------------

export type FeedEventType =
  | 'CONNECTED'
  | 'SIMULATION_STARTED'
  | 'SIMULATION_PAUSED'
  | 'SIMULATION_RESUMED'
  | 'SIMULATION_STOPPED'
  | 'SIMULATION_COMPLETED'
  | 'PROJECT_CREATED'
  | 'AGENT_MSG'
  | 'AGENT_STATUS'
  | 'MEETING_STARTED'
  | 'MEETING_ENDED'
  | 'DECISION_RAISED'
  | 'DECISION_APPROVED'
  | 'DECISION_REJECTED'
  | 'NEW_TOOL'
  | 'BLOCKER'
  | 'PHASE_TRANSITION'
  | 'LESSON_LEARNED'
  | string

export interface FeedEvent {
  type: FeedEventType
  data: Record<string, unknown>
  timestamp: string
}

/** Historical paginated feed entry */
export interface FeedEventResponse extends FeedEvent {}

export interface FeedPageResponse {
  events: FeedEvent[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

// ---------------------------------------------------------------------------
// Artifact / Report
// ---------------------------------------------------------------------------

export interface ArtifactResponse {
  project_name: string
  content: string
  generated: boolean
}

export interface ArtifactReportRequest {
  force_regenerate?: boolean
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface SettingsResponse {
  litellm_base_url: string
  litellm_api_key: string
  litellm_model: string
  max_parallel_agents: number
  memory_compression_interval: string
  webhook_url: string | null
  max_token_budget: number | null
}

export interface SettingsUpdateRequest {
  litellm_base_url?: string
  litellm_api_key?: string
  litellm_model?: string
  max_parallel_agents?: number
  memory_compression_interval?: string
  webhook_url?: string
  max_token_budget?: number
}

export interface TestSettingsRequest {
  litellm_base_url: string
  litellm_api_key: string
  litellm_model: string
}

export interface TestSettingsResponse {
  success: boolean
  latency_ms: number | null
  model_used: string | null
  error: string | null
}

// ---------------------------------------------------------------------------
// Stakeholder view
// ---------------------------------------------------------------------------

export interface StakeholderView {
  project_name: string
  status: SimulationStatus
  health_score: number
  current_phase: string
  phase_progress_pct: number
  simulated_day: number
  total_days: number
  active_agent_count: number
  pending_escalations: Record<string, unknown>[]
  top_decisions: Record<string, unknown>[]
  latest_milestone: Record<string, unknown> | null
  agent_leaderboard: Record<string, unknown>[]
  phase_breakdown: PhaseProgress[]
  last_updated: string
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export interface AdminHealthResponse {
  status: string
  active_projects: number
  active_agents: number
  tokens_per_minute: number
  total_tokens_used: number
  phase_summaries: Record<string, unknown>[]
  uptime_seconds: number
}

export interface AdminHighlightsResponse {
  highlights: Record<string, unknown>[]
  total: number
}

export interface TokenUsageResponse {
  project_name: string
  total_used: number
  budget: number | null
  remaining: number | null
  by_agent: Record<string, number>
  by_tier: Record<string, number>
}

export interface TokenBudgetRequest {
  project_name: string
  max_tokens: number | null
}
