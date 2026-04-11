"""
SAP SIM — Meeting Logger Artifact
Phase: 4.1
Purpose: Provides MeetingLog dataclass and MeetingLogger class for capturing,
         storing, and rendering simulation meeting transcripts as structured
         data and formatted Markdown documents.

Usage:
    logger = MeetingLogger()

    log = logger.start_log(MeetingLog(
        meeting_id="kickoff-day1",
        title="Project Kickoff",
        meeting_type="kickoff",
        phase="Prepare",
        participants=["Alex", "Sara", "Leila"],
        agenda_items=["Introductions", "Project scope", "Next steps"],
        simulated_day=1,
    ))

    logger.add_turn("kickoff-day1", "Alex", "Welcome everyone to the kickoff!")
    logger.add_decision("kickoff-day1", "Use S/4HANA 2023 FPS02 as target release.")
    logger.add_action_item("kickoff-day1", {"owner": "Sara", "task": "Draft architecture blueprint", "due_day": 5})
    log = logger.finalize_log("kickoff-day1")

    logger.save_as_markdown(log, "/tmp/kickoff-day1.md")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TranscriptTurn:
    """A single spoken turn in a meeting transcript."""

    speaker: str
    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class MeetingLog:
    """
    Complete record of a simulated SAP project meeting.

    Required fields must be supplied when calling :meth:`MeetingLogger.start_log`.
    The mutable list/dict fields are populated progressively via add_* methods
    and are finalised by :meth:`MeetingLogger.finalize_log`.
    """

    # --- Identity / metadata ---
    meeting_id: str
    title: str
    meeting_type: str           # e.g. "kickoff", "blueprint", "steering", "ad_hoc"
    phase: str                  # SAP ACTIVATE phase: Discover / Prepare / Explore / Realize / Deploy / Run
    participants: list[str]
    agenda_items: list[str]
    simulated_day: int

    # --- Progressive fields ---
    transcript: list[TranscriptTurn] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    action_items: list[dict[str, Any]] = field(default_factory=list)

    # --- Finalisation fields ---
    duration_minutes: Optional[float] = None
    started_at: Optional[float] = None    # Unix timestamp (wall clock)
    ended_at: Optional[float] = None      # Unix timestamp (wall clock)
    is_finalised: bool = False


# ---------------------------------------------------------------------------
# MeetingLogger
# ---------------------------------------------------------------------------


class MeetingLogger:
    """
    Lifecycle manager for :class:`MeetingLog` objects.

    Thread-safety: not thread-safe; wrap in a lock if concurrent access is needed.
    """

    def __init__(self) -> None:
        self._active: dict[str, MeetingLog] = {}    # meeting_id → in-progress log
        self._archive: dict[str, MeetingLog] = {}   # meeting_id → finalised log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_log(self, meeting: MeetingLog) -> MeetingLog:
        """
        Register *meeting* as active and record its wall-clock start time.

        Returns the same :class:`MeetingLog` for chaining convenience.
        Raises :exc:`ValueError` if a meeting with the same ID is already active.
        """
        if meeting.meeting_id in self._active:
            raise ValueError(
                f"Meeting '{meeting.meeting_id}' is already active. "
                "Finalise or close it before starting a new one with the same ID."
            )
        meeting.started_at = time.time()
        meeting.is_finalised = False
        self._active[meeting.meeting_id] = meeting
        logger.debug("MeetingLogger: started '%s' (%s)", meeting.meeting_id, meeting.title)
        return meeting

    def add_turn(self, meeting_id: str, speaker: str, text: str) -> TranscriptTurn:
        """
        Append a spoken turn to the transcript of *meeting_id*.

        Returns the created :class:`TranscriptTurn`.
        """
        log = self._get_active(meeting_id)
        turn = TranscriptTurn(speaker=speaker, text=text.strip())
        log.transcript.append(turn)
        return turn

    def add_decision(self, meeting_id: str, decision: str) -> None:
        """Record a decision reached during *meeting_id*."""
        log = self._get_active(meeting_id)
        log.decisions_made.append(decision.strip())

    def add_action_item(self, meeting_id: str, item: dict[str, Any]) -> None:
        """
        Record an action item for *meeting_id*.

        Recommended keys: ``owner`` (str), ``task`` (str), ``due_day`` (int).
        Any extra keys are preserved verbatim.
        """
        log = self._get_active(meeting_id)
        log.action_items.append(dict(item))   # store a copy

    def finalize_log(self, meeting_id: str) -> MeetingLog:
        """
        Mark *meeting_id* as finalised, compute duration, and move it to the archive.

        Returns the finalised :class:`MeetingLog`.
        Raises :exc:`ValueError` if meeting_id is not active.
        """
        log = self._get_active(meeting_id)
        log.ended_at = time.time()
        if log.started_at is not None:
            log.duration_minutes = (log.ended_at - log.started_at) / 60.0
        log.is_finalised = True
        self._archive[meeting_id] = log
        del self._active[meeting_id]
        logger.debug(
            "MeetingLogger: finalised '%s' — %d turns, %d decisions, %d actions",
            meeting_id,
            len(log.transcript),
            len(log.decisions_made),
            len(log.action_items),
        )
        return log

    def get_log(self, meeting_id: str) -> Optional[MeetingLog]:
        """Return a log whether active or archived; ``None`` if not found."""
        return self._active.get(meeting_id) or self._archive.get(meeting_id)

    def list_active(self) -> list[str]:
        """Return IDs of currently active (non-finalised) meetings."""
        return list(self._active.keys())

    def list_archived(self) -> list[str]:
        """Return IDs of finalised meetings."""
        return list(self._archive.keys())

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------

    def save_as_markdown(self, log: MeetingLog, path: str | Path) -> Path:
        """
        Write *log* to *path* as a formatted Markdown document.

        Creates parent directories if they do not exist.
        Returns the resolved :class:`~pathlib.Path` that was written.
        """
        dest = Path(path).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self._render_markdown(log), encoding="utf-8")
        logger.info("MeetingLogger: saved markdown → %s", dest)
        return dest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active(self, meeting_id: str) -> MeetingLog:
        """Return active log or raise :exc:`ValueError`."""
        log = self._active.get(meeting_id)
        if log is None:
            if meeting_id in self._archive:
                raise ValueError(
                    f"Meeting '{meeting_id}' has already been finalised."
                )
            raise ValueError(
                f"No active meeting found with ID '{meeting_id}'. "
                "Did you call start_log() first?"
            )
        return log

    @staticmethod
    def _render_markdown(log: MeetingLog) -> str:
        """Render a :class:`MeetingLog` as a Markdown string."""
        lines: list[str] = []

        # ── Title block ──────────────────────────────────────────────
        lines.append(f"# {log.title}")
        lines.append("")
        lines.append(f"**Meeting ID:** `{log.meeting_id}`  ")
        lines.append(f"**Type:** {log.meeting_type.replace('_', ' ').title()}  ")
        lines.append(f"**Phase:** {log.phase}  ")
        lines.append(f"**Simulated Day:** {log.simulated_day}  ")
        if log.duration_minutes is not None:
            lines.append(f"**Duration:** {log.duration_minutes:.1f} minutes  ")
        if log.started_at is not None:
            import datetime
            started_str = datetime.datetime.utcfromtimestamp(log.started_at).strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f"**Recorded:** {started_str}  ")
        lines.append("")

        # ── Participants ──────────────────────────────────────────────
        lines.append("## 👥 Participants")
        lines.append("")
        for p in log.participants:
            lines.append(f"- {p}")
        lines.append("")

        # ── Agenda ───────────────────────────────────────────────────
        lines.append("## 📋 Agenda")
        lines.append("")
        for i, item in enumerate(log.agenda_items, start=1):
            lines.append(f"{i}. {item}")
        lines.append("")

        # ── Transcript ───────────────────────────────────────────────
        lines.append("## 💬 Transcript")
        lines.append("")
        if log.transcript:
            for turn in log.transcript:
                lines.append(f"**{turn.speaker}:**")
                lines.append(f"> {turn.text}")
                lines.append("")
        else:
            lines.append("_No transcript recorded._")
            lines.append("")

        # ── Decisions ────────────────────────────────────────────────
        lines.append("## ✅ Decisions Made")
        lines.append("")
        if log.decisions_made:
            for decision in log.decisions_made:
                lines.append(f"- {decision}")
        else:
            lines.append("_No formal decisions recorded._")
        lines.append("")

        # ── Action Items ─────────────────────────────────────────────
        lines.append("## 🎯 Action Items")
        lines.append("")
        if log.action_items:
            lines.append("| # | Task | Owner | Due (Day) | Notes |")
            lines.append("|---|------|-------|-----------|-------|")
            for i, item in enumerate(log.action_items, start=1):
                task = item.get("task", "—")
                owner = item.get("owner", "—")
                due = item.get("due_day", "—")
                notes = item.get("notes", "")
                lines.append(f"| {i} | {task} | {owner} | {due} | {notes} |")
        else:
            lines.append("_No action items recorded._")
        lines.append("")

        # ── Footer ───────────────────────────────────────────────────
        status = "✅ Finalised" if log.is_finalised else "⏳ In Progress"
        lines.append("---")
        lines.append("")
        lines.append(f"*Status: {status} · Generated by SAP SIM Meeting Logger*")
        lines.append("")

        return "\n".join(lines)
