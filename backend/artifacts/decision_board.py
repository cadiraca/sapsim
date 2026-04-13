"""
SAP SIM — Decision Board Artifact
Phase: 7.5
Purpose: Provides the Decision dataclass and DecisionBoard class for tracking,
         voting on, and resolving project decisions throughout a SAP simulation.

Decisions move through the following lifecycle:
    proposed → discussed → approved | rejected | deferred

Voting uses a simple majority model: once the approval threshold is reached
(default 70 % of cast votes), ``auto_resolve`` will flip the status to
``approved``; if the rejection threshold is reached, it becomes ``rejected``.

Persistence: SQLite via utils.persistence.get_db() (db.save_decision / db.update_decision).

Usage::

    board = DecisionBoard(project_name="my-sap-project")

    d = board.propose_decision(Decision(
        title="Adopt S/4HANA Cloud Public Edition",
        description="Move from ECC to S/4HANA Cloud PE for Finance scope.",
        category="technical",
        proposed_by="Alex",
        proposed_at_day=3,
    ))
    await board.save_decision_to_db(d)

    board.vote(d.id, agent_id="Sara",  vote="approve",
               reasoning="Fits our cloud-first strategy.")
    resolved = board.auto_resolve(d.id, current_day=4)
    if resolved:
        await board.update_decision_in_db(resolved.id, {"status": resolved.status, "resolved_day": resolved.resolved_at_day})
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from utils.persistence import get_db

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
    # Serialisation helpers
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
        Used as ``project_id`` in all DB calls.
    consensus_threshold:
        Fraction of *active* (non-abstain) votes that must be ``approve``
        for :meth:`auto_resolve` to mark a decision ``approved``.
        Defaults to ``0.70`` (70 %).

    Thread-safety: not thread-safe; wrap in a lock for concurrent access.
    """

    def __init__(
        self,
        project_name: str,
        consensus_threshold: float = 0.70,
    ) -> None:
        self.project_name = project_name
        self.consensus_threshold = consensus_threshold

        # In-memory store: decision_id → Decision
        self._decisions: dict[str, Decision] = {}

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def propose_decision(self, decision: Decision) -> Decision:
        """
        Register *decision* on the board (status = ``proposed``).

        Returns the same :class:`Decision` for chaining.
        Raises :exc:`ValueError` if a decision with the same ID already exists.

        .. note::
            Call :meth:`save_decision_to_db` immediately after to persist.
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

    async def save_decision_to_db(self, decision: Decision) -> None:
        """Persist *decision* to SQLite via db.save_decision()."""
        db = get_db()
        await db.save_decision(self.project_name, decision.to_dict())
        logger.debug("DecisionBoard: persisted decision '%s' to SQLite", decision.id)

    async def update_decision_in_db(
        self, decision_id: str, updates: dict[str, Any]
    ) -> None:
        """Apply a partial update to an existing decision row via db.update_decision()."""
        db = get_db()
        await db.update_decision(decision_id, updates)
        logger.debug(
            "DecisionBoard: updated decision '%s' in SQLite (fields: %s)",
            decision_id,
            list(updates.keys()),
        )

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

        .. note::
            Call :meth:`update_decision_in_db` with ``{"votes": d.votes}``
            after this to persist the updated vote tally.
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

        .. note::
            Call :meth:`update_decision_in_db` to persist the resolution.
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

    async def get_board(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Query the database for decisions belonging to this project.

        When *filters* contains ``"status"``, only decisions matching that
        status are returned; other filter keys are applied client-side after
        the DB fetch.

        Supported filter keys
        ~~~~~~~~~~~~~~~~~~~~~
        ``status`` : str
            e.g. ``"proposed"``, ``"approved"``; passed directly to the DB query.
        ``category`` : str
            Filter by decision category (applied post-fetch).
        ``proposed_by`` : str
            Filter by proposer agent ID (applied post-fetch).

        Returns
        -------
        list[dict]
            Dicts as returned by :meth:`~backend.db.repository.Database.get_decisions`.
        """
        db = get_db()
        status_filter = filters.get("status") if filters else None
        results = await db.get_decisions(self.project_name, status=status_filter)

        # Client-side filters for keys not handled by the DB layer
        if filters:
            if "category" in filters:
                results = [r for r in results if r.get("category") == filters["category"]]
            if "proposed_by" in filters:
                results = [r for r in results if r.get("proposed_by") == filters["proposed_by"]]

        return results

    async def get_pending(self) -> list[dict[str, Any]]:
        """
        Return all unresolved decisions (status ``proposed`` or ``discussed``)
        by querying the database.

        Returns
        -------
        list[dict]
            Pending decision dicts from the DB.
        """
        db = get_db()
        proposed = await db.get_decisions(self.project_name, status="proposed")
        discussed = await db.get_decisions(self.project_name, status="discussed")
        return proposed + discussed

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Return an in-memory decision by ID, or ``None`` if not found."""
        return self._decisions.get(decision_id)

    def summary(self) -> dict[str, Any]:
        """
        Return a high-level counts summary of all in-memory decisions.

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
