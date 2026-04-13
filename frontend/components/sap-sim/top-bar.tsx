'use client'

import { useEffect, useState } from 'react'
import { Bell, Plus, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import type { SimulationStatusResponse } from '@/lib/types'

// Project name — kept in a single place; swap out once we have a project
// context/store in a later phase.
const PROJECT_NAME = 'Cables-Company'

interface TopBarProps {
  onNewProject: () => void
}

export function TopBar({ onNewProject }: TopBarProps) {
  const [status, setStatus] = useState<SimulationStatusResponse | null>(null)
  const [notificationCount, setNotificationCount] = useState(0)
  const [connected, setConnected] = useState(false)

  // ---------------------------------------------------------------------------
  // Fetch simulation status on mount + poll every 5 s
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false

    const fetchStatus = async () => {
      try {
        const data = await api.getStatus(PROJECT_NAME)
        if (!cancelled) {
          setStatus(data)
          setConnected(true)
          // Use pending decisions count as a proxy for notifications
          setNotificationCount(data.pending_decisions?.length ?? 0)
        }
      } catch {
        if (!cancelled) setConnected(false)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Simulation control helpers
  // ---------------------------------------------------------------------------
  const handleStart = async () => {
    try {
      await api.startSimulation(PROJECT_NAME)
      const fresh = await api.getStatus(PROJECT_NAME)
      setStatus(fresh)
    } catch (err) {
      console.error('Start failed:', err)
    }
  }

  const handlePause = async () => {
    try {
      await api.pauseSimulation(PROJECT_NAME)
      const fresh = await api.getStatus(PROJECT_NAME)
      setStatus(fresh)
    } catch (err) {
      console.error('Pause failed:', err)
    }
  }

  const handleStop = async () => {
    try {
      await api.stopSimulation(PROJECT_NAME)
      const fresh = await api.getStatus(PROJECT_NAME)
      setStatus(fresh)
    } catch (err) {
      console.error('Stop failed:', err)
    }
  }

  // Derived display values (fall back gracefully while loading)
  const projectName = status?.project_name ?? PROJECT_NAME
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

      {/* Centre: live project info */}
      <div className="flex items-center gap-1 text-xs text-[#71717a]">
        <span className="text-white font-medium">PROJECT:</span>
        <span className="text-[#f59e0b]">{projectName}</span>
        <span className="mx-2">·</span>
        <span>Phase:</span>
        <span className="text-[#3b82f6] font-medium capitalize">{phase}</span>
        <span className="mx-2">·</span>
        <span>Day {day} of ~{totalDays}</span>
        {status && (
          <>
            <span className="mx-2">·</span>
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
            disabled={simStatus === 'RUNNING'}
          >
            ▶ Run
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
            onClick={handlePause}
            disabled={simStatus !== 'RUNNING'}
          >
            ⏸ Pause
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs bg-transparent border-[#27272a] text-white hover:bg-[#27272a]"
            onClick={handleStop}
            disabled={simStatus === 'STOPPED' || simStatus === 'IDLE'}
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

        {/* New Project */}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs bg-transparent border-[#27272a] text-[#71717a] hover:text-white hover:bg-[#27272a]"
          onClick={onNewProject}
        >
          <Plus className="h-3 w-3 mr-1" />
          New Project
        </Button>

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
