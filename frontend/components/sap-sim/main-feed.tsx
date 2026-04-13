'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Flag,
  MessageSquare,
  Users,
  Wifi,
  WifiOff,
  Wrench,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSimulationFeed } from '@/hooks/useSimulationFeed'
import type { FeedEvent, FeedEventType } from '@/lib/types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PROJECT_NAME = 'Cables-Company'

// Canonical event types the feed emits
type EventCategory =
  | 'message'
  | 'meeting'
  | 'decision'
  | 'milestone'
  | 'alert'
  | 'system'

const CATEGORY_MAP: Record<FeedEventType, EventCategory> = {
  CONNECTED: 'system',
  SIMULATION_STARTED: 'system',
  SIMULATION_PAUSED: 'system',
  SIMULATION_RESUMED: 'system',
  SIMULATION_STOPPED: 'system',
  SIMULATION_COMPLETED: 'milestone',
  PROJECT_CREATED: 'system',
  AGENT_MSG: 'message',
  AGENT_STATUS: 'system',
  MEETING_STARTED: 'meeting',
  MEETING_ENDED: 'meeting',
  DECISION_RAISED: 'decision',
  DECISION_APPROVED: 'decision',
  DECISION_REJECTED: 'decision',
  NEW_TOOL: 'milestone',
  BLOCKER: 'alert',
  PHASE_TRANSITION: 'milestone',
  LESSON_LEARNED: 'milestone',
} as Record<string, EventCategory>

function categoryOf(type: FeedEventType): EventCategory {
  return CATEGORY_MAP[type] ?? 'system'
}

// ---------------------------------------------------------------------------
// Badge config per category
// ---------------------------------------------------------------------------

const BADGE_CONFIG: Record<
  EventCategory,
  { label: string; icon: React.ReactNode; classes: string }
> = {
  message: {
    label: 'Message',
    icon: <MessageSquare className="h-2.5 w-2.5" />,
    classes: 'bg-[#3b82f6]/20 text-[#3b82f6]',
  },
  meeting: {
    label: 'Meeting',
    icon: <Users className="h-2.5 w-2.5" />,
    classes: 'bg-[#a855f7]/20 text-[#a855f7]',
  },
  decision: {
    label: 'Decision',
    icon: <CheckCircle2 className="h-2.5 w-2.5" />,
    classes: 'bg-[#f59e0b]/20 text-[#f59e0b]',
  },
  milestone: {
    label: 'Milestone',
    icon: <Flag className="h-2.5 w-2.5" />,
    classes: 'bg-[#22c55e]/20 text-[#22c55e]',
  },
  alert: {
    label: 'Alert',
    icon: <AlertTriangle className="h-2.5 w-2.5" />,
    classes: 'bg-[#ef4444]/20 text-[#ef4444]',
  },
  system: {
    label: 'System',
    icon: <Zap className="h-2.5 w-2.5" />,
    classes: 'bg-[#71717a]/20 text-[#71717a]',
  },
}

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

type FilterType = 'All' | 'Messages' | 'Meetings' | 'Decisions' | 'Milestones' | 'Alerts'

const FILTER_CATEGORIES: Record<FilterType, EventCategory | null> = {
  All: null,
  Messages: 'message',
  Meetings: 'meeting',
  Decisions: 'decision',
  Milestones: 'milestone',
  Alerts: 'alert',
}

// ---------------------------------------------------------------------------
// Connection status indicator
// ---------------------------------------------------------------------------

type ConnectionState = 'connected' | 'reconnecting' | 'disconnected'

interface ConnectionStatusProps {
  state: ConnectionState
  error: string | null
}

