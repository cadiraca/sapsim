"""
SAP SIM — API Routes (scaffold)
Phase: 1.2
Purpose: FastAPI router with /health included; full route set implemented in Phase 5.
Dependencies: FastAPI
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint — Phase 1 scaffold."""
    return {"status": "ok", "service": "sapsim-backend"}
