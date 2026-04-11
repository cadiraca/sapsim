"""
SAP SIM — Personality System
Phase: 2.4
Purpose: Defines personality axes, archetypes, roll/drift functions, and tier-drift logic
         for customer-side agents. Consultants have fixed professional identities; customer
         agents have living personalities that shift based on project events.
Dependencies: agents/intelligence.py (for tier drift), Python stdlib only
"""

from __future__ import annotations

import random
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from agents.intelligence import DEFAULT_AGENT_TIERS, INTELLIGENCE_TIERS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Personality axes range
# ---------------------------------------------------------------------------

AXIS_MIN = 1
AXIS_MAX = 5

# ---------------------------------------------------------------------------
# 2. Archetype definitions
#    Each archetype maps to an inclusive range per axis: (min, max)
#    A personality matches an archetype when all three axes fall within range.
# ---------------------------------------------------------------------------

ARCHETYPES: dict[str, dict[str, tuple[int, int]]] = {
    "The Skeptic": {
        "engagement":    (3, 5),
        "trust":         (1, 2),
        "risk_tolerance":(1, 3),
    },
    "The Absent Sponsor": {
        "engagement":    (1, 2),
        "trust":         (3, 4),
        "risk_tolerance":(2, 4),
    },
    "The Spreadsheet Hoarder": {
        "engagement":    (2, 4),
        "trust":         (2, 3),
        "risk_tolerance":(1, 2),
    },
    "The Reluctant Champion": {
        "engagement":    (3, 4),
        "trust":         (2, 3),
        "risk_tolerance":(2, 3),
    },
    "The Power User": {
        "engagement":    (4, 5),
        "trust":         (4, 5),
        "risk_tolerance":(3, 5),
    },
    "The Escalator": {
        "engagement":    (4, 5),
        "trust":         (1, 2),
        "risk_tolerance":(1, 2),
    },
    "The Ghost": {
        "engagement":    (1, 2),
        "trust":         (3, 5),
        "risk_tolerance":(2, 4),
    },
    "The Overloader": {
        "engagement":    (5, 5),
        "trust":         (4, 5),
        "risk_tolerance":(4, 5),
    },
    "The Process Purist": {
        "engagement":    (3, 5),
        "trust":         (2, 4),
        "risk_tolerance":(1, 2),
    },
    "The Shadow IT Builder": {
        "engagement":    (4, 5),
        "trust":         (1, 3),
        "risk_tolerance":(4, 5),
    },
    "The Hands-On Expert": {
        "engagement":    (4, 5),
        "trust":         (3, 5),
        "risk_tolerance":(3, 4),
    },
    "The Change Resistor": {
        "engagement":    (2, 4),
        "trust":         (1, 2),
        "risk_tolerance":(1, 2),
    },
    "The Enthusiast": {
        "engagement":    (4, 5),
        "trust":         (4, 5),
        "risk_tolerance":(4, 5),
    },
    "The Overwhelmed": {
        "engagement":    (2, 3),
        "trust":         (3, 4),
        "risk_tolerance":(2, 3),
    },
}

# Priority order for archetype matching — more specific / restrictive archetypes first.
# When multiple archetypes match, the first in this list wins.
ARCHETYPE_PRIORITY: list[str] = [
    "The Overloader",       # very specific (all axes high-end)
    "The Enthusiast",       # similar to Overloader but slightly looser
    "The Ghost",            # engagement 1-2 is very distinctive
    "The Absent Sponsor",   # engagement 1-2 but different trust/risk pattern
    "The Escalator",        # low trust + high engagement
    "The Skeptic",          # high engagement, low trust
    "The Power User",       # high engagement, high trust
    "The Spreadsheet Hoarder",  # low risk
    "The Shadow IT Builder",    # low trust, high risk
    "The Process Purist",       # low risk
    "The Hands-On Expert",      # high engagement, medium-high trust
    "The Change Resistor",      # low trust, low risk
    "The Reluctant Champion",   # middle values
    "The Overwhelmed",          # middle values
]

# Fallback when no archetype matches
DEFAULT_ARCHETYPE = "The Overwhelmed"

