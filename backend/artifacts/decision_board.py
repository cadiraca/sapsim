"""
SAP SIM — Decision Board Artifact
Phase: 4.2
Purpose: Provides the Decision dataclass and DecisionBoard class for tracking,
         voting on, and resolving project decisions throughout a SAP simulation.

Decisions move through the following lifecycle:
    proposed → discussed → approved | rejected | deferred

Voting uses a simple majority model: once the approval threshold is reached
(default 70 % of cast votes), ``auto_resolve`` will flip the status to
``approved``; if the rejection threshold is reached, it becomes ``rejected``.

Persistence: decisions are stored in
    projects/<project_name>/decisions.json

Usage::

    board = DecisionBoard(project_name="my-sap-project")

    d = board.propose_decision(Decision(
        title="Adopt S/4HANA Cloud Public Edition",
        description="Move from ECC to S/4HANA Cloud PE for Finance scope.",
        category="technical",
        proposed_by="Alex",
        proposed_at_day=3,
    ))

    board.vote(d.id, agent_id="Sara",  vote="approve",
               reasoning="Fits our cloud-first strategy.")
    board.vote(d.id, agent_id="Leila", vote="approve",
               reasoning="Lower TCO long-term.")
    board.vote(d.id, agent_id="Omar",  vote="reject",
               reasoning="Change management risk too high.")

    resolved = board.auto_resolve(d.id)  # returns Decision if resolved
    board.save()
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

DecisionCategory = Literal["technical", "functional", "organizational", "budget"]
DecisionStatus   = Literal["proposed", "discussed", "approved", "rejected", "deferred"]
VoteValue        = Literal["approve", "reject", "abstain"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    """
    A single project decision captured on the Decision Board.

    Required fields must be set at construction time; all others have sensible
    defaults and are populated progressively by :class:`DecisionBoard` methods.
    """

    # --- Core identity ---
    title: str
    description: str
    category: DecisionCategory
    proposed_by: str
    proposed_at_day: int

    # --- Auto-generated ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # --- Lifecycle ---
    status: DecisionStatus = "proposed"

    # --- Voting ---
    # Structure: { agent_id: {"vote": VoteValue, "reasoning": str} }
    votes: dict[str, dict[str, str]] = field(default_factory=dict)

    # --- Rationale / impact ---
    rationale: str = ""
    impact_assessment: str = ""

    # --- Cross-references ---
    related_meeting_id: Optional[str] = None
    resolved_at_day: Optional[int] = None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def approve_count(self) -> int:
        return sum(1 for v in self.votes.values() if v["vote"] == "approve")

    @property
    def reject_count(self) -> int:
        return sum(1 for v in self.votes.values() if v["vote"] == "reject")

    @property
    def abstain_count(self) -> int:
        return sum(1 for v in self.votes.values() if v["vote"] == "abstain")

    @property
    def active_votes(self) -> int:
        """Total votes excluding abstentions."""
        return self.approve_count + self.reject_count

    def vote_summary(self) -> str:
        """Human-readable one-liner: e.g. '3 approve / 1 reject / 1 abstain'."""
        return (
            f"{self.approve_count} approve / "
            f"{self.reject_count} reject / "
            f"{self.abstain_count} abstain"
        )

    # ------------------------------------------------------------------
    # Serialisation helpers (used by DecisionBoard internally)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# DecisionBoard
# ---------------------------------------------------------------------------


class DecisionBoard:
    """
    Central store for all project decisions in a SAP simulation run.

    Parameters
    ----------
    project_name:
        Used to build the persistence path
        ``projects/<project_name>/decisions.json``.
    projects_root:
        Base directory that contains project sub-directories.
        Defaults to ``projects/`` relative to the current working directory.
    consensus_threshold:
        Fraction of *active* (non-abstain) votes that must be ``approve``
        for :meth:`auto_resolve` to mark a decision ``approved``.
        Defaults to ``0.70`` (70 %).

    Thread-safety: not thread-safe; wrap in a lock for concurrent access.
    """

    def __init__(
        self,
        project_name: str,
        projects_root: str | Path = "projects",
        consensus_threshold: float = 0.70,
    ) -> None:
        self.project_name = project_name
        self.projects_root = Path(projects_root).expanduser().resolve()
        self.consensus_threshold = consensus_threshold

        # In-memory store: decision_id → Decision
        self._decisions: dict[str, Decision] = {}

        # Load from disk if a save file already exists
        if self._persistence_path.exists():
            self.load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @property
    def _persistence_path(self) -> Path:
        return self.projects_root / self.project_name / "decisions.json"

    def save(self) -> Path:
        """
        Persist all decisions to ``projects/<project_name>/decisions.json``.

        Creates parent directories if necessary.
        Returns the resolved path that was written.
        """
        dest = self._persistence_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project": self.project_name,
            "consensus_threshold": self.consensus_threshold,
            "decisions": [d.to_dict() for d in self._decisions.values()],
        }
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("DecisionBoard: saved %d decision(s) → %s", len(self._decisions), dest)
        return dest

    def load(self) -> None:
        """
        Load decisions from ``projects/<project_name>/decisions.json``.

        Silently returns if the file does not exist.
        Raises :exc:`ValueError` on malformed JSON.
        """
        src = self._persistence_path
        if not src.exists():
            logger.debug("DecisionBoard: no save file at %s — starting fresh", src)
            return
        try:
            raw = json.loads(src.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed decisions.json at {src}: {exc}") from exc

        # Optionally restore threshold from file
        if "consensus_threshold" in raw:
            self.consensus_threshold = float(raw["consensus_threshold"])

        self._decisions = {}
        for item in raw.get("decisions", []):
            try:
                d = Decision.from_dict(item)
                self._decisions[d.id] = d
            except (TypeError, KeyError) as exc:
                logger.warning("DecisionBoard: skipping malformed decision entry: %s", exc)

        logger.info(
            "DecisionBoard: loaded %d decision(s) from %s", len(self._decisions), src
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def propose_decision(self, decision: Decision) -> Decision:
        """
        Register *decision* on the board (status = ``proposed``).

        Returns the same :class:`Decision` for chaining.
        Raises :exc:`ValueError` if a decision with the same ID already exists.
        """
        if decision.id in self._decisions:
            raise ValueError(
                f"Decision '{decision.id}' already exists on the board. "
                "Use a new Decision instance or supply a unique id."
            )
        decision.status = "proposed"
        self._decisions[decision.id] = decision
        logger.debug(
            "DecisionBoard: proposed '%s' (id=%s, category=%s)",
            decision.title,
            decision.id,
            decision.category,
        )
        return decision

    def vote(
        self,
        decision_id: str,
        agent_id: str,
        vote: VoteValue,
        reasoning: str = "",
    ) -> Decision:
        """
        Cast (or update) a vote on *decision_id* for *agent_id*.

        Parameters
        ----------
        decision_id: ID of the target decision.
        agent_id:    Identifier of the voting agent.
        vote:        One of ``"approve"``, ``"reject"``, ``"abstain"``.
        reasoning:   Optional free-text rationale for the vote.

        Returns the updated :class:`Decision`.
        Raises :exc:`ValueError` if *decision_id* is unknown or already resolved.
        """
        d = self._get_decision(decision_id)
        if d.status in ("approved", "rejected"):
            raise ValueError(
                f"Decision '{decision_id}' is already {d.status}. Voting is closed."
            )

        valid_votes: set[str] = {"approve", "reject", "abstain"}
        if vote not in valid_votes:
            raise ValueError(
                f"Invalid vote value '{vote}'. Must be one of {valid_votes}."
            )

        is_update = agent_id in d.votes
        d.votes[agent_id] = {"vote": vote, "reasoning": reasoning.strip()}

        # Bump status to "discussed" once at least one vote is cast
        if d.status == "proposed":
            d.status = "discussed"

        action = "updated" if is_update else "cast"
        logger.debug(
            "DecisionBoard: vote %s — decision='%s', agent='%s', vote='%s'",
            action,
            d.title,
            agent_id,
            vote,
        )
        return d

    def mark_discussed(self, decision_id: str) -> Decision:
        """
        Manually advance a decision to ``discussed`` without casting a vote.

        Useful when a facilitator records that the topic was covered in a meeting
        but no formal votes were cast yet.
        """
        d = self._get_decision(decision_id)
        if d.status == "proposed":
            d.status = "discussed"
        return d

    def defer_decision(self, decision_id: str, resolved_at_day: Optional[int] = None) -> Decision:
        """Mark *decision_id* as deferred (put on hold for a later day)."""
        d = self._get_decision(decision_id)
        d.status = "deferred"
        if resolved_at_day is not None:
            d.resolved_at_day = resolved_at_day
        logger.debug("DecisionBoard: deferred decision '%s'", decision_id)
        return d

    def auto_resolve(
        self,
        decision_id: str,
        current_day: Optional[int] = None,
    ) -> Optional[Decision]:
        """
        Check whether *decision_id* has reached consensus and resolve it if so.

        Resolution rules
        ----------------
        - If ``approve_votes / active_votes >= consensus_threshold``
          → status becomes ``approved``.
        - If ``reject_votes / active_votes >= consensus_threshold``
          → status becomes ``rejected``.
        - Otherwise the decision remains unresolved and ``None`` is returned.

        *current_day* is recorded as ``resolved_at_day`` when provided.
        Returns the resolved :class:`Decision`, or ``None`` if not yet resolved.
        """
        d = self._get_decision(decision_id)

        if d.status in ("approved", "rejected"):
            logger.debug(
                "DecisionBoard: auto_resolve called on already-%s decision '%s'",
                d.status,
                decision_id,
            )
            return d

        active = d.active_votes
        if active == 0:
            logger.debug(
                "DecisionBoard: auto_resolve — no active votes on '%s'", decision_id
            )
            return None

        approve_ratio = d.approve_count / active
        reject_ratio  = d.reject_count  / active

        if approve_ratio >= self.consensus_threshold:
            d.status = "approved"
            d.resolved_at_day = current_day
            logger.info(
                "DecisionBoard: APPROVED '%s' (%.0f%% approve, threshold %.0f%%)",
                d.title,
                approve_ratio * 100,
                self.consensus_threshold * 100,
            )
            return d

        # Rejection: symmetric — requires the same threshold of reject votes
        # (e.g. 70 % reject needed to auto-reject when threshold is 70 %)
        if reject_ratio >= self.consensus_threshold:
            d.status = "rejected"
            d.resolved_at_day = current_day
            logger.info(
                "DecisionBoard: REJECTED '%s' (%.0f%% reject, threshold %.0f%%)",
                d.title,
                reject_ratio * 100,
                self.consensus_threshold * 100,
            )
            return d

        logger.debug(
            "DecisionBoard: auto_resolve — no consensus yet on '%s' (%s)",
            d.title,
            d.vote_summary(),
        )
        return None

    # ------------------------------------------------------------------
    # Query / filter API
    # ------------------------------------------------------------------

    def get_board(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[Decision]:
        """
        Return decisions matching *filters*.

        Supported filter keys
        ~~~~~~~~~~~~~~~~~~~~~
        ``status`` : str or list[str]
            e.g. ``"proposed"`` or ``["proposed", "discussed"]``
        ``category`` : str or list[str]
            e.g. ``"technical"``
        ``proposed_by`` : str
            Agent ID of the proposer.
        ``related_meeting_id`` : str
            Limit to decisions from a specific meeting.
        ``resolved_at_day_lte`` : int
            Decisions resolved on or before this simulated day.
        ``proposed_at_day_gte`` : int
            Decisions proposed on or after this simulated day.

        If *filters* is ``None`` or ``{}``, all decisions are returned in
        proposal order (by ``proposed_at_day``, then ``id``).
        """
        results = list(self._decisions.values())

        if not filters:
            return self._sort(results)

        # status filter
        if "status" in filters:
            allowed = (
                {filters["status"]}
                if isinstance(filters["status"], str)
                else set(filters["status"])
            )
            results = [d for d in results if d.status in allowed]

        # category filter
        if "category" in filters:
            allowed = (
                {filters["category"]}
                if isinstance(filters["category"], str)
                else set(filters["category"])
            )
            results = [d for d in results if d.category in allowed]

        # proposed_by filter
        if "proposed_by" in filters:
            results = [d for d in results if d.proposed_by == filters["proposed_by"]]

        # related_meeting_id filter
        if "related_meeting_id" in filters:
            mid = filters["related_meeting_id"]
            results = [d for d in results if d.related_meeting_id == mid]

        # resolved_at_day_lte filter
        if "resolved_at_day_lte" in filters:
            lte = int(filters["resolved_at_day_lte"])
            results = [
                d for d in results
                if d.resolved_at_day is not None and d.resolved_at_day <= lte
            ]

        # proposed_at_day_gte filter
        if "proposed_at_day_gte" in filters:
            gte = int(filters["proposed_at_day_gte"])
            results = [d for d in results if d.proposed_at_day >= gte]

        return self._sort(results)

    def get_pending(self) -> list[Decision]:
        """
        Return all unresolved decisions (status is ``proposed`` or ``discussed``).

        These are decisions that still require a vote or resolution.
        """
        return self.get_board(filters={"status": ["proposed", "discussed"]})

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Return a decision by ID, or ``None`` if not found."""
        return self._decisions.get(decision_id)

    def summary(self) -> dict[str, Any]:
        """
        Return a high-level counts summary of all decisions on the board.

        Example return value::

            {
                "total": 8,
                "by_status": {"proposed": 1, "discussed": 2, "approved": 4,
                               "rejected": 1, "deferred": 0},
                "by_category": {"technical": 5, "functional": 2,
                                 "organizational": 1, "budget": 0},
                "consensus_threshold": 0.7
            }
        """
        all_d = list(self._decisions.values())
        by_status: dict[str, int] = {
            s: 0 for s in ("proposed", "discussed", "approved", "rejected", "deferred")
        }
        by_category: dict[str, int] = {
            c: 0 for c in ("technical", "functional", "organizational", "budget")
        }
        for d in all_d:
            by_status[d.status] = by_status.get(d.status, 0) + 1
            by_category[d.category] = by_category.get(d.category, 0) + 1

        return {
            "total": len(all_d),
            "by_status": by_status,
            "by_category": by_category,
            "consensus_threshold": self.consensus_threshold,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_decision(self, decision_id: str) -> Decision:
        """Return decision by ID or raise :exc:`ValueError`."""
        d = self._decisions.get(decision_id)
        if d is None:
            raise ValueError(
                f"Decision '{decision_id}' not found on the board. "
                "Did you call propose_decision() first?"
            )
        return d

    @staticmethod
    def _sort(decisions: list[Decision]) -> list[Decision]:
        """Sort by proposed_at_day asc, then id asc for stable ordering."""
        return sorted(decisions, key=lambda d: (d.proposed_at_day, d.id))
