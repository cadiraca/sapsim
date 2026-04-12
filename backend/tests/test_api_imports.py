"""
SAP SIM — API + Artifact Import Verification
Phase: 5.2
Purpose: Verify that every API route module and every artifact module
         can be imported without errors, and that the key symbols exposed
         by each are actually present and callable/instantiable.

Run:
    cd backend
    source venv/bin/activate
    python -m pytest tests/test_api_imports.py -v
  or directly:
    python tests/test_api_imports.py
"""

from __future__ import annotations

import importlib
import sys
import pytest


# ---------------------------------------------------------------------------
# 1. API layer — routes, models, SSE
# ---------------------------------------------------------------------------

API_MODULES = [
    "api.routes",
    "api.models",
    "api.sse",
]


@pytest.mark.parametrize("module_path", API_MODULES)
def test_api_module_imports(module_path: str) -> None:
    """Every API module must import without errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None, f"Module '{module_path}' imported as None"


# ---------------------------------------------------------------------------
# 2. Artifact modules
# ---------------------------------------------------------------------------

ARTIFACT_MODULES = [
    "artifacts.meeting_logger",
    "artifacts.decision_board",
    "artifacts.tool_registry",
    "artifacts.test_strategy",
    "artifacts.lessons_learned",
    "artifacts.final_report",
]


@pytest.mark.parametrize("module_path", ARTIFACT_MODULES)
def test_artifact_module_imports(module_path: str) -> None:
    """Every artifact module must import without errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None, f"Module '{module_path}' imported as None"


# ---------------------------------------------------------------------------
# 3. Route-level symbol checks — FastAPI router and key endpoint functions
# ---------------------------------------------------------------------------

def test_routes_exports_router() -> None:
    """api.routes must export an APIRouter instance named 'router'."""
    from fastapi import APIRouter
    from api.routes import router
    assert isinstance(router, APIRouter), "routes.router must be an APIRouter"


def test_routes_has_list_meetings_endpoint() -> None:
    from api.routes import list_meetings
    assert callable(list_meetings)


def test_routes_has_get_decisions_endpoint() -> None:
    from api.routes import get_decisions
    assert callable(get_decisions)


def test_routes_has_propose_decision_endpoint() -> None:
    """POST /decisions endpoint must exist."""
    from api.routes import propose_decision
    assert callable(propose_decision)


def test_routes_has_get_tools_endpoint() -> None:
    from api.routes import get_tools
    assert callable(get_tools)


def test_routes_has_get_test_strategy_endpoint() -> None:
    from api.routes import get_test_strategy
    assert callable(get_test_strategy)


def test_routes_has_get_lessons_endpoint() -> None:
    from api.routes import get_lessons
    assert callable(get_lessons)


def test_routes_has_generate_artifact_report_endpoint() -> None:
    """POST /artifacts/report endpoint must exist."""
    from api.routes import generate_artifact_report
    assert callable(generate_artifact_report)


def test_routes_has_get_meeting_detail_endpoint() -> None:
    from api.routes import get_meeting
    assert callable(get_meeting)


# ---------------------------------------------------------------------------
# 4. Model symbol checks — Pydantic models used by the routes
# ---------------------------------------------------------------------------

def test_models_propose_decision_request() -> None:
    """ProposeDecisionRequest must be importable and instantiable."""
    from api.models import ProposeDecisionRequest
    req = ProposeDecisionRequest(
        title="Test Decision",
        description="A test description",
        proposed_by="PM_ALEX",
        proposed_at_day=1,
    )
    assert req.title == "Test Decision"
    assert req.category == "technical"  # default


def test_models_artifact_report_request() -> None:
    """ArtifactReportRequest must be importable and instantiable."""
    from api.models import ArtifactReportRequest
    req = ArtifactReportRequest()
    assert req.force_regenerate is False

    req_force = ArtifactReportRequest(force_regenerate=True)
    assert req_force.force_regenerate is True


def test_models_decision_response() -> None:
    from api.models import DecisionResponse
    resp = DecisionResponse(total=0)
    assert resp.pending == []
    assert resp.approved == []
    assert resp.rejected == []
    assert resp.deferred == []


