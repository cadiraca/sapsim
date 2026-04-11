"""
SAP SIM — API Routes
Phase: 1.2 (scaffold) → 1.6 (SSE endpoint added)
Purpose: FastAPI router. Full route set implemented in Phase 5.
         SSE stream endpoint added in Phase 1.6.
Dependencies: FastAPI, sse-starlette, api.sse
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from api.sse import get_bus

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict:
    """Health check — always returns 200 while the service is up."""
    return {"status": "ok", "service": "sapsim-backend"}


# ---------------------------------------------------------------------------
# SSE Stream  —  GET /api/stream/{project_name}
# ---------------------------------------------------------------------------


@router.get("/api/stream/{project_name}")
async def stream_project_events(project_name: str, request: Request) -> EventSourceResponse:
    """SSE endpoint that streams all EventBus events for *project_name*.

    Clients connect with ``EventSource('/api/stream/{project_name}')`` and
    receive a continuous ``text/event-stream`` of JSON-encoded events.

    Each SSE message has:
    - ``event``:  the event type string (e.g. ``AGENT_MSG``)
    - ``data``:   JSON-encoded payload dict

    The stream stays open until the client disconnects or the bus is closed.
    A ``CONNECTED`` ping is sent immediately upon connection so the client
    knows the stream is live.

    Args:
        project_name: Unique project identifier (matches projects/ folder name).
        request:      FastAPI request object (used for disconnect detection).
    """
    bus = get_bus(project_name)

    async def event_generator() -> AsyncGenerator[dict, None]:
        # Send an immediate connected confirmation
        yield {
            "event": "CONNECTED",
            "data": json.dumps(
                {"project": project_name, "message": "Stream connected"}
            ),
        }

        async for envelope in bus.subscribe():
            # Check if client has disconnected
            if await request.is_disconnected():
                logger.info(
                    "SSE client disconnected from project '%s'", project_name
                )
                break
            yield {
                "event": envelope["type"],
                "data": json.dumps(envelope["data"], default=str),
            }

    return EventSourceResponse(event_generator())
