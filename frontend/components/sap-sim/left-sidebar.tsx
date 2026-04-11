'use client'

import { Play, Pause, Square, Settings, Users, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { 
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { agents, currentProject, activeMeetings, type Agent, type SimulationStatus } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

interface LeftSidebarProps {
  simulationStatus: SimulationStatus
  onSimulationControl: (action: 'run' | 'pause' | 'stop') => void
  onSettingsClick: () => void
  onAgentClick: (agent: Agent) => void
}

function AgentRow({ agent, onClick }: { agent: Agent; onClick: () => void }) {
  const borderColor = agent.side === 'consultant' 
    ? 'border-l-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'border-l-[#f59e0b]' 
      : 'border-l-[#71717a]'
  
  const statusColor = agent.status === 'thinking' 
    ? 'bg-[#f59e0b]' 
    : agent.status === 'speaking' 
      ? 'bg-[#22c55e]' 
      : 'bg-[#71717a]'

  const avatarBg = agent.side === 'consultant' 
    ? 'bg-[#3b82f6]/20 text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]' 
      : 'bg-[#71717a]/20 text-[#71717a]'

  const content = (
    <button 
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2 py-1.5 px-2 hover:bg-[#27272a] border-l-2 transition-colors",
        borderColor
      )}
    >
      <div className={cn("h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0", avatarBg)}>
        {agent.initials}
      </div>
      <div className="flex-1 min-w-0 text-left">
        <div className="text-xs font-medium text-white truncate">{agent.codename}</div>
        <div className="text-[10px] text-[#71717a] truncate">{agent.role}</div>
      </div>
      <div className={cn("h-2 w-2 rounded-full shrink-0", statusColor)} />
    </button>
  )

  if (agent.personality) {
    return (
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>
            {content}
          </TooltipTrigger>
          <TooltipContent side="right" className="bg-[#18181b] border-[#27272a] p-3 w-48">
            <div className="text-xs font-medium text-[#f59e0b] mb-2">{agent.personality.archetype}</div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Engagement</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div className="h-full bg-[#3b82f6] rounded-full" style={{ width: `${agent.personality.engagement}%` }} />
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Trust</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div className="h-full bg-[#22c55e] rounded-full" style={{ width: `${agent.personality.trust}%` }} />
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#71717a]">Risk Tolerance</span>
                <div className="w-20 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                  <div className="h-full bg-[#f59e0b] rounded-full" style={{ width: `${agent.personality.riskTolerance}%` }} />
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

export function LeftSidebar({ simulationStatus, onSimulationControl, onSettingsClick, onAgentClick }: LeftSidebarProps) {
  const phaseColors: Record<string, string> = {
    Discover: 'bg-[#71717a]',
    Prepare: 'bg-[#3b82f6]',
    Explore: 'bg-[#f59e0b]',
    Realize: 'bg-[#a855f7]',
    Deploy: 'bg-[#22c55e]',
    Run: 'bg-[#ef4444]',
  }

  const statusColors: Record<SimulationStatus, string> = {
    RUNNING: 'bg-[#22c55e]',
    PAUSED: 'bg-[#f59e0b]',
    STOPPED: 'bg-[#ef4444]',
  }

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
        <div className="text-xs text-[#71717a] mb-1 truncate">{currentProject.name}</div>
        <div className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-white", phaseColors[currentProject.phase])}>
          {currentProject.phase} Phase
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
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75"></span>
            )}
            <span className={cn("relative inline-flex rounded-full h-2.5 w-2.5", statusColors[simulationStatus])}></span>
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
          {agents.map((agent) => (
            <AgentRow key={agent.id} agent={agent} onClick={() => onAgentClick(agent)} />
          ))}
        </div>
      </div>

      {/* Active Meetings */}
      <div className="border-t border-[#27272a]">
        <div className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-[#71717a]">
          <Calendar className="h-3 w-3" />
          ACTIVE MEETINGS
        </div>
        <div className="px-2 pb-2 space-y-1">
          {activeMeetings.map((meeting) => (
            <button 
              key={meeting.id}
              className="w-full text-left px-2 py-1.5 rounded bg-[#27272a]/50 hover:bg-[#27272a] transition-colors"
            >
              <div className="text-xs text-white truncate">{meeting.title}</div>
              <div className="text-[10px] text-[#71717a]">{meeting.time}</div>
            </button>
          ))}
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
