"""
SAP SIM — Conductor / Orchestrator
Phase: 3.4
Purpose: Manages the main simulation loop. Owns the project state, phase transitions,
         meeting scheduling, agent action cycles, SSE event emission, and pause/stop
         signalling.  The Mission Controller (frontend) talks exclusively to the
         Conductor via the REST API and SSE stream.

Dependencies: base_agent, phase_manager, meeting_scheduler, state_machine, api.sse
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from simulation.state_machine import (
    STATUS_COMPLETED,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_STOPPED,
    ProjectState,
    create_new_state,
    load_state,
    save_state,
)
from simulation.phase_manager import PhaseManager
from simulation.meeting_scheduler import MeetingScheduler
from api.sse import EventBus, get_bus

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conductor tunables
# ---------------------------------------------------------------------------

# Maximum agents running concurrently in a single tick
_MAX_CONCURRENT_AGENTS: int = 5

# How many recent tick highlights to retain in memory
_HIGHLIGHTS_BUFFER_SIZE: int = 50

# How often (in ticks) to force-save project state even without a phase change
_STATE_SAVE_INTERVAL: int = 10


class Conductor:
    """Manages the SAP SIM main simulation loop.

    The Conductor is the single source of truth for a running simulation.
    It owns the ``ProjectState``, ``PhaseManager``, ``MeetingScheduler``, all
    agent instances, and the ``EventBus``.  Every simulated "day" is one call
    to :meth:`run_tick`.

    Typical lifecycle::

        conductor = Conductor(project_name="acme-s4")
        await conductor.initialize_simulation("acme-s4", config)
        while conductor.is_running:
            await conductor.run_tick()
            await asyncio.sleep(tick_delay)

    Attributes:
        project_state:     Live :class:`~simulation.state_machine.ProjectState`.
        phase_manager:     :class:`~simulation.phase_manager.PhaseManager` for this project.
        meeting_scheduler: :class:`~simulation.meeting_scheduler.MeetingScheduler`.
        agents:            Dict mapping codename → :class:`~agents.base_agent.BaseAgent`.
        event_bus:         :class:`~api.sse.EventBus` for this project.
        is_running:        True while the simulation loop is active.
        tick_count:        Number of ticks executed since the simulation started.
    """

    def __init__(self, project_name: str) -> None:
        """Create a Conductor for *project_name*.

        The Conductor is not usable until :meth:`initialize_simulation` completes.

        Args:
            project_name: Unique project identifier (used as directory name).
        """
        self.project_name: str = project_name

        # Core components — populated by initialize_simulation()
        self.project_state: Optional[ProjectState] = None
        self.phase_manager: Optional[PhaseManager] = None
        self.meeting_scheduler: Optional[MeetingScheduler] = None
        self.agents: dict[str, "BaseAgent"] = {}
        self.event_bus: Optional[EventBus] = None

        # Loop control
        self.is_running: bool = False
        self._paused: bool = False
        self._stop_requested: bool = False

        # Tick counter
        self.tick_count: int = 0

        # Recent activity highlights (ring-buffer, newest last)
        self._highlights: list[dict[str, Any]] = []

        # Semaphore for concurrent agent call limiting
        self._agent_semaphore: asyncio.Semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AGENTS)

        # Internal message queue: dicts with {from, to, content, timestamp}
        self._message_queue: list[dict[str, Any]] = []

        logger.info("[Conductor] Created for project '%s'", project_name)

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------

    async def initialize_simulation(
        self,
        project_name: str,
        config: dict[str, Any],
    ) -> ProjectState:
        """Set up all components and prepare the simulation for its first tick.

        Steps:
        1. Obtain/create the ``ProjectState`` (load from disk or create fresh).
        2. Wire up ``PhaseManager`` and ``MeetingScheduler``.
        3. Get the ``EventBus`` from the registry.
        4. Instantiate agents from *config* (or reload from disk).
        5. Load phase meetings for the initial phase.
        6. Mark state as RUNNING.
        7. Emit ``SIMULATION_STARTED``.

        Args:
            project_name: Unique project identifier.
            config:       Dict with optional keys:

                          - ``agents``: list of agent constructor callables or dicts
                          - ``resume``: bool — if True, load saved state from disk
                          - ``litellm_client``: shared LiteLLM client instance

        Returns:
            The initialized :class:`~simulation.state_machine.ProjectState`.
        """
        self.project_name = project_name

        # --- 1. Project state ---
        resume = config.get("resume", False)
        if resume:
            state = await load_state(project_name)
            if state is None:
                logger.warning(
                    "[Conductor] No saved state for '%s'; creating fresh.", project_name
                )
                state = await create_new_state(project_name)
        else:
            state = await create_new_state(project_name)

        self.project_state = state

        # --- 2. Phase and meeting managers ---
        self.phase_manager = PhaseManager(project_name=project_name)
        self.event_bus = get_bus(project_name)
        self.meeting_scheduler = MeetingScheduler(
            project_name=project_name,
            event_bus=self.event_bus,
        )

        # --- 3. Agent instantiation ---
        litellm_client = config.get("litellm_client")
        agent_factories = config.get("agents", [])

        for factory_or_instance in agent_factories:
            if callable(factory_or_instance):
                # factory(codename, project_name, litellm_client) → BaseAgent
                agent: "BaseAgent" = factory_or_instance(
                    project_name=project_name,
                    litellm_client=litellm_client,
                )
            else:
                # Already an instantiated agent
                agent = factory_or_instance

            self.agents[agent.codename] = agent

        # If resuming, try to restore per-agent state from disk
        if resume and litellm_client:
            await self._restore_agent_states(litellm_client)

        # --- 4. Load phase meetings ---
        self.meeting_scheduler.load_phase_meetings(state.current_phase)

        # --- 5. Transition to RUNNING ---
        if state.status == STATUS_IDLE:
            state.transition_status(STATUS_RUNNING)
        elif state.status == STATUS_PAUSED:
            state.transition_status(STATUS_RUNNING)

        self.is_running = True
        self._paused = False
        self._stop_requested = False

        # Sync agents with current phase
        self._sync_agents_to_phase(state)

        await save_state(state)

        # --- 6. Broadcast SIMULATION_STARTED ---
        methodology = self.phase_manager.load_methodology()
        await self.event_bus.publish(
            "SIMULATION_STARTED",
            {
                "project_name": project_name,
                "status": state.status,
                "current_phase": state.current_phase,
                "total_days": state.total_days,
                "agents": list(self.agents.keys()),
                "methodology": methodology.get("name", "SAP Activate"),
                "timestamp": time.time(),
            },
        )

        logger.info(
            "[Conductor] Simulation initialized: project='%s', phase='%s', agents=%d",
            project_name, state.current_phase, len(self.agents),
        )
        return state

    # -----------------------------------------------------------------------
    # Main simulation tick
    # -----------------------------------------------------------------------

    async def run_tick(self) -> dict[str, Any]:
        """Advance the simulation by one simulated day.

        A single tick proceeds through four stages:

        1. **Guard checks** — bail if not running / paused / stop requested.
        2. **Phase objective check** — evaluate whether the current phase is
           complete and, if so, call :meth:`~simulation.phase_manager.PhaseManager.advance_phase`.
        3. **Meeting step** — hand control to the
           :class:`~simulation.meeting_scheduler.MeetingScheduler` which will
           run the next pending meeting (if any).
        4. **Agent action step** — all *idle* agents act concurrently, limited
           by the internal :class:`asyncio.Semaphore`.
        5. **Progress update** — update ``phase_progress`` based on elapsed days.
        6. **Milestone check** — auto-complete milestones whose criteria are met.
        7. **State persistence** — save every N ticks.
        8. **Tick event** — emit ``TICK_COMPLETE`` via the EventBus.

        Returns:
            A tick summary dict (also appended to the highlights buffer).

        Raises:
            RuntimeError: If called before :meth:`initialize_simulation`.
        """
        if self.project_state is None or self.event_bus is None:
            raise RuntimeError("Conductor.run_tick() called before initialize_simulation().")

        state = self.project_state

        # --- Guard: stop requested ---
        if self._stop_requested:
            await self._do_stop()
            return self._make_tick_summary(notes="Stop requested — simulation halted.")

        # --- Guard: paused ---
        if self._paused:
            logger.debug("[Conductor] Tick skipped — simulation is paused.")
            return self._make_tick_summary(notes="Simulation is paused.")

        # --- Guard: terminal states ---
        if state.status in (STATUS_COMPLETED, STATUS_STOPPED):
            self.is_running = False
            return self._make_tick_summary(notes=f"Simulation already {state.status}.")

        self.tick_count += 1
        tick_events: list[str] = []

        # ----------------------------------------------------------------
        # Stage 1: Advance the simulated day
        # ----------------------------------------------------------------
        state.advance_day()
        tick_events.append(f"Day {state.simulated_day} begins.")

        # ----------------------------------------------------------------
        # Stage 2: Phase completion check
        # ----------------------------------------------------------------
        assert self.phase_manager is not None
        if self.phase_manager.is_phase_complete(state):
            old_phase = state.current_phase
            state = await self.phase_manager.advance_phase(state)
            self.project_state = state

            if state.status == STATUS_COMPLETED:
                self.is_running = False
                await self.event_bus.publish(
                    "SIMULATION_COMPLETED",
                    {
                        "project_name": self.project_name,
                        "total_days": state.simulated_day,
                        "tick_count": self.tick_count,
                        "timestamp": time.time(),
                    },
                )
                tick_events.append("🎉 All SAP Activate phases complete — simulation finished!")
                return self._finalize_tick(state, tick_events)

            new_phase = state.current_phase
            tick_events.append(f"Phase transition: {old_phase.upper()} → {new_phase.upper()}")

            # Reload meetings for the new phase
            assert self.meeting_scheduler is not None
            self.meeting_scheduler.load_phase_meetings(new_phase)
            self._sync_agents_to_phase(state)

            await self.event_bus.publish(
                "PHASE_TRANSITION",
                {
                    "from_phase": old_phase,
                    "to_phase": new_phase,
                    "simulated_day": state.simulated_day,
                    "phase_info": self.phase_manager.get_current_phase(state),
                    "timestamp": time.time(),
                },
            )

        # ----------------------------------------------------------------
        # Stage 3: Meeting step
        # ----------------------------------------------------------------
        assert self.meeting_scheduler is not None
        await self.meeting_scheduler.tick(state, self.agents)
        if self.meeting_scheduler.active_meeting:
            m = self.meeting_scheduler.active_meeting
            tick_events.append(f"Meeting in progress: '{m.title}'")

        # ----------------------------------------------------------------
        # Stage 4: Agent action step
        # ----------------------------------------------------------------
        project_state_dict = self._build_project_state_dict(state)
        agent_tasks = []
        active_codenames: list[str] = []

        for codename, agent in self.agents.items():
            if agent.status in ("idle",):
                active_codenames.append(codename)
                agent_tasks.append(
                    self._run_agent_with_semaphore(agent, project_state_dict)
                )

        if agent_tasks:
            results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                for err in errors:
                    logger.error("[Conductor] Agent error in tick %d: %s", self.tick_count, err)
            tick_events.append(
                f"{len(agent_tasks)} agent(s) acted: {', '.join(active_codenames[:8])}"
                + (f" (+{len(active_codenames)-8} more)" if len(active_codenames) > 8 else "")
            )

        # Update state's active_agents list
        state.active_agents = [c for c, a in self.agents.items() if a.status != "idle"]

        # ----------------------------------------------------------------
        # Stage 5: Phase progress update (simple day-based calculation)
        # ----------------------------------------------------------------
        self._update_phase_progress(state)

        # ----------------------------------------------------------------
        # Stage 6: Milestone auto-completion
        # ----------------------------------------------------------------
        newly_completed = self._check_milestones(state)
        for ms_name in newly_completed:
            tick_events.append(f"✅ Milestone achieved: {ms_name}")
            await self.event_bus.publish(
                "MILESTONE_COMPLETED",
                {
                    "milestone": ms_name,
                    "phase": state.current_phase,
                    "simulated_day": state.simulated_day,
                    "timestamp": time.time(),
                },
            )

        # ----------------------------------------------------------------
        # Stage 7: State persistence (periodic)
        # ----------------------------------------------------------------
        if self.tick_count % _STATE_SAVE_INTERVAL == 0:
            await save_state(state)

        # ----------------------------------------------------------------
        # Stage 8: Emit TICK_COMPLETE
        # ----------------------------------------------------------------
        return self._finalize_tick(state, tick_events)

    # -----------------------------------------------------------------------
    # Simulation control
    # -----------------------------------------------------------------------

    def pause(self) -> None:
        """Pause the simulation loop.

        The current tick, if any, finishes before the pause takes effect.
        Calling :meth:`resume` restarts tick processing.
        """
        if self.project_state is None:
            return
        self._paused = True
        logger.info("[Conductor] Simulation paused at day %d.", self.project_state.simulated_day)
        asyncio.ensure_future(self._emit_status_change("SIMULATION_PAUSED"))

    def resume(self) -> None:
        """Resume a paused simulation.

        No-op if the simulation is not currently paused.
        """
        if not self._paused:
            return
        self._paused = False
        logger.info("[Conductor] Simulation resumed.")
        if self.project_state:
            try:
                self.project_state.transition_status(STATUS_RUNNING)
            except ValueError:
                pass  # Already RUNNING
        asyncio.ensure_future(self._emit_status_change("SIMULATION_RESUMED"))

    def stop(self) -> None:
        """Request a graceful stop of the simulation.

        The stop is applied at the start of the next :meth:`run_tick` call.
        Use :meth:`pause` if you want to freeze without terminating.
        """
        self._stop_requested = True
        logger.info("[Conductor] Stop requested.")

    async def _do_stop(self) -> None:
        """Execute the stop: transition state, persist, and broadcast."""
        if self.project_state is None:
            return
        state = self.project_state
        try:
            state.transition_status(STATUS_STOPPED)
        except ValueError:
            pass  # Already in a terminal state
        self.is_running = False
        self._stop_requested = False
        await save_state(state)
        if self.event_bus:
            await self.event_bus.publish(
                "SIMULATION_STOPPED",
                {
                    "project_name": self.project_name,
                    "simulated_day": state.simulated_day,
                    "tick_count": self.tick_count,
                    "timestamp": time.time(),
                },
            )
        logger.info(
            "[Conductor] Simulation stopped: project='%s', day=%d, ticks=%d",
            self.project_name, state.simulated_day, self.tick_count,
        )

    # -----------------------------------------------------------------------
    # Highlights — Mission Controller summary
    # -----------------------------------------------------------------------

    def get_highlights(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return a summary of recent simulation activity.

        The Mission Controller uses this to populate its activity feed without
        having to replay the entire SSE stream.

        Args:
            limit: Maximum number of highlights to return (newest first).

        Returns:
            List of highlight dicts, each with keys:
            ``tick``, ``day``, ``phase``, ``events``, ``timestamp``.
        """
        recent = self._highlights[-_HIGHLIGHTS_BUFFER_SIZE:]
        return list(reversed(recent))[:limit]

    # -----------------------------------------------------------------------
    # Agent messaging
    # -----------------------------------------------------------------------

    def route_message(
        self,
        from_agent: str,
        to_agent: str,
        message: str,
    ) -> dict[str, Any]:
        """Route a direct message between two agents (or broadcast to all).

        Messages are enqueued in the internal ``_message_queue`` and will be
        delivered to the target agent on its next :meth:`~agents.base_agent.BaseAgent.act` call
        via the ``pending_messages`` key in the act-context dict.

        Args:
            from_agent: Sender codename (use ``"CONDUCTOR"`` for system messages).
            to_agent:   Recipient codename, or ``"ALL"`` for a broadcast.
            message:    The message text.

        Returns:
            The message envelope dict that was enqueued.
        """
        envelope: dict[str, Any] = {
            "id": f"MSG-{int(time.time() * 1000)}",
            "from": from_agent.upper(),
            "to": to_agent.upper(),
            "content": message,
            "timestamp": time.time(),
            "delivered": False,
        }
        self._message_queue.append(envelope)

        logger.debug(
            "[Conductor] Routed message: %s → %s (%d chars)",
            from_agent, to_agent, len(message),
        )

        # Async broadcast to SSE (fire-and-forget)
        if self.event_bus:
            asyncio.ensure_future(
                self.event_bus.publish(
                    "AGENT_MESSAGE",
                    {
                        "from": envelope["from"],
                        "to": envelope["to"],
                        "content": message,
                        "timestamp": envelope["timestamp"],
                    },
                )
            )

        return envelope

    # -----------------------------------------------------------------------
    # Private helpers — agent lifecycle
    # -----------------------------------------------------------------------

    async def _run_agent_with_semaphore(
        self,
        agent: "BaseAgent",
        project_state_dict: dict[str, Any],
    ) -> None:
        """Acquire the semaphore then call ``agent.act()``.

        Args:
            agent:              The agent to run.
            project_state_dict: Serialised project state snapshot for this tick.
        """
        async with self._agent_semaphore:
            assert self.event_bus is not None
            await agent.act(project_state_dict, self.event_bus)

    def _sync_agents_to_phase(self, state: ProjectState) -> None:
        """Push current phase context to all agents.

        Called on initialization and after every phase transition.

        Args:
            state: The current project state.
        """
        assert self.phase_manager is not None
        phase_info = self.phase_manager.get_current_phase(state)
        summary = self._build_project_summary(state)

        for agent in self.agents.values():
            agent.current_phase = state.current_phase
            agent.phase_description = phase_info.get("description", "")
            agent.project_summary = summary

    async def _restore_agent_states(self, litellm_client: Any) -> None:
        """Attempt to reload persisted agent state from disk for all registered agents.

        Only updates agents that already exist in ``self.agents``; new agent
        entries are left unchanged (fresh state).

        Args:
            litellm_client: Shared LiteLLM client (passed through to ``BaseAgent.load``).
        """
        from agents.base_agent import BaseAgent

        for codename, agent in list(self.agents.items()):
            restored = await BaseAgent.load(
                codename=codename,
                project_name=self.project_name,
                litellm_client=litellm_client,
            )
            if restored is not None:
                # Preserve the subclass type but copy mutable state
                agent.memory_turns = restored.memory_turns
                agent.memory_summary = restored.memory_summary
                agent.current_task = restored.current_task
                agent.status = "idle"
                agent.intelligence_tier = restored.intelligence_tier
                agent.current_phase = restored.current_phase
                agent.project_summary = restored.project_summary
                logger.debug("[Conductor] Restored state for agent '%s'", codename)

    # -----------------------------------------------------------------------
    # Private helpers — state calculations
    # -----------------------------------------------------------------------

    def _update_phase_progress(self, state: ProjectState) -> None:
        """Recalculate phase progress from elapsed simulated days.

        Progress is the proportion of the phase's planned duration that has
        elapsed, capped at 99% until :meth:`~simulation.phase_manager.PhaseManager.advance_phase`
        formally completes it (prevents premature phase-complete checks).

        Args:
            state: Current project state (mutated in-place via
                   :meth:`~simulation.state_machine.ProjectState.update_phase_progress`).
        """
        from simulation.state_machine import PHASES, PHASES_BY_ID

        # Calculate the start day of the current phase
        phase_start_day = 0
        for p in PHASES:
            if p["id"] == state.current_phase:
                break
            phase_start_day += p["duration_days"]

        phase_duration = PHASES_BY_ID[state.current_phase]["duration_days"]
        elapsed_in_phase = max(0, state.simulated_day - phase_start_day)
        raw_progress = (elapsed_in_phase / phase_duration) * 100.0
        # Cap at 99 until formal phase completion
        capped_progress = min(99.0, raw_progress)

        current_progress = state.phase_progress.get(state.current_phase, 0.0)
        # Never regress progress
        new_progress = max(current_progress, capped_progress)
        state.update_phase_progress(state.current_phase, new_progress)

    def _check_milestones(self, state: ProjectState) -> list[str]:
        """Auto-complete milestones for the current phase whose conditions are met.

        A milestone is auto-completed when phase progress for its phase reaches
        ≥ 75% (heuristic: "enough work has happened").  Custom conditions can be
        injected by subclassing.

        Args:
            state: Current project state (mutated in-place).

        Returns:
            List of milestone *name* strings that were newly completed this tick.
        """
        newly_completed: list[str] = []
        current_phase = state.current_phase
        phase_progress = state.phase_progress.get(current_phase, 0.0)

        for milestone in state.milestones:
            if milestone.get("completed"):
                continue
            if milestone.get("phase") != current_phase:
                continue
            # Simple heuristic: phase progress > 75% unlocks milestones
            if phase_progress >= 75.0:
                if state.complete_milestone(milestone["id"]):
                    newly_completed.append(milestone["name"])

        return newly_completed

    # -----------------------------------------------------------------------
    # Private helpers — data assembly
    # -----------------------------------------------------------------------

    def _build_project_state_dict(self, state: ProjectState) -> dict[str, Any]:
        """Build the project state dict injected into each agent's act() call.

        Extends the standard ``state.to_dict()`` with the current message queue
        and a prose project summary.

        Args:
            state: Current project state.

        Returns:
            Dict suitable for passing to :meth:`~agents.base_agent.BaseAgent.act`.
        """
        d = state.to_dict()
        d["message_queue"] = list(self._message_queue)
        d["project_summary"] = self._build_project_summary(state)
        d["phase_description"] = state.current_phase_info.get("description", "")
        return d

    def _build_project_summary(self, state: ProjectState) -> str:
        """Return a brief text summary of project status for agent context.

        Args:
            state: Current project state.

        Returns:
            Multi-line string description of project progress.
        """
        phase_info = state.current_phase_info
        return (
            f"Project: {state.project_name}\n"
            f"Phase: {phase_info['name']} ({state.current_phase})\n"
            f"Day: {state.simulated_day} / {state.total_days}\n"
            f"Phase progress: {state.phase_progress.get(state.current_phase, 0):.1f}%\n"
            f"Overall progress: {state.overall_progress:.1f}%\n"
            f"Status: {state.status}\n"
            f"Phase description: {phase_info.get('description', '')}"
        )

    # -----------------------------------------------------------------------
    # Private helpers — tick finalization
    # -----------------------------------------------------------------------

    def _finalize_tick(
        self,
        state: ProjectState,
        tick_events: list[str],
    ) -> dict[str, Any]:
        """Build a tick summary, append to highlights, and emit TICK_COMPLETE.

        Args:
            state:       Current project state.
            tick_events: List of human-readable event strings for this tick.

        Returns:
            The tick summary dict.
        """
        summary = self._make_tick_summary(
            notes="; ".join(tick_events) if tick_events else "Tick completed.",
            tick_events=tick_events,
        )

        # Append to highlights ring-buffer
        self._highlights.append(summary)
        if len(self._highlights) > _HIGHLIGHTS_BUFFER_SIZE:
            self._highlights.pop(0)

        # Emit TICK_COMPLETE (fire-and-forget — don't block the tick)
        if self.event_bus:
            asyncio.ensure_future(
                self.event_bus.publish(
                    "TICK_COMPLETE",
                    {
                        "tick": self.tick_count,
                        "simulated_day": state.simulated_day,
                        "phase": state.current_phase,
                        "overall_progress": state.overall_progress,
                        "phase_progress": state.phase_progress.get(state.current_phase, 0),
                        "active_agents": list(state.active_agents),
                        "events": tick_events,
                        "timestamp": time.time(),
                    },
                )
            )

        return summary

    def _make_tick_summary(
        self,
        notes: str = "",
        tick_events: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Construct a standardised tick summary dict.

        Args:
            notes:       Short plain-text description of what happened.
            tick_events: Optional list of individual event strings.

        Returns:
            Summary dict with tick metadata.
        """
        state = self.project_state
        return {
            "tick": self.tick_count,
            "day": state.simulated_day if state else 0,
            "phase": state.current_phase if state else "unknown",
            "phase_progress": (
                state.phase_progress.get(state.current_phase, 0.0) if state else 0.0
            ),
            "overall_progress": state.overall_progress if state else 0.0,
            "status": state.status if state else STATUS_IDLE,
            "events": tick_events or [],
            "notes": notes,
            "timestamp": time.time(),
        }

    # -----------------------------------------------------------------------
    # Private helpers — event broadcasting
    # -----------------------------------------------------------------------

    async def _emit_status_change(self, event_type: str) -> None:
        """Emit a status change event to the EventBus.

        Args:
            event_type: SSE event type string (e.g. ``"SIMULATION_PAUSED"``).
        """
        if self.event_bus is None or self.project_state is None:
            return
        await self.event_bus.publish(
            event_type,
            {
                "project_name": self.project_name,
                "status": self.project_state.status,
                "simulated_day": self.project_state.simulated_day,
                "tick_count": self.tick_count,
                "timestamp": time.time(),
            },
        )

    # -----------------------------------------------------------------------
    # Dunder helpers
    # -----------------------------------------------------------------------

    def __repr__(self) -> str:
        state = self.project_state
        return (
            f"<Conductor project='{self.project_name}' "
            f"running={self.is_running} paused={self._paused} "
            f"tick={self.tick_count} "
            f"day={state.simulated_day if state else '?'} "
            f"phase={state.current_phase if state else '?'} "
            f"agents={len(self.agents)}>"
        )