def test_models_meeting_response() -> None:
    from api.models import MeetingResponse
    resp = MeetingResponse(
        id="m1",
        title="Kickoff",
        phase="Prepare",
        simulated_day=1,
        facilitator="PM_ALEX",
        participants=["PM_ALEX", "ARCH_SARA"],
        duration_turns=5,
        decisions_count=2,
    )
    assert resp.id == "m1"


def test_models_artifact_response() -> None:
    from api.models import ArtifactResponse
    resp = ArtifactResponse(
        project_name="test",
        content="# Report",
        generated=True,
    )
    assert resp.generated is True


# ---------------------------------------------------------------------------
# 5. Artifact class instantiation — smoke tests (no disk I/O, no LLM calls)
# ---------------------------------------------------------------------------

def test_meeting_logger_instantiation() -> None:
    from artifacts.meeting_logger import MeetingLogger, MeetingLog
    ml = MeetingLogger()
    assert ml.list_active() == []
    assert ml.list_archived() == []


def test_meeting_log_lifecycle() -> None:
    from artifacts.meeting_logger import MeetingLogger, MeetingLog
    ml = MeetingLogger()
    log = ml.start_log(MeetingLog(
        meeting_id="test-kickoff",
        title="Kickoff",
        meeting_type="kickoff",
        phase="Prepare",
        participants=["PM_ALEX"],
        agenda_items=["Scope"],
        simulated_day=1,
    ))
    ml.add_turn("test-kickoff", "PM_ALEX", "Welcome everyone.")
    ml.add_decision("test-kickoff", "Use S/4HANA 2023.")
    ml.add_action_item("test-kickoff", {"owner": "PM_ALEX", "task": "Draft charter", "due_day": 5})
    finalised = ml.finalize_log("test-kickoff")
    assert finalised.is_finalised is True
    assert len(finalised.transcript) == 1
    assert len(finalised.decisions_made) == 1
    assert "test-kickoff" in ml.list_archived()


def test_decision_board_instantiation(tmp_path) -> None:
    from artifacts.decision_board import DecisionBoard, Decision
    board = DecisionBoard(project_name="test-proj", projects_root=str(tmp_path))
    assert board.summary()["total"] == 0


def test_decision_board_propose_and_conflict(tmp_path) -> None:
    from artifacts.decision_board import DecisionBoard, Decision
    board = DecisionBoard(project_name="test-proj", projects_root=str(tmp_path))
    d = Decision(
        title="Adopt S/4HANA Cloud",
        description="Move to S/4HANA Cloud PE.",
        category="technical",
        proposed_by="PM_ALEX",
        proposed_at_day=1,
    )
    board.propose_decision(d)
    assert board.summary()["total"] == 1

    # Duplicate ID → ValueError
    import pytest as _pytest
    with _pytest.raises(ValueError, match="already exists"):
        board.propose_decision(d)


def test_tool_registry_instantiation(tmp_path, monkeypatch) -> None:
    from artifacts.tool_registry import ToolRegistry
    monkeypatch.setattr(ToolRegistry, "PROJECTS_ROOT", tmp_path)
    registry = ToolRegistry(project_name="test-proj")
    assert len(registry) == 0


def test_tool_registry_announce_and_duplicate(tmp_path, monkeypatch) -> None:
    from artifacts.tool_registry import ToolRegistry, SimulatedTool
    monkeypatch.setattr(ToolRegistry, "PROJECTS_ROOT", tmp_path)
    registry = ToolRegistry(project_name="test-proj")
    tool = SimulatedTool(
        name="ZFIN_OPEN_ITEMS",
        category="reporting",
        description="Open items ageing report.",
        sap_module="FI",
        tcodes=["ZFI001"],
        tables=["BSID"],
        announced_by="FI_CHEN",
        announced_at_day=2,
    )
    registry.announce_tool(tool)
    assert len(registry) == 1

    import pytest as _pytest
    with _pytest.raises(ValueError, match="already registered"):
        registry.announce_tool(tool)


