'use client'

import { AlertTriangle, CheckCircle2, TrendingUp } from 'lucide-react'
import { stakeholderMetrics, currentProject, type Agent } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

function GaugeRing({ value, label, color }: { value: number; label: string; color: string }) {
  const circumference = 2 * Math.PI * 28
  const strokeDashoffset = circumference - (value / 100) * circumference
  
  const statusColor = value >= 80 ? '#22c55e' : value >= 60 ? '#f59e0b' : '#ef4444'
  
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-16 w-16">
        <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64">
          <circle
            cx="32"
            cy="32"
            r="28"
            fill="none"
            stroke="#27272a"
            strokeWidth="4"
          />
          <circle
            cx="32"
            cy="32"
            r="28"
            fill="none"
            stroke={statusColor}
            strokeWidth="4"
            strokeLinecap="round"
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

function AgentAvatar({ agent }: { agent: Agent }) {
  const avatarBg = agent.side === 'consultant' 
    ? 'bg-[#3b82f6]/20 text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]' 
      : 'bg-[#71717a]/20 text-[#71717a]'
  
  return (
    <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-[8px] font-bold shrink-0", avatarBg)}>
      {agent.initials}
    </div>
  )
}

export function StakeholderView() {
  const phases = ['Discover', 'Prepare', 'Explore', 'Realize', 'Deploy', 'Run']
  const currentPhaseIndex = phases.indexOf(currentProject.phase)
  
  return (
    <aside className="w-[220px] bg-[#18181b] border-l border-[#27272a] flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-[#27272a]">
        <h2 className="text-xs font-semibold text-[#71717a]">STAKEHOLDER BRIEF</h2>
        <p className="text-[10px] text-[#71717a]/60">Executive summary view</p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Project Health */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2">PROJECT HEALTH</h3>
          <div className="flex justify-between">
            <GaugeRing value={stakeholderMetrics.schedule} label="Schedule" color="#3b82f6" />
            <GaugeRing value={stakeholderMetrics.budget} label="Budget" color="#22c55e" />
            <GaugeRing value={stakeholderMetrics.risk} label="Risk" color="#ef4444" />
          </div>
        </div>
        
        {/* Requires Attention */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-[#ef4444]" />
            REQUIRES ATTENTION
          </h3>
          <div className="space-y-2">
            {stakeholderMetrics.escalations.map((item, i) => (
              <div 
                key={i}
                className="p-2 bg-[#ef4444]/10 border border-[#ef4444]/20 rounded text-xs"
              >
                <div className="flex items-center gap-1 mb-1">
                  <span className={cn(
                    "px-1 py-0.5 rounded text-[9px] font-medium",
                    item.severity === 'High' ? 'bg-[#ef4444]/20 text-[#ef4444]' : 'bg-[#f59e0b]/20 text-[#f59e0b]'
                  )}>
                    {item.severity}
                  </span>
                </div>
                <p className="text-[#e4e4e7] text-[11px]">{item.title}</p>
              </div>
            ))}
          </div>
        </div>
        
        {/* Phase Progress */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2">PHASE PROGRESS</h3>
          <div className="flex items-center gap-0.5">
            {phases.map((phase, i) => (
              <div 
                key={phase}
                className="flex-1 flex flex-col items-center"
              >
                <div 
                  className={cn(
                    "h-1.5 w-full rounded-full",
                    i < currentPhaseIndex 
                      ? 'bg-[#22c55e]' 
                      : i === currentPhaseIndex 
                        ? 'bg-[#3b82f6]' 
                        : 'bg-[#27272a]'
                  )}
                />
                <span className={cn(
                  "text-[8px] mt-1",
                  i === currentPhaseIndex ? 'text-[#3b82f6] font-medium' : 'text-[#71717a]'
                )}>
                  {phase.slice(0, 3)}
                </span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Recent Decisions */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3 text-[#22c55e]" />
            RECENT DECISIONS
          </h3>
          <div className="space-y-1">
            {stakeholderMetrics.recentDecisions.map((decision, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[11px] text-[#e4e4e7]">
                <span className="text-[#22c55e] shrink-0">✓</span>
                <span className="line-clamp-1">{decision}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Agent Performance */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2 flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-[#3b82f6]" />
            AGENT PERFORMANCE
          </h3>
          <div className="space-y-1.5">
            {stakeholderMetrics.topAgents.map((item, i) => (
              <div key={item.agent.id} className="flex items-center gap-2">
                <span className="text-[10px] text-[#71717a] w-3">{i + 1}.</span>
                <AgentAvatar agent={item.agent} />
                <span className="text-[11px] text-white flex-1 truncate">{item.agent.codename}</span>
                <span className="text-[10px] text-[#3b82f6] font-medium">{item.activity}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Latest Milestone */}
        <div>
          <h3 className="text-[10px] font-medium text-[#71717a] mb-2">LATEST MILESTONE</h3>
          <div className="p-2 bg-[#22c55e]/10 border border-[#22c55e]/20 rounded flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-[#22c55e] shrink-0" />
            <span className="text-[11px] text-[#e4e4e7]">{stakeholderMetrics.latestMilestone}</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
