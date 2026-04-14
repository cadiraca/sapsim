'use client'

import React, { useCallback, useEffect, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Users,
  CheckCircle2,
  Wrench,
  FileText,
  Lightbulb,
  AlertCircle,
  Loader2,
  InboxIcon,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useProject } from '@/lib/project-context'
import type {
  Meeting,
  MeetingDetailResponse,
  DecisionResponse,
  DecisionItem,
  ToolItem,
  ToolResponse,
  TestCaseResponse,
  TestCase,
  LessonResponse,
  Lesson,
} from '@/lib/types'
import { cn } from '@/lib/utils'

type TabType = 'meetings' | 'decisions' | 'tools' | 'test-strategy' | 'lessons'

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-[#71717a]">
      <Loader2 className="h-5 w-5 animate-spin" />
      <span className="text-xs">{label}</span>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-[#71717a]">
      <AlertCircle className="h-5 w-5 text-[#ef4444]" />
      <span className="text-xs text-center text-[#ef4444]">{message}</span>
      <button
        onClick={onRetry}
        className="text-xs text-[#3b82f6] hover:underline"
      >
        Retry
      </button>
    </div>
  )
}

function EmptyState({
  label,
  icon,
  message,
}: {
  label?: string
  icon?: React.ReactNode
  message?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-[#71717a]">
      {icon ?? <InboxIcon className="h-5 w-5" />}
      <span className="text-xs text-center">{message ?? label ?? 'Nothing here yet'}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status badge helpers
// ---------------------------------------------------------------------------

const MEETING_STATUS_COLORS: Record<string, string> = {
  completed: 'bg-[#22c55e]/20 text-[#22c55e]',
  in_progress: 'bg-[#3b82f6]/20 text-[#3b82f6]',
  scheduled: 'bg-[#71717a]/20 text-[#71717a]',
}

const DECISION_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-[#71717a]/20 text-[#71717a]',
  proposed: 'bg-[#3b82f6]/20 text-[#3b82f6]',
  approved: 'bg-[#22c55e]/20 text-[#22c55e]',
  rejected: 'bg-[#ef4444]/20 text-[#ef4444]',
  deferred: 'bg-[#f59e0b]/20 text-[#f59e0b]',
}

const DECISION_IMPACT_COLORS: Record<string, string> = {
  Low: 'bg-[#22c55e]/20 text-[#22c55e]',
  Medium: 'bg-[#f59e0b]/20 text-[#f59e0b]',
  High: 'bg-[#ef4444]/20 text-[#ef4444]',
  Critical: 'bg-[#ef4444] text-white',
}

// ---------------------------------------------------------------------------
// Meetings tab
// ---------------------------------------------------------------------------

function MeetingItem({ meeting, projectName }: { meeting: Meeting; projectName: string }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState<MeetingDetailResponse | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const handleExpand = async () => {
    const next = !expanded
    setExpanded(next)
    if (next && !detail && !loadingDetail) {
      setLoadingDetail(true)
      setDetailError(null)
      try {
        const data = await api.getMeeting(projectName, meeting.id)
        setDetail(data)
      } catch (err) {
        setDetailError(err instanceof Error ? err.message : 'Failed to load transcript')
      } finally {
        setLoadingDetail(false)
      }
    }
  }

  // Derive a display status: if duration_turns > 0 assume completed
  const status = meeting.duration_turns > 0 ? 'completed' : 'scheduled'
  const statusLabel = status === 'completed' ? 'Completed' : 'Scheduled'

  return (
    <div className="border border-[#27272a] rounded-lg overflow-hidden">
      <button
        onClick={handleExpand}
        className="w-full flex items-center gap-3 p-3 hover:bg-[#27272a]/50 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-[#71717a] shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[#71717a] shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">{meeting.title}</div>
          <div className="flex items-center gap-2 text-[10px] text-[#71717a] mt-0.5">
            <span>{meeting.phase} Phase</span>
            <span>·</span>
            <span>Day {meeting.simulated_day}</span>
            <span>·</span>
            <span>{meeting.duration_turns} turns</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={cn(
              'px-1.5 py-0.5 rounded text-[9px] font-medium',
              MEETING_STATUS_COLORS[status] ?? 'bg-[#71717a]/20 text-[#71717a]',
            )}
          >
            {statusLabel}
          </span>
          {meeting.decisions_count > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-[#f59e0b]/20 text-[#f59e0b]">
              {meeting.decisions_count} decision{meeting.decisions_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-[#27272a] space-y-3 text-xs">
          {/* Facilitator + participants */}
          <div>
            <h4 className="font-medium text-[#71717a] mb-1">Participants</h4>
            <div className="flex flex-wrap gap-1">
              {meeting.participants.map((p) => (
                <span
                  key={p}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[9px] font-medium',
                    p === meeting.facilitator
                      ? 'bg-[#3b82f6]/20 text-[#3b82f6]'
                      : 'bg-[#27272a] text-[#a1a1aa]',
                  )}
                >
                  {p === meeting.facilitator ? `★ ${p}` : p}
                </span>
              ))}
            </div>
          </div>

          {/* Detail: loading / error / content */}
          {loadingDetail && (
            <div className="flex items-center gap-2 text-[#71717a]">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Loading transcript…</span>
            </div>
          )}

          {detailError && (
            <div className="flex items-center gap-2 text-[#ef4444]">
              <AlertCircle className="h-3 w-3" />
              <span>{detailError}</span>
            </div>
          )}

          {detail && (
            <>
              {detail.agenda && detail.agenda.length > 0 && (
                <div>
                  <h4 className="font-medium text-[#71717a] mb-1">Agenda</h4>
                  <ul className="space-y-0.5 text-[#e4e4e7]">
                    {detail.agenda.map((item, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-[#3b82f6]">•</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.transcript && detail.transcript.length > 0 && (
                <div>
                  <h4 className="font-medium text-[#71717a] mb-1">Transcript</h4>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {detail.transcript.map((turn, i) => (
                      <div key={i} className="text-[10px]">
                        <span className="text-[#3b82f6] font-medium">{turn.speaker}: </span>
                        <span className="text-[#e4e4e7]">{turn.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {detail.decisions && detail.decisions.length > 0 && (
                <div>
                  <h4 className="font-medium text-[#71717a] mb-1">Decisions</h4>
                  <ul className="space-y-0.5 text-[#e4e4e7]">
                    {detail.decisions.map((item, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-[#22c55e]">✓</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {detail.action_items && detail.action_items.length > 0 && (
                <div>
                  <h4 className="font-medium text-[#71717a] mb-1">Action Items</h4>
                  <ul className="space-y-0.5 text-[#e4e4e7]">
                    {detail.action_items.map((item, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-[#a855f7]">→</span>
                        {typeof item === 'string' ? item : JSON.stringify(item)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function MeetingsTab({ projectName }: { projectName: string }) {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getMeetings(projectName)
      setMeetings(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load meetings')
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => { load() }, [load])

  if (loading) return <LoadingState label="Loading meetings…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (meetings.length === 0) return <EmptyState label="No meetings yet" />

  return (
    <div className="space-y-2 h-full overflow-y-auto">
      {meetings.map((meeting) => (
        <MeetingItem key={meeting.id} meeting={meeting} projectName={projectName} />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Decisions tab
// ---------------------------------------------------------------------------

function DecisionCard({ decision }: { decision: DecisionItem }) {
  return (
    <div className="p-2.5 bg-[#27272a]/50 border border-[#27272a] rounded-lg">
      <div className="text-xs font-medium text-white mb-1 line-clamp-2">{decision.title}</div>
      <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
        {decision.impact_assessment && (
          <span
            className={cn(
              'px-1.5 py-0.5 rounded text-[9px] font-medium',
              DECISION_IMPACT_COLORS[decision.impact_assessment] ?? 'bg-[#71717a]/20 text-[#71717a]',
            )}
          >
            {decision.impact_assessment}
          </span>
        )}
        <span
          className={cn(
            'px-1.5 py-0.5 rounded text-[9px] font-medium',
            DECISION_STATUS_COLORS[decision.status] ?? 'bg-[#71717a]/20 text-[#71717a]',
          )}
        >
          {decision.status}
        </span>
      </div>
      {decision.description && (
        <p className="text-[10px] text-[#71717a] line-clamp-2 mb-1.5">{decision.description}</p>
      )}
      <div className="flex items-center justify-between text-[9px] text-[#71717a]">
        <span>By: {decision.proposed_by}</span>
        <span>Day {decision.proposed_at_day}</span>
      </div>
    </div>
  )
}

function DecisionsTab({ projectName }: { projectName: string }) {
  const [data, setData] = useState<DecisionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getDecisions(projectName)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load decisions')
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => { load() }, [load])

  if (loading) return <LoadingState label="Loading decisions…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data || data.total === 0) return <EmptyState label="No decisions yet" />

  const columns: { key: keyof Omit<DecisionResponse, 'total'>; label: string }[] = [
    { key: 'pending', label: 'Pending' },
    { key: 'approved', label: 'Approved' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'deferred', label: 'Deferred' },
  ]

  return (
    <div className="flex gap-2 h-full overflow-x-auto pb-2">
      {columns.map(({ key, label }) => {
        const items = data[key] as DecisionItem[]
        return (
          <div key={key} className="flex-1 min-w-[140px] flex flex-col">
            <div className="flex items-center justify-between text-xs font-medium text-[#71717a] mb-2 px-1">
              <span>{label}</span>
              {items.length > 0 && (
                <span className="text-[9px] bg-[#27272a] px-1.5 py-0.5 rounded-full">
                  {items.length}
                </span>
              )}
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto">
              {items.length === 0 ? (
                <div className="text-[10px] text-[#52525b] text-center py-4">—</div>
              ) : (
                items.map((decision) => (
                  <DecisionCard key={decision.id} decision={decision} />
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tools tab — grouped by category
// ---------------------------------------------------------------------------

function ToolCard({ tool }: { tool: ToolItem }) {
  return (
    <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg border-l-2 border-l-[#a855f7]">
      <div className="flex items-center gap-2 mb-2">
        <Wrench className="h-4 w-4 text-[#a855f7] shrink-0" />
        <span className="text-sm font-medium text-white truncate">{tool.name}</span>
      </div>
      <p className="text-xs text-[#e4e4e7] mb-2">{tool.description}</p>
      <div className="flex items-center justify-between text-[10px] text-[#71717a]">
        <div className="flex items-center gap-1">
          <span>By:</span>
          <span className="text-[#a1a1aa]">{tool.created_by}</span>
        </div>
        {tool.used_by && tool.used_by.length > 0 && (
          <div className="flex items-center gap-1">
            <span>Used by</span>
            <span className="text-[#a1a1aa]">{tool.used_by.length}</span>
            <span>agent{tool.used_by.length !== 1 ? 's' : ''}</span>
          </div>
        )}
        {tool.created_at_day !== undefined && (
          <span>Day {tool.created_at_day}</span>
        )}
      </div>
    </div>
  )
}

function ToolsTab({ projectName }: { projectName: string }) {
  const [data, setData] = useState<ToolResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getTools(projectName)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tools')
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => { load() }, [load])

  if (loading) return <LoadingState label="Loading tools…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data || data.total === 0) return <EmptyState label="No tools invented yet" />

  // Group by category (use tool.category field if present, else 'General')
  const grouped = data.tools.reduce<Record<string, ToolItem[]>>((acc, tool) => {
    const cat = (tool['category'] as string | undefined) ?? 'General'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(tool)
    return acc
  }, {})

  return (
    <div className="space-y-4 overflow-y-auto">
      {/* Summary bar */}
      <div className="flex items-center justify-between text-[10px] text-[#71717a] bg-[#27272a]/30 rounded px-2 py-1.5">
        <span>{data.total} tool{data.total !== 1 ? 's' : ''} in registry</span>
        <span>{Object.keys(grouped).length} categor{Object.keys(grouped).length !== 1 ? 'ies' : 'y'}</span>
      </div>

      {Object.entries(grouped).map(([category, tools]) => (
        <div key={category}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-semibold text-[#a855f7] uppercase tracking-wider">
              {category}
            </span>
            <div className="flex-1 h-px bg-[#27272a]" />
            <span className="text-[9px] text-[#52525b]">{tools.length}</span>
          </div>
          <div className="space-y-2">
            {tools.map((tool) => (
              <ToolCard key={tool.id} tool={tool} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Test Strategy tab — live data from /api/projects/:name/test-strategy
// ---------------------------------------------------------------------------

function TestStrategyTab({ projectName }: { projectName: string }) {
  const [data, setData] = useState<TestCaseResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getTestStrategy(projectName)
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load test strategy')
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <LoadingState label="Loading test strategy…" />
  if (error) return <ErrorState message={error} onRetry={loadData} />
  if (!data) return <EmptyState icon={<FileText className="h-5 w-5" />} message="No test strategy yet" />

  const tests: TestCase[] = data.tests ?? []
  const coverage = data.overall_progress ?? 0

  const statusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'passed': return 'text-[#22c55e] bg-[#22c55e]/10'
      case 'failed': return 'text-[#ef4444] bg-[#ef4444]/10'
      case 'blocked': return 'text-[#f59e0b] bg-[#f59e0b]/10'
      default: return 'text-[#71717a] bg-[#27272a]'
    }
  }

  return (
    <div className="space-y-3 h-full overflow-y-auto">
      {/* Coverage header */}
      <div className="p-2 bg-[#1c1c1f] rounded space-y-1">
        <div className="flex justify-between items-center">
          <span className="text-[10px] text-[#71717a]">Overall Coverage</span>
          <span className="text-[10px] font-semibold text-white">{Math.round(coverage)}%</span>
        </div>
        <div className="h-1.5 bg-[#27272a] rounded-full overflow-hidden">
          <div
            className="h-full bg-[#3b82f6] rounded-full transition-all duration-500"
            style={{ width: `${coverage}%` }}
          />
        </div>
        {data.last_updated && (
          <p className="text-[9px] text-[#71717a]">
            Updated: {new Date(data.last_updated).toLocaleDateString()}
          </p>
        )}
      </div>

      {/* Scope */}
      {data.scope?.length > 0 && (
        <div>
          <h4 className="text-[9px] font-medium text-[#71717a] uppercase mb-1">Scope</h4>
          <div className="flex flex-wrap gap-1">
            {data.scope.map((s, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-[#27272a] text-[#e4e4e7] text-[9px] rounded">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Test cases table */}
      {tests.length > 0 ? (
        <div>
          <h4 className="text-[9px] font-medium text-[#71717a] uppercase mb-1">Test Cases ({tests.length})</h4>
          <div className="space-y-1">
            {tests.map((tc) => (
              <div key={tc.id} className="flex items-center gap-2 p-1.5 bg-[#1c1c1f] rounded">
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-[#e4e4e7] truncate">{tc.name}</p>
                  {tc.module && <p className="text-[9px] text-[#71717a]">{tc.module}</p>}
                </div>
                <span className={cn('text-[8px] px-1.5 py-0.5 rounded font-medium shrink-0', statusColor(tc.status))}>
                  {tc.status ?? 'pending'}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState icon={<FileText className="h-4 w-4" />} message="No test cases yet. They'll appear as the simulation progresses." />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Lessons tab — live data from /api/projects/:name/lessons
// ---------------------------------------------------------------------------

type LessonsByPhase = Record<string, Lesson[]>

function LessonsTab({ projectName }: { projectName: string }) {
  const [data, setData] = useState<LessonResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getLessons(projectName)
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load lessons')
    } finally {
      setLoading(false)
    }
  }, [projectName])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <LoadingState label="Loading lessons…" />
  if (error) return <ErrorState message={error} onRetry={loadData} />
  if (!data || data.lessons.length === 0) {
    return <EmptyState icon={<Lightbulb className="h-5 w-5" />} message="Lessons will surface here as agents reflect on their work." />
  }

  // Group by phase
  const byPhase: LessonsByPhase = {}
  for (const lesson of data.lessons) {
    const phase = lesson.phase ?? 'General'
    if (!byPhase[phase]) byPhase[phase] = []
    byPhase[phase].push(lesson)
  }

  const categoryColor = (category: string) => {
    switch (category?.toLowerCase()) {
      case 'process': return 'bg-[#3b82f6]/10 text-[#3b82f6]'
      case 'technical': return 'bg-[#8b5cf6]/10 text-[#8b5cf6]'
      case 'people': return 'bg-[#f59e0b]/10 text-[#f59e0b]'
      case 'tools': return 'bg-[#22c55e]/10 text-[#22c55e]'
      default: return 'bg-[#27272a] text-[#71717a]'
    }
  }

  return (
    <div className="space-y-4 h-full overflow-y-auto">
      <div className="text-[9px] text-[#71717a]">{data.total} lesson{data.total !== 1 ? 's' : ''} recorded</div>
      {Object.entries(byPhase).map(([phase, lessons]) => (
        <div key={phase}>
          <h4 className="text-[9px] font-semibold text-[#71717a] uppercase mb-1.5 flex items-center gap-1">
            <span className="w-1 h-1 rounded-full bg-[#3b82f6] inline-block" />
            {phase} ({lessons.length})
          </h4>
          <div className="space-y-1.5">
            {lessons.map((lesson) => (
              <div key={lesson.id} className="p-2 bg-[#1c1c1f] rounded space-y-1">
                <div className="flex items-center gap-1.5">
                  <span className={cn('text-[8px] px-1.5 py-0.5 rounded font-medium', categoryColor(lesson.category))}>
                    {lesson.category}
                  </span>
                  <span className="text-[9px] text-[#71717a] ml-auto">Day {lesson.day}</span>
                </div>
                <p className="text-[11px] text-[#e4e4e7] leading-relaxed">{lesson.lesson}</p>
                <div className="flex items-center justify-between">
                  <span className="text-[9px] text-[#71717a] truncate">↑ {lesson.raised_by}</span>
                  {lesson.validation_count > 0 && (
                    <span className="text-[9px] text-[#22c55e]">✓ {lesson.validation_count}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root ContextPanel component
// ---------------------------------------------------------------------------

export function ContextPanel() {
  const { activeProject } = useProject()
  const projectName = activeProject ?? ''
  const [activeTab, setActiveTab] = useState<TabType>('meetings')

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'meetings', label: 'Meetings', icon: <Users className="h-3 w-3" /> },
    { id: 'decisions', label: 'Decisions', icon: <CheckCircle2 className="h-3 w-3" /> },
    { id: 'tools', label: 'Tools', icon: <Wrench className="h-3 w-3" /> },
    { id: 'test-strategy', label: 'Test Strategy', icon: <FileText className="h-3 w-3" /> },
    { id: 'lessons', label: 'Lessons', icon: <Lightbulb className="h-3 w-3" /> },
  ]

  return (
    <section className="w-[340px] bg-[#18181b] border-l border-[#27272a] flex flex-col shrink-0 overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-[#27272a] shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1 py-2.5 text-[10px] font-medium transition-colors border-b-2',
              activeTab === tab.id
                ? 'text-white border-[#3b82f6]'
                : 'text-[#71717a] border-transparent hover:text-white',
            )}
          >
            {tab.icon}
            <span className="hidden xl:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-3">
        {activeTab === 'meetings' && <MeetingsTab projectName={projectName} />}
        {activeTab === 'decisions' && <DecisionsTab projectName={projectName} />}
        {activeTab === 'tools' && <ToolsTab projectName={projectName} />}
        {activeTab === 'test-strategy' && <TestStrategyTab projectName={projectName} />}
        {activeTab === 'lessons' && <LessonsTab projectName={projectName} />}
      </div>
    </section>
  )
}
