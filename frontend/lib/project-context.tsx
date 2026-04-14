'use client'

/**
 * SAP SIM — Project Context
 * Provides: activeProject (string | null), projectList (string[])
 * On mount: fetches GET /api/projects, sets list, restores last active from
 * localStorage or defaults to the first project found.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProjectContextValue {
  /** Currently selected project name, or null when none exists */
  activeProject: string | null
  /** All known project names */
  projectList: string[]
  /** Whether the initial project fetch is in progress */
  loading: boolean
  /** Switch to a different project (also persists to localStorage) */
  setActiveProject: (name: string) => void
  /** Re-fetch the project list from the backend */
  refreshProjects: () => Promise<void>
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ProjectContext = createContext<ProjectContextValue | null>(null)

const LS_KEY = 'sapsim:activeProject'

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projectList, setProjectList] = useState<string[]>([])
  const [activeProject, setActiveProjectState] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchProjects = useCallback(async () => {
    try {
      const projects = await api.getProjects()
      const names = projects.map((p) => p.name).filter(Boolean)
      setProjectList(names)
      return names
    } catch {
      return [] as string[]
    }
  }, [])

  // On mount: load projects, restore last active from localStorage or pick first
  useEffect(() => {
    let cancelled = false

    const init = async () => {
      const names = await fetchProjects()
      if (cancelled) return

      const stored = typeof window !== 'undefined' ? localStorage.getItem(LS_KEY) : null
      if (stored && names.includes(stored)) {
        setActiveProjectState(stored)
      } else if (names.length > 0) {
        setActiveProjectState(names[0])
        if (typeof window !== 'undefined') {
          localStorage.setItem(LS_KEY, names[0])
        }
      }
      setLoading(false)
    }

    init()
    return () => { cancelled = true }
  }, [fetchProjects])

  const setActiveProject = useCallback((name: string) => {
    setActiveProjectState(name)
    if (typeof window !== 'undefined') {
      localStorage.setItem(LS_KEY, name)
    }
  }, [])

  const refreshProjects = useCallback(async () => {
    const names = await fetchProjects()
    // If current project no longer exists in list, reset to first
    setActiveProjectState((prev) => {
      if (prev && names.includes(prev)) return prev
      return names[0] ?? null
    })
  }, [fetchProjects])

  const value = useMemo<ProjectContextValue>(
    () => ({ activeProject, projectList, loading, setActiveProject, refreshProjects }),
    [activeProject, projectList, loading, setActiveProject, refreshProjects],
  )

  return (
    <ProjectContext.Provider value={value}>
      {children}
    </ProjectContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext)
  if (!ctx) {
    throw new Error('useProject() must be used inside <ProjectProvider>')
  }
  return ctx
}