function ConnectionStatus({ state, error }: ConnectionStatusProps) {
  if (state === 'connected') {
    return (
      <div className="flex items-center gap-1.5 text-[#22c55e]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-[#22c55e]" />
        </span>
        <Wifi className="h-3 w-3" />
        <span className="text-[10px] font-medium hidden sm:inline">LIVE</span>
      </div>
    )
  }

  if (state === 'reconnecting') {
    return (
      <div
        className="flex items-center gap-1.5 text-[#f59e0b]"
        title={error ?? 'Reconnecting…'}
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#f59e0b] opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-[#f59e0b]" />
        </span>
        <Wifi className="h-3 w-3" />
        <span className="text-[10px] font-medium hidden sm:inline">RECONNECTING</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 text-[#71717a]" title={error ?? 'Disconnected'}>
      <span className="inline-flex rounded-full h-2 w-2 bg-[#71717a]" />
      <WifiOff className="h-3 w-3" />
      <span className="text-[10px] font-medium hidden sm:inline">DISCONNECTED</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Feed event card
// ---------------------------------------------------------------------------

interface FeedEventCardProps {
  event: FeedEvent
  index: number
}

function FeedEventCard({ event }: FeedEventCardProps) {
  const category = categoryOf(event.type)
  const badge = BADGE_CONFIG[category]
  const d = event.data as Record<string, unknown>

  // Extract common fields from event data
  const agentName = (d.agent_name ?? d.agent ?? d.codename ?? '') as string
  const agentRole = (d.agent_role ?? d.role ?? '') as string
  const agentInitials = agentName
    ? agentName
        .split('_')
        .map((p: string) => p[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'
  const agentSide = (d.side ?? d.agent_side ?? '') as string

  const content =
    (d.content ?? d.message ?? d.text ?? d.description ?? d.summary ?? '') as string
  const day = d.day as string | number | undefined
  const phase = d.phase as string | undefined

  // Border colour per category
  const borderAccent: Record<EventCategory, string> = {
    message: 'border-l-[#3b82f6]',
    meeting: 'border-l-[#a855f7]',
    decision: 'border-l-[#f59e0b]',
    milestone: 'border-l-[#22c55e]',
    alert: 'border-l-[#ef4444]',
    system: 'border-l-[#71717a]',
  }

  const avatarBg =
    agentSide === 'consultant'
      ? 'bg-[#3b82f6]/20 text-[#3b82f6]'
      : agentSide === 'customer'
        ? 'bg-[#f59e0b]/20 text-[#f59e0b]'
        : 'bg-[#71717a]/20 text-[#71717a]'

  // Format timestamp: prefer ISO string from event, fall back to now
  const time = new Date(event.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <article
      className={cn(
        'p-4 bg-[#18181b] border border-[#27272a] rounded-lg border-l-2',
        'hover:bg-[#18181b]/80 transition-colors',
        borderAccent[category],
        category === 'meeting' && 'bg-[#27272a]/30',
        category === 'alert' && 'bg-[#ef4444]/5',
      )}
    >
      <div className="flex gap-3">
        {/* Avatar */}
        <div
          className={cn(
            'rounded-full flex items-center justify-center font-bold shrink-0 h-8 w-8 text-xs',
            avatarBg,
          )}
        >
          {agentInitials || badge.icon}
        </div>

        <div className="flex-1 min-w-0">
          {/* Agent name / role */}
          <div className="flex items-center gap-2 mb-1">
            {agentName ? (
              <>
                <span className="font-medium text-sm text-white">{agentName}</span>
                {agentRole && (
                  <span className="text-xs text-[#71717a]">{agentRole}</span>
                )}
              </>
            ) : (
              <span className="font-medium text-sm text-[#71717a]">System</span>
            )}
          </div>

          {/* Meta line */}
          <div className="text-[11px] text-[#71717a] mb-2">
            {day !== undefined && `Day ${day} · `}
            {phase && `${phase} Phase · `}
            {time}
          </div>

          {/* Type badge */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            <span
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium',
                badge.classes,
              )}
            >
              {badge.icon}
              {badge.label}
            </span>

            {/* Extra contextual badge for specific event types */}
            {event.type === 'BLOCKER' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-[#ef4444]/20 text-[#ef4444]">
                <AlertTriangle className="h-2.5 w-2.5" />
                BLOCKER
              </span>
            )}
            {event.type === 'NEW_TOOL' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-[#a855f7]/20 text-[#a855f7]">
                <Wrench className="h-2.5 w-2.5" />
                NEW TOOL
              </span>
            )}
            {(event.type === 'DECISION_APPROVED' || event.type === 'DECISION_REJECTED') && (
              <span
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium',
                  event.type === 'DECISION_APPROVED'
                    ? 'bg-[#22c55e]/20 text-[#22c55e]'
                    : 'bg-[#ef4444]/20 text-[#ef4444]',
                )}
              >
                {event.type === 'DECISION_APPROVED' ? '✓ Approved' : '✗ Rejected'}
              </span>
            )}
          </div>

          {/* Content */}
          {content && (
            <p className="text-sm text-[#e4e4e7] font-mono leading-relaxed">{content}</p>
          )}

          {/* Fallback: raw data preview for unrecognised events without content */}
          {!content && (
            <p className="text-xs text-[#71717a] font-mono truncate">
              {event.type}
            </p>
          )}
        </div>
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Empty / placeholder states
// ---------------------------------------------------------------------------

function EmptyState({
  connected,
  filter,
}: {
  connected: boolean
  filter: FilterType
}) {
  if (!connected) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[#71717a] gap-3 py-20">
        <WifiOff className="h-8 w-8" />
        <p className="text-sm">Waiting for connection…</p>
      </div>
    )
  }
  return (
    <div className="flex flex-col items-center justify-center h-full text-[#71717a] gap-3 py-20">
      <MessageSquare className="h-8 w-8" />
      <p className="text-sm">
        {filter === 'All'
          ? 'No events yet — start the simulation!'
          : `No ${filter.toLowerCase()} events yet`}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MainFeed() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('All')
  const [search, setSearch] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const { events, connected, error } = useSimulationFeed(PROJECT_NAME)

  // Derive connection state for indicator
  const connectionState: ConnectionState = connected
    ? 'connected'
    : error
      ? 'reconnecting'
      : 'disconnected'

  // -------------------------------------------------------------------------
  // Filtering
  // -------------------------------------------------------------------------

  const filteredEvents = events.filter((event) => {
    const category = categoryOf(event.type)
    const targetCategory = FILTER_CATEGORIES[activeFilter]
    if (targetCategory !== null && category !== targetCategory) return false

    if (search.trim()) {
      const q = search.toLowerCase()
      const d = event.data as Record<string, unknown>
      const haystack = [
        event.type,
        d.agent_name,
        d.agent,
        d.codename,
        d.content,
        d.message,
        d.text,
        d.description,
        d.phase,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      if (!haystack.includes(q)) return false
    }

    return true
  })

  // -------------------------------------------------------------------------
  // Auto-scroll: scroll to bottom whenever new events arrive, unless the user
  // has scrolled up (autoScroll is false).
  // -------------------------------------------------------------------------

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setAutoScroll(distFromBottom < 80)
  }, [])

  useEffect(() => {
    if (!autoScroll) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [filteredEvents.length, autoScroll])

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const filters: FilterType[] = [
    'All',
    'Messages',
    'Meetings',
    'Decisions',
    'Milestones',
    'Alerts',
  ]

  return (
    <section className="flex-1 flex flex-col min-w-0 min-h-0 bg-[#0e0e10]">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-[#27272a] shrink-0 gap-3">
        <div className="flex items-center gap-2 shrink-0">
          <MessageSquare className="h-4 w-4 text-[#3b82f6]" />
          <h2 className="font-semibold text-white text-sm">LIVE FEED</h2>
          <ConnectionStatus state={connectionState} error={error} />
        </div>

        {/* Filters */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {filters.map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                'px-2.5 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap',
                activeFilter === filter
                  ? 'bg-[#3b82f6] text-white'
                  : 'text-[#71717a] hover:text-white hover:bg-[#27272a]',
              )}
            >
              {filter}
            </button>
          ))}
        </div>
      </header>

      {/* Search */}
      <div className="px-4 py-2 border-b border-[#27272a] shrink-0">
        <input
          type="search"
          placeholder="Search events, agents, phases…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-[#18181b] border border-[#27272a] rounded px-3 py-1.5 text-xs text-[#e4e4e7] placeholder-[#52525b] focus:outline-none focus:border-[#3b82f6] transition-colors"
        />
      </div>

      {/* Feed */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-3"
      >
        {filteredEvents.length === 0 ? (
          <EmptyState connected={connected} filter={activeFilter} />
        ) : (
          filteredEvents.map((event, idx) => (
            <FeedEventCard key={`${event.type}-${event.timestamp}-${idx}`} event={event} index={idx} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* "Scroll to bottom" nudge when auto-scroll is paused */}
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true)
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
          }}
          className="absolute bottom-6 right-6 bg-[#3b82f6] text-white text-xs px-3 py-1.5 rounded-full shadow-lg hover:bg-[#2563eb] transition-colors z-10"
        >
          ↓ Latest
        </button>
      )}
    </section>
  )
}
