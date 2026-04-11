"""
SAP SIM — Agent Intelligence Tiers
Phase: 1.4 (Addendum)
Purpose: Maps agent codenames to LLM intelligence tiers. Tiers define which model
         each agent uses, simulating real-world variance in capability, experience,
         and engagement level across the 30-agent SAP implementation team.
Dependencies: None (pure configuration)

Tier summary:
  strategic   → claude-4-6-opus    (PM, architect, exec, PMO)
  senior      → claude-4-6-sonnet  (domain leads, QA, IT mgr, cust PM)
  operational → gemini-2.5-pro     (developers, business analysts, functional key users)
  basic       → qwen3.6-plus       (low-engagement archetypes: ghost, reluctant champion)

Tier drift for customer agents is handled in backend/agents/personality.py.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# 1. Model identifiers (match backend/utils/litellm_client.py build_kwargs format)
#    The "openai/" prefix is added by LiteLLMClient._build_kwargs(); use bare names here.
# ---------------------------------------------------------------------------

INTELLIGENCE_TIERS: dict[str, dict] = {
    "strategic": {
        "tier_name": "strategic",
        "model": "claude-4-6-opus",
        "label": "Tier 1 — Strategic",
        "description": (
            "Big-picture thinkers with complex trade-off reasoning. "
            "Used for PMs, architects, executives, and PMO roles."
        ),
        "rationale": "Handles ambiguous, multi-stakeholder decisions with nuance.",
    },
    "senior": {
        "tier_name": "senior",
        "model": "claude-4-6-sonnet",
        "label": "Tier 2 — Senior",
        "description": (
            "Domain experts and solid decision-makers. "
            "Used for module leads, security, BI, change management, QA."
        ),
        "rationale": "Deep domain knowledge with reliable context retention.",
    },
    "operational": {
        "tier_name": "operational",
        "model": "gemini-2.5-pro",
        "label": "Tier 3 — Operational",
        "description": (
            "Capable but with narrower scope. "
            "Used for developers, business analysts, and functional key users."
        ),
        "rationale": "Handles day-to-day tasks; occasionally misses broader context.",
    },
    "basic": {
        "tier_name": "basic",
        "model": "qwen3.6-plus",
        "label": "Tier 4 — Basic",
        "description": (
            "Low-engagement archetypes. Terse responses, may miss things. "
            "Used for ghost, reluctant champion, and absent sponsor archetypes."
        ),
        "rationale": "Reflects low availability / engagement of certain customer stakeholders.",
    },
}


# ---------------------------------------------------------------------------
# 2. Default tier assignment for all 30 agent codenames
# ---------------------------------------------------------------------------

DEFAULT_AGENT_TIERS: dict[str, str] = {
    # -----------------------------------------------------------------------
    # CONSULTANT SIDE — 16 agents
    # -----------------------------------------------------------------------

    # Strategic: Project lead + architecture + PMO
    "PM_ALEX":    "strategic",   # Project Manager — tracks everything, guards scope
    "ARCH_SARA":  "strategic",   # Solution Architect — thinks in whiteboards / models
    "PMO_NIKO":   "strategic",   # PMO — governance, reporting, risk management

    # Senior: All module leads + cross-cutting roles
    "FI_CHEN":    "senior",      # FI Lead — finance accounting & controlling
    "CO_MARTA":   "senior",      # CO Lead — cost center / profit center / CO-PA
    "MM_RAVI":    "senior",      # MM Lead — procurement, inventory management
    "SD_ISLA":    "senior",      # SD Lead — O2C, pricing, billing
    "PP_JONAS":   "senior",      # PP Lead — MRP, production orders
    "WM_FATIMA":  "senior",      # WM/EWM Lead — warehouse management
    "INT_MARCO":  "senior",      # Integration Lead — PI/PO, iDocs, APIs (paranoid)
    "SEC_DIANA":  "senior",      # Security Lead — roles, SoD, GRC
    "BI_SAM":     "senior",      # BI/Analytics Lead — BW/4HANA, CDS views
    "CHG_NADIA":  "senior",      # Change Management Lead — adoption, training
    "DM_FELIX":   "senior",      # Data Migration Lead — LSMW, BAPI, cutover

    # Senior: Basis admin (terse, technical, protective of landscape)
    "BASIS_KURT": "senior",      # Basis Admin — system landscape, transports, security, performance

    # Operational: Developers (narrower scope, fast but skip docs)
    "DEV_PRIYA":  "operational", # Developer — fast coder, sometimes skips documentation
    "DEV_LEON":   "operational", # Developer — asks clarifying questions, improves rapidly

    # -----------------------------------------------------------------------
    # CUSTOMER SIDE — 12 agents
    # -----------------------------------------------------------------------

    # Strategic: Executive sponsor
    "EXEC_VICTOR":    "strategic",   # Executive Sponsor — go-live pressure, escalations

    # Senior: IT Manager + Customer PM + QA
    "IT_MGR_HELEN":   "senior",      # IT Manager — landscape ownership, infra decisions
    "CUST_PM_OMAR":   "senior",      # Customer PM — counterpart to PM_ALEX
    "QA_CLAIRE":      "senior",      # QA Lead (cross-functional) — test strategy owner

    # Operational: Functional key users
    "FI_KU_ROSE":     "operational", # FI Key User — accounting team representative
    "CO_KU_BJORN":    "operational", # CO Key User — controlling team representative
    "MM_KU_GRACE":    "operational", # MM Key User — procurement team representative
    "SD_KU_TONY":     "operational", # SD Key User — sales team representative
    "BA_CUST_JAMES":  "operational", # Business Analyst (customer side) — requirements

    # Basic: Low-engagement / difficult archetypes
    "WM_KU_ELENA":    "basic",       # WM Key User — difficult about warehouse design
    "PP_KU_IBRAHIM":  "basic",       # PP Key User — limited availability
    "HR_KU_SOPHIE":   "basic",       # HR Key User — peripheral scope, often absent
    "CHAMP_LEILA":    "basic",       # Change Champion — reluctant; needs encouragement
}


# Sanity check: ensure all 30 agents are covered
_EXPECTED_AGENTS = {
    # Consultants (16)
    "PM_ALEX", "ARCH_SARA", "PMO_NIKO", "BASIS_KURT",
    "FI_CHEN", "CO_MARTA", "MM_RAVI", "SD_ISLA", "PP_JONAS", "WM_FATIMA",
    "INT_MARCO", "SEC_DIANA", "BI_SAM", "CHG_NADIA", "DM_FELIX",
    "DEV_PRIYA", "DEV_LEON",
    # Customers (12)
    "EXEC_VICTOR", "IT_MGR_HELEN", "CUST_PM_OMAR", "QA_CLAIRE",
    "FI_KU_ROSE", "CO_KU_BJORN", "MM_KU_GRACE", "SD_KU_TONY", "BA_CUST_JAMES",
    "WM_KU_ELENA", "PP_KU_IBRAHIM", "HR_KU_SOPHIE", "CHAMP_LEILA",
}
assert set(DEFAULT_AGENT_TIERS.keys()) == _EXPECTED_AGENTS, (
    "DEFAULT_AGENT_TIERS mismatch — update intelligence.py to cover all 30 agents."
)


# ---------------------------------------------------------------------------
# 3. Public API
# ---------------------------------------------------------------------------

def get_model_for_agent(
    codename: str,
    tier_override: Optional[str] = None,
) -> str:
    """
    Return the LLM model identifier for the given agent codename.

    Args:
        codename: Agent codename (e.g. "PM_ALEX", "WM_KU_ELENA").
                  Case-insensitive — normalised to upper-case internally.
        tier_override: Optional tier name that overrides the agent's default
                       assignment.  Used by personality drift logic when an agent
                       earns (or loses) engagement and moves to a different tier.

    Returns:
        A model identifier string (e.g. "claude-4-6-opus").

    Raises:
        KeyError: If codename is unknown and no override is given.
        ValueError: If tier_override references an undefined tier.
    """
    codename_upper = codename.upper()

    if tier_override is not None:
        tier_name = tier_override.lower()
        if tier_name not in INTELLIGENCE_TIERS:
            raise ValueError(
                f"Unknown tier '{tier_override}'. "
                f"Valid tiers: {list(INTELLIGENCE_TIERS.keys())}"
            )
        return INTELLIGENCE_TIERS[tier_name]["model"]

    if codename_upper not in DEFAULT_AGENT_TIERS:
        raise KeyError(
            f"Unknown agent codename '{codename}'. "
            f"Known agents: {sorted(DEFAULT_AGENT_TIERS.keys())}"
        )

    tier_name = DEFAULT_AGENT_TIERS[codename_upper]
    return INTELLIGENCE_TIERS[tier_name]["model"]


def get_tier_for_agent(codename: str) -> str:
    """
    Return the tier name (e.g. "strategic") for the given agent codename.

    Args:
        codename: Agent codename — case-insensitive.

    Returns:
        Tier name string.

    Raises:
        KeyError: If codename is unknown.
    """
    codename_upper = codename.upper()
    if codename_upper not in DEFAULT_AGENT_TIERS:
        raise KeyError(
            f"Unknown agent codename '{codename}'. "
            f"Known agents: {sorted(DEFAULT_AGENT_TIERS.keys())}"
        )
    return DEFAULT_AGENT_TIERS[codename_upper]


def get_tier_info(tier_name: str) -> dict:
    """
    Return the full tier metadata dict for the given tier name.

    Args:
        tier_name: One of "strategic", "senior", "operational", "basic".

    Returns:
        Dict with keys: tier_name, model, label, description, rationale.

    Raises:
        ValueError: If tier_name is unknown.
    """
    key = tier_name.lower()
    if key not in INTELLIGENCE_TIERS:
        raise ValueError(
            f"Unknown tier '{tier_name}'. "
            f"Valid tiers: {list(INTELLIGENCE_TIERS.keys())}"
        )
    return INTELLIGENCE_TIERS[key]


def agents_in_tier(tier_name: str) -> list[str]:
    """
    Return all agent codenames assigned to the given tier (by default assignment).

    Args:
        tier_name: One of "strategic", "senior", "operational", "basic".

    Returns:
        Sorted list of codenames.

    Raises:
        ValueError: If tier_name is unknown.
    """
    key = tier_name.lower()
    if key not in INTELLIGENCE_TIERS:
        raise ValueError(
            f"Unknown tier '{tier_name}'. "
            f"Valid tiers: {list(INTELLIGENCE_TIERS.keys())}"
        )
    return sorted(
        codename
        for codename, tier in DEFAULT_AGENT_TIERS.items()
        if tier == key
    )
