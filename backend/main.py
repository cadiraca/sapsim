"""
SAP SIM — FastAPI Backend Entry Point
Phase: 7.6
Purpose: App factory with CORS, main routes, and admin router.
         Admin API is mounted at /api/admin (operator/Mission-Controller use).
         Lifespan handler initialises and tears down the SQLite persistence
         layer on startup/shutdown via utils.persistence.
Dependencies: fastapi, uvicorn, api.routes, api.admin, utils.persistence
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as admin_router
from api.routes import router
from utils.persistence import close_persistence, init_persistence


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage persistence layer lifecycle tied to the FastAPI application."""
    await init_persistence()
    try:
        yield
    finally:
        await close_persistence()


app = FastAPI(
    title="SAP SIM API",
    description="Backend for the SAP Simulation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(admin_router, prefix="/api/admin")


@app.get("/health")
async def health():
    """Top-level health check — always available even if router is broken."""
    return {"status": "ok", "service": "sapsim-backend"}
