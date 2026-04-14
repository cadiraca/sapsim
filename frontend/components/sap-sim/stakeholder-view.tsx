'use client'

import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, TrendingUp, UserCircle } from 'lucide-react'
import { api } from '@/lib/api'
import { useProject } from '@/lib/project-context'
import type { StakeholderView as StakeholderViewData, AgentDetailResponse } from '@/lib/types'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Gauge Ring
// ---------------------------------------------------------------------------

function GaugeRing({ value, label }: { value: number; label: string }) {
  const circumference = 2 * Math.PI * 28
  const strokeDashoffset = circumference - (value / 100) * circumference
  const statusColor =
    value >= 80 ? '#22c55e' : value >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-16 w-16">
        <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="28" fill="none" stroke="#27272a" strokeWidth="4" />
          <circle
            cx="32" cy="32" r="28" fill="none"
            stroke={statusColor} strokeWidth="4" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-white">{value}%</span>
        </div>
      </div>
      <span className="text-[10px] text-[#71717a] mt-1">{label}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Customer Agent Card — shows satisfaction/engagement/concerns
// ---------------------------------------------------------------------------

interface CustomerAgentCardProps {
  codename: string
  projectName: string
}

function CustomerAgentCard({ codename, projectName }: CustomerAgentCardProps) {
  const [agent, setAgent] = useState<AgentDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAgent(projectName, codename)
      .then(setAgent)
      .catch(() => setAgent(null))
      .finally(() => setLoading(false))
  }, [projectName, codename])

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-2 bg-[#1c1c1f] rounded">
        <Loader2 className="h-3 w-3 animate-spin text-[#71717a]" />
        <span className="text-[10px] text-[#71717a]">{codename}</span>
      </div>
    )
  }

  if (!agent) return null

  const satisfaction = agent.personality?.trust != null
    ? Math.round((agent.personality.trust / 5) * 100)
    : null
  const engagement = agent.personality?.engagement != null
    ? Math.round((agent.personality.engagement / 5) * 100)
    : null

  const satColor = satisfaction == null ? '#71717a' : satisfaction >= 70 ? '#22c55e' : satisfaction >= 40 ? '#f59e0b' : '#ef4444'
  const engColor = engagement == null ? '#71717a' : engagement >= 70 ? '#22c55e' : engagement >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <div className="p-2 bg-[#1c1c1f] rounded space-y-1.5">
      <div className="flex items-center gap-1.5">
        <div className="h-5 w-5 rounded-full bg-[#f59e0b]/20 text-[#f59e0b] flex items-center justify-center text-[8px] font-bold shrink-0">
          {codename.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-medium text-white truncate">{codename}</p>
          {agent.personality?.archetype && (
            <p className="text-[9px] text-[#71717a] truncate">{agent.personality.archetype}</p>
          )}
        </div>
        {agent.status === 'thinking' || agent.status === 'speaking' ? (
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] shrink-0" title="Active" />
        ) : null}
      </div>

      {/* Metrics */}
      <div className="flex gap-2">
        {satisfaction != null && (
          <div className="flex-1">
            <div className="flex justify-between mb-0.5">
              <span className="text-[8px] text-[#71717a]">Satisfaction</span>
              <span className="text-[8px]" style={{ color: satColor }}>{satisfaction}%</span>
            </div>
            <div className="h-1 bg-[#27272a] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${satisfaction}%`, backgroundColor: satColor }} />
            </div>
          </div>
        )}
        {engagement != null && (
          <div className="flex-1">
            <div className="flex justify-between mb-0.5">
              <span className="text-[8px] text-[#71717a]">Engagement</span>
              <span className="text-[8px]" style={{ color: engColor }}>{engagement}%</span>
            </div>
            <div className="h-1 bg-[#27272a] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${engagement}%`, backgroundColor: engColor }} />
            </div>
          </div>
        )}
      </div>

      {/* Memory summary as "concerns" */}
      {agent.memory_summary && (
        <p className="text-[9px] text-[#71717a] line-clamp-2 italic">"{agent.memory_summary}"</p>
      )}

      {/* Current task */}
      {agent.current_task && (
        <p className="text-[9px] text-[#3b82f6] truncate">↳ {agent.current_task}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Stakeholder View
// ---------------------------------------------------------------------------

export function StakeholderView() {
  const { activeProject } = useProject()
  const [data, setData] = useState<StakeholderViewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [customerAgents, setCustomerAgents] = useState<string[]>([])

  const phases = ['Discover', 'Prepare', 'Explore', 'Realize', 'Deploy', 'Run']

  const fetchData = useCallback(async () => {
    if (!activeProject) return
    try {
      setError(null)
      const [stakeholder, agents] = await Promise.all([
        api.getStakeholderView(activeProject),
        api.getAgents(activeProject),
      ])
      setData(stakeholder)
      // Pick top-4 customer agents for the detail cards
      const customers = agents
        .filter((a) => a.side === 'customer')
        .slice(0, 4)
        .map((a) => a.codename)
      setCustomerAgents(customers)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load stakeholder data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData, activeProject])

  // ── Loading state ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <aside className="w-[220px] bg-[#18181b] border-l border-[#27272a] flex flex-col shrink-0 overflow-hidden">
        <div className="p-3 border-b border-[#27272a]">
          <h2 className="text-xs font-semibold text-[#71717a]">STAKEHOLDER BRIEF</h2>
          <p className="text-[10px] text-[#71717a]/60">Executive summary view</p>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-[#71717a]">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-[10px]">Loading…</span>
          </div>
        </div>
      </aside>
    )
  }

  // ── Error / empty state ─────────────────────────────────────────────────
  if (error || !data) {
    return (
      <aside className="w-[220px] bg-[#18181b] border-l border-[#27272a] flex flex-col shrink-0 overflow-hidden">
        <div className="p-3 border-b border-[#27272a]">
          <h2 className="text-xs font-semibold text-[#71717a]">STAKEHOLDER BRIEF</h2>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="flex flex-col items-center gap-2 text-[#71717a] text-center">
            <AlertTriangle className="h-5 w-5 text-[#ef4444]" />
            <span className="text-[10px]">{error ?? 'No data yet'}</span>
            <button
              onClick={fetchData}
              className="text-[10px] text-[#3b82f6] underline"
            >
              Retry
            </button>
          </div>
        </div>
      </aside>
    )
  }

  // ── Derive display values ───────────────────────────────────────────────
  const healthScore = data.health_score ?? 0

  // Phase progress from breakdown
  const currentPhaseIndex = phases.findIndex(
    (p) => p.toLowerCase() === data.current_phase?.toLowerCase(),
  )

  // Escalations
  const escalations = (data.pending_escalations ?? []) as Record<string, string>[]

  // Recent decisions
  const topDecisions = (data.top_decisions ?? []) as Record<string, string>[]

  // Leaderboard
  const leaderboard = (data.agent_leaderboard ?? []) as Record<string, unknown>[]

  // Latest milestone
  const latestMilestone = data.latest_milestone as Record<string, string> | null

  return (
    <aside className="w-[220px] bg-[#18181b] border-l border-[#27272a] flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-[#27272a]">
        <h2 className="text-xs font-semibold text-[#71717a]">STAKEHOLDER BRIEF</h2>
        <p className="text-[10px] text-[#71717a]/60">Executive summary view</p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">

        {/* Project Health — single gauge for overall health score */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2">PROJECT HEALTH</h3>
          <div className="flex justify-center gap-4">
            <GaugeRing value={healthScore} label="Health" />
            <GaugeRing
              value={data.phase_progress_pct != null ? Math.round(data.phase_progress_pct) : 0}
              label="Progress"
            />
          </div>
          <div className="mt-2 text-center text-[9px] text-[#71717a]">
            Day {data.simulated_day ?? 0} / {data.total_days ?? 0} •{' '}
            {data.active_agent_count ?? 0} agents active
          </div>
        </div>

        {/* Requires Attention */}
        {escalations.length > 0 && (
          <div>
            <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3 text-[#ef4444]" />
              REQUIRES ATTENTION
            </h3>
            <div className="space-y-2">
              {escalations.slice(0, 3).map((item, i) => (
                <div
                  key={i}
                  className="p-2 bg-[#ef4444]/10 border border-[#ef4444]/20 rounded text-xs"
                >
                  <div className="flex items-center gap-1 mb-1">
                    {item.severity && (
                      <span
                        className={cn(
                          'px-1 py-0.5 rounded text-[9px] font-medium',
                          item.severity === 'High' || item.severity === 'Critical'
                            ? 'bg-[#ef4444]/20 text-[#ef4444]'
                            : 'bg-[#f59e0b]/20 text-[#f59e0b]',
                        )}
                      >
                        {item.severity}
                      </span>
                    )}
                  </div>
                  <p className="text-[#e4e4e7] text-[11px]">
                    {item.title ?? item.description ?? JSON.stringify(item)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {escalations.length === 0 && (
          <div className="p-2 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded text-[11px] text-[#22c55e] text-center">
            No active escalations 🎉
          </div>
        )}

        {/* Phase Progress */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2">PHASE PROGRESS</h3>
          <div className="flex items-center gap-0.5">
            {phases.map((phase, i) => (
              <div key={phase} className="flex-1 flex flex-col items-center">
                <div
                  className={cn(
                    'h-1.5 w-full rounded-full',
                    i < currentPhaseIndex
                      ? 'bg-[#22c55e]'
                      : i === currentPhaseIndex
                        ? 'bg-[#3b82f6]'
                        : 'bg-[#27272a]',
                  )}
                />
                <span
                  className={cn(
                    'text-[8px] mt-1',
                    i === currentPhaseIndex ? 'text-[#3b82f6] font-medium' : 'text-[#71717a]',
                  )}
                >
                  {phase.slice(0, 3)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Decisions */}
        {topDecisions.length > 0 && (
          <div>
            <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-[#22c55e]" />
              RECENT DECISIONS
            </h3>
            <div className="space-y-1">
              {topDecisions.slice(0, 4).map((d, i) => (
                <div key={i} className="flex items-start gap-1.5 text-[11px] text-[#e4e4e7]">
                  <span className="text-[#22c55e] shrink-0">✓</span>
                  <span className="line-clamp-1">{d.title ?? d.description ?? String(d)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Customer Agent Details */}
        {customerAgents.length > 0 && (
          <div>
            <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <UserCircle className="h-3 w-3 text-[#f59e0b]" />
              CUSTOMER AGENTS
            </h3>
            <div className="space-y-2">
              {customerAgents.map((codename) => (
                <CustomerAgentCard
                  key={codename}
                  codename={codename}
                  projectName={activeProject ?? ''}
                />
              ))}
            </div>
          </div>
        )}

        {/* Agent Leaderboard */}
        {leaderboard.length > 0 && (
          <div>
            <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-[#3b82f6]" />
              AGENT PERFORMANCE
            </h3>
            <div className="space-y-1.5">
              {leaderboard.slice(0, 5).map((item, i) => {
                const codename = (item.codename ?? item.agent ?? item.name ?? `Agent ${i + 1}`) as string
                const score = (item.activity ?? item.score ?? item.messages ?? 0) as number
                return (
                  <div key={String(codename)} className="flex items-center gap-2">
                    <span className="text-[10px] text-[#71717a] w-3">{i + 1}.</span>
                    <div className="h-5 w-5 rounded-full bg-[#3b82f6]/20 text-[#3b82f6] flex items-center justify-center text-[8px] font-bold shrink-0">
                      {String(codename).slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-[11px] text-white flex-1 truncate">{codename}</span>
                    <span className="text-[10px] text-[#3b82f6] font-medium">{score}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Latest Milestone */}
        {latestMilestone && (
          <div>
            <h3 className="text-[10px] font-medium text-[#71717a] mb-2">LATEST MILESTONE</h3>
            <div className="p-2 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-[#22c55e] shrink-0" />
              <span className="text-[11px] text-[#e4e4e7]">
                {latestMilestone.title ?? latestMilestone.name ?? latestMilestone.description ?? JSON.stringify(latestMilestone)}
              </span>
            </div>
          </div>
        )}

      </div>
    </aside>
  )
}
