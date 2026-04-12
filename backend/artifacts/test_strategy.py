"""
SAP SIM — Test Strategy
Phase: 4.4

Manages test cases and test coverage for SAP implementation simulations.
Supports unit, integration, UAT, regression, and performance test types.
Tracks test status lifecycle, defect linkage, and produces coverage reports.

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
    strategy.add_test(tc)
    strategy.update_status("TC-001", TestStatus.PASSED, actual_result="Document posted, doc# 100000001")
    print(strategy.get_coverage_report())
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


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
        d["type"] = self.type.value
        d["status"] = self.status.value
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

    Persists to ``projects/<name>/test_strategy.json``.
    """

    def __init__(self, project_name: str):
        self.project_name = project_name
        self._tests: dict[str, TestCase] = {}

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def add_test(self, test: TestCase) -> None:
        """Add a test case. Raises ValueError if the ID already exists."""
        if test.id in self._tests:
            raise ValueError(f"Test case '{test.id}' already exists.")
        self._tests[test.id] = test

    def update_status(
        self,
        test_id: str,
        status: TestStatus,
        actual_result: str = "",
        defect_id: Optional[str] = None,
    ) -> TestCase:
        """
        Update the status (and optionally the actual result / defect ID) of
        an existing test case.  Returns the updated TestCase.
        """
        if test_id not in self._tests:
            raise KeyError(f"Test case '{test_id}' not found.")
        tc = self._tests[test_id]
        tc.status = status
        if actual_result:
            tc.actual_result = actual_result
        if defect_id is not None:
            tc.defect_id = defect_id
        return tc

    def get_test(self, test_id: str) -> TestCase:
        """Return a single test case by ID."""
        if test_id not in self._tests:
            raise KeyError(f"Test case '{test_id}' not found.")
        return self._tests[test_id]

    def all_tests(self) -> list[TestCase]:
        """Return all test cases sorted by priority then ID."""
        return sorted(self._tests.values(), key=lambda t: (t.priority, t.id))

    # -----------------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------------

    def get_coverage_report(self) -> dict:
        """
        Returns a dict summarising test coverage across modules, types, and
        statuses.

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
        tests = list(self._tests.values())
        total = len(tests)

        by_status: dict[str, int] = {s.value: 0 for s in TestStatus}
        by_type: dict[str, int] = {t.value: 0 for t in TestType}
        by_module: dict[str, dict[str, int]] = {}

        defect_count = 0

        for tc in tests:
            by_status[tc.status.value] += 1
            by_type[tc.type.value] += 1

            if tc.module not in by_module:
                by_module[tc.module] = {s.value: 0 for s in TestStatus}
                by_module[tc.module]["total"] = 0
            by_module[tc.module][tc.status.value] += 1
            by_module[tc.module]["total"] += 1

            if tc.defect_id:
                defect_count += 1

        executed = by_status[TestStatus.PASSED.value] + by_status[TestStatus.FAILED.value]
        pass_rate = (
            by_status[TestStatus.PASSED.value] / executed if executed > 0 else 0.0
        )

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_module": by_module,
            "pass_rate": round(pass_rate, 4),
            "defect_count": defect_count,
        }

    def get_defects(self) -> list[TestCase]:
        """Return all test cases that have a linked defect ID."""
        return [tc for tc in self._tests.values() if tc.defect_id]

    def get_by_status(self, status: TestStatus) -> list[TestCase]:
        """Return all test cases with a given status."""
        return [tc for tc in self._tests.values() if tc.status == status]

    def get_by_module(self, module: str) -> list[TestCase]:
        """Return all test cases for a given SAP module."""
        return [tc for tc in self._tests.values() if tc.module == module]

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def _project_dir(self) -> str:
        base = os.path.join(
            os.path.dirname(__file__), "..", "..", "projects", self.project_name
        )
        return os.path.normpath(base)

    def _file_path(self) -> str:
        return os.path.join(self._project_dir(), "test_strategy.json")

    def save(self) -> str:
        """Persist all test cases to disk.  Returns the file path written."""
        os.makedirs(self._project_dir(), exist_ok=True)
        payload = {
            "project": self.project_name,
            "tests": [tc.to_dict() for tc in self.all_tests()],
        }
        path = self._file_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return path

    @classmethod
    def load(cls, project_name: str) -> "TestStrategy":
        """Load a TestStrategy from its persisted JSON file."""
        instance = cls(project_name)
        base = os.path.join(
            os.path.dirname(__file__), "..", "..", "projects", project_name
        )
        path = os.path.normpath(os.path.join(base, "test_strategy.json"))
        if not os.path.exists(path):
            raise FileNotFoundError(f"No test strategy file found at '{path}'.")
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        for item in payload.get("tests", []):
            instance._tests[item["id"]] = TestCase.from_dict(item)
        return instance

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
