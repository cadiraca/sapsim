"""
SAP SIM — Lessons Learned
Phase: 4.4

Captures lessons learned throughout the SAP implementation simulation.
Supports categorisation by phase, impact, and custom filters so project
teams can retrieve actionable insights at any point in the project lifecycle.

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
    collector.add_lesson(lesson)
    print(collector.get_by_phase("Realise"))
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


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

    Persists to ``projects/<name>/lessons.json``.
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self._lessons: dict[str, Lesson] = {}  # keyed by lesson.id

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def add_lesson(self, lesson: Lesson) -> None:
        """Add a new lesson. Raises ValueError if the ID already exists."""
        if lesson.id in self._lessons:
            raise ValueError(f"Lesson '{lesson.id}' already exists.")
        self._lessons[lesson.id] = lesson

    def update_lesson(self, lesson_id: str, **updates) -> Lesson:
        """
        Update fields of an existing lesson.  Supported keyword arguments
        match the Lesson dataclass field names.  Returns the updated Lesson.
        """
        if lesson_id not in self._lessons:
            raise KeyError(f"Lesson '{lesson_id}' not found.")
        lesson = self._lessons[lesson_id]
        for key, value in updates.items():
            if not hasattr(lesson, key):
                raise AttributeError(f"Lesson has no field '{key}'.")
            setattr(lesson, key, value)
        return lesson

    def get_lesson(self, lesson_id: str) -> Lesson:
        """Return a single lesson by ID."""
        if lesson_id not in self._lessons:
            raise KeyError(f"Lesson '{lesson_id}' not found.")
        return self._lessons[lesson_id]

    def all_lessons(self) -> list[Lesson]:
        """Return all lessons sorted by simulation day then ID."""
        return sorted(
            self._lessons.values(), key=lambda l: (l.reported_at_day, l.id)
        )

    # -----------------------------------------------------------------------
    # Filtering / querying
    # -----------------------------------------------------------------------

    def get_lessons(
        self,
        *,
        category: Optional[str] = None,
        phase: Optional[str] = None,
        reported_by: Optional[str] = None,
        impact: Optional[str] = None,
    ) -> list[Lesson]:
        """
        Return lessons matching ALL supplied filter criteria (AND semantics).
        Comparisons are case-insensitive.

        Parameters
        ----------
        category:    filter by category string
        phase:       filter by project phase
        reported_by: filter by reporter name
        impact:      filter by impact level (HIGH / MEDIUM / LOW)
        """
        results = self.all_lessons()

        if category is not None:
            results = [l for l in results if l.category.lower() == category.lower()]
        if phase is not None:
            results = [l for l in results if l.phase.lower() == phase.lower()]
        if reported_by is not None:
            results = [l for l in results if l.reported_by.lower() == reported_by.lower()]
        if impact is not None:
            results = [l for l in results if l.impact.lower() == impact.lower()]

        return results

    def get_by_phase(self, phase: str) -> list[Lesson]:
        """Shorthand: return all lessons for a given phase (case-insensitive)."""
        return self.get_lessons(phase=phase)

    def get_by_category(self, category: str) -> list[Lesson]:
        """Shorthand: return all lessons for a given category (case-insensitive)."""
        return self.get_lessons(category=category)

    def get_high_impact(self) -> list[Lesson]:
        """Return lessons marked as HIGH impact."""
        return self.get_lessons(impact="HIGH")

    def summary(self) -> dict:
        """
        Returns a dict summarising lessons by phase, category, and impact.

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
    # Persistence
    # -----------------------------------------------------------------------

    def _project_dir(self) -> str:
        base = os.path.join(
            os.path.dirname(__file__), "..", "..", "projects", self.project_name
        )
        return os.path.normpath(base)

    def _file_path(self) -> str:
        return os.path.join(self._project_dir(), "lessons.json")

    def save(self) -> str:
        """Persist all lessons to disk.  Returns the file path written."""
        os.makedirs(self._project_dir(), exist_ok=True)
        payload = {
            "project": self.project_name,
            "lessons": [l.to_dict() for l in self.all_lessons()],
        }
        path = self._file_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def load(cls, project_name: str) -> "LessonsCollector":
        """Load a LessonsCollector from its persisted JSON file."""
        instance = cls(project_name)
        base = os.path.join(
            os.path.dirname(__file__), "..", "..", "projects", project_name
        )
        path = os.path.normpath(os.path.join(base, "lessons.json"))
        if not os.path.exists(path):
            raise FileNotFoundError(f"No lessons file found at '{path}'.")
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        for item in payload.get("lessons", []):
            lesson = Lesson.from_dict(item)
            instance._lessons[lesson.id] = lesson
        return instance

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
