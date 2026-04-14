'use client'

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { TopBar } from '@/components/sap-sim/top-bar'
import { LeftSidebar } from '@/components/sap-sim/left-sidebar'
import { MainFeed } from '@/components/sap-sim/main-feed'
import { ContextPanel } from '@/components/sap-sim/context-panel'
import { StakeholderView } from '@/components/sap-sim/stakeholder-view'
import { SettingsModal, ProjectSetupModal, AgentDetailModal } from '@/components/sap-sim/modals'
import { useProject } from '@/lib/project-context'
import { type Agent, type SimulationStatus } from '@/lib/types'
import { Button } from '@/components/ui/button'

// ---------------------------------------------------------------------------
// Welcome screen — shown when there are no projects yet
// ---------------------------------------------------------------------------

function WelcomeScreen({ onNewProject }: { onNewProject: () => void }) {
  return (
    <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#0e0e10] gap-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="h-16 w-16 rounded-xl bg-[#3b82f6] flex items-center justify-center mb-2">
          <span className="text-white font-bold text-2xl">SAP</span>
        </div>
        <h1 className="text-3xl font-bold text-white">SAP SIM</h1>
        <p className="text-[#71717a] text-sm max-w-sm">
          AI-powered SAP implementation simulation. Create your first project to get started.
        </p>
      </div>
      <Button
        className="bg-[#3b82f6] hover:bg-[#3b82f6]/80 text-white px-6 py-3 h-auto text-base"
        onClick={onNewProject}
      >
        <Plus className="h-5 w-5 mr-2" />
        Create First Project
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export default function SAPSimDashboard() {
  const { activeProject, projectList, loading, setActiveProject, refreshProjects } = useProject()

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

  // When a new project is created: refresh list + auto-switch to it
  const handleProjectCreated = async (projectName: string) => {
    await refreshProjects()
    setActiveProject(projectName)
    setProjectSetupOpen(false)
  }

  // Still loading initial project list
  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#0e0e10]">
        <div className="flex flex-col items-center gap-3 text-[#71717a]">
          <div className="h-8 w-8 rounded bg-[#3b82f6] flex items-center justify-center animate-pulse">
            <span className="text-white font-bold text-sm">SAP</span>
          </div>
          <span className="text-sm">Loading projects…</span>
        </div>
      </div>
    )
  }

  // No projects exist — show welcome screen
  if (!loading && projectList.length === 0) {
    return (
      <>
        <WelcomeScreen onNewProject={() => setProjectSetupOpen(true)} />
        <ProjectSetupModal
          isOpen={projectSetupOpen}
          onClose={() => setProjectSetupOpen(false)}
          onProjectCreated={handleProjectCreated}
        />
      </>
    )
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
        onProjectCreated={handleProjectCreated}
      />
      <AgentDetailModal
        agent={selectedAgent}
        onClose={() => setSelectedAgent(null)}
        projectName={activeProject ?? undefined}
      />
    </div>
  )
}