# ---------------------------------------------------------------------------
# 3. Drift rules per event type
#    Each event maps to axis deltas: {axis: delta}
#    Delta is applied (then clamped) to the current axis value.
# ---------------------------------------------------------------------------

DRIFT_RULES: dict[str, dict[str, int]] = {
    "demo_success": {
        "trust":          +1,
        "engagement":     +1,
        "risk_tolerance":  0,
    },
    "demo_failure": {
        "trust":          -1,
        "engagement":     -1,
        "risk_tolerance":  0,
    },
    "deadline_missed": {
        "trust":          -1,
        "engagement":     -1,
        "risk_tolerance":  0,
    },
    "blocker_resolved": {
        "trust":          +1,
        "engagement":      0,
        "risk_tolerance": +1,
    },
    "escalation_ignored": {
        "trust":          -2,
        "engagement":     -1,
        "risk_tolerance":  0,
    },
    "go_live_rehearsal_passed": {
        "trust":          +1,
        "engagement":     +1,
        "risk_tolerance": +1,
    },
    "scope_creep_added": {
        "trust":           0,
        "engagement":     +1,
        "risk_tolerance": -1,
    },
    "scope_creep_rejected": {
        "trust":          -1,
        "engagement":     -1,
        "risk_tolerance":  0,
    },
    "training_delivered": {
        "trust":          +1,
        "engagement":     +1,
        "risk_tolerance": +1,
    },
    "uat_defect_spike": {
        "trust":          -1,
        "engagement":      0,
        "risk_tolerance": -1,
    },
    "critical_decision_made": {
        "trust":           0,
        "engagement":     +1,
        "risk_tolerance":  0,
    },
    "meeting_skipped": {
        "trust":          -1,
        "engagement":     -1,
        "risk_tolerance":  0,
    },
    "positive_feedback_received": {
        "trust":          +1,
        "engagement":     +1,
        "risk_tolerance": +1,
    },
}

# ---------------------------------------------------------------------------
# 4. Tier drift thresholds
#    Customer agents can upgrade or downgrade intelligence tiers as their
#    personality evolves. Thresholds are based on combined axis scores.
# ---------------------------------------------------------------------------

# Combined score = engagement + trust + risk_tolerance (range: 3-15)
TIER_UPGRADE_THRESHOLD = 11   # combined score ≥ this → eligible for tier upgrade
TIER_DOWNGRADE_THRESHOLD = 6  # combined score ≤ this → eligible for tier downgrade

# Which customer agents are eligible for tier drift (excludes strategic-tier customers)
TIER_DRIFT_ELIGIBLE = {
    "WM_KU_ELENA",
    "PP_KU_IBRAHIM",
    "HR_KU_SOPHIE",
    "CHAMP_LEILA",
    "FI_KU_ROSE",
    "CO_KU_BJORN",
    "MM_KU_GRACE",
    "SD_KU_TONY",
    "BA_CUST_JAMES",
    "CUST_PM_OMAR",
    "IT_MGR_HELEN",
}

# Tier order for upgrade/downgrade logic
TIER_ORDER = ["basic", "operational", "senior", "strategic"]


# ---------------------------------------------------------------------------
# 5. Public API
# ---------------------------------------------------------------------------

def evaluate_archetype(engagement: int, trust: int, risk_tolerance: int) -> str:
    """
    Determine the best-matching archetype for the given axis values.

    Iterates archetypes in ARCHETYPE_PRIORITY order and returns the first
    whose ranges encompass all three axes. Falls back to DEFAULT_ARCHETYPE
    if no match is found.

    Args:
        engagement:     Score 1-5.
        trust:          Score 1-5.
        risk_tolerance: Score 1-5.

    Returns:
        Archetype name string.
    """
    axes = {
        "engagement": engagement,
        "trust": trust,
        "risk_tolerance": risk_tolerance,
    }
    for archetype_name in ARCHETYPE_PRIORITY:
        spec = ARCHETYPES[archetype_name]
        if all(
            spec[axis][0] <= axes[axis] <= spec[axis][1]
            for axis in ("engagement", "trust", "risk_tolerance")
        ):
            return archetype_name
    return DEFAULT_ARCHETYPE


