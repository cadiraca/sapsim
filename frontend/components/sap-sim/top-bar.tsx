'use client'

import { Bell, Plus, Download, Wifi } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { currentProject } from '@/lib/mock-data'

interface TopBarProps {
  onNewProject: () => void
}

export function TopBar({ onNewProject }: TopBarProps) {
  return (
    <header className="h-10 bg-[#18181b] border-b border-[#27272a] flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-white">SAP SIM</span>
      </div>
      
      <div className="flex items-center gap-1 text-xs text-[#71717a]">
        <span className="text-white font-medium">PROJECT:</span>
        <span className="text-[#f59e0b]">{currentProject.name}</span>
        <span className="mx-2">·</span>
        <span>Phase:</span>
        <span className="text-[#3b82f6] font-medium">{currentProject.phase}</span>
        <span className="mx-2">·</span>
        <span>Day {currentProject.day} of ~{currentProject.totalDays}</span>
      </div>
      
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-[#71717a]">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22c55e] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#22c55e]"></span>
          </span>
          <span>LiteLLM Connected</span>
        </div>
        
        <button className="relative p-1 hover:bg-[#27272a] rounded">
          <Bell className="h-4 w-4 text-[#71717a]" />
          <span className="absolute -top-0.5 -right-0.5 h-3.5 w-3.5 bg-[#ef4444] rounded-full text-[9px] font-bold flex items-center justify-center text-white">
            3
          </span>
        </button>
        
        <Button 
          variant="outline" 
          size="sm" 
          className="h-7 text-xs bg-transparent border-[#27272a] text-[#71717a] hover:text-white hover:bg-[#27272a]"
          onClick={onNewProject}
        >
          <Plus className="h-3 w-3 mr-1" />
          New Project
        </Button>
        
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
