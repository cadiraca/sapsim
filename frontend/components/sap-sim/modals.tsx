'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  X,
  Eye,
  EyeOff,
  RefreshCw,
  Upload,
  MessageSquare,
  Wrench,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { api } from '@/lib/api'
import { useProject } from '@/lib/project-context'
import type {
  Agent,
  AgentDetailResponse,
  CreateProjectRequest,
  SettingsResponse,
  SettingsUpdateRequest,
} from '@/lib/types'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Settings Modal
// ---------------------------------------------------------------------------

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { activeProject } = useProject()
  const [showApiKey, setShowApiKey] = useState(false)
  const [settings, setSettings] = useState<SettingsUpdateRequest>({
    litellm_base_url: 'http://localhost:4000',
    litellm_api_key: '',
    litellm_model: 'gpt-4o',
    max_parallel_agents: 10,
    memory_compression_interval: 'every-10',
  })

  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null)
  const [healthResult, setHealthResult] = useState<{ ok: boolean; message: string } | null>(null)

  // Load current settings when modal opens
  useEffect(() => {
    if (!isOpen) return
    setLoading(true)
    setTestResult(null)
    setSaveResult(null)
    setHealthResult(null)
    // Settings API requires a project name; use active project or skip gracefully
    if (!activeProject) { setLoading(false); return }
    api
      .getSettings(activeProject)
      .then((data: SettingsResponse) => {
        setSettings({
          litellm_base_url: data.litellm_base_url,
          litellm_api_key: data.litellm_api_key ?? '',
          litellm_model: data.litellm_model,
          max_parallel_agents: data.max_parallel_agents,
          memory_compression_interval: data.memory_compression_interval,
        })
      })
      .catch(() => {
        // If backend unreachable or no project yet, keep defaults
      })
      .finally(() => setLoading(false))
  }, [isOpen])

  const handleSave = async () => {
    setSaving(true)
    setSaveResult(null)
    try {
      if (!activeProject) throw new Error('No active project')
      await api.updateSettings(activeProject, settings)
      setSaveResult({ success: true, message: 'Settings saved.' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed.'
      setSaveResult({ success: false, message: msg })
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.testSettings({
        litellm_base_url: settings.litellm_base_url ?? '',
        litellm_api_key: settings.litellm_api_key ?? '',
        litellm_model: settings.litellm_model ?? '',
      })
      setTestResult({
        success: result.success,
        message: result.success
          ? `OK — ${result.model_used ?? 'model'} (${result.latency_ms}ms)`
          : result.error ?? 'Test failed.',
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Test failed.'
      setTestResult({ success: false, message: msg })
    } finally {
      setTesting(false)
    }
  }

  const handleHealthCheck = async () => {
    setHealthResult(null)
    try {
      const result = await api.health()
      setHealthResult({ ok: true, message: `${result.service}: ${result.status}` })
    } catch {
      setHealthResult({ ok: false, message: 'Backend unreachable.' })
    }
  }

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

        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-[#71717a]" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* API Health Check */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleHealthCheck}
                className="bg-transparent border-[#27272a] text-white hover:bg-[#27272a] text-xs"
              >
                Test Connection
              </Button>
              {healthResult && (
                <span
                  className={cn(
                    'text-xs flex items-center gap-1',
                    healthResult.ok ? 'text-[#22c55e]' : 'text-[#ef4444]',
                  )}
                >
                  {healthResult.ok ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <AlertCircle className="h-3 w-3" />
                  )}
                  {healthResult.message}
                </span>
              )}
            </div>

            <div>
              <label className="block text-sm text-[#71717a] mb-1.5">LiteLLM Base URL</label>
              <Input
                value={settings.litellm_base_url ?? ''}
                onChange={(e) => setSettings({ ...settings, litellm_base_url: e.target.value })}
                className="bg-[#27272a] border-[#27272a] text-white"
                placeholder="http://localhost:4000"
              />
            </div>

            <div>
              <label className="block text-sm text-[#71717a] mb-1.5">API Key / Service Key</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={settings.litellm_api_key ?? ''}
                  onChange={(e) => setSettings({ ...settings, litellm_api_key: e.target.value })}
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
              <div className="flex gap-2">
                <Input
                  value={settings.litellm_model ?? ''}
                  onChange={(e) => setSettings({ ...settings, litellm_model: e.target.value })}
                  className="bg-[#27272a] border-[#27272a] text-white"
                  placeholder="e.g. gpt-4o, claude-3-5-sonnet"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTestConnection}
                  disabled={testing}
                  className="bg-transparent border-[#27272a] text-white hover:bg-[#27272a] shrink-0"
                >
                  {testing ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Test LLM'}
                </Button>
              </div>
              {testResult && (
                <p
                  className={cn(
                    'text-xs mt-1 flex items-center gap-1',
                    testResult.success ? 'text-[#22c55e]' : 'text-[#ef4444]',
                  )}
                >
                  {testResult.success ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <AlertCircle className="h-3 w-3" />
                  )}
                  {testResult.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm text-[#71717a] mb-1.5">
                Max Parallel Agents:{' '}
                <span className="text-white">{settings.max_parallel_agents}</span>
              </label>
              <Slider
                value={[settings.max_parallel_agents ?? 10]}
                onValueChange={(v) => setSettings({ ...settings, max_parallel_agents: v[0] })}
                min={1}
                max={30}
                step={1}
                className="py-2"
              />
            </div>

            <div>
              <label className="block text-sm text-[#71717a] mb-1.5">
                Memory Compression Interval
              </label>
              <select
                value={settings.memory_compression_interval ?? 'every-10'}
                onChange={(e) =>
                  setSettings({ ...settings, memory_compression_interval: e.target.value })
                }
                className="w-full bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm"
              >
                <option value="every-5">Every 5 turns</option>
                <option value="every-10">Every 10 turns</option>
                <option value="every-phase">Every phase</option>
              </select>
            </div>

            {saveResult && (
              <p
                className={cn(
                  'text-xs flex items-center gap-1',
                  saveResult.success ? 'text-[#22c55e]' : 'text-[#ef4444]',
                )}
              >
                {saveResult.success ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <AlertCircle className="h-3 w-3" />
                )}
                {saveResult.message}
              </p>
            )}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <Button
            onClick={handleSave}
            disabled={saving || loading}
            className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Project Setup Modal
// ---------------------------------------------------------------------------

interface ProjectSetupModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated?: (projectName: string) => void
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

/** Quick random personality used when displaying placeholder rolls */
function randomPersonality() {
  return {
    archetype: archetypes[Math.floor(Math.random() * archetypes.length)],
    engagement: Math.floor(Math.random() * 80) + 20,
    trust: Math.floor(Math.random() * 70) + 20,
    riskTolerance: Math.floor(Math.random() * 70) + 10,
  }
}

/** Default customer role codenames shown in the personality preview */
const DEFAULT_CUSTOMER_STUBS = [
  { id: 'c1', initials: 'ES', codename: 'EXEC_SPONSOR' },
  { id: 'c2', initials: 'PM', codename: 'PROJ_MANAGER' },
  { id: 'c3', initials: 'FA', codename: 'FIN_ANALYST' },
  { id: 'c4', initials: 'LM', codename: 'LOGISTICS_MGR' },
  { id: 'c5', initials: 'IO', codename: 'IT_OWNER' },
  { id: 'c6', initials: 'PR', codename: 'PROC_OWNER' },
]

interface PersonalityEntry {
  id: string
  initials: string
  codename: string
  archetype: string
  engagement: number
  trust: number
  riskTolerance: number
}

export function ProjectSetupModal({
  isOpen,
  onClose,
  onProjectCreated,
}: ProjectSetupModalProps) {
  const [step, setStep] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step 1 fields
  const [projectName, setProjectName] = useState('')
  const [methodology, setMethodology] = useState('SAP Activate')
  const [duration, setDuration] = useState('180')
  const [teamSize, setTeamSize] = useState('15')
  const [industry, setIndustry] = useState('Manufacturing')

  // Step 2 — scope document
  const [scopeDoc, setScopeDoc] = useState('')

  // Step 3 — methodology document
  const [methodologyDoc, setMethodologyDoc] = useState('')

  // Step 4 — personality preview (purely visual; reroll is cosmetic)
  const [personalities, setPersonalities] = useState<PersonalityEntry[]>(
    DEFAULT_CUSTOMER_STUBS.map((s) => ({ ...s, ...randomPersonality() })),
  )

  const rerollAgent = useCallback((id: string) => {
    setPersonalities((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...randomPersonality() } : p)),
    )
  }, [])

  const rerollAll = useCallback(() => {
    setPersonalities((prev) => prev.map((p) => ({ ...p, ...randomPersonality() })))
  }, [])

  const handleLaunch = async () => {
    setError(null)
    if (!projectName.trim()) {
      setError('Project name is required.')
      setStep(1)
      return
    }

    setSubmitting(true)
    try {
      // Slugify: replace spaces/special chars with hyphens, collapse runs, trim edges
      const slug = projectName.trim()
        .replace(/[^a-zA-Z0-9_-]+/g, '-')
        .replace(/-{2,}/g, '-')
        .replace(/^-|-$/g, '')
      if (!slug) {
        setError('Project name must contain at least one alphanumeric character.')
        setStep(1)
        setSubmitting(false)
        return
      }
      const req: CreateProjectRequest = {
        name: slug,
        industry,
        scope: scopeDoc.trim() || undefined,
        methodology: methodologyDoc.trim() || methodology,
      }
      const project = await api.createProject(req)
      onProjectCreated?.(project.project_name)
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create project.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // Reset on close
  const handleClose = () => {
    setStep(1)
    setError(null)
    setProjectName('')
    setScopeDoc('')
    setMethodologyDoc('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={handleClose} />
      <div className="relative bg-[#18181b] border border-[#27272a] rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-[#27272a]">
          <h2 className="text-lg font-semibold text-white">New Project Setup</h2>
          <button onClick={handleClose} className="text-[#71717a] hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#27272a]">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={cn(
                  'h-6 w-6 rounded-full flex items-center justify-center text-xs font-medium',
                  step >= s ? 'bg-[#3b82f6] text-white' : 'bg-[#27272a] text-[#71717a]',
                )}
              >
                {s}
              </div>
              {s < 4 && (
                <div
                  className={cn('w-8 h-0.5', step > s ? 'bg-[#3b82f6]' : 'bg-[#27272a]')}
                />
              )}
            </div>
          ))}
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          {/* ── Step 1: Project Information ── */}
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">Step 1: Project Information</h3>

              <div>
                <label className="block text-sm text-[#71717a] mb-1.5">
                  Project Name <span className="text-[#ef4444]">*</span>
                </label>
                <Input
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="bg-[#27272a] border-[#27272a] text-white"
                  placeholder="e.g. Cables-Company"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-[#71717a] mb-1.5">Methodology</label>
                  <select
                    value={methodology}
                    onChange={(e) => setMethodology(e.target.value)}
                    className="w-full bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm"
                  >
                    <option>SAP Activate</option>
                    <option>ASAP</option>
                    <option>Agile / SAFe</option>
                    <option>Custom</option>
                  </select>
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-[#71717a] mb-1.5">
                    Duration (days)
                  </label>
                  <Input
                    type="number"
                    min={30}
                    max={730}
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    className="bg-[#27272a] border-[#27272a] text-white"
                    placeholder="180"
                  />
                </div>
                <div>
                  <label className="block text-sm text-[#71717a] mb-1.5">Team Size</label>
                  <Input
                    type="number"
                    min={5}
                    max={100}
                    value={teamSize}
                    onChange={(e) => setTeamSize(e.target.value)}
                    className="bg-[#27272a] border-[#27272a] text-white"
                    placeholder="15"
                  />
                </div>
              </div>

              {error && (
                <p className="text-xs text-[#ef4444] flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {error}
                </p>
              )}
            </div>
          )}

          {/* ── Step 2: Scope Document ── */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">
                Step 2: Project Scope Document
              </h3>
              <div className="border-2 border-dashed border-[#27272a] rounded-lg p-6">
                <Upload className="h-8 w-8 text-[#71717a] mx-auto mb-2" />
                <p className="text-sm text-[#71717a] text-center mb-2">
                  Upload or paste your project scope document
                </p>
                <textarea
                  value={scopeDoc}
                  onChange={(e) => setScopeDoc(e.target.value)}
                  className="w-full h-40 bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm resize-none mt-2"
                  placeholder="Paste markdown content here... (optional)"
                />
              </div>
            </div>
          )}

          {/* ── Step 3: Methodology Document ── */}
          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-white mb-4">
                Step 3: Methodology Document (Optional)
              </h3>
              <p className="text-xs text-[#71717a]">
                Leave empty to use <strong className="text-white">{methodology}</strong> defaults.
              </p>
              <div className="border-2 border-dashed border-[#27272a] rounded-lg p-6">
                <Upload className="h-8 w-8 text-[#71717a] mx-auto mb-2" />
                <p className="text-sm text-[#71717a] text-center mb-2">
                  Upload or paste your methodology document
                </p>
                <textarea
                  value={methodologyDoc}
                  onChange={(e) => setMethodologyDoc(e.target.value)}
                  className="w-full h-40 bg-[#27272a] border border-[#27272a] text-white rounded-md px-3 py-2 text-sm resize-none mt-2"
                  placeholder="Paste markdown content here..."
                />
              </div>
            </div>
          )}

          {/* ── Step 4: Customer Personalities Preview ── */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-white">
                  Step 4: Customer Personalities Preview
                </h3>
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
              <p className="text-xs text-[#71717a] mb-2">
                Final personalities are assigned by the backend at simulation start. These are
                preview rolls only.
              </p>
              <div className="grid grid-cols-2 gap-3">
                {personalities.map((p) => (
                  <div
                    key={p.id}
                    className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-[#f59e0b]/20 text-[#f59e0b] flex items-center justify-center text-[9px] font-bold">
                          {p.initials}
                        </div>
                        <span className="text-xs font-medium text-white">{p.codename}</span>
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
                      {[
                        { label: 'Engagement', val: p.engagement, color: 'bg-[#3b82f6]' },
                        { label: 'Trust', val: p.trust, color: 'bg-[#22c55e]' },
                        { label: 'Risk Tolerance', val: p.riskTolerance, color: 'bg-[#f59e0b]' },
                      ].map(({ label, val, color }) => (
                        <div key={label} className="flex items-center justify-between text-[9px]">
                          <span className="text-[#71717a]">{label}</span>
                          <div className="w-16 h-1 bg-[#27272a] rounded-full overflow-hidden">
                            <div
                              className={cn('h-full rounded-full', color)}
                              style={{ width: `${val}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {error && (
                <p className="text-xs text-[#ef4444] flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {error}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between p-4 border-t border-[#27272a]">
          <Button
            variant="outline"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || submitting}
            className="bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
          >
            Back
          </Button>
          {step < 4 ? (
            <Button
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 1 && !projectName.trim()}
              className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white"
            >
              Next
            </Button>
          ) : (
            <Button
              onClick={handleLaunch}
              disabled={submitting}
              className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  Creating…
                </>
              ) : (
                'Launch Simulation'
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent Detail Modal
// ---------------------------------------------------------------------------

interface AgentDetailModalProps {
  agent: Agent | null
  onClose: () => void
  projectName?: string
}

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

export function AgentDetailModal({
  agent,
  onClose,
  projectName,
}: AgentDetailModalProps) {
  const { activeProject } = useProject()
  const resolvedProjectName = projectName ?? activeProject ?? ''
  const [detail, setDetail] = useState<AgentDetailResponse | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Fetch full agent detail whenever the selected agent changes
  useEffect(() => {
    if (!agent) {
      setDetail(null)
      return
    }
    setLoadingDetail(true)
    api
      .getAgent(resolvedProjectName, agent.codename)
      .then((d) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false))
  }, [agent, resolvedProjectName])

  if (!agent) return null

  // Merge lightweight agent prop with full detail (detail wins)
  const resolved = detail ?? agent
  const initials = deriveInitials(resolved.codename)

  const avatarBg =
    resolved.side === 'consultant'
      ? 'bg-[#3b82f6]/20 text-[#3b82f6]'
      : resolved.side === 'customer'
        ? 'bg-[#f59e0b]/20 text-[#f59e0b]'
        : 'bg-[#71717a]/20 text-[#71717a]'

  const sideColor =
    resolved.side === 'consultant'
      ? 'text-[#3b82f6]'
      : resolved.side === 'customer'
        ? 'text-[#f59e0b]'
        : 'text-[#71717a]'

  const statusColor =
    resolved.status === 'thinking'
      ? 'bg-[#f59e0b]'
      : resolved.status === 'speaking'
        ? 'bg-[#22c55e]'
        : resolved.status === 'in_meeting'
          ? 'bg-[#a855f7]'
          : 'bg-[#71717a]'

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
          {/* ── Header ── */}
          <div className="flex items-center gap-4">
            <div
              className={cn(
                'h-14 w-14 rounded-full flex items-center justify-center text-xl font-bold',
                avatarBg,
              )}
            >
              {initials}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">{resolved.codename}</h3>
              <p className="text-sm text-[#71717a]">{resolved.role}</p>
              <p className={cn('text-xs font-medium capitalize', sideColor)}>{resolved.side}</p>
              {resolved.tier && (
                <p className="text-[10px] text-[#71717a] capitalize">{resolved.tier} tier</p>
              )}
            </div>
            {loadingDetail && (
              <Loader2 className="h-4 w-4 animate-spin text-[#71717a] ml-auto" />
            )}
          </div>

          {/* ── Personality Radar Chart (customer agents) ── */}
          {resolved.personality && (() => {
            const radarData = [
              { trait: 'Engagement', value: scoreToPercent(resolved.personality!.engagement) },
              { trait: 'Trust', value: scoreToPercent(resolved.personality!.trust) },
              { trait: 'Risk Tolerance', value: scoreToPercent(resolved.personality!.risk_tolerance) },
            ]
            return (
              <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg">
                <div className="text-sm font-medium text-[#f59e0b] mb-1">
                  {resolved.personality!.archetype}
                </div>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                      <PolarGrid stroke="#27272a" />
                      <PolarAngleAxis
                        dataKey="trait"
                        tick={{ fill: '#a1a1aa', fontSize: 10 }}
                      />
                      <PolarRadiusAxis
                        angle={90}
                        domain={[0, 100]}
                        tick={{ fill: '#52525b', fontSize: 8 }}
                        tickCount={5}
                      />
                      <Radar
                        name="Personality"
                        dataKey="value"
                        stroke="#f59e0b"
                        fill="#f59e0b"
                        fillOpacity={0.25}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
                {/* Numeric summary below chart */}
                <div className="grid grid-cols-3 gap-2 mt-1">
                  {radarData.map(({ trait, value }) => (
                    <div key={trait} className="text-center">
                      <div className="text-xs text-white font-medium">{value}%</div>
                      <div className="text-[9px] text-[#71717a]">{trait}</div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* ── Current Status ── */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2">CURRENT STATUS</h4>
            <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <div className={cn('h-2 w-2 rounded-full', statusColor)} />
                <span className="text-sm text-white capitalize">
                  {resolved.status.replace('_', ' ')}
                </span>
              </div>
              <p className="text-xs text-[#71717a]">
                {resolved.current_task ?? 'No active task'}
              </p>
            </div>
          </div>

          {/* ── Memory Summary (from detail) ── */}
          {detail?.memory_summary && (
            <div>
              <h4 className="text-xs font-medium text-[#71717a] mb-2">MEMORY SUMMARY</h4>
              <div className="p-3 bg-[#27272a]/50 border border-[#27272a] rounded-lg text-xs text-[#a1a1aa]">
                <p>{detail.memory_summary}</p>
                {detail.memory_turns > 0 && (
                  <p className="mt-1 text-[#52525b]">{detail.memory_turns} memory turns</p>
                )}
              </div>
            </div>
          )}

          {/* ── Communication History / Activity ── */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <MessageSquare className="h-3 w-3" />
              {detail?.recent_activity && detail.recent_activity.length > 0
                ? 'RECENT ACTIVITY'
                : 'COMMUNICATION HISTORY'}
            </h4>
            <div className="space-y-2">
              {detail?.recent_activity && detail.recent_activity.length > 0 ? (
                detail.recent_activity.slice(0, 8).map((item, i) => {
                  const timestamp =
                    (item as Record<string, unknown>).timestamp as string | undefined
                  const content =
                    ((item as Record<string, unknown>).content as string | undefined) ??
                    ((item as Record<string, unknown>).message as string | undefined) ??
                    JSON.stringify(item)
                  const timeLabel = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `#${i + 1}`
                  return (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-[#71717a] shrink-0 w-14">{timeLabel}</span>
                      <span className="text-[#e4e4e7]">{content}</span>
                    </div>
                  )
                })
              ) : (
                <p className="text-xs text-[#52525b] italic">
                  {loadingDetail ? 'Loading activity…' : 'No recent activity recorded.'}
                </p>
              )}
            </div>
          </div>

          {/* ── Skills / Tools ── */}
          <div>
            <h4 className="text-xs font-medium text-[#71717a] mb-2 flex items-center gap-1">
              <Wrench className="h-3 w-3" />
              {detail?.skills && detail.skills.length > 0 ? 'SKILLS' : 'TOOLS'}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {detail?.skills && detail.skills.length > 0 ? (
                detail.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2 py-1 bg-[#a855f7]/20 text-[#a855f7] text-[10px] rounded"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <>
                  <span className="px-2 py-1 bg-[#a855f7]/20 text-[#a855f7] text-[10px] rounded">
                    Integration Touchpoint Tracker
                  </span>
                  <span className="px-2 py-1 bg-[#27272a] text-[#71717a] text-[10px] rounded">
                    Config Drift Detector
                  </span>
                </>
              )}
            </div>
          </div>

          {/* ── Model info ── */}
          {resolved.model && (
            <div className="text-[10px] text-[#52525b]">
              Model: <span className="text-[#71717a]">{resolved.model}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
