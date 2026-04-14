'use client'

import { useEffect, useRef, useState } from 'react'
import { Bell, Plus, Download, ChevronDown, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useProject } from '@/lib/project-context'
import type { SimulationStatusResponse } from '@/lib/types'

interface TopBarProps {
  onNewProject: () => void
}

export function TopBar({ onNewProject }: TopBarProps) {
  const { activeProject, projectList, setActiveProject } = useProject()

  const [status, setStatus] = useState<SimulationStatusResponse | null>(null)
  const [notificationCount, setNotificationCount] = useState(0)
  const [connected, setConnected] = useState(false)
  const [selectorOpen, setSelectorOpen] = useState(false)
  const selectorRef = useRef<HTMLDivElement>(null)

  // Close selector when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setSelectorOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // ---------------------------------------------------------------------------
  // Fetch simulation status on mount + poll every 5 s
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!activeProject) return
    let cancelled = false

    const fetchStatus = async () => {
      try {
        const data = await api.getStatus(activeProject)
        if (!cancelled) {
          setStatus(data)
          setConnected(true)
          setNotificationCount(data.pending_decisions?.length ?? 0)
        }
      } catch {
        if (!cancelled) {
          setConnected(false)
          setStatus(null)
        }
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [activeProject])

  // ---------------------------------------------------------------------------
  // Simulation control helpers
  // ---------------------------------------------------------------------------
  const handleStart = async () => {
    if (!activeProject) return
    try {
      await api.startSimulation(activeProject)
      const fresh = await api.getStatus(activeProject)
      setStatus(fresh)
    } catch (err) {
      console.error('Start failed:', err)
    }
  }

  const handlePause = async () => {
    if (!activeProject) return
    try {
      await api.pauseSimulation(activeProject)
      const fresh = await api.getStatus(activeProject)
      setStatus(fresh)
    } catch (err) {
      console.error('Pause failed:', err)
    }
  }

  const handleStop = async () => {
    if (!activeProject) return
    try {
      await api.stopSimulation(activeProject)
      const fresh = await api.getStatus(activeProject)
      setStatus(fresh)
    } catch (err) {
      console.error('Stop failed:', err)
    }
  }

  // Derived display values (fall back gracefully while loading)
  const projectName = status?.project_name ?? activeProject ?? '—'
  const phase = status?.current_phase ?? '—'
  const day = status?.simulated_day ?? '—'
  const totalDays = status?.total_days ?? '—'
  const simStatus = status?.status ?? 'IDLE'

  return (
    <header className="h-10 bg-[#18181b] border-b border-[#27272a] flex items-center justify-between px-4 shrink-0">
      {/* Left: branding */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-white">SAP SIM</span>
      </div>

      {/* Centre: project selector + live project info */}
      <div className="flex items-center gap-1 text-xs text-[#71717a]">
        {/* Project Selector Dropdown */}
        <div className="relative" ref={selectorRef}>
          <button
            onClick={() => setSelectorOpen((o) => !o)}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[#27272a] transition-colors"
            title="Switch project"
          >
            <span className="text-white font-medium">PROJECT:</span>
            <span className="text-[#f59e0b] font-semibold">{projectName}</span>
            <ChevronDown className="h-3 w-3 text-[#71717a]" />
          </button>

          {selectorOpen && (
            <div className="absolute top-full left-0 mt-1 w-56 bg-[#18181b] border border-[#27272a] rounded-lg shadow-xl z-50 overflow-hidden">
              {/* Project list */}
              <div className="max-h-48 overflow-y-auto py-1">
                {projectList.length === 0 ? (
                  <div className="px-3 py-2 text-[10px] text-[#71717a]">No projects yet</div>
                ) : (
                  projectList.map((name) => (
                    <button
                      key={name}
                      onClick={() => {
                        setActiveProject(name)
                        setSelectorOpen(false)
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[#27272a] transition-colors text-left"
                    >
                      <Check
                        className={`h-3 w-3 shrink-0 ${
                          name === activeProject ? 'text-[#3b82f6]' : 'opacity-0'
                        }`}
                      />
                      <span
                        className={
                          name === activeProject
                            ? 'text-white font-medium'
                            : 'text-[#a1a1aa]'
                        }
                      >
                        {name}
                      </span>
                    </button>
                  ))
                )}
              </div>

              {/* New Project button inside dropdown */}
              <div className="border-t border-[#27272a] p-1">
                <button
                  onClick={() => {
                    setSelectorOpen(false)
                    onNewProject()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-[#3b82f6] hover:bg-[#27272a] rounded transition-colors"
                >
                  <Plus className="h-3 w-3" />
                  New Project
                </button>
              </div>
            </div>
          )}
        </div>

        <span className="mx-1">·</span>
        <span>Phase:</span>
        <span className="text-[#3b82f6] font-medium capitalize">{phase}</span>
        <span className="mx-1">·</span>
        <span>Day {day} of ~{totalDays}</span>
        {status && (
          <>
            <span className="mx-1">·</span>
            <span
              className={
                simStatus === 'RUNNING'
                  ? 'text-[#22c55e] font-medium'
                  : simStatus === 'PAUSED'
                  ? 'text-[#f59e0b] font-medium'
                  : 'text-[#ef4444] font-medium'
              }
            >
              {simStatus}
            </span>
          </>
        )}
      </div>

      {/* Right: controls */}
      <div className="flex items-center gap-3">
        {/* LiteLLM connection indicator */}
        <div className="flex items-center gap-1.5 text-xs text-[#71717a]">
          <span className="relative flex h-2 w-2">
            {connected && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75" />
            )}
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                connected ? 'bg-[#22c55e]' : 'bg-[#ef4444]'
              }`}
            />
          </span>
          <span>{connected ? 'LiteLLM Connected' : 'Connecting…'}</span>
        </div>

        {/* Simulation control buttons */}
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            className="h-7 text-xs bg-[#22c55e] hover:bg-[#22c55e]/80 text-white"
            onClick={handleStart}
            disabled={!activeProject || simStatus === 'RUNNING'}
          >
            ▶ Run
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
            onClick={handlePause}
            disabled={!activeProject || simStatus !== 'RUNNING'}
          >
            ⏸ Pause
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
            onClick={handleStop}
            disabled={!activeProject || simStatus === 'STOPPED' || simStatus === 'IDLE'}
          >
            ■ Stop
          </Button>
        </div>

        {/* Notifications */}
        <button className="relative p-1 hover:bg-[#27272a] rounded">
          <Bell className="h-4 w-4 text-[#71717a]" />
          {notificationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 h-3.5 w-3.5 bg-[#ef4444] rounded-full text-[9px] font-bold flex items-center justify-center text-white">
              {notificationCount > 9 ? '9+' : notificationCount}
            </span>
          )}
        </button>

        {/* Export Report */}
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs text-[#71717a] hover:text-white hover:bg-[#27272a]"
        >
          <Download className="h-3 w-3 mr-1" />
          Export Report
        </Button>
      </div>
    </header>
  )
}
