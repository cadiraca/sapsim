'use client'

import { useEffect, useState } from 'react'
import { Play, Pause, Square, Settings, Users, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { api } from '@/lib/api'
import type { Agent, SimulationStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Single source of truth for project name — swap once a project context/store
// exists in a later phase.
const PROJECT_NAME = 'Cables-Company'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive 2-letter initials from a codename like "PM_ALEX" → "PA" */
function deriveInitials(codename: string): string {
  const parts = codename.split('_').filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  }
  return codename.slice(0, 2).toUpperCase()
}

/** Normalize a 1-5 personality score to a 0-100 percentage */
function scoreToPercent(value: number): number {
  return Math.round(((value - 1) / 4) * 100)
}

// ---------------------------------------------------------------------------
// AgentRow sub-component
// ---------------------------------------------------------------------------

function AgentRow({
  agent,
  onClick,
}: {
  agent: Agent
  onClick: () => void
}) {
  const initials = deriveInitials(agent.codename)

  // Side colours
  const borderColor =
    agent.side === 'consultant'
      ? 'border-l-[#3b82f6]'
      : agent.side === 'customer'
      ? 'border-l-[#f59e0b]'
      : 'border-l-[#71717a]'

  const avatarBg =
    agent.side === 'consultant'
      ? 'bg-[#3b82f6]/20 text-[#3b82f6]'
      : agent.side === 'customer'
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]'
      : 'bg-[#71717a]/20 text-[#71717a]'

  // Status dot: map API AgentStatus values to colours
  const statusColor =
    agent.status === 'thinking'
      ? 'bg-[#f59e0b]'
      : agent.status === 'speaking'
      ? 'bg-[#22c55e]'
      : agent.status === 'in_meeting'
      ? 'bg-[#a855f7]'
      : 'bg-[#71717a]' // idle

  const content = (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2 py-1.5 px-2 hover:bg-[#27272a] border-l-2 transition-colors',
        borderColor,
      )}
    >
      <div
        className={cn(
          'h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0',
          avatarBg,
        )}
      >
        {initials}
      </div>
      <div className="flex-1 min-w-0 text-left">
        <div className="text-xs font-medium text-white truncate">{agent.codename}</div>
        <div className="text-[10px] text-[#71717a] truncate">{agent.role}</div>
      </div>
      <div className={cn('h-2 w-2 rounded-full shrink-0', statusColor)} />
    </button>
  )

  if (agent.personality) {
    const engPct = scoreToPercent(agent.personality.engagement)
    const trustPct = scoreToPercent(agent.personality.trust)
    const riskPct = scoreToPercent(agent.personality.risk_tolerance)

    return (
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent
            side="right"
            className="bg-[#18181b] border-[#27272a] p-3 w-48"
          >
            <div className="text-xs font-medium text-[#f59e0b] mb-2">
              {agent.personality.archetype}
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Engagement</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#3b82f6] rounded-full"
                    style={{ width: `${engPct}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Trust</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#22c55e] rounded-full"
                    style={{ width: `${trustPct}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Risk Tolerance</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#f59e0b] rounded-full"
                    style={{ width: `${riskPct}%` }}
                  />
                </div>
              </div>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return content
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LeftSidebarProps {
  simulationStatus: SimulationStatus
  onSimulationControl: (action: 'run' | 'pause' | 'stop') => void
  onSettingsClick: () => void
  onAgentClick: (agent: Agent) => void
}

// ---------------------------------------------------------------------------
// LeftSidebar
// ---------------------------------------------------------------------------

export function LeftSidebar({
  simulationStatus,
  onSimulationControl,
  onSettingsClick,
  onAgentClick,
}: LeftSidebarProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [projectPhase, setProjectPhase] = useState<string>('—')
  const [projectName, setProjectName] = useState<string>(PROJECT_NAME)
  const [activeMeetings, setActiveMeetings] = useState<
    { id: string; title: string; time: string }[]
  >([])

  // ---------------------------------------------------------------------------
  // Fetch agents + project status; poll every 5 s
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false

    const fetchData = async () => {
      try {
        const [agentList, statusData] = await Promise.all([
          api.getAgents(PROJECT_NAME),
          api.getStatus(PROJECT_NAME),
        ])

        if (!cancelled) {
          setAgents(agentList)
          setProjectPhase(statusData.current_phase)
          setProjectName(statusData.project_name)

          // Derive "active meetings" from agents currently in_meeting
          const inMeeting = agentList
            .filter(a => a.status === 'in_meeting')
            .slice(0, 3)
            .map((a, i) => ({
              id: String(i),
              title: `${a.codename} in Meeting`,
              time: 'now',
            }))
          setActiveMeetings(inMeeting)
        }
      } catch {
        // silently fail — keep last known state
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Phase badge colour
  // ---------------------------------------------------------------------------
  const phaseColors: Record<string, string> = {
    discover: 'bg-[#71717a]',
    Discover: 'bg-[#71717a]',
    prepare: 'bg-[#3b82f6]',
    Prepare: 'bg-[#3b82f6]',
    explore: 'bg-[#f59e0b]',
    Explore: 'bg-[#f59e0b]',
    realize: 'bg-[#a855f7]',
    Realize: 'bg-[#a855f7]',
    deploy: 'bg-[#22c55e]',
    Deploy: 'bg-[#22c55e]',
    run: 'bg-[#ef4444]',
    Run: 'bg-[#ef4444]',
  }

  const statusColors: Partial<Record<SimulationStatus, string>> = {
    RUNNING: 'bg-[#22c55e]',
    PAUSED: 'bg-[#f59e0b]',
    STOPPED: 'bg-[#ef4444]',
    COMPLETED: 'bg-[#3b82f6]',
    IDLE: 'bg-[#71717a]',
  }

  const phaseBadge = phaseColors[projectPhase] ?? 'bg-[#71717a]'
  const statusDot = statusColors[simulationStatus] ?? 'bg-[#71717a]'

  return (
    <aside className="w-[220px] bg-[#18181b] border-r border-[#27272a] flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-[#27272a]">
        <div className="flex items-center gap-2 mb-2">
          <div className="h-8 w-8 rounded bg-[#3b82f6] flex items-center justify-center">
            <span className="text-white font-bold text-xs">SAP</span>
          </div>
          <span className="font-bold text-white">SAP SIM</span>
        </div>
        <div className="text-xs text-[#71717a] mb-1 truncate">{projectName}</div>
        <div
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-white capitalize',
            phaseBadge,
          )}
        >
          {projectPhase} Phase
        </div>
      </div>

      {/* Simulation Controls */}
      <div className="p-3 border-b border-[#27272a]">
        <div className="flex items-center gap-2 mb-2">
          <Button
            size="sm"
            className="h-7 flex-1 bg-[#22c55e] hover:bg-[#22c55e]/80 text-white text-xs"
            onClick={() => onSimulationControl('run')}
            disabled={simulationStatus === 'RUNNING'}
          >
            <Play className="h-3 w-3 mr-1" />
            Run
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 flex-1 bg-transparent border-[#27272a] text-white text-xs hover:bg-[#27272a]"
            onClick={() => onSimulationControl('pause')}
            disabled={simulationStatus !== 'RUNNING'}
          >
            <Pause className="h-3 w-3 mr-1" />
            Pause
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 w-7 bg-transparent border-[#27272a] text-white hover:bg-[#27272a] p-0"
            onClick={() => onSimulationControl('stop')}
          >
            <Square className="h-3 w-3" />
          </Button>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="relative flex h-2.5 w-2.5">
            {simulationStatus === 'RUNNING' && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75" />
            )}
            <span className={cn('relative inline-flex rounded-full h-2.5 w-2.5', statusDot)} />
          </span>
          <span className="text-[#71717a]">{simulationStatus}</span>
        </div>
      </div>

      {/* Agents List */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-[#71717a]">
          <Users className="h-3 w-3" />
          AGENTS ({agents.length})
        </div>
        <div className="flex-1 overflow-y-auto">
          {agents.length === 0 ? (
            <div className="px-3 py-2 text-[10px] text-[#71717a]">Loading agents…</div>
          ) : (
            agents.map(agent => (
              <AgentRow
                key={agent.codename}
                agent={agent}
                onClick={() => onAgentClick(agent)}
              />
            ))
          )}
        </div>
      </div>

      {/* Active Meetings */}
      <div className="border-t border-[#27272a]">
        <div className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-[#71717a]">
          <Calendar className="h-3 w-3" />
          ACTIVE MEETINGS
        </div>
        <div className="px-2 pb-2 space-y-1">
          {activeMeetings.length === 0 ? (
            <div className="px-2 py-1 text-[10px] text-[#71717a]">None active</div>
          ) : (
            activeMeetings.map(meeting => (
              <button
                key={meeting.id}
                className="w-full text-left px-2 py-1.5 rounded bg-[#27272a]/50 hover:bg-[#27272a] transition-colors"
              >
                <div className="text-xs text-white truncate">{meeting.title}</div>
                <div className="text-[10px] text-[#71717a]">{meeting.time}</div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Settings */}
      <button
        onClick={onSettingsClick}
        className="flex items-center gap-2 px-3 py-3 border-t border-[#27272a] text-[#71717a] hover:text-white hover:bg-[#27272a] transition-colors"
      >
        <Settings className="h-4 w-4" />
        <span className="text-xs">Settings</span>
      </button>
    </aside>
  )
}
