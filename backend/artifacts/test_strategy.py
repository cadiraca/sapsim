"""
SAP SIM — Test Strategy
Phase: 7.5

Manages test cases and test coverage for SAP implementation simulations.
Supports unit, integration, UAT, regression, and performance test types.
Tracks test status lifecycle, defect linkage, and produces coverage reports.

Persistence: SQLite via utils.persistence.get_db()
    (db.save_test_case / db.update_test_status / db.get_test_cases / db.get_coverage_stats)

Example:
    from artifacts.test_strategy import TestCase, TestStrategy, TestType, TestStatus

    strategy = TestStrategy("my_project")
    tc = TestCase(
        id="TC-001",
        title="FI Posting Validation",
        module="FI",
        type=TestType.UAT,
        status=TestStatus.PLANNED,
        assigned_to="Carlos",
        priority=1,
        steps=["Open FB50", "Enter document data", "Post"],
        expected_result="Document posted successfully",
    )
    await strategy.add_test(tc)
    await strategy.update_status("TC-001", TestStatus.PASSED, actual_result="Document posted, doc# 100000001")
    print(await strategy.get_coverage_report())
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from utils.persistence import get_db


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TestType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    UAT = "uat"
    REGRESSION = "regression"
    PERFORMANCE = "performance"


class TestStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# TestCase dataclass
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """A single test case in the simulation's test strategy."""

    id: str
    title: str
    module: str
    type: TestType
    status: TestStatus
    assigned_to: str
    priority: int                          # 1 = highest
    steps: list[str] = field(default_factory=list)
    expected_result: str = ""
    actual_result: str = ""
    defect_id: Optional[str] = None        # linked defect/issue ID, if any

    # -----------------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value if hasattr(self.type, "value") else self.type
        d["status"] = self.status.value if hasattr(self.status, "value") else self.status
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        data = dict(data)
        data["type"] = TestType(data["type"])
        data["status"] = TestStatus(data["status"])
        return cls(**data)


# ---------------------------------------------------------------------------
# TestStrategy class
# ---------------------------------------------------------------------------

class TestStrategy:
    """
    Manages the full test strategy for a SAP simulation project.

    Persists to SQLite via :func:`utils.persistence.get_db`.

    Parameters
    ----------
    project_name:
        Project identifier used as ``project_id`` in all DB calls.
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self._tests: dict[str, TestCase] = {}

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    async def add_test(self, test: TestCase) -> None:
        """
        Add a test case to in-memory store and persist to SQLite.

        Raises ValueError if the ID already exists in memory.
        """
        if test.id in self._tests:
            raise ValueError(f"Test case '{test.id}' already exists.")
        self._tests[test.id] = test

        db = get_db()
        await db.save_test_case(self.project_name, test.to_dict())

    async def update_status(
        self,
        test_id: str,
        status: TestStatus,
        actual_result: str = "",
        defect_id: Optional[str] = None,
    ) -> TestCase:
        """
        Update the status (and optionally the actual result / defect ID) of
        an existing test case in-memory and in the DB.

        Returns the updated TestCase.
        """
        if test_id not in self._tests:
            raise KeyError(f"Test case '{test_id}' not found.")
        tc = self._tests[test_id]
        tc.status = status
        if actual_result:
            tc.actual_result = actual_result
        if defect_id is not None:
            tc.defect_id = defect_id

        db = get_db()
        await db.update_test_status(test_id, status, result=actual_result)

        # If defect_id changed, do a full re-save to capture it
        if defect_id is not None:
            await db.save_test_case(self.project_name, tc.to_dict())

        return tc

    def get_test(self, test_id: str) -> TestCase:
        """Return a single test case by ID from the in-memory store."""
        if test_id not in self._tests:
            raise KeyError(f"Test case '{test_id}' not found.")
        return self._tests[test_id]

    def all_tests(self) -> list[TestCase]:
        """Return all in-memory test cases sorted by priority then ID."""
        return sorted(self._tests.values(), key=lambda t: (t.priority, t.id))

    # -----------------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------------

    async def get_coverage_report(self) -> dict:
        """
        Returns a dict summarising test coverage across modules, types, and
        statuses, computed by the database.

        Delegates to :meth:`~backend.db.repository.Database.get_coverage_stats`.

        Structure::

            {
                "total": int,
                "by_status": {status: count, ...},
                "by_type": {type: count, ...},
                "by_module": {module: {"total": n, "passed": n, "failed": n, ...}},
                "pass_rate": float,          # 0.0 – 1.0
                "defect_count": int,
            }
        """
        db = get_db()
        return await db.get_coverage_stats(self.project_name)

    async def get_test_cases_from_db(
        self,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        Query test cases from the database, optionally filtered by *status*.

        Returns a list of plain dicts as returned by
        :meth:`~backend.db.repository.Database.get_test_cases`.
        """
        db = get_db()
        return await db.get_test_cases(self.project_name, status=status)

    def get_defects(self) -> list[TestCase]:
        """Return all in-memory test cases that have a linked defect ID."""
        return [tc for tc in self._tests.values() if tc.defect_id]

    def get_by_status(self, status: TestStatus) -> list[TestCase]:
        """Return all in-memory test cases with a given status."""
        return [tc for tc in self._tests.values() if tc.status == status]

    def get_by_module(self, module: str) -> list[TestCase]:
        """Return all in-memory test cases for a given SAP module."""
        return [tc for tc in self._tests.values() if tc.module == module]

    # -----------------------------------------------------------------------
    # Dunder helpers
    # -----------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tests)

    def __repr__(self) -> str:
        return (
            f"TestStrategy(project={self.project_name!r}, "
            f"tests={len(self._tests)})"
        )
