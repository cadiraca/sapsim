"""
SAP SIM — Agent Factory
Phase: 2.5
Purpose: Single entry point for instantiating any of the 30 simulation agents.
         Handles class resolution, disk-state restoration (resume support),
         personality rolling for customer agents, and intelligence-tier wiring.
Dependencies: agents/roles/*, agents/base_agent.BaseAgent, agents/personality,
              agents/intelligence, utils/persistence (via BaseAgent.load)
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from agents.base_agent import BaseAgent
from agents.intelligence import DEFAULT_AGENT_TIERS
from agents.personality import roll_personality

if TYPE_CHECKING:
    from utils.litellm_client import LiteLLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Codename → (module path, class name) registry
#    Entries are ordered: consultants first, customers second, cross-functional last.
# ---------------------------------------------------------------------------

_ROLE_REGISTRY: dict[str, tuple[str, str]] = {
    # ---- Consultant side (16) ----
    "PM_ALEX":       ("agents.roles.pm_alex",       "PmAlex"),
    "ARCH_SARA":     ("agents.roles.arch_sara",      "ArchSara"),
    "BASIS_KURT":    ("agents.roles.basis_kurt",     "BasisKurt"),
    "DEV_PRIYA":     ("agents.roles.dev_priya",      "DevPriya"),
    "DEV_LEON":      ("agents.roles.dev_leon",       "DevLeon"),
    "FI_CHEN":       ("agents.roles.fi_chen",        "FiChen"),
    "CO_MARTA":      ("agents.roles.co_marta",       "CoMarta"),
    "MM_RAVI":       ("agents.roles.mm_ravi",        "MmRavi"),
    "SD_ISLA":       ("agents.roles.sd_isla",        "SdIsla"),
    "PP_JONAS":      ("agents.roles.pp_jonas",       "PpJonas"),
    "WM_FATIMA":     ("agents.roles.wm_fatima",      "WmFatima"),
    "INT_MARCO":     ("agents.roles.int_marco",      "IntMarco"),
    "SEC_DIANA":     ("agents.roles.sec_diana",      "SecDiana"),
    "BI_SAM":        ("agents.roles.bi_sam",         "BiSam"),
    "CHG_NADIA":     ("agents.roles.chg_nadia",      "ChgNadia"),
    "DM_FELIX":      ("agents.roles.dm_felix",       "DmFelix"),

    # ---- Customer side (12) ----
    "EXEC_VICTOR":   ("agents.roles.exec_victor",    "ExecVictor"),
    "IT_MGR_HELEN":  ("agents.roles.it_mgr_helen",   "ItMgrHelen"),
    "CUST_PM_OMAR":  ("agents.roles.cust_pm_omar",   "CustPmOmar"),
    "FI_KU_ROSE":    ("agents.roles.fi_ku_rose",     "FiKuRose"),
    "CO_KU_BJORN":   ("agents.roles.co_ku_bjorn",    "CoKuBjorn"),
    "MM_KU_GRACE":   ("agents.roles.mm_ku_grace",    "MmKuGrace"),
    "SD_KU_TONY":    ("agents.roles.sd_ku_tony",     "SdKuTony"),
    "WM_KU_ELENA":   ("agents.roles.wm_ku_elena",    "WmKuElena"),
    "PP_KU_IBRAHIM": ("agents.roles.pp_ku_ibrahim",  "PpKuIbrahim"),
    "HR_KU_SOPHIE":  ("agents.roles.hr_ku_sophie",   "HrKuSophie"),
    "BA_CUST_JAMES": ("agents.roles.ba_cust_james",  "BaCustJames"),
    "CHAMP_LEILA":   ("agents.roles.champ_leila",    "ChampLeila"),

    # ---- Cross-functional (2) ----
    "PMO_NIKO":      ("agents.roles.pmo_niko",       "PmoNiko"),
    "QA_CLAIRE":     ("agents.roles.qa_claire",      "QaClaire"),
}

# Sanity check at import time: registry covers all agents defined in intelligence.py
_EXPECTED_CODENAMES = set(DEFAULT_AGENT_TIERS.keys())
_REGISTERED_CODENAMES = set(_ROLE_REGISTRY.keys())
assert _REGISTERED_CODENAMES == _EXPECTED_CODENAMES, (
    "factory._ROLE_REGISTRY is out of sync with intelligence.DEFAULT_AGENT_TIERS.\n"
    f"  Missing in registry: {_EXPECTED_CODENAMES - _REGISTERED_CODENAMES}\n"
    f"  Extra in registry:   {_REGISTERED_CODENAMES - _EXPECTED_CODENAMES}"
)

# Customer-side codenames — these receive personality rolls if none is provided
_CUSTOMER_CODENAMES: frozenset[str] = frozenset(
    codename
    for codename, (module, cls) in _ROLE_REGISTRY.items()
    # We determine side by checking the module names; cross-functional excluded
    # The authoritative set: all 12 customer agents as defined in roles/
)
# Hard-code the exact 12 customer agents for clarity (avoids runtime import to check side)
_CUSTOMER_CODENAMES = frozenset({
    "EXEC_VICTOR", "IT_MGR_HELEN", "CUST_PM_OMAR", "FI_KU_ROSE",
    "CO_KU_BJORN",  "MM_KU_GRACE", "SD_KU_TONY",   "WM_KU_ELENA",
    "PP_KU_IBRAHIM","HR_KU_SOPHIE","BA_CUST_JAMES", "CHAMP_LEILA",
})


# ---------------------------------------------------------------------------
# 2. Private: resolve role class
# ---------------------------------------------------------------------------

def _resolve_role_class(codename: str) -> type[BaseAgent]:
    """
    Dynamically import and return the role class for ``codename``.

    Args:
        codename: Upper-case agent codename (e.g. ``"PM_ALEX"``).

    Returns:
        The role class (a subclass of BaseAgent).

    Raises:
        ValueError: If codename is not in the registry.
        ImportError: If the module cannot be imported.
        AttributeError: If the class is not found in the module.
    """
    entry = _ROLE_REGISTRY.get(codename)
    if entry is None:
        raise ValueError(
            f"Unknown agent codename '{codename}'. "
            f"Registered agents: {sorted(_ROLE_REGISTRY.keys())}"
        )

    module_path, class_name = entry
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# ---------------------------------------------------------------------------
# 3. Public: create_agent
# ---------------------------------------------------------------------------

async def create_agent(
    codename: str,
    project_name: str,
    litellm_client: "LiteLLMClient",
    personality: Optional[dict[str, Any]] = None,
    personality_seed: Optional[int] = None,
) -> BaseAgent:
    """
    Create (or restore) an agent instance for the given codename.

    Behaviour:
    1. Resolve the role class from the registry.
    2. Attempt to load existing state from disk (for simulation resumption).
       - If state exists → restore, apply any personality override if provided.
    3. If no saved state:
       - If ``personality`` is provided → use it directly.
       - Else if agent is customer-side → roll a new personality.
       - Else (consultant / cross-functional) → no personality.
    4. If a personality ``intelligence_tier_override`` is set (from drift logic),
       apply it to the agent's ``intelligence_tier``.
    5. Return the initialised agent.

    Args:
        codename:         Agent codename (case-insensitive; normalised internally).
        project_name:     Project this agent belongs to.
        litellm_client:   Shared LiteLLM client for LLM calls.
        personality:      Optional pre-built personality dict (overrides roll).
        personality_seed: Optional seed forwarded to roll_personality() for
                          reproducible personality generation in tests.

    Returns:
        Initialised BaseAgent subclass instance, ready to call ``.act()``.

    Raises:
        ValueError: Unknown codename.
        ImportError: Role module not loadable.
    """
    codename_upper = codename.upper()

    # 1. Resolve role class
    role_class = _resolve_role_class(codename_upper)

    # 2. Attempt state restoration from disk
    restored_agent: Optional[BaseAgent] = await BaseAgent.load(
        codename=codename_upper,
        project_name=project_name,
        litellm_client=litellm_client,
    )

    if restored_agent is not None:
        # --- Resumed simulation ---
        logger.info("[%s] Restored from saved state (project=%s)", codename_upper, project_name)

        # Apply personality override if explicitly supplied (e.g. re-roll from UI)
        if personality is not None:
            restored_agent.personality = personality
            logger.debug("[%s] Personality overridden on restore.", codename_upper)

        # Apply any tier drift recorded in personality
        _apply_tier_drift(restored_agent)

        return restored_agent

    # 3. Fresh instantiation
    # -------------------------------------------------------------------
    # Determine personality for this agent
    # -------------------------------------------------------------------
    resolved_personality: Optional[dict[str, Any]] = None

    if personality is not None:
        # Caller explicitly provided one
        resolved_personality = personality
        logger.debug("[%s] Using caller-provided personality.", codename_upper)

    elif codename_upper in _CUSTOMER_CODENAMES:
        # Customer agent with no saved state — roll a fresh personality
        resolved_personality = roll_personality(seed=personality_seed)
        logger.info(
            "[%s] Rolled new personality: archetype=%s eng=%d trust=%d risk=%d",
            codename_upper,
            resolved_personality.get("archetype"),
            resolved_personality.get("engagement"),
            resolved_personality.get("trust"),
            resolved_personality.get("risk_tolerance"),
        )
    else:
        # Consultant / cross-functional — no personality axes
        resolved_personality = None

    # -------------------------------------------------------------------
    # Instantiate the role class (subclass of BaseAgent)
    # -------------------------------------------------------------------
    agent: BaseAgent = role_class(
        codename=codename_upper,
        project_name=project_name,
        litellm_client=litellm_client,
        personality=resolved_personality,
    )

    # 4. Apply tier drift from personality (if tier_override already set)
    _apply_tier_drift(agent)

    logger.info(
        "[%s] Created new agent: role=%s side=%s tier=%s",
        codename_upper,
        agent.role,
        agent.side,
        agent.intelligence_tier,
    )

    return agent


# ---------------------------------------------------------------------------
# 4. Batch factory — create all 30 agents for a project
# ---------------------------------------------------------------------------

async def create_all_agents(
    project_name: str,
    litellm_client: "LiteLLMClient",
    personality_overrides: Optional[dict[str, dict[str, Any]]] = None,
    personality_seeds: Optional[dict[str, int]] = None,
) -> dict[str, BaseAgent]:
    """
    Create (or restore) all 30 agents for a project in one call.

    Customer agents without an override are given randomly rolled personalities.
    Personality seeds can be supplied per-agent for reproducible test setups.

    Args:
        project_name:          Project identifier.
        litellm_client:        Shared LiteLLM client.
        personality_overrides: Optional mapping of codename → personality dict.
                               Codenames are case-insensitive.
        personality_seeds:     Optional mapping of codename → seed for roll_personality().

    Returns:
        Dict mapping upper-case codename → initialised BaseAgent instance.
    """
    overrides = {k.upper(): v for k, v in (personality_overrides or {}).items()}
    seeds = {k.upper(): v for k, v in (personality_seeds or {}).items()}

    agents: dict[str, BaseAgent] = {}

    for codename in _ROLE_REGISTRY:
        agent = await create_agent(
            codename=codename,
            project_name=project_name,
            litellm_client=litellm_client,
            personality=overrides.get(codename),
            personality_seed=seeds.get(codename),
        )
        agents[codename] = agent

    logger.info(
        "All %d agents created/restored for project '%s'.",
        len(agents), project_name,
    )
    return agents


# ---------------------------------------------------------------------------
# 5. Private: apply tier drift from personality
# ---------------------------------------------------------------------------

def _apply_tier_drift(agent: BaseAgent) -> None:
    """
    If the agent's personality contains an ``intelligence_tier_override``,
    update ``agent.intelligence_tier`` to reflect the drifted tier.

    This is called both on fresh instantiation and on restoration from disk.

    Args:
        agent: The agent instance to potentially mutate.
    """
    if not agent.personality:
        return

    tier_override = agent.personality.get("intelligence_tier_override")
    if tier_override and tier_override != agent.intelligence_tier:
        logger.info(
            "[%s] Applying tier drift: %s → %s",
            agent.codename, agent.intelligence_tier, tier_override,
        )
        agent.intelligence_tier = tier_override


# ---------------------------------------------------------------------------
# 6. Utility: list all registered codenames
# ---------------------------------------------------------------------------

def list_codenames(side: Optional[str] = None) -> list[str]:
    """
    Return sorted list of all registered agent codenames.

    Args:
        side: Optional filter — one of "consultant", "customer", "cross-functional",
              or None (all agents).

    Returns:
        Sorted list of upper-case codenames.
    """
    if side is None:
        return sorted(_ROLE_REGISTRY.keys())

    side_lower = side.lower()
    result: list[str] = []

    if side_lower == "customer":
        result = sorted(_CUSTOMER_CODENAMES)
    elif side_lower in ("crossfunctional", "cross-functional", "cross_functional"):
        result = sorted(["PMO_NIKO", "QA_CLAIRE"])
    elif side_lower == "consultant":
        all_non_customer = set(_ROLE_REGISTRY.keys()) - _CUSTOMER_CODENAMES - {"PMO_NIKO", "QA_CLAIRE"}
        result = sorted(all_non_customer)
    else:
        logger.warning("list_codenames: unknown side filter '%s' — returning all.", side)
        result = sorted(_ROLE_REGISTRY.keys())

    return result


# ---------------------------------------------------------------------------
# 7. AgentFactory — class façade over the module-level functions
#    Provides a single importable name for code/tests that expect a class.
# ---------------------------------------------------------------------------

class AgentFactory:
    """
    Thin façade class that exposes the module-level factory functions as
    static / class methods.  Exists primarily so that integration tests and
    external code can do ``from agents.factory import AgentFactory`` without
    breaking the existing function-based API.
    """

    @staticmethod
    async def create_agent(
        codename: str,
        project_name: str,
        litellm_client: "LiteLLMClient",
        personality: Optional[dict[str, Any]] = None,
        personality_seed: Optional[int] = None,
    ) -> BaseAgent:
        """Delegate to module-level :func:`create_agent`."""
        return await create_agent(
            codename=codename,
            project_name=project_name,
            litellm_client=litellm_client,
            personality=personality,
            personality_seed=personality_seed,
        )

    @staticmethod
    async def create_all_agents(
        project_name: str,
        litellm_client: "LiteLLMClient",
        personality_overrides: Optional[dict[str, dict[str, Any]]] = None,
        personality_seeds: Optional[dict[str, int]] = None,
    ) -> dict[str, BaseAgent]:
        """Delegate to module-level :func:`create_all_agents`."""
        return await create_all_agents(
            project_name=project_name,
            litellm_client=litellm_client,
            personality_overrides=personality_overrides,
            personality_seeds=personality_seeds,
        )

    @staticmethod
    def list_codenames(side: Optional[str] = None) -> list[str]:
        """Delegate to module-level :func:`list_codenames`."""
        return list_codenames(side=side)

    @staticmethod
    def resolve_role_class(codename: str) -> type[BaseAgent]:
        """Delegate to module-level :func:`_resolve_role_class`."""
        return _resolve_role_class(codename)

