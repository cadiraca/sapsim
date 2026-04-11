'use client'

import { useState } from 'react'
import { 
  ChevronDown, 
  ChevronRight,
  Users, 
  CheckCircle2, 
  Wrench, 
  FileText, 
  Lightbulb,
  Clock,
  AlertCircle
} from 'lucide-react'
import { 
  meetings, 
  decisions, 
  tools, 
  lessons, 
  testStrategy,
  type Meeting, 
  type Decision,
  type Tool,
  type Lesson,
  type Agent 
} from '@/lib/mock-data'
import { cn } from '@/lib/utils'

type TabType = 'meetings' | 'decisions' | 'tools' | 'test-strategy' | 'lessons'

function AgentAvatar({ agent, size = 'sm' }: { agent: Agent; size?: 'sm' | 'xs' }) {
  const avatarBg = agent.side === 'consultant' 
    ? 'bg-[#3b82f6]/20 text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]' 
      : 'bg-[#71717a]/20 text-[#71717a]'
  
  const sizeClasses = size === 'xs' ? 'h-4 w-4 text-[7px]' : 'h-5 w-5 text-[8px]'
  
  return (
    <div className={cn("rounded-full flex items-center justify-center font-bold shrink-0", avatarBg, sizeClasses)}>
      {agent.initials}
    </div>
  )
}

