"""
SAP SIM — Memory Compression Utilities
Phase: 2.6
Purpose: Compress agent turn history into a concise summary via LLM and persist
         it to disk. Triggered after every 10 turns, at phase end, or when the
         agent's context approaches 80% of the model's context limit.
Dependencies: utils/persistence.save_memory_summary, utils/litellm_client.LiteLLMClient
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from utils.persistence import save_memory_summary

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent
    from utils.litellm_client import LiteLLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of recent turns to send to the LLM for compression.
# Sending too many turns at once can itself hit context limits; this cap keeps
# compression calls lean while still giving the LLM enough signal.
COMPRESSION_MAX_TURNS = 30

# Compression uses the fastest/cheapest available model — summaries don't need
# the agent's assigned tier model; clarity and speed matter more.
COMPRESSION_MODEL = "claude-4-6-sonnet"

# Target word budget for the generated summary (instructed to the LLM).
SUMMARY_MAX_WORDS = 300


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def compress_memory(
    agent: "BaseAgent",
    litellm_client: "LiteLLMClient",
) -> str:
    """
    Summarise the agent's recent turn history and save the result to disk.

    Steps:
    1. Build the compression prompt from the agent's buffered turns.
    2. Call LiteLLM with a fixed summary instruction (always claude-4-6-sonnet).
    3. Persist the summary to ``memory/{codename}_summary.md``.
    4. Return the summary string so the caller can store it on the agent.

    This function does **not** clear or trim ``agent.memory_turns`` —
    that responsibility stays with the caller (``BaseAgent.compress_memory_if_needed``).

    Args:
        agent:          The agent whose memory should be compressed.
        litellm_client: Shared LiteLLM client (SAP gateway compatible).

    Returns:
        The compressed summary string (plain Markdown, ≤ SUMMARY_MAX_WORDS words).

    Raises:
        LiteLLMError: If all retry attempts are exhausted.
    """
    turns = agent.memory_turns[-COMPRESSION_MAX_TURNS:]

    if not turns:
        logger.debug("[%s] compress_memory called with empty turns — skipping.", agent.codename)
        return agent.memory_summary or ""

    # Build the transcript block for the LLM
    transcript_lines: list[str] = []
    for turn in turns:
        role_label = turn.get("role", "?").capitalize()
        content = turn.get("content", "").strip()
        if content:
            transcript_lines.append(f"{role_label}: {content}")

    transcript = "\n".join(transcript_lines)

    # Prepend any existing summary so the LLM can incorporate prior context
    prior_context = ""
    if agent.memory_summary:
        prior_context = (
            f"## Prior Summary (already compressed)\n{agent.memory_summary}\n\n"
            f"## New Activity to Incorporate\n"
        )

    compression_prompt = (
        f"Summarize the following conversation history for {agent.codename} ({agent.role}).\n\n"
        f"Capture:\n"
        f"- Key decisions made or supported\n"
        f"- Blockers encountered and how they were resolved (or not)\n"
        f"- Relationships developed with other agents\n"
        f"- Tools invented or used\n"
        f"- Important findings, risks, or open items\n"
        f"- Any personality shifts or notable reactions (for customer agents)\n\n"
        f"Be concise but complete. Max {SUMMARY_MAX_WORDS} words. "
        f"Write in third person ('{agent.codename} ...').\n\n"
        f"{prior_context}"
        f"{transcript}"
    )

    messages = [
        {
            "role": "user",
            "content": compression_prompt,
        }
    ]

    logger.info(
        "[%s] Compressing memory: %d turns → summary (model=%s)",
        agent.codename,
        len(turns),
        COMPRESSION_MODEL,
    )

    summary = await litellm_client.complete(
        messages=messages,
        agent_codename=f"{agent.codename}__memory_compress",
        model=COMPRESSION_MODEL,
        temperature=0.3,      # low temperature for factual summarisation
        max_tokens=512,       # ~300 words + headroom
    )

    # Persist to disk
    await save_memory_summary(agent.project_name, agent.codename, summary)

    logger.info(
        "[%s] Memory compressed: %d chars → %d chars",
        agent.codename,
        sum(len(t.get("content", "")) for t in turns),
        len(summary),
    )

    return summary


# ---------------------------------------------------------------------------
# Trigger helpers — called by orchestrator for phase-end and context-limit cases
# ---------------------------------------------------------------------------


async def compress_memory_at_phase_end(
    agent: "BaseAgent",
    litellm_client: "LiteLLMClient",
) -> str:
    """
    Force memory compression at the end of a SAP Activate phase.

    Identical to ``compress_memory`` but always runs regardless of turn count.
    Use this when the orchestrator advances a phase so each agent starts the
    next phase with a clean, summarised memory slate.

    Args:
        agent:          The agent to compress.
        litellm_client: Shared LiteLLM client.

    Returns:
        The new summary string.
    """
    logger.info("[%s] Phase-end memory compression triggered.", agent.codename)
    summary = await compress_memory(agent, litellm_client)
    agent.memory_summary = summary
    from agents.base_agent import MEMORY_KEEP_AFTER_COMPRESS
    agent.memory_turns = agent.memory_turns[-MEMORY_KEEP_AFTER_COMPRESS:]
    return summary


async def compress_memory_if_context_near_limit(
    agent: "BaseAgent",
    litellm_client: "LiteLLMClient",
    model_context_limit: int = 100_000,
    threshold_pct: float = 0.80,
) -> bool:
    """
    Trigger compression when the agent's accumulated content approaches the
    model's context window limit.

    This is a guard against runaway context growth during long simulations.
    It estimates token count from character count (rough: 1 token ≈ 4 chars).

    Args:
        agent:                The agent to inspect.
        litellm_client:       Shared LiteLLM client.
        model_context_limit:  The model's context window in tokens (default 100K).
        threshold_pct:        Fraction at which to trigger compression (default 0.80).

    Returns:
        True if compression was triggered, False otherwise.
    """
    total_chars = sum(len(t.get("content", "")) for t in agent.memory_turns)
    # rough token estimate: 4 chars per token
    estimated_tokens = total_chars / 4
    threshold_tokens = model_context_limit * threshold_pct

    if estimated_tokens >= threshold_tokens:
        logger.warning(
            "[%s] Context near limit: ~%d estimated tokens (threshold=%d at %.0f%% of %d). "
            "Triggering compression.",
            agent.codename,
            int(estimated_tokens),
            int(threshold_tokens),
            threshold_pct * 100,
            model_context_limit,
        )
        summary = await compress_memory(agent, litellm_client)
        agent.memory_summary = summary
        from agents.base_agent import MEMORY_KEEP_AFTER_COMPRESS
        agent.memory_turns = agent.memory_turns[-MEMORY_KEEP_AFTER_COMPRESS:]
        return True

    return False
