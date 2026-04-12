/**
 * SAP SIM — Typed API Client
 * Phase: 6.1
 * Purpose: Single-source fetch() wrapper for every backend endpoint.
 *          Configurable BASE_URL (default http://localhost:8000/api).
 *          All methods return typed responses from lib/types.ts.
 */

import type {
  AdminHealthResponse,
  AdminHighlightsResponse,
  AgentDetailResponse,
  AgentResponse,
  ArtifactReportRequest,
  ArtifactResponse,
  CreateProjectRequest,
  DecisionResponse,
  FeedPageResponse,
  LessonResponse,
  MeetingDetailResponse,
  MeetingResponse,
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
} from './types'

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api'

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message?: string,
  ) {
    super(message ?? `API error ${status}`)
    this.name = 'ApiError'
  }
}

async function request<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${baseUrl.replace(/\/+$/, '')}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (!res.ok) {
    let body: unknown
    try {
      body = await res.json()
    } catch {
      body = await res.text()
    }
    throw new ApiError(res.status, body, `${res.status} ${res.statusText} — ${path}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// API Client class
// ---------------------------------------------------------------------------

export class SapSimApiClient {
  private readonly baseUrl: string

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl
  }

  // ── helpers ────────────────────────────────────────────────────────────

  private get<T>(path: string): Promise<T> {
    return request<T>(this.baseUrl, path, { method: 'GET' })
  }

  private post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(this.baseUrl, path, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }

  private put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(this.baseUrl, path, {
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }

  private delete<T = void>(path: string): Promise<T> {
    return request<T>(this.baseUrl, path, { method: 'DELETE' })
  }

  // ── Health ──────────────────────────────────────────────────────────────

  /** GET /health — top-level liveness check */
  health(): Promise<{ status: string; service: string }> {
    // Health lives outside /api on the backend
    return request(this.baseUrl.replace(/\/api\/?$/, ''), '/health')
  }

  // ── Projects ────────────────────────────────────────────────────────────

  /** GET /api/projects — list all projects */
  getProjects(): Promise<ProjectListResponse[]> {
    return this.get('/projects')
  }

  /** GET /api/projects/:name — full project state */
  getProject(projectName: string): Promise<ProjectResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}`)
  }

  /** POST /api/projects — create a new project */
  createProject(req: CreateProjectRequest): Promise<ProjectResponse> {
    return this.post('/projects', req)
  }

  /** DELETE /api/projects/:name — delete a project and all its data */
  deleteProject(projectName: string): Promise<void> {
    return this.delete(`/projects/${encodeURIComponent(projectName)}`)
  }

  // ── Simulation control ──────────────────────────────────────────────────

  /** POST /api/projects/:name/start — start simulation */
  startSimulation(
    projectName: string,
    req: StartSimulationRequest = {},
  ): Promise<ProjectResponse> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/start`, req)
  }

  /** POST /api/projects/:name/pause — pause a running simulation */
  pauseSimulation(projectName: string): Promise<ProjectResponse> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/pause`)
  }

  /** POST /api/projects/:name/resume — resume a paused simulation */
  resumeSimulation(projectName: string): Promise<ProjectResponse> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/resume`)
  }

  /** POST /api/projects/:name/stop — stop (and save) simulation */
  stopSimulation(projectName: string): Promise<ProjectResponse> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/stop`)
  }

  // ── Simulation status ───────────────────────────────────────────────────

  /** GET /api/projects/:name/simulation/status — engine-level status */
  getStatus(projectName: string): Promise<SimulationStatusResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/simulation/status`)
  }

  // ── Agents ──────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/agents — list all 30 agents with current status */
  getAgents(projectName: string): Promise<AgentResponse[]> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/agents`)
  }

  /** GET /api/projects/:name/agents/:codename — full agent detail */
  getAgent(projectName: string, codename: string): Promise<AgentDetailResponse> {
    return this.get(
      `/projects/${encodeURIComponent(projectName)}/agents/${encodeURIComponent(codename)}`,
    )
  }

  /** POST /api/projects/:name/agents/reroll — re-roll customer personalities */
  rerollAgents(projectName: string, req: RerollRequest = {}): Promise<AgentResponse[]> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/agents/reroll`, req)
  }

  // ── Meetings ─────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/meetings — list all meeting logs */
  getMeetings(projectName: string): Promise<MeetingResponse[]> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/meetings`)
  }

  /** GET /api/projects/:name/meetings/:id — full meeting detail */
  getMeeting(projectName: string, meetingId: string): Promise<MeetingDetailResponse> {
    return this.get(
      `/projects/${encodeURIComponent(projectName)}/meetings/${encodeURIComponent(meetingId)}`,
    )
  }

  // ── Decisions ────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/decisions — decision board grouped by status */
  getDecisions(projectName: string): Promise<DecisionResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/decisions`)
  }

  /** POST /api/projects/:name/decisions — propose a new decision */
  proposeDecision(
    projectName: string,
    req: ProposeDecisionRequest,
  ): Promise<DecisionResponse> {
    return this.post(`/projects/${encodeURIComponent(projectName)}/decisions`, req)
  }

  // ── Tools ────────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/tools — tool registry */
  getTools(projectName: string): Promise<ToolResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/tools`)
  }

  // ── Test strategy ─────────────────────────────────────────────────────────

  /** GET /api/projects/:name/test-strategy — live test strategy document */
  getTestStrategy(projectName: string): Promise<TestCaseResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/test-strategy`)
  }

  // ── Lessons learned ───────────────────────────────────────────────────────

  /** GET /api/projects/:name/lessons — lessons learned log */
  getLessons(projectName: string): Promise<LessonResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/lessons`)
  }

  // ── Feed ──────────────────────────────────────────────────────────────────

  /**
   * GET /api/projects/:name/feed — paginated historical feed
   * @param page  1-based page number
   * @param limit events per page (1–500)
   * @param eventType optional filter by event type string
   */
  getFeed(
    projectName: string,
    page = 1,
    limit = 50,
    eventType?: string,
  ): Promise<FeedPageResponse> {
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    })
    if (eventType) params.set('event_type', eventType)
    return this.get(
      `/projects/${encodeURIComponent(projectName)}/feed?${params.toString()}`,
    )
  }

  // ── Report ────────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/report — return (or generate) the final report */
  getReport(projectName: string): Promise<ArtifactResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/report`)
  }

  /** POST /api/projects/:name/artifacts/report — trigger full report generation */
  generateReport(
    projectName: string,
    req: ArtifactReportRequest = {},
  ): Promise<ArtifactResponse> {
    return this.post(
      `/projects/${encodeURIComponent(projectName)}/artifacts/report`,
      req,
    )
  }

  // ── Stakeholder view ──────────────────────────────────────────────────────

  /** GET /api/projects/:name/stakeholder — executive summary */
  getStakeholderView(projectName: string): Promise<StakeholderView> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/stakeholder`)
  }

  // ── Settings ──────────────────────────────────────────────────────────────

  /** GET /api/projects/:name/settings */
  getSettings(projectName: string): Promise<SettingsResponse> {
    return this.get(`/projects/${encodeURIComponent(projectName)}/settings`)
  }

  /** PUT /api/projects/:name/settings */
  updateSettings(
    projectName: string,
    req: SettingsUpdateRequest,
  ): Promise<SettingsResponse> {
    return this.put(`/projects/${encodeURIComponent(projectName)}/settings`, req)
  }

  /** POST /api/settings/test — test a LiteLLM endpoint */
  testSettings(req: TestSettingsRequest): Promise<TestSettingsResponse> {
    return this.post('/settings/test', req)
  }

  // ── Admin ─────────────────────────────────────────────────────────────────

  /** GET /api/admin/health — aggregate backend health */
  getAdminHealth(): Promise<AdminHealthResponse> {
    return this.get('/admin/health')
  }

  /** GET /api/admin/highlights — last N significant events */
  getAdminHighlights(n = 20, projectName?: string): Promise<AdminHighlightsResponse> {
    const params = new URLSearchParams({ n: String(n) })
    if (projectName) params.set('project_name', projectName)
    return this.get(`/admin/highlights?${params.toString()}`)
  }

  /** GET /api/admin/token-usage */
  getTokenUsage(projectName: string): Promise<TokenUsageResponse> {
    return this.get(`/admin/token-usage?project_name=${encodeURIComponent(projectName)}`)
  }

  /** POST /api/admin/token-budget */
  setTokenBudget(req: TokenBudgetRequest): Promise<{ project_name: string; max_token_budget: number | null }> {
    return this.post('/admin/token-budget', req)
  }

  // ── SSE stream URL helper ─────────────────────────────────────────────────

  /**
   * Returns the full SSE stream URL for a project.
   * Use this with `new EventSource(api.streamUrl('my-project'))`.
   */
  streamUrl(projectName: string): string {
    return `${this.baseUrl.replace(/\/+$/, '')}/stream/${encodeURIComponent(projectName)}`
  }
}

// ---------------------------------------------------------------------------
// Default singleton
// ---------------------------------------------------------------------------

/** Pre-built client using NEXT_PUBLIC_API_URL or http://localhost:8000/api */
export const api = new SapSimApiClient()

export { ApiError }