def roll_personality(seed: Optional[int] = None) -> dict[str, Any]:
    """
    Randomly generate a personality for a customer agent.

    Selects a random archetype, then rolls axis scores within that archetype's
    defined ranges. History starts empty.

    Args:
        seed: Optional random seed for reproducibility (useful in tests).

    Returns:
        Personality dict with keys:
            engagement (int), trust (int), risk_tolerance (int),
            archetype (str), history (list)
    """
    rng = random.Random(seed)

    # Pick a random archetype
    archetype_name = rng.choice(list(ARCHETYPES.keys()))
    spec = ARCHETYPES[archetype_name]

    engagement = rng.randint(spec["engagement"][0],    spec["engagement"][1])
    trust      = rng.randint(spec["trust"][0],         spec["trust"][1])
    risk_tol   = rng.randint(spec["risk_tolerance"][0], spec["risk_tolerance"][1])

    personality: dict[str, Any] = {
        "engagement":     engagement,
        "trust":          trust,
        "risk_tolerance": risk_tol,
        "archetype":      archetype_name,
        "history":        [],
    }

    logger.debug(
        "Rolled personality: archetype=%s eng=%d trust=%d risk=%d",
        archetype_name, engagement, trust, risk_tol,
    )

    return personality


def drift_personality(
    personality: dict[str, Any],
    event_type: str,
    agent_codename: Optional[str] = None,
    simulated_day: int = 0,
) -> dict[str, Any]:
    """
    Apply event-driven drift to a personality and optionally adjust intelligence tier.

    Drift rules are looked up from DRIFT_RULES. Axes are clamped to [AXIS_MIN, AXIS_MAX]
    after adjustment. Archetype is re-evaluated after each drift. Tier upgrade/downgrade
    logic fires for eligible agents when combined axis score crosses a threshold.

    Args:
        personality:     The personality dict to mutate (shallow-copied internally;
                         the original is NOT modified).
        event_type:      One of the keys in DRIFT_RULES.
        agent_codename:  Optional codename — used for tier drift eligibility check
                         and log context.
        simulated_day:   Current simulated day number — recorded in history.

    Returns:
        New personality dict with updated axes, archetype, tier (if applicable),
        and history entry appended.

    Raises:
        ValueError: If event_type is not in DRIFT_RULES.
    """
    if event_type not in DRIFT_RULES:
        raise ValueError(
            f"Unknown event type '{event_type}'. "
            f"Valid events: {sorted(DRIFT_RULES.keys())}"
        )

    # Work on a shallow copy — preserve original
    updated = dict(personality)
    updated["history"] = list(personality.get("history", []))

    deltas = DRIFT_RULES[event_type]

    # Capture before values
    before = {
        "engagement":     updated["engagement"],
        "trust":          updated["trust"],
        "risk_tolerance": updated["risk_tolerance"],
    }

    # Apply deltas with clamping
    updated["engagement"] = _clamp(
        updated["engagement"] + deltas.get("engagement", 0)
    )
    updated["trust"] = _clamp(
        updated["trust"] + deltas.get("trust", 0)
    )
    updated["risk_tolerance"] = _clamp(
        updated["risk_tolerance"] + deltas.get("risk_tolerance", 0)
    )

    # Re-evaluate archetype
    prev_archetype = updated.get("archetype", DEFAULT_ARCHETYPE)
    updated["archetype"] = evaluate_archetype(
        updated["engagement"],
        updated["trust"],
        updated["risk_tolerance"],
    )

    # Build history entry
    entry: dict[str, Any] = {
        "event":      event_type,
        "day":        simulated_day,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "deltas":     {k: v for k, v in deltas.items() if v != 0},
        "before":     before,
        "after": {
            "engagement":     updated["engagement"],
            "trust":          updated["trust"],
            "risk_tolerance": updated["risk_tolerance"],
        },
        "archetype_changed": prev_archetype != updated["archetype"],
        "archetype_before":  prev_archetype,
        "archetype_after":   updated["archetype"],
    }

    # ---- Tier drift logic ----
    tier_change = _evaluate_tier_drift(updated, agent_codename)
    if tier_change:
        entry["tier_before"] = tier_change["from"]
        entry["tier_after"]  = tier_change["to"]
        updated["intelligence_tier_override"] = tier_change["to"]
        logger.info(
            "[%s] Tier drift: %s → %s (event=%s, day=%d)",
            agent_codename or "?", tier_change["from"], tier_change["to"],
            event_type, simulated_day,
        )

    updated["history"].append(entry)

    if agent_codename:
        logger.debug(
            "[%s] drift_personality event=%s eng:%d→%d trust:%d→%d risk:%d→%d arch:%s→%s",
            agent_codename,
            event_type,
            before["engagement"],    updated["engagement"],
            before["trust"],         updated["trust"],
            before["risk_tolerance"], updated["risk_tolerance"],
            prev_archetype,          updated["archetype"],
        )

    return updated


