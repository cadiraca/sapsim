"""
SAP SIM — Lessons Learned
Phase: 7.5

Captures lessons learned throughout the SAP implementation simulation.
Supports categorisation by phase, impact, and custom filters so project
teams can retrieve actionable insights at any point in the project lifecycle.

Persistence: SQLite via utils.persistence.get_db()
    (db.save_lesson / db.get_lessons)

Example:
    from artifacts.lessons_learned import Lesson, LessonsCollector

    collector = LessonsCollector("my_project")
    lesson = Lesson(
        id="LL-001",
        title="Data migration cutover window underestimated",
        description="The legacy extract took 6 hours; only 3 hours were scheduled.",
        category="Data Migration",
        phase="Realise",
        reported_by="Carlos",
        reported_at_day=42,
        impact="HIGH",
        recommendation="Always run a full dress-rehearsal migration at least two weeks before go-live.",
    )
    await collector.add_lesson(lesson)
    print(await collector.get_by_phase("Realise"))
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from utils.persistence import get_db


# ---------------------------------------------------------------------------
# Lesson dataclass
# ---------------------------------------------------------------------------

@dataclass
class Lesson:
    """A single lessons-learned entry captured during the simulation."""

    id: str
    title: str
    description: str
    category: str          # e.g. "Change Management", "Data Migration", "Testing"
    phase: str             # Simulate, Prepare, Explore, Realise, Deploy, Run
    reported_by: str
    reported_at_day: int   # simulation day number (1-based)
    impact: str            # HIGH / MEDIUM / LOW  (free-text for flexibility)
    recommendation: str

    # -----------------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(**data)


# ---------------------------------------------------------------------------
# LessonsCollector class
# ---------------------------------------------------------------------------

class LessonsCollector:
    """
    Collects and queries lessons learned for a SAP simulation project.

    Persists to SQLite via :func:`utils.persistence.get_db`.

    Parameters
    ----------
    project_name:
        Project identifier used as ``project_id`` in all DB calls.
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self._lessons: dict[str, Lesson] = {}  # keyed by lesson.id

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    async def add_lesson(self, lesson: Lesson) -> None:
        """
        Add a new lesson to in-memory store and persist to SQLite via db.save_lesson().

        Raises ValueError if the ID already exists in memory.
        """
        if lesson.id in self._lessons:
            raise ValueError(f"Lesson '{lesson.id}' already exists.")
        self._lessons[lesson.id] = lesson

        db = get_db()
        await db.save_lesson(self.project_name, lesson.to_dict())

    def update_lesson(self, lesson_id: str, **updates) -> Lesson:
        """
        Update fields of an existing in-memory lesson.

        Supported keyword arguments match the Lesson dataclass field names.
        Returns the updated Lesson.

        .. note::
            Call :meth:`save_lesson_to_db` after this to persist changes to SQLite.
        """
        if lesson_id not in self._lessons:
            raise KeyError(f"Lesson '{lesson_id}' not found.")
        lesson = self._lessons[lesson_id]
        for key, value in updates.items():
            if not hasattr(lesson, key):
                raise AttributeError(f"Lesson has no field '{key}'.")
            setattr(lesson, key, value)
        return lesson

    async def save_lesson_to_db(self, lesson_id: str) -> None:
        """Re-persist an in-memory lesson (e.g. after :meth:`update_lesson`) to SQLite."""
        if lesson_id not in self._lessons:
            raise KeyError(f"Lesson '{lesson_id}' not found.")
        db = get_db()
        await db.save_lesson(self.project_name, self._lessons[lesson_id].to_dict())

    def get_lesson(self, lesson_id: str) -> Lesson:
        """Return a single lesson by ID from in-memory store."""
        if lesson_id not in self._lessons:
            raise KeyError(f"Lesson '{lesson_id}' not found.")
        return self._lessons[lesson_id]

    def all_lessons(self) -> list[Lesson]:
        """Return all in-memory lessons sorted by simulation day then ID."""
        return sorted(
            self._lessons.values(), key=lambda l: (l.reported_at_day, l.id)
        )

    # -----------------------------------------------------------------------
    # Filtering / querying (DB-backed)
    # -----------------------------------------------------------------------

    async def get_lessons(
        self,
        *,
        phase: Optional[str] = None,
    ) -> list[dict]:
        """
        Query the database for lessons belonging to this project.

        Parameters
        ----------
        phase:
            When supplied, only lessons from this SAP ACTIVATE phase are
            returned (delegated to :meth:`~backend.db.repository.Database.get_lessons`).

        Returns
        -------
        list[dict]
            Plain dicts as returned by the repository, sorted by
            ``reported_day`` ASC.
        """
        db = get_db()
        return await db.get_lessons(self.project_name, phase=phase)

    async def get_by_phase(self, phase: str) -> list[dict]:
        """Shorthand: return all DB lessons for a given phase."""
        return await self.get_lessons(phase=phase)

    def get_by_category(self, category: str) -> list[Lesson]:
        """Return all in-memory lessons for a given category (case-insensitive)."""
        return [
            l for l in self.all_lessons()
            if l.category.lower() == category.lower()
        ]

    def get_high_impact(self) -> list[Lesson]:
        """Return in-memory lessons marked as HIGH impact."""
        return [l for l in self.all_lessons() if l.impact.upper() == "HIGH"]

    def summary(self) -> dict:
        """
        Returns a dict summarising in-memory lessons by phase, category, and impact.

        Structure::

            {
                "total": int,
                "by_phase": {phase: count, ...},
                "by_category": {category: count, ...},
                "by_impact": {impact: count, ...},
            }
        """
        lessons = list(self._lessons.values())
        total = len(lessons)

        by_phase: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_impact: dict[str, int] = {}

        for l in lessons:
            by_phase[l.phase] = by_phase.get(l.phase, 0) + 1
            by_category[l.category] = by_category.get(l.category, 0) + 1
            by_impact[l.impact] = by_impact.get(l.impact, 0) + 1

        return {
            "total": total,
            "by_phase": dict(sorted(by_phase.items())),
            "by_category": dict(sorted(by_category.items())),
            "by_impact": dict(sorted(by_impact.items())),
        }

    # -----------------------------------------------------------------------
    # Dunder helpers
    # -----------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._lessons)

    def __repr__(self) -> str:
        return (
            f"LessonsCollector(project={self.project_name!r}, "
            f"lessons={len(self._lessons)})"
        )
