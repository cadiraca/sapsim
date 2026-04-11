"""
SAP SIM — Import Verification Test Suite
Phase: 2.6 (integration verification)
Purpose: Verify that every backend module and all 30 agent role classes can be
         imported without errors. Fails fast on any broken import so CI or a
         manual smoke-test run catches issues before the server starts.
Dependencies: None beyond standard stdlib; runs inside the backend venv.

Run:
    cd backend
    source venv/bin/activate
    python -m pytest tests/test_imports.py -v
  or directly:
    python tests/test_imports.py
"""

from __future__ import annotations

import importlib
import sys
import pytest


# ---------------------------------------------------------------------------
# 1. Core utilities
# ---------------------------------------------------------------------------

CORE_MODULES = [
    "config",
    "utils.litellm_client",
    "utils.persistence",
    "utils.memory",
]


@pytest.mark.parametrize("module_path", CORE_MODULES)
def test_core_module_imports(module_path: str) -> None:
    """Each core utility module must import cleanly."""
    mod = importlib.import_module(module_path)
    assert mod is not None, f"Module '{module_path}' imported as None"


# ---------------------------------------------------------------------------
# 2. API / SSE
# ---------------------------------------------------------------------------

API_MODULES = [
    "api.sse",
    "api.routes",
]


@pytest.mark.parametrize("module_path", API_MODULES)
def test_api_module_imports(module_path: str) -> None:
    """API and SSE modules must import cleanly."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# 3. Agent system — base, intelligence, personality, factory
# ---------------------------------------------------------------------------

AGENT_CORE_MODULES = [
    "agents.base_agent",
    "agents.intelligence",
    "agents.personality",
    "agents.factory",
    "agents.orchestrator",
]


@pytest.mark.parametrize("module_path", AGENT_CORE_MODULES)
def test_agent_core_imports(module_path: str) -> None:
    """Core agent modules must import cleanly."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# 4. All 30 role modules
# ---------------------------------------------------------------------------

ROLE_MODULES = [
    # Consultant core (Batch 1)
    "agents.roles.pm_alex",
    "agents.roles.arch_sara",
    "agents.roles.basis_kurt",
    "agents.roles.dev_priya",
    "agents.roles.dev_leon",
    "agents.roles.fi_chen",
    "agents.roles.co_marta",
    "agents.roles.mm_ravi",
    "agents.roles.sd_isla",
    "agents.roles.pp_jonas",
    # Consultant extended + Customer strategic (Batch 2)
    "agents.roles.wm_fatima",
    "agents.roles.int_marco",
    "agents.roles.sec_diana",
    "agents.roles.bi_sam",
    "agents.roles.chg_nadia",
    "agents.roles.dm_felix",
    "agents.roles.exec_victor",
    "agents.roles.it_mgr_helen",
    "agents.roles.cust_pm_omar",
    "agents.roles.fi_ku_rose",
    # Customer operational KUs + cross-functional (Batch 3)
    "agents.roles.co_ku_bjorn",
    "agents.roles.mm_ku_grace",
    "agents.roles.sd_ku_tony",
    "agents.roles.wm_ku_elena",
    "agents.roles.pp_ku_ibrahim",
    "agents.roles.hr_ku_sophie",
    "agents.roles.ba_cust_james",
    "agents.roles.champ_leila",
    "agents.roles.pmo_niko",
    "agents.roles.qa_claire",
]


@pytest.mark.parametrize("module_path", ROLE_MODULES)
def test_role_module_imports(module_path: str) -> None:
    """Each of the 30 role modules must import cleanly."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# 5. Roles __init__ — ROLE_REGISTRY completeness
# ---------------------------------------------------------------------------

def test_roles_init_exports_role_registry() -> None:
    """agents.roles.__init__ must export ROLE_REGISTRY with exactly 30 entries."""
    from agents.roles import ROLE_REGISTRY
    assert isinstance(ROLE_REGISTRY, dict), "ROLE_REGISTRY must be a dict"
    assert len(ROLE_REGISTRY) == 30, (
        f"Expected 30 entries in ROLE_REGISTRY, got {len(ROLE_REGISTRY)}.\n"
        f"Present: {sorted(ROLE_REGISTRY.keys())}"
    )


def test_role_registry_all_classes_are_base_agent_subclasses() -> None:
    """Every class in ROLE_REGISTRY must be a BaseAgent subclass."""
    from agents.roles import ROLE_REGISTRY
    from agents.base_agent import BaseAgent

    for codename, cls in ROLE_REGISTRY.items():
        assert issubclass(cls, BaseAgent), (
            f"ROLE_REGISTRY['{codename}'] = {cls!r} is not a BaseAgent subclass"
        )


def test_role_registry_codenames_match_intelligence_tiers() -> None:
    """Every codename in ROLE_REGISTRY must appear in DEFAULT_AGENT_TIERS."""
    from agents.roles import ROLE_REGISTRY
    from agents.intelligence import DEFAULT_AGENT_TIERS

    registry_keys = set(ROLE_REGISTRY.keys())
    tier_keys = set(DEFAULT_AGENT_TIERS.keys())

    missing_from_tiers = registry_keys - tier_keys
    missing_from_registry = tier_keys - registry_keys

    assert not missing_from_tiers, (
        f"Codenames in ROLE_REGISTRY but not DEFAULT_AGENT_TIERS: {missing_from_tiers}"
    )
    assert not missing_from_registry, (
        f"Codenames in DEFAULT_AGENT_TIERS but not ROLE_REGISTRY: {missing_from_registry}"
    )


# ---------------------------------------------------------------------------
# 6. Simulation layer
# ---------------------------------------------------------------------------

SIMULATION_MODULES = [
    "simulation.state_machine",
    "simulation.phase_manager",
    "simulation.meeting_scheduler",
    "simulation.engine",
]


@pytest.mark.parametrize("module_path", SIMULATION_MODULES)
def test_simulation_module_imports(module_path: str) -> None:
    """Simulation layer modules must import cleanly."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# 7. Key public symbols — spot-check that critical names are actually exported