function MeetingItem({ meeting }: { meeting: Meeting }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="border border-[#27272a] rounded-lg overflow-hidden">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-[#27272a]/50 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-[#71717a] shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[#71717a] shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">{meeting.title}</div>
          <div className="flex items-center gap-2 text-[10px] text-[#71717a]">
            <span>{meeting.phase} Phase</span>
            <span>·</span>
            <span>{meeting.date}</span>
            <span>·</span>
            <span>{meeting.duration}</span>
          </div>
        </div>
        <div className="flex -space-x-1">
          {meeting.attendees.slice(0, 4).map((agent) => (
            <AgentAvatar key={agent.id} agent={agent} size="xs" />
          ))}
          {meeting.attendees.length > 4 && (
            <div className="h-4 w-4 rounded-full bg-[#27272a] text-[7px] flex items-center justify-center text-[#71717a] font-medium">
              +{meeting.attendees.length - 4}
            </div>
          )}
        </div>
      </button>
      
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-[#27272a] space-y-3 text-xs">
          <div>
            <h4 className="font-medium text-[#71717a] mb-1">Agenda</h4>
            <ul className="space-y-0.5 text-[#e4e4e7]">
              {meeting.agenda.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-[#3b82f6]">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-[#71717a] mb-1">Discussion</h4>
            <ul className="space-y-0.5 text-[#e4e4e7]">
              {meeting.discussion.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-[#f59e0b]">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-[#71717a] mb-1">Decisions</h4>
            <ul className="space-y-0.5 text-[#e4e4e7]">
              {meeting.decisions.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-[#22c55e]">✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="font-medium text-[#71717a] mb-1">Action Items</h4>
            <ul className="space-y-0.5 text-[#e4e4e7]">
              {meeting.actionItems.map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-[#a855f7]">→</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

function DecisionsTab() {
  const columns = ['Pending', 'Approved', 'Rejected', 'Deferred'] as const
  
  const impactColors: Record<string, string> = {
    Low: 'bg-[#22c55e]/20 text-[#22c55e]',
    Medium: 'bg-[#f59e0b]/20 text-[#f59e0b]',
    High: 'bg-[#ef4444]/20 text-[#ef4444]',
    Critical: 'bg-[#ef4444] text-white',
  }
  
  return (
    <div className="flex gap-2 h-full overflow-x-auto pb-2">
      {columns.map((status) => (
        <div key={status} className="flex-1 min-w-[140px] flex flex-col">
          <div className="text-xs font-medium text-[#71717a] mb-2 px-1">{status}</div>
          <div className="flex-1 space-y-2 overflow-y-auto">
            {decisions.filter(d => d.status === status).map((decision) => (
              <div 
                key={decision.id}
                className="p-2.5 bg-[#27272a]/50 border border-[#27272a] rounded-lg"
              >
                <div className="text-xs font-medium text-white mb-1 line-clamp-2">{decision.title}</div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className={cn("px-1.5 py-0.5 rounded text-[9px] font-medium", impactColors[decision.impact])}>
                    {decision.impact}
                  </span>
                </div>
                <p className="text-[10px] text-[#71717a] line-clamp-2 mb-1.5">{decision.description}</p>
                <div className="flex items-center gap-1.5">
                  <AgentAvatar agent={decision.proposedBy} size="xs" />
                  <span className="text-[9px] text-[#71717a]">{decision.dateRaised}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ToolsTab() {
  return (
    <div className="space-y-3 overflow-y-auto">
      {tools.map((tool) => (
        <div 
          key={tool.id}
          className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg border-l-2 border-l-[#a855f7]"
        >
          <div className="flex items-center gap-2 mb-2">
            <Wrench className="h-4 w-4 text-[#a855f7]" />
            <span className="text-sm font-medium text-white">{tool.name}</span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-[#a855f7]/20 text-[#a855f7]">
              INVENTED
            </span>
          </div>
          <p className="text-xs text-[#e4e4e7] mb-2">{tool.description}</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[10px] text-[#71717a]">
              <AgentAvatar agent={tool.createdBy} size="xs" />
              <span>{tool.createdBy.codename}</span>
              <span>·</span>
              <span>{tool.createdDate}</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#71717a]">Used by:</span>
              <div className="flex -space-x-1">
                {tool.usedBy.slice(0, 4).map((agent) => (
                  <AgentAvatar key={agent.id} agent={agent} size="xs" />
                ))}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function TestStrategyTab() {
  const progressColors: Record<string, string> = {
    unit: 'bg-[#71717a]',
    integration: 'bg-[#3b82f6]',
    uat: 'bg-[#f59e0b]',
    regression: 'bg-[#22c55e]',
  }
  
  return (
    <div className="space-y-4 overflow-y-auto text-xs">
      <div>
        <h4 className="font-medium text-[#71717a] mb-1 flex items-center gap-1">
          <FileText className="h-3 w-3" /> Test Scope
        </h4>
        <p className="text-[#e4e4e7]">{testStrategy.scope}</p>
      </div>
      
      <div>
        <h4 className="font-medium text-[#71717a] mb-1">Test Types</h4>
        <ul className="space-y-1 text-[#e4e4e7]">
          {testStrategy.testTypes.map((type, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-[#3b82f6]">•</span>
              {type}
            </li>
          ))}
        </ul>
      </div>
      
      <div>
        <h4 className="font-medium text-[#71717a] mb-1">UAT Plan</h4>
        <p className="text-[#e4e4e7]">{testStrategy.uatPlan}</p>
      </div>
      
      <div>
        <h4 className="font-medium text-[#71717a] mb-1">Defect Management</h4>
        <p className="text-[#e4e4e7]">{testStrategy.defectManagement}</p>
      </div>
      
      <div>
        <h4 className="font-medium text-[#71717a] mb-1">Sign-off Criteria</h4>
        <p className="text-[#e4e4e7]">{testStrategy.signOffCriteria}</p>
      </div>
      
      <div>
        <h4 className="font-medium text-[#71717a] mb-2">Test Progress</h4>
        <div className="space-y-2">
          {Object.entries(testStrategy.progress).map(([key, value]) => (
            <div key={key}>
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="text-[#71717a] capitalize">{key}</span>
                <span className="text-white">{value}%</span>
              </div>
              <div className="h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                <div 
                  className={cn("h-full rounded-full transition-all", progressColors[key])}
                  style={{ width: `${value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function LessonsTab() {
  const categoryColors: Record<string, string> = {
    Process: 'bg-[#3b82f6]/20 text-[#3b82f6]',
    Technical: 'bg-[#a855f7]/20 text-[#a855f7]',
    People: 'bg-[#f59e0b]/20 text-[#f59e0b]',
    Tools: 'bg-[#22c55e]/20 text-[#22c55e]',
  }
  
  return (
    <div className="space-y-3 overflow-y-auto">
      {lessons.map((lesson) => (
        <div 
          key={lesson.id}
          className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg relative"
        >
          <div className="flex items-center gap-2 mb-2">
            <AgentAvatar agent={lesson.agent} size="sm" />
            <div className="flex-1 min-w-0">
              <span className="text-xs font-medium text-white">{lesson.agent.codename}</span>
              <div className="flex items-center gap-1.5 text-[10px] text-[#71717a]">
                <span>{lesson.phase} Phase</span>
                <span>·</span>
                <span>{lesson.date}</span>
              </div>
            </div>
            <span className={cn("px-1.5 py-0.5 rounded text-[9px] font-medium", categoryColors[lesson.category])}>
              {lesson.category}
            </span>
          </div>
          <p className="text-xs text-[#e4e4e7] mb-2">{lesson.text}</p>
          <div className="flex items-center gap-1 text-[10px] text-[#71717a]">
            <CheckCircle2 className="h-3 w-3 text-[#22c55e]" />
            Validated by {lesson.validatedBy} agents
          </div>
        </div>
      ))}
    </div>
  )
}

export function ContextPanel() {
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
              "flex-1 flex items-center justify-center gap-1 py-2.5 text-[10px] font-medium transition-colors border-b-2",
              activeTab === tab.id 
                ? "text-white border-[#3b82f6]" 
                : "text-[#71717a] border-transparent hover:text-white"
            )}
          >
            {tab.icon}
            <span className="hidden xl:inline">{tab.label}</span>
          </button>
        ))}
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-hidden p-3">
        {activeTab === 'meetings' && (
          <div className="space-y-2 h-full overflow-y-auto">
            {meetings.map((meeting) => (
              <MeetingItem key={meeting.id} meeting={meeting} />
            ))}
          </div>
        )}
        {activeTab === 'decisions' && <DecisionsTab />}
        {activeTab === 'tools' && <ToolsTab />}
        {activeTab === 'test-strategy' && <TestStrategyTab />}
        {activeTab === 'lessons' && <LessonsTab />}
      </div>
    </section>
  )
}
