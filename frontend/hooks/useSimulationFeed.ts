/**
 * SAP SIM — useSimulationFeed
 * Phase: 6.1
 * Purpose: React hook that opens an EventSource connection to
 *          /api/stream/:projectName and accumulates live FeedEvent objects.
 *          Handles auto-reconnection with exponential back-off.
 */

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { api as defaultApi, SapSimApiClient } from '../lib/api'
import type { FeedEvent, FeedEventType } from '../lib/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseSimulationFeedOptions {
  /** Maximum number of events to keep in the array (default: 200) */
  maxEvents?: number
  /** Initial back-off delay in ms (default: 1000) */
  initialReconnectDelayMs?: number
  /** Maximum back-off delay in ms (default: 30_000) */
  maxReconnectDelayMs?: number
  /** Only keep events matching these types; undefined = keep all */
  filterTypes?: FeedEventType[]
  /** Whether to start connected (default: true) */
  enabled?: boolean
  /** Custom API client instance (defaults to the module singleton) */
  client?: SapSimApiClient
}

export interface UseSimulationFeedResult {
  /** Accumulated live feed events, newest last */
  events: FeedEvent[]
  /** Whether the EventSource is currently open */
  connected: boolean
  /** Last error message, if any */
  error: string | null
  /** Manually clear all accumulated events */
  clearEvents: () => void
  /** Force a reconnect (e.g. after the simulation is started) */
  reconnect: () => void
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSimulationFeed(
  projectName: string,
  options: UseSimulationFeedOptions = {},
): UseSimulationFeedResult {
  const {
    maxEvents = 200,
    initialReconnectDelayMs = 1000,
    maxReconnectDelayMs = 30_000,
    filterTypes,
    enabled = true,
    client = defaultApi,
  } = options

  const [events, setEvents] = useState<FeedEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Stable refs so callbacks in event listeners don't close over stale state
  const esRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelayRef = useRef<number>(initialReconnectDelayMs)
  const isMountedRef = useRef(true)
  const enabledRef = useRef(enabled)

  // Keep enabledRef in sync
  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  // ---------------------------------------------------------------------------
  // Connect / disconnect helpers
  // ---------------------------------------------------------------------------

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    if (isMountedRef.current) {
      setConnected(false)
    }
  }, [])

  const connect = useCallback(() => {
    if (!isMountedRef.current || !enabledRef.current) return
    if (!projectName) return

    // Clean up any existing connection
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    const url = client.streamUrl(projectName)
    let es: EventSource

    try {
      es = new EventSource(url)
    } catch (err) {
      setError(`Failed to create EventSource: ${err}`)
      return
    }

    esRef.current = es

    es.onopen = () => {
      if (!isMountedRef.current) return
      setConnected(true)
      setError(null)
      // Reset back-off on successful connection
      reconnectDelayRef.current = initialReconnectDelayMs
    }

    // The SSE stream uses named events (event: TYPE\ndata: {...})
    // We must listen to specific events OR use onmessage for unnamed events.
    // The backend uses EventSourceResponse with event field set, so we
    // listen generically via addEventListener with a wildcard approach:
    // Since EventSource doesn't support wildcard, we attach handlers for
    // known types AND fall back to onmessage for untyped data lines.

    const handleMessage = (e: MessageEvent) => {
      if (!isMountedRef.current) return
      try {
        const data: unknown = typeof e.data === 'string' ? JSON.parse(e.data) : e.data
        const eventType = (e.type === 'message' ? 'UNKNOWN' : e.type) as FeedEventType

        // Apply type filter
        if (filterTypes && filterTypes.length > 0 && !filterTypes.includes(eventType)) {
          return
        }

        const feedEvent: FeedEvent = {
          type: eventType,
          data: (data as Record<string, unknown>) ?? {},
          timestamp: new Date().toISOString(),
        }

        setEvents(prev => {
          const next = [...prev, feedEvent]
          return next.length > maxEvents ? next.slice(next.length - maxEvents) : next
        })
      } catch {
        // Ignore malformed messages
      }
    }

    // Known event types from the backend
    const KNOWN_EVENT_TYPES: FeedEventType[] = [
      'CONNECTED',
      'SIMULATION_STARTED',
      'SIMULATION_PAUSED',
      'SIMULATION_RESUMED',
      'SIMULATION_STOPPED',
      'SIMULATION_COMPLETED',
      'PROJECT_CREATED',
      'AGENT_MSG',
      'AGENT_STATUS',
      'MEETING_STARTED',
      'MEETING_ENDED',
      'DECISION_RAISED',
      'DECISION_APPROVED',
      'DECISION_REJECTED',
      'NEW_TOOL',
      'BLOCKER',
      'PHASE_TRANSITION',
      'LESSON_LEARNED',
    ]

    for (const eventType of KNOWN_EVENT_TYPES) {
      es.addEventListener(eventType, handleMessage)
    }

    // Catch-all for unnamed/unknown events
    es.onmessage = handleMessage

    es.onerror = () => {
      if (!isMountedRef.current) return
      setConnected(false)

      // Close the broken connection
      es.close()
      esRef.current = null

      if (!enabledRef.current || !isMountedRef.current) return

      // Schedule reconnect with exponential back-off
      const delay = reconnectDelayRef.current
      reconnectDelayRef.current = Math.min(delay * 2, maxReconnectDelayMs)

      setError(`Connection lost — reconnecting in ${Math.round(delay / 1000)}s…`)

      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current && enabledRef.current) {
          connect()
        }
      }, delay)
    }
  }, [
    projectName,
    client,
    initialReconnectDelayMs,
    maxReconnectDelayMs,
    maxEvents,
    filterTypes,
  ])

  // ---------------------------------------------------------------------------
  // Effect: connect/disconnect lifecycle
  // ---------------------------------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true

    if (enabled && projectName) {
      connect()
    }

    return () => {
      isMountedRef.current = false
      disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectName, enabled])

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  const clearEvents = useCallback(() => {
    setEvents([])
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    reconnectDelayRef.current = initialReconnectDelayMs
    connect()
  }, [connect, disconnect, initialReconnectDelayMs])

  return { events, connected, error, clearEvents, reconnect }
}
