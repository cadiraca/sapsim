'use client'

import { useState } from 'react'
import { X, Eye, EyeOff, RefreshCw, Upload, MessageSquare, Wrench } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { agents, type Agent } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

// Settings Modal
interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [showApiKey, setShowApiKey] = useState(false)
  const [settings, setSettings] = useState({
    baseUrl: 'http://localhost:4000',
    apiKey: '',
    modelName: 'gpt-4o',
    maxParallelAgents: 10,
    memoryCompression: 'every-10',
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-[#18181b] border border-[#27272a] rounded-lg w-full max-w-md p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">Simulation Settings</h2>
          <button onClick={onClose} className="text-[#71717a] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[#71717a] mb-1.5">LiteLLM Base URL</label>
            <Input 
              value={settings.baseUrl}
              onChange={(e) => setSettings({ ...settings, baseUrl: e.target.value })}
              className="bg-[#27272a] border-[#27272a] text-white"
              placeholder="http://localhost:4000"
            />
          </div>

          <div>
            <label className="block text-sm text-[#71717a] mb-1.5">API Key / Service Key</label>
            <div className="relative">
              <Input 
                type={showApiKey ? 'text' : 'password'}
                value={settings.apiKey}
                onChange={(e) => setSettings({ ...settings, apiKey: e.target.value })}
                className="bg-[#27272a] border-[#27272a] text-white pr-10"
                placeholder="sk-..."
              />
              <button 
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71717a] hover:text-white"
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-[#71717a] mb-1.5">Model Name</label>
            <Input 
              value={settings.modelName}
              onChange={(e) => setSettings({ ...settings, modelName: e.target.value })}
              className="bg-[#27272a] border-[#27272a] text-white"
              placeholder="e.g. gpt-4o, claude-3-5-sonnet"
            />
          </div>

          <div>
            <label className="block text-sm text-[#71717a] mb-1.5">
              Max Parallel Agents: <span className="text-white">{settings.maxParallelAgents}</span>
            </label>
            <Slider 
              value={[settings.maxParallelAgents]}
              onValueChange={(v) => setSettings({ ...settings, maxParallelAgents: v[0] })}
              min={1}
              max={30}
              step={1}
              className="py-2"
            />
          </div>

          <div>
            <label className="block text-sm text-[#71717a] mb-1.5">Memory Compression Interval</label>
            <select 
              value={settings.memoryCompression}
              onChange={(e) => setSettings({ ...settings, memoryCompression: e.target.value })}
              className="w-full bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm"
            >
              <option value="every-5">Every 5 turns</option>
              <option value="every-10">Every 10 turns</option>
              <option value="every-phase">Every phase</option>
            </select>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <Button className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white">
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  )
}

// Project Setup Modal
interface ProjectSetupModalProps {
  isOpen: boolean
  onClose: () => void
}

interface CustomerPersonality {
  id: string
  agent: Agent
  archetype: string
  engagement: number
  trust: number
  riskTolerance: number
}

const archetypes = [
  'The Skeptic',
  'The Absent Sponsor',
  'The Spreadsheet Hoarder',
  'The Reluctant Champion',
  'The Process Purist',
  'The Shadow IT Builder',
  'The Hands-On Expert',
  'The Change Resistor',
  'The Enthusiast',
  'The Overwhelmed',
]

function generatePersonality(): Omit<CustomerPersonality, 'id' | 'agent'> {
  return {
    archetype: archetypes[Math.floor(Math.random() * archetypes.length)],
    engagement: Math.floor(Math.random() * 80) + 20,
    trust: Math.floor(Math.random() * 70) + 20,
    riskTolerance: Math.floor(Math.random() * 70) + 10,
  }
}

export function ProjectSetupModal({ isOpen, onClose }: ProjectSetupModalProps) {
  const [step, setStep] = useState(1)
  const [projectName, setProjectName] = useState('')
  const [industry, setIndustry] = useState('Manufacturing')
  const [scopeDoc, setScopeDoc] = useState('')
  const [methodologyDoc, setMethodologyDoc] = useState('')
  
  const customerAgents = agents.filter(a => a.side === 'customer')
  const [personalities, setPersonalities] = useState<CustomerPersonality[]>(
    customerAgents.map(agent => ({
      id: agent.id,
      agent,
      ...generatePersonality(),
    }))
  )

  const rerollAgent = (id: string) => {
    setPersonalities(prev => prev.map(p => 
      p.id === id ? { ...p, ...generatePersonality() } : p
    ))
  }

  const rerollAll = () => {
    setPersonalities(prev => prev.map(p => ({ ...p, ...generatePersonality() })))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-[#18181b] border border-[#27272a] rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-[#27272a]">
          <h2 className="text-lg font-semibold text-white">Project Setup</h2>
          <button onClick={onClose} className="text-[#71717a] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#27272a]">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div className={cn(
                "h-6 w-6 rounded-full flex items-center justify-center text-xs font-medium",
                step >= s ? "bg-[#3b82f6] text-white" : "bg-[#27272a] text-[#71717a]"
              )}>
                {s}
              </div>
              {s < 4 && <div className={cn("w-8 h-0.5", step > s ? "bg-[#3b82f6]" : "bg-[#27272a]")} />}
            </div>
          ))}
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">Step 1: Project Information</h3>
              <div>
                <label className="block text-sm text-[#71717a] mb-1.5">Project Name</label>
                <Input 
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="bg-[#27272a] border-[#27272a] text-white"
                  placeholder="e.g. Apex Manufacturing S/4HANA Transformation"
                />
              </div>
              <div>
                <label className="block text-sm text-[#71717a] mb-1.5">Industry</label>
                <select 
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="w-full bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm"
                >
                  <option>Manufacturing</option>
                  <option>Retail</option>
                  <option>Services</option>
                  <option>Pharma</option>
                  <option>Logistics</option>
                  <option>Energy</option>
                  <option>Custom</option>
                </select>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">Step 2: Project Scope Document</h3>
              <div className="border-2 border-dashed border-[#27272a] rounded-lg p-6 text-center">
                <Upload className="h-8 w-8 text-[#71717a] mx-auto mb-2" />
                <p className="text-sm text-[#71717a] mb-2">Upload or paste your project scope document</p>
                <textarea 
                  value={scopeDoc}
                  onChange={(e) => setScopeDoc(e.target.value)}
                  className="w-full h-32 bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm resize-none mt-2"
                  placeholder="Paste markdown content here..."
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">Step 3: Methodology (Optional)</h3>
              <p className="text-xs text-[#71717a] mb-2">Leave empty to use SAP Activate by default</p>
              <div className="border-2 border-dashed border-[#27272a] rounded-lg p-6 text-center">
                <Upload className="h-8 w-8 text-[#71717a] mx-auto mb-2" />
                <p className="text-sm text-[#71717a] mb-2">Upload or paste your methodology document</p>
                <textarea 
                  value={methodologyDoc}
                  onChange={(e) => setMethodologyDoc(e.target.value)}
                  className="w-full h-32 bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm resize-none mt-2"
                  placeholder="Paste markdown content here..."
                />
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-white">Step 4: Customer Personalities</h3>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={rerollAll}
                  className="bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  Re-roll All
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {personalities.map((p) => (
                  <div 
                    key={p.id}
                    className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-[#f59e0b]/20 text-[#f59e0b] flex items-center justify-center text-[9px] font-bold">
                          {p.agent.initials}
                        </div>
                        <span className="text-xs font-medium text-white">{p.agent.codename}</span>
                      </div>
                      <button 
                        onClick={() => rerollAgent(p.id)}
                        className="text-[#71717a] hover:text-white"
                      >
                        <RefreshCw className="h-3 w-3" />
                      </button>
                    </div>
                    <div className="text-[10px] text-[#f59e0b] mb-2">{p.archetype}</div>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-[#71717a]">Engagement</span>
                        <div className="w-16 h-1 bg-[#27272a] rounded-full overflow-hidden">
                          <div className="h-full bg-[#3b82f6] rounded-full" style={{ width: `${p.engagement}%` }} />
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-[#71717a]">Trust</span>
                        <div className="w-16 h-1 bg-[#27272a] rounded-full overflow-hidden">
                          <div className="h-full bg-[#22c55e] rounded-full" style={{ width: `${p.trust}%` }} />
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-[9px]">
                        <span className="text-[#71717a]">Risk Tolerance</span>
                        <div className="w-16 h-1 bg-[#27272a] rounded-full overflow-hidden">
                          <div className="h-full bg-[#f59e0b] rounded-full" style={{ width: `${p.riskTolerance}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between p-4 border-t border-[#27272a]">
          <Button 
            variant="outline"
            onClick={() => setStep(s => Math.max(1, s - 1))}
            disabled={step === 1}
            className="bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
          >
            Back
          </Button>
          {step < 4 ? (
            <Button 
              onClick={() => setStep(s => s + 1)}
              className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white"
            >
              Next
            </Button>
          ) : (
            <Button 
              onClick={onClose}
              className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white"
            >
              Launch Simulation
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// Agent Detail Modal
interface AgentDetailModalProps {
  agent: Agent | null
  onClose: () => void
}

export function AgentDetailModal({ agent, onClose }: AgentDetailModalProps) {
  if (!agent) return null

  const avatarBg = agent.side === 'consultant' 
    ? 'bg-[#3b82f6]/20 text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'bg-[#f59e0b]/20 text-[#f59e0b]' 
      : 'bg-[#71717a]/20 text-[#71717a]'

  const sideColor = agent.side === 'consultant' 
    ? 'text-[#3b82f6]' 
    : agent.side === 'customer' 
      ? 'text-[#f59e0b]' 
      : 'text-[#71717a]'

  // Mock activity log
  const activityLog = [
    { time: '10:23am', content: 'Reviewed integration documentation' },
    { time: '10:15am', content: 'Participated in FI-CO meeting' },
    { time: '9:45am', content: 'Updated task status to In Progress' },
    { time: '9:30am', content: 'Started daily standup' },
    { time: '9:00am', content: 'Logged in to simulation' },
  ]

  // Mock relationships
  const relationships = agents.slice(0, 6).filter(a => a.id !== agent.id)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-[#18181b] border border-[#27272a] rounded-lg w-full max-w-lg max-h-[90vh] overflow-hidden shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-[#27272a]">
          <h2 className="text-lg font-semibold text-white">Agent Profile</h2>
          <button onClick={onClose} className="text-[#71717a] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-60px)] space-y-4">
          {/* Header */}
          <div className="flex items-center gap-4">
            <div className={cn("h-14 w-14 rounded-full flex items-center justify-center text-xl font-bold", avatarBg)}>
              {agent.initials}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">{agent.codename}</h3>
              <p className="text-sm text-[#71717a]">{agent.role}</p>
              <p className={cn("text-xs font-medium capitalize", sideColor)}>{agent.side}</p>
            </div>
          </div>

          {/* Personality (for customer agents) */}
          {agent.personality && (
            <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg">
              <div className="text-sm font-medium text-[#f59e0b] mb-2">{agent.personality.archetype}</div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-[#71717a]">Engagement</span>
                    <span className="text-white">{agent.personality.engagement}%</span>
                  </div>
                  <div className="h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                    <div className="h-full bg-[#3b82f6] rounded-full" style={{ width: `${agent.personality.engagement}%` }} />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-[#71717a]">Trust</span>
                    <span className="text-white">{agent.personality.trust}%</span>
                  </div>
                  <div className="h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                    <div className="h-full bg-[#22c55e] rounded-full" style={{ width: `${agent.personality.trust}%` }} />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-[#71717a]">Risk Tolerance</span>
                    <span className="text-white">{agent.personality.riskTolerance}%</span>
                  </div>
                  <div className="h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                    <div className="h-full bg-[#f59e0b] rounded-full" style={{ width: `${agent.personality.riskTolerance}%` }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Current Status */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2">CURRENT STATUS</h4>
            <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <div className={cn(
                  "h-2 w-2 rounded-full",
                  agent.status === 'thinking' ? 'bg-[#f59e0b]' : agent.status === 'speaking' ? 'bg-[#22c55e]' : 'bg-[#71717a]'
                )} />
                <span className="text-sm text-white capitalize">{agent.status}</span>
              </div>
              <p className="text-xs text-[#71717a]">Current task: Reviewing integration documentation for MM module</p>
            </div>
          </div>

          {/* Activity Log */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <MessageSquare className="h-3 w-3" />
              ACTIVITY LOG
            </h4>
            <div className="space-y-2">
              {activityLog.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-[#71717a] shrink-0 w-14">{item.time}</span>
                  <span className="text-[#e4e4e7]">{item.content}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Tools */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <Wrench className="h-3 w-3" />
              TOOLS
            </h4>
            <div className="flex flex-wrap gap-1.5">
              <span className="px-2 py-1 bg-[#a855f7]/20 text-[#a855f7] text-[10px] rounded">Integration Touchpoint Tracker</span>
              <span className="px-2 py-1 bg-[#27272a] text-[#71717a] text-[10px] rounded">Config Drift Detector</span>
            </div>
          </div>

          {/* Relationships */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2">FREQUENT INTERACTIONS</h4>
            <div className="flex flex-wrap gap-2">
              {relationships.map((a) => (
                <div key={a.id} className="flex items-center gap-1.5 px-2 py-1 bg-[#27272a]/50 rounded">
                  <div className={cn(
                    "h-5 w-5 rounded-full flex items-center justify-center text-[8px] font-bold",
                    a.side === 'consultant' ? 'bg-[#3b82f6]/20 text-[#3b82f6]' : a.side === 'customer' ? 'bg-[#f59e0b]/20 text-[#f59e0b]' : 'bg-[#71717a]/20 text-[#71717a]'
                  )}>
                    {a.initials}
                  </div>
                  <span className="text-[10px] text-white">{a.codename}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