# ---------------------------------------------------------------------------
# 6. Private helpers
# ---------------------------------------------------------------------------

def _clamp(value: int) -> int:
    """Clamp axis score to [AXIS_MIN, AXIS_MAX]."""
    return max(AXIS_MIN, min(AXIS_MAX, value))


def _combined_score(personality: dict[str, Any]) -> int:
    """Return sum of the three axis values (range: 3-15)."""
    return (
        personality.get("engagement", 3)
        + personality.get("trust", 3)
        + personality.get("risk_tolerance", 3)
    )


def _evaluate_tier_drift(
    personality: dict[str, Any],
    agent_codename: Optional[str],
) -> Optional[dict[str, str]]:
    """
    Check whether a tier upgrade or downgrade should occur for this agent.

    Only fires for agents in TIER_DRIFT_ELIGIBLE. Compares combined axis score
    against TIER_UPGRADE_THRESHOLD / TIER_DOWNGRADE_THRESHOLD and promotes or
    demotes one tier at a time.

    Args:
        personality:     Updated personality dict.
        agent_codename:  Agent codename (may be None).

    Returns:
        Dict {"from": old_tier, "to": new_tier} if a change is warranted,
        otherwise None.
    """
    if not agent_codename:
        return None

    codename_upper = agent_codename.upper()
    if codename_upper not in TIER_DRIFT_ELIGIBLE:
        return None

    current_tier = personality.get(
        "intelligence_tier_override",
        DEFAULT_AGENT_TIERS.get(codename_upper),
    )
    if current_tier not in TIER_ORDER:
        return None

    score = _combined_score(personality)
    current_idx = TIER_ORDER.index(current_tier)

    if score >= TIER_UPGRADE_THRESHOLD and current_idx < len(TIER_ORDER) - 1:
        new_tier = TIER_ORDER[current_idx + 1]
        return {"from": current_tier, "to": new_tier}

    if score <= TIER_DOWNGRADE_THRESHOLD and current_idx > 0:
        new_tier = TIER_ORDER[current_idx - 1]
        return {"from": current_tier, "to": new_tier}

    return None


# ---------------------------------------------------------------------------
# 7. Convenience: describe personality in plain text (useful for debugging/UI)
# ---------------------------------------------------------------------------

def describe_personality(personality: dict[str, Any]) -> str:
    """
    Return a short human-readable description of a personality dict.

    Args:
        personality: Personality dict (output of roll_personality or drift_personality).

    Returns:
        Multi-line string.
    """
    archetype = personality.get("archetype", DEFAULT_ARCHETYPE)
    engagement = personality.get("engagement", "?")
    trust = personality.get("trust", "?")
    risk = personality.get("risk_tolerance", "?")
    history_len = len(personality.get("history", []))
    tier_override = personality.get("intelligence_tier_override")

    lines = [
        f"Archetype:       {archetype}",
        f"Engagement:      {engagement}/5",
        f"Trust:           {trust}/5",
        f"Risk Tolerance:  {risk}/5",
        f"Drift events:    {history_len}",
    ]
    if tier_override:
        lines.append(f"Tier override:   {tier_override}")

    return "\n".join(lines)
