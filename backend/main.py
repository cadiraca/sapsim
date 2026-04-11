"""
SAP SIM — FastAPI Backend Entry Point
Phase: 1.2
Purpose: App factory with CORS and health endpoint; routes delegated to api/routes.py.
Dependencies: fastapi, uvicorn, api.routes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health():
    """Top-level health check — always available even if router is broken."""
    return {"status": "ok", "service": "sapsim-backend"}
