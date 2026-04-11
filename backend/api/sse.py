"""
SAP SIM — SSE EventBus
Phase: 1.6
Purpose: In-memory async pub/sub bus. Agents and the orchestrator publish events;
         SSE endpoint subscribers consume them as an async generator.
Dependencies: asyncio, json
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class EventBus:
    """Lightweight in-memory async pub/sub bus.

    One ``EventBus`` instance exists per active project.  Multiple SSE clients
    can subscribe simultaneously; each gets its own ``asyncio.Queue``.

    Usage::

        bus = EventBus()

        # Publisher (orchestrator / agents)
        await bus.publish("AGENT_MSG", {"codename": "PM_ALEX", "text": "..."})

        # Consumer (SSE endpoint)
        async for event in bus.subscribe():
            yield event   # already a JSON string ready for SSE
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any] | None]] = []

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all active subscribers.

        Args:
            event_type: A short uppercase string (e.g. ``"AGENT_MSG"``,
                        ``"MEETING_STARTED"``, ``"PHASE_ADVANCE"``).
            data:       Arbitrary JSON-serialisable dict with event payload.
        """
        envelope: dict[str, Any] = {"type": event_type, "data": data}
        dead: list[asyncio.Queue[dict[str, Any] | None]] = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                # Slow consumer — drop the event for them and log it
                logger.warning("EventBus: slow subscriber, dropping event %s", event_type)
            except Exception as exc:  # noqa: BLE001
                logger.error("EventBus: failed to enqueue event: %s", exc)
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def subscribe(self, maxsize: int = 512) -> AsyncGenerator[dict[str, Any], None]:
        """Return an async generator that yields events as they are published.

        Each call creates an independent queue, so multiple concurrent SSE
        connections each receive their own copy of every event.

        The generator runs until a ``None`` sentinel is received (sent by
        :meth:`close`) or the caller breaks out of the loop.

        Args:
            maxsize: Maximum number of buffered events before drops occur.

        Yields:
            Event envelopes: ``{"type": str, "data": dict}``
        """
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(q)

        async def _gen() -> AsyncGenerator[dict[str, Any], None]:
            try:
                while True:
                    event = await q.get()
                    if event is None:
                        break
                    yield event
            finally:
                try:
                    self._subscribers.remove(q)
                except ValueError:
                    pass  # Already removed

        return _gen()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Signal all subscribers to stop by sending a ``None`` sentinel."""
        for q in list(self._subscribers):
            await q.put(None)
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Number of currently active subscribers."""
        return len(self._subscribers)


# ---------------------------------------------------------------------------
# Per-project bus registry
# ---------------------------------------------------------------------------

_buses: dict[str, EventBus] = {}


def get_bus(project_name: str) -> EventBus:
    """Return (or create) the EventBus for a given project.

    Args:
        project_name: The unique project identifier.

    Returns:
        The singleton ``EventBus`` for this project.
    """
    if project_name not in _buses:
        _buses[project_name] = EventBus()
        logger.info("EventBus: created bus for project '%s'", project_name)
    return _buses[project_name]


async def destroy_bus(project_name: str) -> None:
    """Close and remove the EventBus for a project (e.g. after simulation stop).

    Args:
        project_name: The unique project identifier.
    """
    if project_name in _buses:
        await _buses[project_name].close()
        del _buses[project_name]
        logger.info("EventBus: destroyed bus for project '%s'", project_name)
