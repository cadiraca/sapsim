"""
SAP SIM — Simulation Engine
Phase: 3.5
Purpose: Top-level controller that wraps the Conductor.  Provides project
         lifecycle management (create, start, pause, resume, stop, status),
         chaos/failure injection, and a configurable background asyncio loop
         that drives the simulation tick.  Uses a singleton pattern so all
         API routes share the same engine instance.

Dependencies: agents.orchestrator (Conductor), agents.factory,
              simulation.state_machine, utils.litellm_client, config
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional, TypedDict

from agents.factory import create_all_agents
from agents.orchestrator import Conductor
from config import load_settings
from simulation.state_machine import (
    STATUS_COMPLETED,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_STOPPED,
    ProjectState,
    save_state,
)
from utils.litellm_client import LiteLLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_TICK_INTERVAL_SECONDS: float = 5.0

# ---------------------------------------------------------------------------
# Public type: SimulationStatus dict returned by get_status()
# ---------------------------------------------------------------------------


class SimulationStatus(TypedDict):
    """Dict shape returned by :meth:`SimulationEngine.get_status`."""

    project_name: str
    status: str                    # IDLE / RUNNING / PAUSED / COMPLETED / STOPPED
    current_phase: str
    simulated_day: int
    total_days: int
    overall_progress: float        # 0–100
    phase_progress: dict[str, float]  # phase_id → %
    active_agents: list[str]
    tick_count: int
    tick_interval_seconds: float
    loop_running: bool             # whether the background asyncio task is alive
    pending_decisions: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    injected_failures: list[dict[str, Any]]
    last_updated: float            # Unix timestamp


# ---------------------------------------------------------------------------
# Chaos scenario definitions
# ---------------------------------------------------------------------------

# Recognised chaos scenario identifiers
_CHAOS_SCENARIOS: frozenset[str] = frozenset({
    "key_person_leaves",
    "budget_cut",
    "scope_change",
    "data_quality_issue",
})

# Default severity and description for each scenario
_CHAOS_DEFAULTS: dict[str, dict[str, Any]] = {
    "key_person_leaves": {
        "description": "A key team member unexpectedly leaves the project.",
        "severity": "high",
        "phase_progress_penalty": 10.0,   # % penalty applied to current phase
        "risk_delta": 15,
    },
    "budget_cut": {
        "description": "The project budget has been cut, reducing available resources.",
        "severity": "high",
        "phase_progress_penalty": 5.0,
        "risk_delta": 20,
    },
    "scope_change": {
        "description": "A significant scope change has been requested by the customer.",
        "severity": "medium",
        "phase_progress_penalty": 8.0,
        "risk_delta": 12,
    },
    "data_quality_issue": {
        "description": "Serious data quality problems have been discovered in legacy data.",
        "severity": "medium",
        "phase_progress_penalty": 6.0,
        "risk_delta": 10,
    },
}


# ---------------------------------------------------------------------------
# SimulationEngine — singleton
# ---------------------------------------------------------------------------


class SimulationEngine:
    """Top-level controller that owns all active :class:`~agents.orchestrator.Conductor` instances.

    One ``SimulationEngine`` instance manages *every* concurrently running
    project.  Each project gets its own ``Conductor`` and its own background
    :class:`asyncio.Task` that calls :meth:`Conductor.run_tick` on a
    configurable interval.

    **Singleton access** — always use :func:`get_engine` instead of
    instantiating directly::

        engine = get_engine()
        await engine.create_project("acme-s4", config={})
        await engine.start("acme-s4")

    Attributes:
        tick_interval_seconds: Default seconds between ticks for new projects.
    """

    def __init__(self, tick_interval_seconds: float = DEFAULT_TICK_INTERVAL_SECONDS) -> None:
        self.tick_interval_seconds: float = tick_interval_seconds

        # project_name → Conductor
        self._conductors: dict[str, Conductor] = {}

        # project_name → asyncio.Task (background loop)
        self._tasks: dict[str, asyncio.Task[None]] = {}

        # project_name → per-project tick interval override
        self._tick_intervals: dict[str, float] = {}

        # project_name → list of injected failure records
        self._injected_failures: dict[str, list[dict[str, Any]]] = {}

        # project_name → LiteLLMClient (kept alive for the project lifetime)
        self._litellm_clients: dict[str, LiteLLMClient] = {}

        logger.info(
            "[SimulationEngine] Initialised (default tick=%.1fs).",
            tick_interval_seconds,
        )

    # -----------------------------------------------------------------------
    # create_project
    # -----------------------------------------------------------------------

    async def create_project(
        self,
        name: str,
        config: Optional[dict[str, Any]] = None,
    ) -> ProjectState:
        """Create a new simulation project and initialise its Conductor.

        This method:
        1. Loads project settings (or uses defaults).
        2. Creates a :class:`~utils.litellm_client.LiteLLMClient`.
        3. Instantiates all 30 agents via the factory.
        4. Creates a :class:`~agents.orchestrator.Conductor` and calls
           :meth:`Conductor.initialize_simulation`.
        5. Registers everything internally so :meth:`start` can launch the loop.

        Args:
            name:   Unique project identifier (slug, alphanumeric/hyphens).
            config: Optional overrides.  Recognised keys:

                    - ``tick_interval_seconds`` (float) — per-project tick speed.
                    - ``resume`` (bool) — resume from saved state.
                    - ``personality_overrides`` (dict) — per-codename personality.
                    - ``personality_seeds`` (dict) — per-codename RNG seeds.
                    - ``litellm_base_url`` / ``litellm_api_key`` / ``litellm_model``
                      override the project settings file values.

        Returns:
            The initialised :class:`~simulation.state_machine.ProjectState`.

        Raises:
            ValueError: If a project with *name* already exists.
        """
        cfg = config or {}

        if name in self._conductors:
            raise ValueError(
                f"Project '{name}' already exists in the engine. "
                "Call stop() and remove it before re-creating."
            )

        # ----------------------------------------------------------------
        # 1. Load project settings
        # ----------------------------------------------------------------
        settings = load_settings(name)
        base_url  = cfg.get("litellm_base_url", settings.litellm_base_url)
        api_key   = cfg.get("litellm_api_key",  settings.litellm_api_key)
        model     = cfg.get("litellm_model",     settings.litellm_model)
        tick_iv   = float(cfg.get("tick_interval_seconds", self.tick_interval_seconds))

        # ----------------------------------------------------------------
        # 2. Create LiteLLMClient
        # ----------------------------------------------------------------
        litellm_client = LiteLLMClient(
            base_url=base_url,
            api_key=api_key,
            default_model=model,
        )
        self._litellm_clients[name] = litellm_client

        # ----------------------------------------------------------------
        # 3. Instantiate all 30 agents
        # ----------------------------------------------------------------
        resume              = bool(cfg.get("resume", False))
        personality_overrides = cfg.get("personality_overrides")
        personality_seeds     = cfg.get("personality_seeds")

        agents = await create_all_agents(
            project_name=name,
            litellm_client=litellm_client,
            personality_overrides=personality_overrides,
            personality_seeds=personality_seeds,
        )

        # ----------------------------------------------------------------
        # 4. Create Conductor and initialize
        # ----------------------------------------------------------------
        conductor = Conductor(project_name=name)

        init_config: dict[str, Any] = {
            "resume": resume,
            "litellm_client": litellm_client,
            "agents": list(agents.values()),
        }

        state = await conductor.initialize_simulation(name, init_config)

        # ----------------------------------------------------------------
        # 5. Register
        # ----------------------------------------------------------------
        self._conductors[name]        = conductor
        self._tick_intervals[name]    = tick_iv
        self._injected_failures[name] = []

        logger.info(
            "[SimulationEngine] Project '%s' created: phase=%s agents=%d tick=%.1fs",
            name, state.current_phase, len(agents), tick_iv,
        )
        return state

    # -----------------------------------------------------------------------
    # start
    # -----------------------------------------------------------------------

    async def start(self, project_name: str) -> None:
        """Start (or restart) the background tick loop for *project_name*.

        The loop calls :meth:`Conductor.run_tick` every
        ``tick_interval_seconds``.  If the loop is already running this is a
        no-op.

        Args:
            project_name: Must have been created with :meth:`create_project`.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._get_conductor(project_name)

        # Resume a paused conductor before starting the loop
        if conductor._paused:
            conductor.resume()

        # Ensure conductor is in RUNNING state
        state = conductor.project_state
        if state and state.status == STATUS_PAUSED:
            try:
                state.transition_status(STATUS_RUNNING)
                await save_state(state)
            except ValueError:
                pass

        # Already looping?
        task = self._tasks.get(project_name)
        if task and not task.done():
            logger.debug(
                "[SimulationEngine] start('%s') — loop already running.", project_name
            )
            return

        task = asyncio.create_task(
            self._tick_loop(project_name),
            name=f"sapsim-tick-{project_name}",
        )
        self._tasks[project_name] = task
        task.add_done_callback(
            lambda t: self._on_task_done(project_name, t)
        )

        logger.info("[SimulationEngine] Background tick loop started for '%s'.", project_name)

    # -----------------------------------------------------------------------
    # pause
    # -----------------------------------------------------------------------

    def pause(self, project_name: str) -> None:
        """Pause the simulation for *project_name*.

        The current tick (if running) completes first.  Call :meth:`resume` to
        continue.

        Args:
            project_name: Registered project name.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._get_conductor(project_name)
        conductor.pause()

        state = conductor.project_state
        if state:
            try:
                state.transition_status(STATUS_PAUSED)
            except ValueError:
                pass

        logger.info("[SimulationEngine] Project '%s' paused.", project_name)

    # -----------------------------------------------------------------------
    # resume
    # -----------------------------------------------------------------------

    async def resume(self, project_name: str) -> None:
        """Resume a paused simulation.

        Re-starts the background tick loop if it has stopped.

        Args:
            project_name: Registered project name.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._get_conductor(project_name)
        conductor.resume()

        # Re-launch loop if it exited while paused
        task = self._tasks.get(project_name)
        if task is None or task.done():
            await self.start(project_name)

        logger.info("[SimulationEngine] Project '%s' resumed.", project_name)

    # -----------------------------------------------------------------------
    # stop
    # -----------------------------------------------------------------------

    async def stop(self, project_name: str) -> None:
        """Gracefully stop the simulation and cancel its background loop.

        The Conductor's :meth:`~agents.orchestrator.Conductor.stop` method is
        called (which transitions state to STOPPED on the next tick); the
        asyncio Task is then cancelled.

        Args:
            project_name: Registered project name.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._get_conductor(project_name)
        conductor.stop()

        # Cancel the background task
        task = self._tasks.get(project_name)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Persist STOPPED state directly in case the task was cancelled
        state = conductor.project_state
        if state and state.status not in (STATUS_COMPLETED, STATUS_STOPPED):
            try:
                state.transition_status(STATUS_STOPPED)
            except ValueError:
                pass
            await save_state(state)

        logger.info("[SimulationEngine] Project '%s' stopped.", project_name)

    # -----------------------------------------------------------------------
    # get_status
    # -----------------------------------------------------------------------

    def get_status(self, project_name: str) -> SimulationStatus:
        """Return a :class:`SimulationStatus` snapshot for *project_name*.

        Args:
            project_name: Registered project name.

        Returns:
            :class:`SimulationStatus` TypedDict.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._get_conductor(project_name)
        state = conductor.project_state

        task        = self._tasks.get(project_name)
        loop_alive  = bool(task and not task.done())
        tick_iv     = self._tick_intervals.get(project_name, self.tick_interval_seconds)
        failures    = list(self._injected_failures.get(project_name, []))

        if state is None:
            return SimulationStatus(
                project_name=project_name,
                status=STATUS_IDLE,
                current_phase="unknown",
                simulated_day=0,
                total_days=0,
                overall_progress=0.0,
                phase_progress={},
                active_agents=[],
                tick_count=conductor.tick_count,
                tick_interval_seconds=tick_iv,
                loop_running=loop_alive,
                pending_decisions=[],
                milestones=[],
                injected_failures=failures,
                last_updated=time.time(),
            )

        return SimulationStatus(
            project_name=project_name,
            status=state.status,
            current_phase=state.current_phase,
            simulated_day=state.simulated_day,
            total_days=state.total_days,
            overall_progress=state.overall_progress,
            phase_progress=dict(state.phase_progress),
            active_agents=list(state.active_agents),
            tick_count=conductor.tick_count,
            tick_interval_seconds=tick_iv,
            loop_running=loop_alive,
            pending_decisions=list(state.pending_decisions),
            milestones=list(state.milestones),
            injected_failures=failures,
            last_updated=time.time(),
        )

    # -----------------------------------------------------------------------
    # inject_failure
    # -----------------------------------------------------------------------

    async def inject_failure(
        self,
        project_name: str,
        scenario: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Inject a chaos/failure scenario into a running simulation.

        Supported scenarios: ``key_person_leaves``, ``budget_cut``,
        ``scope_change``, ``data_quality_issue``.

        Effects:
        - Logs the failure to the project's injected-failures list.
        - Applies a phase-progress penalty to the current phase.
        - Emits a ``FAILURE_INJECTED`` SSE event.
        - Routes a system message through the Conductor's message queue.

        Args:
            project_name: Registered project name.
            scenario:     One of the supported scenario identifiers.
            params:       Optional overrides for scenario defaults (e.g.
                          ``{"phase_progress_penalty": 20.0}``).

        Returns:
            The failure record that was logged.

        Raises:
            KeyError:   If *project_name* is not registered.
            ValueError: If *scenario* is not recognised.
        """
        if scenario not in _CHAOS_SCENARIOS:
            raise ValueError(
                f"Unknown failure scenario '{scenario}'. "
                f"Valid scenarios: {sorted(_CHAOS_SCENARIOS)}"
            )

        conductor = self._get_conductor(project_name)
        state     = conductor.project_state

        if state is None:
            raise RuntimeError(
                f"Project '{project_name}' conductor has no state — "
                "was initialize_simulation() called?"
            )

        # ----------------------------------------------------------------
        # Build failure record
        # ----------------------------------------------------------------
        defaults  = dict(_CHAOS_DEFAULTS[scenario])
        effective = {**defaults, **(params or {})}

        failure_record: dict[str, Any] = {
            "id":          f"CHAOS-{int(time.time() * 1000)}",
            "scenario":    scenario,
            "description": effective.get("description", ""),
            "severity":    effective.get("severity", "medium"),
            "phase":       state.current_phase,
            "simulated_day": state.simulated_day,
            "timestamp":   time.time(),
            "params":      effective,
        }

        # ----------------------------------------------------------------
        # Apply phase-progress penalty
        # ----------------------------------------------------------------
        penalty = float(effective.get("phase_progress_penalty", 0.0))
        if penalty > 0:
            current_progress = state.phase_progress.get(state.current_phase, 0.0)
            new_progress = max(0.0, current_progress - penalty)
            state.update_phase_progress(state.current_phase, new_progress)
            failure_record["phase_progress_before"] = current_progress
            failure_record["phase_progress_after"]  = new_progress
            logger.info(
                "[SimulationEngine] Chaos '%s': phase=%s progress %.1f → %.1f",
                scenario, state.current_phase, current_progress, new_progress,
            )

        # ----------------------------------------------------------------
        # Apply risk delta (if state tracks it)
        # ----------------------------------------------------------------
        risk_delta = int(effective.get("risk_delta", 0))
        if risk_delta and hasattr(state, "risk_score"):
            state.risk_score = min(100, getattr(state, "risk_score", 0) + risk_delta)

        # ----------------------------------------------------------------
        # Log the failure
        # ----------------------------------------------------------------
        self._injected_failures[project_name].append(failure_record)

        # ----------------------------------------------------------------
        # Persist updated state
        # ----------------------------------------------------------------
        await save_state(state)

        # ----------------------------------------------------------------
        # Route a system message to all agents
        # ----------------------------------------------------------------
        conductor.route_message(
            from_agent="CONDUCTOR",
            to_agent="ALL",
            message=(
                f"⚠️ CHAOS EVENT [{scenario.upper()}]: {effective['description']} "
                f"(Phase: {state.current_phase}, Day: {state.simulated_day})"
            ),
        )

        # ----------------------------------------------------------------
        # Emit SSE event
        # ----------------------------------------------------------------
        if conductor.event_bus:
            asyncio.ensure_future(
                conductor.event_bus.publish(
                    "FAILURE_INJECTED",
                    {
                        "project_name":  project_name,
                        "scenario":      scenario,
                        "description":   effective["description"],
                        "severity":      effective["severity"],
                        "phase":         state.current_phase,
                        "simulated_day": state.simulated_day,
                        "penalty":       penalty,
                        "timestamp":     failure_record["timestamp"],
                    },
                )
            )

        logger.info(
            "[SimulationEngine] Failure injected: project='%s' scenario='%s' day=%d",
            project_name, scenario, state.simulated_day,
        )
        return failure_record

    # -----------------------------------------------------------------------
    # Introspection helpers
    # -----------------------------------------------------------------------

    def list_projects(self) -> list[str]:
        """Return all registered project names."""
        return sorted(self._conductors.keys())

    def get_conductor(self, project_name: str) -> Conductor:
        """Return the :class:`Conductor` for *project_name* (public access).

        Args:
            project_name: Registered project name.

        Raises:
            KeyError: If not registered.
        """
        return self._get_conductor(project_name)

    def is_registered(self, project_name: str) -> bool:
        """True if *project_name* has been registered with :meth:`create_project`."""
        return project_name in self._conductors

    # -----------------------------------------------------------------------
    # Background loop
    # -----------------------------------------------------------------------

    async def _tick_loop(self, project_name: str) -> None:
        """Background coroutine: drive the simulation for *project_name*.

        Calls :meth:`Conductor.run_tick` on the configured interval.  The loop
        exits automatically when the simulation reaches a terminal state
        (COMPLETED or STOPPED).

        Args:
            project_name: Registered project name.
        """
        conductor = self._get_conductor(project_name)
        interval  = self._tick_intervals.get(project_name, self.tick_interval_seconds)

        logger.info(
            "[SimulationEngine] Tick loop running for '%s' (interval=%.1fs).",
            project_name, interval,
        )

        try:
            while True:
                state = conductor.project_state

                # Exit if terminal
                if state and state.status in (STATUS_COMPLETED, STATUS_STOPPED):
                    logger.info(
                        "[SimulationEngine] '%s' reached terminal state '%s' — loop exiting.",
                        project_name, state.status,
                    )
                    break

                # Skip tick if paused, but keep the loop alive (resume will re-use it)
                if conductor._paused:
                    await asyncio.sleep(interval)
                    continue

                try:
                    await conductor.run_tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception(
                        "[SimulationEngine] Unhandled error in tick for '%s': %s",
                        project_name, exc,
                    )
                    # Brief back-off after an error to avoid a tight failure loop
                    await asyncio.sleep(min(interval * 2, 30.0))
                    continue

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info(
                "[SimulationEngine] Tick loop for '%s' was cancelled.", project_name
            )
            raise

    def _on_task_done(self, project_name: str, task: asyncio.Task[None]) -> None:
        """Callback invoked when the background task finishes (naturally or via error).

        Args:
            project_name: Owning project.
            task:         The completed task.
        """
        if task.cancelled():
            logger.debug("[SimulationEngine] Task for '%s' cancelled.", project_name)
            return

        exc = task.exception()
        if exc:
            logger.error(
                "[SimulationEngine] Task for '%s' raised an exception: %s",
                project_name, exc,
            )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _get_conductor(self, project_name: str) -> Conductor:
        """Return conductor or raise KeyError with a helpful message.

        Args:
            project_name: Registered project name.

        Raises:
            KeyError: If *project_name* is not registered.
        """
        conductor = self._conductors.get(project_name)
        if conductor is None:
            raise KeyError(
                f"No project '{project_name}' registered with SimulationEngine. "
                f"Registered projects: {sorted(self._conductors.keys())}"
            )
        return conductor

    # -----------------------------------------------------------------------
    # Dunder
    # -----------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<SimulationEngine projects={len(self._conductors)} "
            f"running={sum(1 for t in self._tasks.values() if not t.done())} "
            f"tick_interval={self.tick_interval_seconds}s>"
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine_instance: Optional[SimulationEngine] = None


def get_engine(tick_interval_seconds: float = DEFAULT_TICK_INTERVAL_SECONDS) -> SimulationEngine:
    """Return the global :class:`SimulationEngine` singleton.

    Creates it on first call with *tick_interval_seconds*.  Subsequent calls
    ignore *tick_interval_seconds* and return the existing instance.

    Args:
        tick_interval_seconds: Default tick interval for newly created projects.
                               Only used when the singleton is first created.

    Returns:
        The singleton :class:`SimulationEngine` instance.

    Example::

        from simulation.engine import get_engine

        engine = get_engine()
        await engine.create_project("acme-s4", config={"tick_interval_seconds": 3.0})
        await engine.start("acme-s4")
        status = engine.get_status("acme-s4")
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SimulationEngine(tick_interval_seconds=tick_interval_seconds)
        logger.info(
            "[SimulationEngine] Singleton created (tick=%.1fs).", tick_interval_seconds
        )
    return _engine_instance
