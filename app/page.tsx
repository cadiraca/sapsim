'use client'

import { useState } from 'react'
import { TopBar } from '@/components/sap-sim/top-bar'
import { LeftSidebar } from '@/components/sap-sim/left-sidebar'
import { MainFeed } from '@/components/sap-sim/main-feed'
import { ContextPanel } from '@/components/sap-sim/context-panel'
import { StakeholderView } from '@/components/sap-sim/stakeholder-view'
import { SettingsModal, ProjectSetupModal, AgentDetailModal } from '@/components/sap-sim/modals'
import { type Agent, type SimulationStatus } from '@/lib/mock-data'

export default function SAPSimDashboard() {
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatus>('RUNNING')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [projectSetupOpen, setProjectSetupOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)

  const handleSimulationControl = (action: 'run' | 'pause' | 'stop') => {
    switch (action) {
      case 'run':
        setSimulationStatus('RUNNING')
        break
      case 'pause':
        setSimulationStatus('PAUSED')
        break
      case 'stop':
        setSimulationStatus('STOPPED')
        break
    }
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#0e0e10]">
      {/* Top Bar */}
      <TopBar onNewProject={() => setProjectSetupOpen(true)} />
      
      {/* Main Content - 4 Column Layout */}
      <div className="flex-1 flex min-h-0">
        {/* Column 1: Left Sidebar */}
        <LeftSidebar 
          simulationStatus={simulationStatus}
          onSimulationControl={handleSimulationControl}
          onSettingsClick={() => setSettingsOpen(true)}
          onAgentClick={(agent) => setSelectedAgent(agent)}
        />
        
        {/* Column 2: Main Feed */}
        <MainFeed />
        
        {/* Column 3: Context Panel */}
        <ContextPanel />
        
        {/* Column 4: Stakeholder View */}
        <StakeholderView />
      </div>

      {/* Modals */}
      <SettingsModal 
        isOpen={settingsOpen} 
        onClose={() => setSettingsOpen(false)} 
      />
      <ProjectSetupModal 
        isOpen={projectSetupOpen} 
        onClose={() => setProjectSetupOpen(false)} 
      />
      <AgentDetailModal 
        agent={selectedAgent} 
        onClose={() => setSelectedAgent(null)} 
      />
    </div>
  )
}
