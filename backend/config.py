"""
SAP SIM — Configuration Loader
Phase: 1.3
Purpose: Load per-project settings from projects/{project}/settings.json.
         Provides typed config with defaults for all simulation parameters.
Dependencies: pydantic, python-dotenv, pathlib
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Settings schema — stored at projects/{project_name}/settings.json
# ---------------------------------------------------------------------------

class ProjectSettings(BaseModel):
    """LiteLLM and simulation settings for a project."""

    # LiteLLM gateway
    litellm_base_url: str = Field(
        default="http://localhost:4000",
        description="Base URL for the LiteLLM-compatible gateway (no trailing slash)",
    )
    litellm_api_key: str = Field(
        default="",
        description="API key for the LiteLLM gateway",
    )
    litellm_model: str = Field(
        default="claude-4-6-sonnet",
        description="Default model for agents that don't have a tier override",
    )

    # Parallelism
    max_parallel_agents: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of agents that can think/act simultaneously",
    )

    # Memory management
    memory_compression_interval: str = Field(
        default="every_10_turns",
        description="When to compress agent memory: 'every_N_turns' or 'every_phase'",
    )

    # Webhook for King Charly monitoring (optional)
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL to POST simulation events to (phase transitions, blockers, etc.)",
    )

    # Token budget
    max_token_budget: Optional[int] = Field(
        default=None,
        description="Hard limit on total tokens for this run (None = unlimited)",
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

PROJECTS_ROOT = Path(__file__).parent.parent / "projects"


def get_settings_path(project_name: str) -> Path:
    """Return the absolute path to a project's settings.json."""
    return PROJECTS_ROOT / project_name / "settings.json"


def load_settings(project_name: str) -> ProjectSettings:
    """
    Load settings for a project from disk.
    If the file doesn't exist, returns default settings.
    """
    path = get_settings_path(project_name)
    if not path.exists():
        return ProjectSettings()

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    return ProjectSettings(**raw)


def save_settings(project_name: str, settings: ProjectSettings) -> None:
    """
    Persist settings for a project to disk.
    Creates the project directory tree if needed.
    """
    path = get_settings_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fh:
        json.dump(settings.model_dump(), fh, indent=2)
