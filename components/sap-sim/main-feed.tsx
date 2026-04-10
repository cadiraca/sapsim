'use client'

import { useState } from 'react'
import { AlertTriangle, Wrench, Users, MessageSquare } from 'lucide-react'
import { feedCards, type FeedCard, type Agent } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

type FilterType = 'All' | 'Consultant' | 'Customer' | 'Meetings' | 'Decisions' | 'Tools'

function AgentAvatar({ agent, size = 'md' }: { agent: Agent; size?: 'sm' | 'md' }) {
  const avatarBg = agent.side === 'consultant' 
    ? 'bg-[#3b82f6]/20 text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]' 
      : 'bg-[#71717a]/20 text-[#71717a]'
  
  const sizeClasses = size === 'sm' ? 'h-5 w-5 text-[8px]' : 'h-8 w-8 text-xs'
  
  return (
    <div className={cn("rounded-full flex items-center justify-center font-bold shrink-0", avatarBg, sizeClasses)}>
      {agent.initials}
    </div>
  )
}

function FeedCardItem({ card }: { card: FeedCard }) {
  const hasBlocker = card.tags.includes('BLOCKER')
  const hasEscalation = card.tags.includes('ESCALATION')
  const hasNewTool = card.tags.includes('NEW TOOL')
  const hasMeeting = card.tags.includes('MEETING')
  const hasDecision = card.tags.includes('DECISION NEEDED')

  const borderColor = hasEscalation || hasBlocker
    ? 'border-l-[#ef4444]'
    : hasNewTool
      ? 'border-l-[#a855f7]'
      : hasMeeting
        ? 'border-l-[#3b82f6]'
        : 'border-l-transparent'

  const tagColors: Record<string, string> = {
    'BLOCKER': 'bg-[#ef4444]/20 text-[#ef4444]',
    'ESCALATION': 'bg-[#ef4444]/20 text-[#ef4444]',
    'DECISION NEEDED': 'bg-[#f59e0b]/20 text-[#f59e0b]',
    'NEW TOOL': 'bg-[#a855f7]/20 text-[#a855f7]',
    'MEETING': 'bg-[#3b82f6]/20 text-[#3b82f6]',
  }

  return (
    <article className={cn(
      "p-4 bg-[#18181b] border border-[#27272a] rounded-lg border-l-2 hover:bg-[#18181b]/80 transition-colors",
      borderColor,
      hasMeeting && "bg-[#27272a]/30"
    )}>
      <div className="flex gap-3">
        <AgentAvatar agent={card.agent} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm text-white">{card.agent.codename}</span>
            <span className="text-xs text-[#71717a]">{card.agent.role}</span>
          </div>
          <div className="text-[11px] text-[#71717a] mb-2">
            Day {card.day} · {card.phase} Phase · {card.timestamp}
          </div>
          
          {/* Tags */}
          {card.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {card.tags.map((tag) => (
                <span 
                  key={tag}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium",
                    tagColors[tag] || 'bg-[#27272a] text-[#71717a]'
                  )}
                >
                  {tag === 'BLOCKER' || tag === 'ESCALATION' ? <AlertTriangle className="h-2.5 w-2.5" /> : null}
                  {tag === 'NEW TOOL' ? <Wrench className="h-2.5 w-2.5" /> : null}
                  {tag === 'MEETING' ? <Users className="h-2.5 w-2.5" /> : null}
                  {tag}
                </span>
              ))}
            </div>
          )}
          
          {/* Content */}
          <p className="text-sm text-[#e4e4e7] font-mono leading-relaxed">{card.content}</p>
          
          {/* Reactions */}
          {card.reactions.length > 0 && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[#27272a]">
              <div className="flex -space-x-1.5">
                {card.reactions.slice(0, 5).map((agent) => (
                  <AgentAvatar key={agent.id} agent={agent} size="sm" />
                ))}
              </div>
              <span className="text-[11px] text-[#71717a]">
                {card.reactions.length} {card.reactions.length === 1 ? 'reaction' : 'reactions'}
              </span>
            </div>
          )}
        </div>
      </div>
    </article>
  )
}

export function MainFeed() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('All')
  
  const filters: FilterType[] = ['All', 'Consultant', 'Customer', 'Meetings', 'Decisions', 'Tools']
  
  const filteredCards = feedCards.filter((card) => {
    if (activeFilter === 'All') return true
    if (activeFilter === 'Consultant') return card.agent.side === 'consultant'
    if (activeFilter === 'Customer') return card.agent.side === 'customer'
    if (activeFilter === 'Meetings') return card.tags.includes('MEETING')
    if (activeFilter === 'Decisions') return card.tags.includes('DECISION NEEDED')
    if (activeFilter === 'Tools') return card.tags.includes('NEW TOOL')
    return true
  })

  return (
    <section className="flex-1 flex flex-col min-w-0 min-h-0 bg-[#0e0e10]">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-[#27272a] shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-[#3b82f6]" />
          <h2 className="font-semibold text-white text-sm">LIVE FEED</h2>
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#22c55e]"></span>
          </span>
        </div>
        <div className="flex items-center gap-1">
          {filters.map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                activeFilter === filter 
                  ? "bg-[#3b82f6] text-white" 
                  : "text-[#71717a] hover:text-white hover:bg-[#27272a]"
              )}
            >
              {filter}
            </button>
          ))}
        </div>
      </header>
      
      {/* Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {filteredCards.map((card) => (
          <FeedCardItem key={card.id} card={card} />
        ))}
      </div>
    </section>
  )
}