# ---------------------------------------------------------------------------

def test_litellm_client_exports_class() -> None:
    from utils.litellm_client import LiteLLMClient, build_client_from_settings
    assert callable(LiteLLMClient)
    assert callable(build_client_from_settings)


def test_persistence_exports_functions() -> None:
    from utils.persistence import (
        save_project_state,
        load_project_state,
        append_feed_event,
        save_agent_state,
        load_agent_state,
        save_memory_summary,
        load_memory_summary,
    )
    for fn in [
        save_project_state, load_project_state, append_feed_event,
        save_agent_state, load_agent_state, save_memory_summary, load_memory_summary,
    ]:
        assert callable(fn), f"{fn.__name__} must be callable"


def test_memory_exports_compress_function() -> None:
    from utils.memory import (
        compress_memory,
        compress_memory_at_phase_end,
        compress_memory_if_context_near_limit,
    )
    assert callable(compress_memory)
    assert callable(compress_memory_at_phase_end)
    assert callable(compress_memory_if_context_near_limit)


def test_sse_exports_event_bus() -> None:
    from api.sse import EventBus, get_bus, destroy_bus
    assert callable(EventBus)
    assert callable(get_bus)
    assert callable(destroy_bus)


def test_config_exports_settings_model() -> None:
    from config import ProjectSettings, load_settings, save_settings
    assert callable(ProjectSettings)
    assert callable(load_settings)
    assert callable(save_settings)


def test_personality_exports_roll_and_drift() -> None:
    from agents.personality import roll_personality, drift_personality
    assert callable(roll_personality)
    assert callable(drift_personality)


def test_factory_exports_create_agent() -> None:
    from agents.factory import create_agent, create_all_agents, list_codenames
    assert callable(create_agent)
    assert callable(create_all_agents)
    assert callable(list_codenames)


def test_intelligence_exports_get_model() -> None:
    from agents.intelligence import (
        get_model_for_agent,
        get_tier_for_agent,
        DEFAULT_AGENT_TIERS,
        INTELLIGENCE_TIERS,
    )
    assert callable(get_model_for_agent)
    assert callable(get_tier_for_agent)
    assert isinstance(DEFAULT_AGENT_TIERS, dict)
    assert isinstance(INTELLIGENCE_TIERS, dict)


def test_base_agent_exports_class() -> None:
    from agents.base_agent import BaseAgent, MEMORY_COMPRESSION_THRESHOLD
    assert callable(BaseAgent)
    assert isinstance(MEMORY_COMPRESSION_THRESHOLD, int)


# ---------------------------------------------------------------------------
# 8. Instantiation smoke test — create one role instance without LLM calls
# ---------------------------------------------------------------------------

def test_role_class_instantiation_pm_alex() -> None:
    """Verify PmAlex (Tier 1) can be instantiated with a mock LiteLLM client."""
    from unittest.mock import MagicMock
    from agents.roles.pm_alex import PmAlex

    mock_client = MagicMock()
    agent = PmAlex(
        codename="PM_ALEX",
        project_name="test-project",
        litellm_client=mock_client,
    )
    assert agent.codename == "PM_ALEX"
    assert agent.side in ("consultant", "customer", "crossfunctional")
    assert isinstance(agent.skills, list)
    assert len(agent.skills) > 0, "PM_ALEX should have at least one skill"


def test_role_class_instantiation_customer_with_personality() -> None:
    """Verify a customer agent can be instantiated with a personality dict."""
    from unittest.mock import MagicMock
    from agents.roles.exec_victor import ExecVictor
    from agents.personality import roll_personality

    mock_client = MagicMock()
    personality = roll_personality(seed=42)
    agent = ExecVictor(
        codename="EXEC_VICTOR",
        project_name="test-project",
        litellm_client=mock_client,
        personality=personality,
    )
    assert agent.codename == "EXEC_VICTOR"
    assert agent.personality is not None
    assert "archetype" in agent.personality


def test_system_prompt_builds_without_error() -> None:
    """Verify build_system_prompt() runs to completion for a consultant agent."""
    from unittest.mock import MagicMock
    from agents.roles.arch_sara import ArchSara

    mock_client = MagicMock()
    agent = ArchSara(
        codename="ARCH_SARA",
        project_name="test-project",
        litellm_client=mock_client,
    )
    prompt = agent.build_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100, "System prompt should not be empty"
    assert "ARCH_SARA" in prompt


# ---------------------------------------------------------------------------
# Entry-point for running directly: python tests/test_imports.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    sys.exit(result.returncode)
