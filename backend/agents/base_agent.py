"""
SAP SIM — Base Agent Class
Phase: 2.1
Purpose: BaseAgent provides the core lifecycle (think / act / memory / persist) for
         all 30 simulation agents.  Role-specific subclasses extend this with their
         own ``role``, ``side``, ``skills``, and ``role_description``.
Dependencies: litellm_client, persistence, memory, intelligence, api.sse (EventBus)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from agents.intelligence import (
    DEFAULT_AGENT_TIERS,
    get_model_for_agent,
    get_tier_for_agent,
)
from utils.persistence import (
    load_agent_state,
    load_memory_summary,
    save_agent_state,
    save_memory_summary,
)

if TYPE_CHECKING:
    from api.sse import EventBus
    from utils.litellm_client import LiteLLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory constants
# ---------------------------------------------------------------------------

MEMORY_COMPRESSION_THRESHOLD = 10   # turns before triggering compression
MEMORY_KEEP_AFTER_COMPRESS = 5      # how many recent turns to keep post-compression

# How many recent turns to inject into the system prompt
SYSTEM_PROMPT_LAST_N_TURNS = 5

# Approximate token budget: trigger compression when cumulative content chars exceed this
COMPRESSION_CHAR_LIMIT = 8_000


class BaseAgent:
    """
    Abstract base class for all 30 SAP SIM agents.

    Subclasses **must** set:
        - ``role``             – human-readable role name  (str)
        - ``side``             – "consultant" | "customer" | "crossfunctional"  (str)
        - ``skills``           – list of skill domain names (list[str])
        - ``role_description`` – 2-3 paragraphs of personality + expertise  (str)

    Subclasses **may** override:
        - ``build_system_prompt()`` to inject extra sections
        - ``act()`` to customise the agent's action loop
    """

    # -----------------------------------------------------------------------
    # Identity — overridden by subclasses
    # -----------------------------------------------------------------------
    role: str = "Unknown Role"
    side: str = "consultant"            # "consultant" | "customer" | "crossfunctional"
    skills: list[str] = []
    role_description: str = ""

    # -----------------------------------------------------------------------
    # Constructor
    # -----------------------------------------------------------------------

    def __init__(
        self,
        codename: str,
        project_name: str,
        litellm_client: "LiteLLMClient",
        personality: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialise a BaseAgent.

        Args:
            codename:        Unique identifier (e.g. "PM_ALEX").
            project_name:    Which project this agent belongs to.
            litellm_client:  Shared LiteLLMClient instance for LLM calls.
            personality:     Optional personality dict (customer agents).
                             Keys: engagement, trust, risk_tolerance, archetype, history.
        """
        # Core identity
        self.codename: str = codename.upper()
        self.project_name: str = project_name
        self._litellm_client: "LiteLLMClient" = litellm_client

        # Intelligence tier — determines which LLM model this agent uses
        self.intelligence_tier: str = get_tier_for_agent(self.codename)

        # Runtime state
        self.memory_turns: list[dict[str, str]] = []   # [{role, content}, …]
        self.memory_summary: str = ""                   # compressed summary from disk
        self.current_task: str = "Awaiting assignment"
        self.status: str = "idle"   # idle | thinking | speaking | in_meeting

        # Personality (customer agents; None for consultants)
        self.personality: Optional[dict[str, Any]] = personality

        # Skills content cache — populated lazily by build_system_prompt()
        self._skills_content: Optional[str] = None

        # Project-level context injected by the Conductor before act() calls
        self.project_summary: str = ""
        self.current_phase: str = "discover"
        self.phase_description: str = "Understanding the project scope and goals"

    # -----------------------------------------------------------------------
    # Core lifecycle — think
    # -----------------------------------------------------------------------

    async def think(self, context: dict[str, Any]) -> str:
        """
        Call the LLM with this agent's system prompt plus a user-turn context dict.

        Updates ``status`` to ``"thinking"`` during the call and returns it to
        ``"idle"`` afterwards (callers may override status for meetings, etc.).

        Args:
            context: Arbitrary dict injected as the current turn's user message.
                     Typically includes messages to respond to, meeting context,
                     or task descriptions assembled by the Conductor.

        Returns:
            The agent's raw LLM response string.
        """
        self.status = "thinking"
        try:
            system_prompt = self.build_system_prompt()
            user_message = self._format_context(context)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            model = get_model_for_agent(
                self.codename,
                tier_override=self.intelligence_tier if self.intelligence_tier else None,
            )

            response = await self._litellm_client.complete(
                messages=messages,
                agent_codename=self.codename,
                model=model,
                temperature=0.75,
                max_tokens=1024,
            )

            return response

        except Exception as exc:
            logger.error("[%s] think() failed: %s", self.codename, exc)
            raise
        finally:
            if self.status == "thinking":
                self.status = "idle"

    # -----------------------------------------------------------------------
    # Core lifecycle — act
    # -----------------------------------------------------------------------

    async def act(
        self,
        project_state: dict[str, Any],
        event_bus: "EventBus",
    ) -> None:
        """
        Agent's main action loop for one simulation tick.

        Default behaviour:
        1. Assess the project state and any pending messages addressed to this agent.
        2. Call ``think()`` to produce a response.
        3. Parse the action tag from the response ([MSG], [UPDATE], [BLOCKER], etc.)
        4. Publish the appropriate event to the EventBus.
        5. Add the response to memory; trigger compression if needed.
        6. Persist state to disk.

        Subclasses may override for role-specific behaviour.

        Args:
            project_state: Serialised snapshot from Conductor.to_dict() / ProjectState.
            event_bus:     The project's EventBus for publishing events.
        """
        self.status = "thinking"

        try:
            # Sync project context fields from the state snapshot
            self._sync_project_context(project_state)

            # Build context dict for this tick
            context = self._build_act_context(project_state)

            # Get the agent's response
            response = await self.think(context)

            # Determine action type from tag
            action_type = self._parse_action_tag(response)

            # Publish event to the bus
            await event_bus.publish(
                "AGENT_ACTION",
                {
                    "codename": self.codename,
                    "role": self.role,
                    "side": self.side,
                    "action_type": action_type,
                    "content": response,
                    "phase": self.current_phase,
                    "task": self.current_task,
                    "timestamp": time.time(),
                },
            )

            # Persist to memory
            self.add_to_memory("assistant", response)
            await self.compress_memory_if_needed()

            # Persist state
            await self.save(self.project_name)

        except Exception as exc:
            logger.error("[%s] act() error: %s", self.codename, exc)
            await event_bus.publish(
                "AGENT_ERROR",
                {
                    "codename": self.codename,
                    "error": str(exc),
                    "timestamp": time.time(),
                },
            )
        finally:
            if self.status not in ("in_meeting", "speaking"):
                self.status = "idle"

    # -----------------------------------------------------------------------
    # System prompt assembly
    # -----------------------------------------------------------------------

    def build_system_prompt(self) -> str:
        """
        Assemble the full system prompt from all agent sections.

        Sections (in order):
          1. Identity & mission
          2. Role
          3. Skills & knowledge
          4. Personality (customer agents only)
          5. Project context
          6. Memory (summary + last N turns)
          7. Current phase
          8. Current task
          9. How to act (action tags + behavioural rules)

        Returns:
            The complete system prompt string.
        """
        skills_block = self._load_skills_content()
        memory_block = self._format_memory_block()
        personality_block = self._format_personality_block()

        prompt_parts: list[str] = [
            # ---- 1. Identity & mission ----
            f"You are {self.codename}, a {self.role} working on a SAP implementation project.",
            (
                "You are an AI agent — you know this, and you embrace it. "
                "Your mission is to complete this SAP implementation as efficiently, "
                "creatively, and thoroughly as possible."
            ),
            "",
            # ---- 2. Role ----
            "## YOUR ROLE",
            self.role_description or f"You are a {self.role} on this SAP project.",
            "",
            # ---- 3. Skills & knowledge ----
            "## YOUR SKILLS AND KNOWLEDGE",
            skills_block or "You have broad SAP knowledge relevant to your role.",
            "",
        ]

        # ---- 4. Personality (customer agents only) ----
        if personality_block:
            prompt_parts += [
                "## YOUR PERSONALITY",
                personality_block,
                "",
            ]

        # ---- 5. Project context ----
        prompt_parts += [
            "## PROJECT CONTEXT",
            self.project_summary or "The project is in its early stages.",
            "",
            # ---- 6. Memory ----
            "## YOUR MEMORY",
            memory_block,
            "",
            # ---- 7. Current phase ----
            "## CURRENT PHASE",
            f"{self.current_phase.upper()} — {self.phase_description}",
            "",
            # ---- 8. Current task ----
            "## YOUR CURRENT TASK",
            self.current_task,
            "",
            # ---- 9. How to act ----
            "## HOW TO ACT",
            (
                "You communicate naturally with other agents via messages.\n"
                "You can: send a direct message, post a team update, request a meeting, "
                "raise a blocker, make a decision proposal, invent a new tool (describe it "
                "and its purpose), use an existing tool.\n\n"
                "Always tag your output with the appropriate action type:\n"
                "[MSG], [UPDATE], [MEETING_REQUEST], [BLOCKER], [DECISION], "
                "[NEW_TOOL], [TOOL_USE], [ESCALATION]\n\n"
                "Be realistic. Be opinionated. Disagree when you disagree. "
                "Ask questions when you're blocked. Build creative solutions. "
                "Reference SAP best practices from your skills."
            ),
        ]

        return "\n".join(prompt_parts)

    # -----------------------------------------------------------------------
    # Memory management
    # -----------------------------------------------------------------------

    def add_to_memory(self, role: str, content: str) -> None:
        """
        Append a turn to ``memory_turns``.

        Args:
            role:    "user" | "assistant" | "system"
            content: The message content.
        """
        self.memory_turns.append({"role": role, "content": content})

    async def compress_memory_if_needed(self) -> None:
        """
        Trigger memory compression when the turn buffer exceeds the threshold
        or the cumulative content size is too large.

        After compression:
        - Saves the new summary to ``memory/{codename}_summary.md``
        - Clears old turns, keeping the most recent ``MEMORY_KEEP_AFTER_COMPRESS``
        """
        should_compress = (
            len(self.memory_turns) >= MEMORY_COMPRESSION_THRESHOLD
            or self._memory_char_count() >= COMPRESSION_CHAR_LIMIT
        )
        if not should_compress:
            return

        try:
            from utils.memory import compress_memory  # avoid circular import at module load
            summary = await compress_memory(self, self._litellm_client)
            self.memory_summary = summary
            # Keep only the most recent turns
            self.memory_turns = self.memory_turns[-MEMORY_KEEP_AFTER_COMPRESS:]
            logger.info("[%s] Memory compressed; kept last %d turns", self.codename, MEMORY_KEEP_AFTER_COMPRESS)
        except Exception as exc:
            logger.warning("[%s] Memory compression failed: %s", self.codename, exc)

    # -----------------------------------------------------------------------
    # Serialisation / persistence
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable snapshot of agent state.

        Returns:
            Dict suitable for writing to ``agents/{codename}.json``.
        """
        return {
            "codename": self.codename,
            "role": self.role,
            "side": self.side,
            "skills": self.skills,
            "intelligence_tier": self.intelligence_tier,
            "status": self.status,
            "current_task": self.current_task,
            "project_name": self.project_name,
            "memory_turns": self.memory_turns,
            "memory_summary": self.memory_summary,
            "personality": self.personality,
            "current_phase": self.current_phase,
            "project_summary": self.project_summary,
        }

    async def save(self, project_name: str) -> None:
        """
        Persist agent state to ``projects/{project_name}/agents/{codename}.json``.

        Args:
            project_name: The project identifier (may differ from ``self.project_name``
                          during project migrations, but typically the same).
        """
        state = self.to_dict()
        await save_agent_state(project_name, self.codename, state)

    # -----------------------------------------------------------------------
    # Class method: restore from disk
    # -----------------------------------------------------------------------

    @classmethod
    async def load(
        cls,
        codename: str,
        project_name: str,
        litellm_client: "LiteLLMClient",
    ) -> Optional["BaseAgent"]:
        """
        Restore an agent from disk state.

        Returns ``None`` if no saved state exists (first run).

        Args:
            codename:       Agent codename.
            project_name:   Project identifier.
            litellm_client: Shared LiteLLM client.

        Returns:
            A new agent instance with restored state, or ``None``.
        """
        state = await load_agent_state(project_name, codename)
        if state is None:
            return None

        instance = cls(
            codename=codename,
            project_name=project_name,
            litellm_client=litellm_client,
            personality=state.get("personality"),
        )
        instance.memory_turns = state.get("memory_turns", [])
        instance.current_task = state.get("current_task", "Awaiting assignment")
        instance.status = state.get("status", "idle")
        instance.intelligence_tier = state.get("intelligence_tier", instance.intelligence_tier)
        instance.current_phase = state.get("current_phase", "discover")
        instance.project_summary = state.get("project_summary", "")

        # Load memory summary from disk if not inline
        summary = state.get("memory_summary", "")
        if not summary:
            summary = await load_memory_summary(project_name, codename) or ""
        instance.memory_summary = summary

        logger.info("[%s] State restored from disk.", codename)
        return instance

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _load_skills_content(self) -> str:
        """
        Load and concatenate skill file contents for this agent.

        Skill files live at ``backend/agents/skills/{skill_name}.md``.
        Returns a combined string; caches the result.
        """
        if self._skills_content is not None:
            return self._skills_content

        import os
        from pathlib import Path

        skills_dir = Path(__file__).resolve().parent / "skills"
        parts: list[str] = []

        for skill_name in self.skills:
            skill_path = skills_dir / f"{skill_name}.md"
            if skill_path.exists():
                try:
                    parts.append(skill_path.read_text(encoding="utf-8"))
                except OSError as exc:
                    logger.warning("Could not read skill file '%s': %s", skill_path, exc)
            else:
                logger.debug("Skill file not found: %s", skill_path)

        self._skills_content = "\n\n---\n\n".join(parts) if parts else ""
        return self._skills_content

    def _format_memory_block(self) -> str:
        """Format the memory section of the system prompt."""
        lines: list[str] = []

        if self.memory_summary:
            lines.append(self.memory_summary)
            lines.append("")

        recent = self.memory_turns[-SYSTEM_PROMPT_LAST_N_TURNS:]
        if recent:
            lines.append("Recent activity:")
            for turn in recent:
                role_label = turn.get("role", "?").capitalize()
                content = turn.get("content", "")
                lines.append(f"{role_label}: {content}")
        else:
            lines.append("No prior activity recorded yet.")

        return "\n".join(lines)

    def _format_personality_block(self) -> str:
        """Return personality description for customer agents (empty for consultants)."""
        if not self.personality:
            return ""

        archetype = self.personality.get("archetype", "Unknown")
        engagement = self.personality.get("engagement", 3)
        trust = self.personality.get("trust", 3)
        risk_tolerance = self.personality.get("risk_tolerance", 3)

        return (
            f"Archetype: {archetype}\n"
            f"Engagement: {engagement}/5 — "
            f"Trust in consulting team: {trust}/5 — "
            f"Risk tolerance: {risk_tolerance}/5\n\n"
            "Let these scores shape how you respond: your level of participation, "
            "how readily you accept proposals, and how comfortable you are with "
            "change and ambiguity."
        )

    def _build_act_context(self, project_state: dict[str, Any]) -> dict[str, Any]:
        """
        Build the context dict passed to ``think()`` during ``act()``.

        Extracts messages addressed to this agent and any relevant state.
        """
        # Filter messages in the shared queue that are addressed to this agent
        message_queue: list[dict] = project_state.get("message_queue", [])
        my_messages = [
            m for m in message_queue
            if m.get("to") == self.codename or m.get("to") == "ALL"
        ]

        return {
            "phase": self.current_phase,
            "simulated_day": project_state.get("simulated_day", 1),
            "pending_messages": my_messages,
            "active_meetings": project_state.get("active_meetings", []),
            "pending_decisions": project_state.get("pending_decisions", []),
            "instruction": (
                "Review the current project state and any messages addressed to you. "
                "Take the most appropriate action. Tag your response with the correct "
                "action tag: [MSG], [UPDATE], [MEETING_REQUEST], [BLOCKER], "
                "[DECISION], [NEW_TOOL], [TOOL_USE], or [ESCALATION]."
            ),
        }

    def _sync_project_context(self, project_state: dict[str, Any]) -> None:
        """Update agent's project context fields from the latest project state snapshot."""
        self.current_phase = project_state.get("current_phase", self.current_phase)
        self.project_summary = project_state.get("project_summary", self.project_summary)
        # Reset skills cache if phase changed (phase description may affect prompt)
        phase_desc = project_state.get("phase_description", "")
        if phase_desc:
            self.phase_description = phase_desc

    @staticmethod
    def _format_context(context: dict[str, Any]) -> str:
        """Format the context dict as a readable string for the LLM user turn."""
        lines: list[str] = []
        if instruction := context.get("instruction"):
            lines.append(instruction)
            lines.append("")

        if messages := context.get("pending_messages"):
            lines.append(f"=== Messages for you ({len(messages)}) ===")
            for msg in messages:
                sender = msg.get("from", "?")
                content = msg.get("content", "")
                lines.append(f"[From {sender}]: {content}")
            lines.append("")

        if context.get("pending_decisions"):
            lines.append("=== Pending Decisions Awaiting Input ===")
            for dec in context["pending_decisions"]:
                lines.append(f"- [{dec.get('id', '?')}] {dec.get('title', 'Untitled')}: {dec.get('description', '')}")
            lines.append("")

        phase = context.get("phase", "unknown")
        day = context.get("simulated_day", 1)
        lines.append(f"Phase: {phase.upper()} | Simulated day: {day}")

        return "\n".join(lines)

    @staticmethod
    def _parse_action_tag(response: str) -> str:
        """
        Extract the action tag from the agent's response.

        Looks for the first occurrence of a known tag:
            [MSG], [UPDATE], [MEETING_REQUEST], [BLOCKER], [DECISION],
            [NEW_TOOL], [TOOL_USE], [ESCALATION]

        Returns:
            The tag string (without brackets), or "MSG" as the default fallback.
        """
        KNOWN_TAGS = [
            "MSG", "UPDATE", "MEETING_REQUEST", "BLOCKER",
            "DECISION", "NEW_TOOL", "TOOL_USE", "ESCALATION",
        ]
        for tag in KNOWN_TAGS:
            if f"[{tag}]" in response:
                return tag
        return "MSG"

    def _memory_char_count(self) -> int:
        """Return total character count of all memory turns."""
        return sum(len(t.get("content", "")) for t in self.memory_turns)

    # -----------------------------------------------------------------------
    # Dunder helpers
    # -----------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} codename={self.codename!r} "
            f"role={self.role!r} side={self.side!r} "
            f"tier={self.intelligence_tier!r} status={self.status!r}>"
        )