def test_test_strategy_instantiation() -> None:
    from artifacts.test_strategy import TestStrategy, TestCase, TestType, TestStatus
    ts = TestStrategy("test-proj")
    assert len(ts) == 0


def test_test_strategy_add_and_duplicate() -> None:
    from artifacts.test_strategy import TestStrategy, TestCase, TestType, TestStatus
    ts = TestStrategy("test-proj")
    tc = TestCase(
        id="TC-001",
        title="FI Posting",
        module="FI",
        type=TestType.UAT,
        status=TestStatus.PLANNED,
        assigned_to="FI_CHEN",
        priority=1,
    )
    ts.add_test(tc)
    assert len(ts) == 1

    import pytest as _pytest
    with _pytest.raises(ValueError, match="already exists"):
        ts.add_test(tc)


def test_test_strategy_coverage_report() -> None:
    from artifacts.test_strategy import TestStrategy, TestCase, TestType, TestStatus
    ts = TestStrategy("test-proj")
    ts.add_test(TestCase(
        id="TC-001", title="FI Post", module="FI",
        type=TestType.UAT, status=TestStatus.PASSED,
        assigned_to="FI_CHEN", priority=1,
    ))
    ts.add_test(TestCase(
        id="TC-002", title="MM PO", module="MM",
        type=TestType.INTEGRATION, status=TestStatus.FAILED,
        assigned_to="MM_RAVI", priority=2,
    ))
    report = ts.get_coverage_report()
    assert report["total"] == 2
    assert report["pass_rate"] == 0.5


def test_lessons_collector_instantiation() -> None:
    from artifacts.lessons_learned import LessonsCollector
    lc = LessonsCollector("test-proj")
    assert len(lc) == 0


def test_lessons_collector_add_and_query() -> None:
    from artifacts.lessons_learned import LessonsCollector, Lesson
    lc = LessonsCollector("test-proj")
    lesson = Lesson(
        id="LL-001",
        title="Data migration window underestimated",
        description="Legacy extract took 6h; only 3h scheduled.",
        category="Data Migration",
        phase="Realize",
        reported_by="DM_FELIX",
        reported_at_day=42,
        impact="HIGH",
        recommendation="Run dress-rehearsal migration 2 weeks before go-live.",
    )
    lc.add_lesson(lesson)
    assert len(lc) == 1
    assert lc.get_by_phase("Realize")[0].id == "LL-001"
    assert lc.get_high_impact()[0].id == "LL-001"

    import pytest as _pytest
    with _pytest.raises(ValueError, match="already exists"):
        lc.add_lesson(lesson)


def test_final_report_generator_instantiation(tmp_path) -> None:
    from artifacts.final_report import FinalReportGenerator
    gen = FinalReportGenerator(
        project_name="test-proj",
        projects_root=str(tmp_path),
    )
    assert gen.project_name == "test-proj"


def test_final_report_generator_generate_no_artifacts(tmp_path) -> None:
    """generate_report must not crash on an empty project (no artifacts on disk)."""
    from artifacts.final_report import FinalReportGenerator
    # Create a minimal project.json so the generator doesn't warn on missing file
    proj_dir = tmp_path / "test-proj"
    proj_dir.mkdir(parents=True)
    import json
    (proj_dir / "project.json").write_text(
        json.dumps({
            "project_name": "test-proj",
            "status": "IDLE",
            "current_phase": "discover",
            "simulated_day": 0,
            "total_days": 165,
            "industry": "Manufacturing",
            "scope": "Full SAP S/4HANA implementation",
            "methodology": "SAP Activate",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_updated": "2026-01-01T00:00:00+00:00",
            "phase_progress": [],
            "active_agents": [],
            "milestones": [],
        }),
        encoding="utf-8",
    )
    gen = FinalReportGenerator(
        project_name="test-proj",
        projects_root=str(tmp_path),
    )
    report = gen.generate_report("test-proj")
    assert isinstance(report, str)
    assert "test-proj" in report
    assert "Executive Summary" in report


# ---------------------------------------------------------------------------
# 6. Route factory helpers (private helpers used by endpoints)
# ---------------------------------------------------------------------------

