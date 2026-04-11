"""
SAP SIM — FastAPI Backend Entry Point
Phase: 3.6
Purpose: App factory with CORS, main routes, and admin router.
         Admin API is mounted at /api/admin (operator/Mission-Controller use).
Dependencies: fastapi, uvicorn, api.routes, api.admin
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as admin_router
from api.routes import router

app = FastAPI(
    title="SAP SIM API",
    description="Backend for the SAP Simulation Platform",
    version="0.1.0",
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