def test_get_decision_board_helper_smoke(tmp_path, monkeypatch) -> None:
    """_get_decision_board must return a DecisionBoard without crashing."""
    from utils.persistence import PROJECTS_BASE
    import api.routes as routes_module
    monkeypatch.setattr(routes_module, "_project_dir",
                        lambda name: tmp_path / name)
    # Ensure the project dir exists for DecisionBoard init
    (tmp_path / "smoke-proj").mkdir(parents=True, exist_ok=True)

    # Patch PROJECTS_BASE used inside the helper
    import unittest.mock as mock
    with mock.patch("utils.persistence.PROJECTS_BASE", tmp_path):
        board = routes_module._get_decision_board("smoke-proj")
    from artifacts.decision_board import DecisionBoard
    assert isinstance(board, DecisionBoard)


def test_get_tool_registry_helper_smoke(tmp_path, monkeypatch) -> None:
    """_get_tool_registry must return a ToolRegistry without crashing."""
    from artifacts.tool_registry import ToolRegistry
    monkeypatch.setattr(ToolRegistry, "PROJECTS_ROOT", tmp_path)
    import api.routes as routes_module
    registry = routes_module._get_tool_registry("smoke-proj")
    assert isinstance(registry, ToolRegistry)


def test_get_lessons_collector_helper_smoke() -> None:
    """_get_lessons_collector must return a LessonsCollector for a new project."""
    import api.routes as routes_module
    lc = routes_module._get_lessons_collector("nonexistent-proj-12345")
    from artifacts.lessons_learned import LessonsCollector
    assert isinstance(lc, LessonsCollector)


def test_get_test_strategy_helper_smoke() -> None:
    """_get_test_strategy must return a TestStrategy for a new project."""
    import api.routes as routes_module
    ts = routes_module._get_test_strategy("nonexistent-proj-12345")
    from artifacts.test_strategy import TestStrategy
    assert isinstance(ts, TestStrategy)


def test_get_meeting_logger_helper_smoke(tmp_path, monkeypatch) -> None:
    """_get_meeting_logger must return a MeetingLogger (empty if no meetings dir)."""
    import api.routes as routes_module
    monkeypatch.setattr(routes_module, "_project_dir",
                        lambda name: tmp_path / name)
    ml = routes_module._get_meeting_logger("smoke-proj")
    from artifacts.meeting_logger import MeetingLogger
    assert isinstance(ml, MeetingLogger)
    assert ml.list_archived() == []


def test_get_meeting_logger_loads_json_files(tmp_path, monkeypatch) -> None:
    """_get_meeting_logger must hydrate archived logs from on-disk JSON files."""
    import json
    import api.routes as routes_module

    proj_dir = tmp_path / "test-proj"
    meetings_dir = proj_dir / "meetings"
    meetings_dir.mkdir(parents=True)

    meeting_data = {
        "id": "kickoff-day1",
        "title": "Project Kickoff",
        "meeting_type": "kickoff",
        "phase": "Prepare",
        "participants": ["PM_ALEX", "ARCH_SARA"],
        "agenda": ["Scope review", "Next steps"],
        "simulated_day": 1,
        "transcript": [
            {"speaker": "PM_ALEX", "text": "Welcome everyone!"},
        ],
        "decisions": ["Use S/4HANA 2023 FPS02"],
        "action_items": [{"owner": "ARCH_SARA", "task": "Draft blueprint", "due_day": 5}],
    }
    (meetings_dir / "kickoff-day1.json").write_text(
        json.dumps(meeting_data), encoding="utf-8"
    )

    monkeypatch.setattr(routes_module, "_project_dir",
                        lambda name: tmp_path / name)

    ml = routes_module._get_meeting_logger("test-proj")
    assert "kickoff-day1" in ml.list_archived()
    log = ml.get_log("kickoff-day1")
    assert log is not None
    assert log.title == "Project Kickoff"
    assert len(log.transcript) == 1
    assert len(log.decisions_made) == 1
    assert len(log.action_items) == 1


# ---------------------------------------------------------------------------
# Entry-point for running directly: python tests/test_api_imports.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    sys.exit(result.returncode)
