"""
SAP SIM — Final Report Generator
Phase: 4.5

Compiles all project artifacts into a comprehensive Markdown report suitable
for executive review or project archiving.

The report covers:
    1. Executive Summary
    2. Project Timeline (phases with progress / dates)
    3. Team & Roles
    4. Key Decisions (Markdown table)
    5. Meeting Summary (count by type per phase)
    6. Tool Landscape (registered tools by category / module)
    7. Test Results (coverage, pass/fail, defects)
    8. Lessons Learned (grouped by phase and impact)
    9. Recommendations (derived from HIGH-impact lessons + open decisions)

Persistence:
    projects/<project_name>/final_report.md

Usage::

    from artifacts.final_report import FinalReportGenerator

    gen = FinalReportGenerator(project_name="my-sap-project")
    report = gen.generate_report("my-sap-project")
    gen.save_report(report, "my-sap-project")
    print(report[:500])

Or supply explicit artifact instances (useful in unit tests or simulations
that keep objects in memory rather than on disk)::

    gen = FinalReportGenerator(
        project_name="my-sap-project",
        meeting_logger=my_logger,
        decision_board=my_board,
        tool_registry=my_registry,
        test_strategy=my_strategy,
        lessons_collector=my_collector,
    )
    report = gen.generate_report("my-sap-project")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from artifacts.meeting_logger import MeetingLog, MeetingLogger
from artifacts.decision_board import Decision, DecisionBoard
from artifacts.tool_registry import SimulatedTool, ToolRegistry
from artifacts.test_strategy import TestCase, TestStrategy, TestStatus
from artifacts.lessons_learned import Lesson, LessonsCollector

logger = logging.getLogger(__name__)

# SAP Activate phases in canonical order
_PHASES_ORDERED = ["Discover", "Prepare", "Explore", "Realize", "Deploy", "Run"]

# Project-state JSON filename (produced by the simulation engine)
_PROJECT_JSON = "project.json"


class FinalReportGenerator:
    """
    Compiles all SAP SIM project artifacts into a single Markdown document.

    Parameters
    ----------
    project_name:
        Name of the project (used for locating artifact files on disk).
    projects_root:
        Root directory that contains project sub-directories.
        Defaults to ``../../projects`` relative to this file, which resolves
        to ``<repo-root>/projects``.
    meeting_logger:
        Optional pre-populated :class:`~artifacts.meeting_logger.MeetingLogger`.
        When omitted the generator attempts to load archived logs from disk.
    decision_board:
        Optional pre-populated :class:`~artifacts.decision_board.DecisionBoard`.
        When omitted the generator loads from ``decisions.json``.
    tool_registry:
        Optional pre-populated :class:`~artifacts.tool_registry.ToolRegistry`.
        When omitted the generator loads from ``tools.json``.
    test_strategy:
        Optional pre-populated :class:`~artifacts.test_strategy.TestStrategy`.
        When omitted the generator loads from ``test_strategy.json``.
    lessons_collector:
        Optional pre-populated :class:`~artifacts.lessons_learned.LessonsCollector`.
        When omitted the generator loads from ``lessons.json``.
    """

    def __init__(
        self,
        project_name: str,
        projects_root: str | Path | None = None,
        meeting_logger: Optional[MeetingLogger] = None,
        decision_board: Optional[DecisionBoard] = None,
        tool_registry: Optional[ToolRegistry] = None,
        test_strategy: Optional[TestStrategy] = None,
        lessons_collector: Optional[LessonsCollector] = None,
    ) -> None:
        self.project_name = project_name

        if projects_root is None:
            projects_root = Path(__file__).parent.parent.parent / "projects"
        self.projects_root = Path(projects_root).expanduser().resolve()

        # Artifact instances — populated lazily via _load_artifacts()
        self._meeting_logger = meeting_logger
        self._decision_board = decision_board
        self._tool_registry = tool_registry
        self._test_strategy = test_strategy
        self._lessons_collector = lessons_collector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report(self, project_name: str) -> str:
        """
        Compile all artifacts into a comprehensive Markdown report string.

        Parameters
        ----------
        project_name:
            The project to report on.  Must match an existing project directory
            under ``projects_root`` (or artifacts already supplied at
            construction time).

        Returns
        -------
        str
            A multi-section Markdown document.
        """
        self.project_name = project_name
        self._load_artifacts()

        state = self._load_project_state()
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        sections: list[str] = []

        sections.append(self._section_title(project_name, generated_at, state))
        sections.append(self._section_executive_summary(state))
        sections.append(self._section_timeline(state))
        sections.append(self._section_team(state))
        sections.append(self._section_decisions())
        sections.append(self._section_meetings())
        sections.append(self._section_tools())
        sections.append(self._section_test_results())
        sections.append(self._section_lessons_learned())
        sections.append(self._section_recommendations())
        sections.append(self._section_footer(generated_at))

        return "\n\n".join(sections)

    def save_report(self, report: str, project_name: str) -> Path:
        """
        Write *report* to ``projects/<project_name>/final_report.md``.

        Creates parent directories as needed.

        Parameters
        ----------
        report:
            The Markdown string returned by :meth:`generate_report`.
        project_name:
            Project name; determines the output directory.

        Returns
        -------
        pathlib.Path
            The absolute path of the written file.
        """
        dest = self.projects_root / project_name / "final_report.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(report, encoding="utf-8")
        logger.info("FinalReportGenerator: report saved → %s", dest)
        return dest

    # ------------------------------------------------------------------
    # Artifact loading
    # ------------------------------------------------------------------

    def _load_artifacts(self) -> None:
        """
        Load any artifact instances that were not provided at construction time.

        Each artifact is only loaded if the corresponding instance attribute is
        still ``None``.  Loading failures (missing files) produce empty
        instances so the report renders gracefully even for incomplete projects.
        """
        # MeetingLogger — no standard disk-load method; we build a hollow one.
        # Archived logs are kept in memory and not re-hydrated from disk here
        # (meeting files are individual Markdown exports, not a single store).
        # The simulation engine is expected to pass an in-memory instance.
        if self._meeting_logger is None:
            self._meeting_logger = MeetingLogger(self.project_name)

        # DecisionBoard
        if self._decision_board is None:
            self._decision_board = DecisionBoard(
                project_name=self.project_name,
            )

        # ToolRegistry
        if self._tool_registry is None:
            self._tool_registry = ToolRegistry(project_name=self.project_name)

        # TestStrategy
        if self._test_strategy is None:
            ts_path = (
                self.projects_root / self.project_name / "test_strategy.json"
            )
            if ts_path.exists():
                try:
                    self._test_strategy = TestStrategy.load(self.project_name)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not load TestStrategy: %s", exc)
                    self._test_strategy = TestStrategy(self.project_name)
            else:
                self._test_strategy = TestStrategy(self.project_name)

        # LessonsCollector
        if self._lessons_collector is None:
            ll_path = (
                self.projects_root / self.project_name / "lessons.json"
            )
            if ll_path.exists():
                try:
                    self._lessons_collector = LessonsCollector.load(
                        self.project_name
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not load LessonsCollector: %s", exc)
                    self._lessons_collector = LessonsCollector(self.project_name)
            else:
                self._lessons_collector = LessonsCollector(self.project_name)

    def _load_project_state(self) -> dict[str, Any]:
        """
        Read ``projects/<project_name>/project.json``.

        Returns an empty dict (with sensible defaults) if the file is absent.
        """
        path = self.projects_root / self.project_name / _PROJECT_JSON
        if not path.exists():
            logger.warning("FinalReportGenerator: no project.json at %s", path)
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("FinalReportGenerator: malformed project.json: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    # ── Title block ──────────────────────────────────────────────────

    def _section_title(
        self,
        project_name: str,
        generated_at: str,
        state: dict[str, Any],
    ) -> str:
        industry = state.get("industry", "—")
        methodology = state.get("methodology", "SAP Activate")
        status = state.get("status", "—")
        total_days = state.get("total_days", "—")
        simulated_day = state.get("simulated_day", "—")
        created_at = state.get("created_at", "—")
        scope_text = state.get("scope") or "_Not specified._"

        lines = [
            f"# 📊 Final Project Report — {project_name}",
            "",
            f"> **Generated:** {generated_at}  ",
            f"> **Status:** {status}  ",
            f"> **Industry:** {industry}  ",
            f"> **Methodology:** {methodology}  ",
            f"> **Project Start:** {created_at}  ",
            f"> **Simulated Day:** {simulated_day} / {total_days}",
            "",
            "---",
        ]
        return "\n".join(lines)

    # ── 1. Executive Summary ─────────────────────────────────────────

    def _section_executive_summary(self, state: dict[str, Any]) -> str:
        project_name = state.get("project_name", self.project_name)
        industry = state.get("industry", "—")
        methodology = state.get("methodology", "SAP Activate")
        current_phase = (state.get("current_phase") or "—").title()
        simulated_day = state.get("simulated_day", 0)
        total_days = state.get("total_days", 0)
        scope_text = state.get("scope") or "_Not specified._"

        # Aggregated counts
        decision_summary = (
            self._decision_board.summary() if self._decision_board else {}
        )
        total_decisions = decision_summary.get("total", 0)
        approved_decisions = decision_summary.get("by_status", {}).get("approved", 0)

        all_meetings = self._all_archived_meetings()
        total_meetings = len(all_meetings)

        tool_count = len(self._tool_registry) if self._tool_registry else 0

        test_coverage = (
            self._test_strategy.get_coverage_report() if self._test_strategy else {}
        )
        total_tests = test_coverage.get("total", 0)
        pass_rate = test_coverage.get("pass_rate", 0.0)

        lessons_summary = (
            self._lessons_collector.summary() if self._lessons_collector else {}
        )
        total_lessons = lessons_summary.get("total", 0)

        progress_pct = (
            round((simulated_day / total_days) * 100, 1)
            if total_days
            else 0.0
        )

        lines = [
            "## 1. Executive Summary",
            "",
            f"Project **{project_name}** is an {industry} SAP implementation "
            f"following the **{methodology}** framework.",
            "",
            f"At the time of this report the simulation has completed "
            f"**Day {simulated_day} of {total_days}** ({progress_pct}% of the "
            f"planned timeline), and is currently in the **{current_phase}** phase.",
            "",
            "### Project Snapshot",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Current Phase | {current_phase} |",
            f"| Timeline Progress | Day {simulated_day} / {total_days} ({progress_pct}%) |",
            f"| Total Decisions | {total_decisions} ({approved_decisions} approved) |",
            f"| Meetings Held | {total_meetings} |",
            f"| Tools Registered | {tool_count} |",
            f"| Test Cases | {total_tests} (pass rate {pass_rate:.1%}) |",
            f"| Lessons Learned | {total_lessons} |",
            "",
            "### Scope",
            "",
            scope_text,
        ]
        return "\n".join(lines)

    # ── 2. Project Timeline ──────────────────────────────────────────

    def _section_timeline(self, state: dict[str, Any]) -> str:
        phase_progress: list[dict[str, Any]] = state.get("phase_progress", [])
        current_phase_id = state.get("current_phase", "")
        total_days = state.get("total_days", 0)
        simulated_day = state.get("simulated_day", 0)

        lines = [
            "## 2. Project Timeline",
            "",
            "The following table shows each SAP Activate phase with its "
            "simulated progress.",
            "",
            "| Phase | Status | Progress |",
            "|-------|--------|----------|",
        ]

        if phase_progress:
            for p in phase_progress:
                name = p.get("phase_name", p.get("phase_id", "—"))
                pct = p.get("percentage", 0.0)
                is_current = p.get("is_current", False)
                is_completed = p.get("is_completed", False)

                if is_completed:
                    status_icon = "✅ Completed"
                elif is_current:
                    status_icon = "🔄 In Progress"
                else:
                    pct = 0.0  # future phases have no real progress yet
                    status_icon = "⏳ Pending"

                bar = self._progress_bar(pct)
                lines.append(f"| {name} | {status_icon} | {bar} {pct:.0f}% |")
        else:
            lines.append("| _(no phase data available)_ | — | — |")

        lines += [
            "",
            f"**Overall simulated progress:** Day {simulated_day} / {total_days}",
        ]

        # Milestones
        milestones: list[dict[str, Any]] = state.get("milestones", [])
        if milestones:
            lines += [
                "",
                "### Key Milestones",
                "",
                "| Milestone | Day | Status |",
                "|-----------|-----|--------|",
            ]
            for m in milestones:
                m_name = m.get("name", m.get("title", "—"))
                m_day = m.get("day", m.get("due_day", "—"))
                m_status = m.get("status", "—")
                lines.append(f"| {m_name} | {m_day} | {m_status} |")

        return "\n".join(lines)

    # ── 3. Team & Roles ──────────────────────────────────────────────

    def _section_team(self, state: dict[str, Any]) -> str:
        active_agents: list[Any] = state.get("active_agents", [])

        lines = [
            "## 3. Team & Roles",
            "",
        ]

        if not active_agents:
            lines.append(
                "_No agent roster data found in project state. "
                "Agent information is captured at simulation runtime._"
            )
            return "\n".join(lines)

        lines += [
            "| Agent | Role | Status |",
            "|-------|------|--------|",
        ]

        for agent in active_agents:
            if isinstance(agent, dict):
                name = agent.get("name", agent.get("id", "—"))
                role = agent.get("role", "—")
                status = agent.get("status", "Active")
            else:
                name = str(agent)
                role = "—"
                status = "Active"
            lines.append(f"| {name} | {role} | {status} |")

        return "\n".join(lines)

    # ── 4. Key Decisions ─────────────────────────────────────────────

    def _section_decisions(self) -> str:
        lines = ["## 4. Key Decisions", ""]

        if not self._decision_board:
            lines.append("_No decision board data available._")
            return "\n".join(lines)

        all_decisions = self._decision_board.get_board()
        if not all_decisions:
            lines.append("_No decisions have been recorded._")
            return "\n".join(lines)

        summary = self._decision_board.summary()
        lines += [
            f"**Total decisions:** {summary['total']}  ",
            f"**Approved:** {summary['by_status'].get('approved', 0)} · "
            f"**Rejected:** {summary['by_status'].get('rejected', 0)} · "
            f"**Deferred:** {summary['by_status'].get('deferred', 0)} · "
            f"**Pending:** {summary['by_status'].get('proposed', 0) + summary['by_status'].get('discussed', 0)}",
            "",
            "| # | Title | Category | Status | Proposed By | Day | Votes |",
            "|---|-------|----------|--------|-------------|-----|-------|",
        ]

        for i, d in enumerate(all_decisions, start=1):
            status_icon = {
                "approved": "✅ Approved",
                "rejected": "❌ Rejected",
                "deferred": "⏸ Deferred",
                "discussed": "💬 Discussed",
                "proposed": "🔵 Proposed",
            }.get(d.status, d.status)

            lines.append(
                f"| {i} | {d.title} | {d.category.title()} | {status_icon} "
                f"| {d.proposed_by} | {d.proposed_at_day} | {d.vote_summary()} |"
            )

        # Decisions still pending
        pending = self._decision_board.get_pending()
        if pending:
            lines += [
                "",
                f"> ⚠️ **{len(pending)} decision(s) remain unresolved** and require "
                "attention before project closure.",
            ]

        return "\n".join(lines)

    # ── 5. Meeting Summary ───────────────────────────────────────────

    def _section_meetings(self) -> str:
        lines = ["## 5. Meeting Summary", ""]

        all_meetings = self._all_archived_meetings()

        if not all_meetings:
            lines.append("_No meeting logs are available in this session._")
            return "\n".join(lines)

        total = len(all_meetings)

        # Count by type
        by_type: dict[str, int] = {}
        # Count by phase → type
        by_phase_type: dict[str, dict[str, int]] = {}
        # Action items / decisions tallies
        total_actions = 0
        total_decisions_in_meetings = 0

        for log in all_meetings:
            mtype = log.meeting_type.replace("_", " ").title()
            by_type[mtype] = by_type.get(mtype, 0) + 1

            phase = log.phase or "Unknown"
            if phase not in by_phase_type:
                by_phase_type[phase] = {}
            by_phase_type[phase][mtype] = by_phase_type[phase].get(mtype, 0) + 1

            total_actions += len(log.action_items)
            total_decisions_in_meetings += len(log.decisions_made)

        lines += [
            f"**Total meetings:** {total}  ",
            f"**Total action items:** {total_actions}  ",
            f"**Total decisions recorded in meetings:** {total_decisions_in_meetings}",
            "",
            "### Meetings by Type",
            "",
            "| Meeting Type | Count |",
            "|--------------|-------|",
        ]
        for mtype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {mtype} | {count} |")

        if by_phase_type:
            lines += [
                "",
                "### Meetings by Phase",
                "",
            ]
            # Build a pivot table: phases × types
            all_types_ordered = sorted(
                {t for counts in by_phase_type.values() for t in counts}
            )
            header = "| Phase | " + " | ".join(all_types_ordered) + " | Total |"
            separator = "|-------|" + "-------|" * len(all_types_ordered) + "-------|"
            lines += [header, separator]

            for phase in _PHASES_ORDERED + sorted(
                set(by_phase_type) - set(p.title() for p in _PHASES_ORDERED)
            ):
                # Match case-insensitively
                matched_phase = next(
                    (p for p in by_phase_type if p.lower() == phase.lower()), None
                )
                if matched_phase is None:
                    continue
                counts = by_phase_type[matched_phase]
                row_total = sum(counts.values())
                cells = [str(counts.get(t, 0)) for t in all_types_ordered]
                lines.append(
                    f"| {matched_phase} | " + " | ".join(cells) + f" | {row_total} |"
                )

        return "\n".join(lines)

    # ── 6. Tool Landscape ────────────────────────────────────────────

    def _section_tools(self) -> str:
        lines = ["## 6. Tool Landscape", ""]

        if not self._tool_registry:
            lines.append("_No tool registry data available._")
            return "\n".join(lines)

        all_tools = self._tool_registry.get_all_tools()
        if not all_tools:
            lines.append("_No tools have been registered._")
            return "\n".join(lines)

        stats = self._tool_registry.get_usage_stats()
        lines += [
            f"**Total tools registered:** {stats['total_tools']}  ",
            f"**Total usage events:** {stats['total_usages']}  ",
            f"**Never used:** {len(stats['never_used'])}",
            "",
            "### Tools by Status",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]
        for status, count in sorted(stats["by_status"].items()):
            lines.append(f"| {status.title()} | {count} |")

        lines += [
            "",
            "### Tools by Category",
            "",
            "| Category | Count |",
            "|----------|-------|",
        ]
        for cat, count in sorted(stats["by_category"].items()):
            lines.append(f"| {cat.title()} | {count} |")

        lines += [
            "",
            "### Tools by SAP Module",
            "",
            "| Module | Count |",
            "|--------|-------|",
        ]
        for mod, count in sorted(stats["by_module"].items()):
            lines.append(f"| {mod} | {count} |")

        # Top used tools
        if stats["most_used"]:
            lines += [
                "",
                "### Most Used Tools",
                "",
                "| Tool Name | Usage Count |",
                "|-----------|-------------|",
            ]
            for entry in stats["most_used"]:
                tool = self._tool_registry.get_tool(entry["id"])
                name = tool.name if tool else entry["id"]
                lines.append(f"| {name} | {entry['usage_count']} |")

        # Full catalogue
        lines += [
            "",
            "### Full Catalogue",
            "",
            "| Name | Module | Category | Status | Announced By | Day | Uses | T-Codes |",
            "|------|--------|----------|--------|--------------|-----|------|---------|",
        ]
        for t in all_tools:
            tcodes = ", ".join(t.tcodes) if t.tcodes else "—"
            status_icon = {
                "announced": "📢",
                "in_use": "✅",
                "deprecated": "🚫",
            }.get(t.status, t.status)
            lines.append(
                f"| {t.name} | {t.sap_module} | {t.category.title()} "
                f"| {status_icon} {t.status.title()} | {t.announced_by} "
                f"| {t.announced_at_day} | {t.usage_count} | `{tcodes}` |"
            )

        return "\n".join(lines)

    # ── 7. Test Results ──────────────────────────────────────────────

    def _section_test_results(self) -> str:
        lines = ["## 7. Test Results", ""]

        if not self._test_strategy:
            lines.append("_No test strategy data available._")
            return "\n".join(lines)

        cov = self._test_strategy.get_coverage_report()
        total = cov["total"]

        if total == 0:
            lines.append("_No test cases have been recorded._")
            return "\n".join(lines)

        by_status = cov["by_status"]
        by_type = cov["by_type"]
        by_module = cov["by_module"]
        pass_rate = cov["pass_rate"]
        defect_count = cov["defect_count"]

        passed = by_status.get(TestStatus.PASSED.value, 0)
        failed = by_status.get(TestStatus.FAILED.value, 0)
        blocked = by_status.get(TestStatus.BLOCKED.value, 0)
        in_progress = by_status.get(TestStatus.IN_PROGRESS.value, 0)
        planned = by_status.get(TestStatus.PLANNED.value, 0)

        lines += [
            f"**Total test cases:** {total}  ",
            f"**Pass rate:** {pass_rate:.1%}  ",
            f"**Defects linked:** {defect_count}",
            "",
            "### Status Overview",
            "",
            "| Status | Count | % of Total |",
            "|--------|-------|------------|",
            f"| ✅ Passed | {passed} | {passed/total:.1%} |",
            f"| ❌ Failed | {failed} | {failed/total:.1%} |",
            f"| 🔄 In Progress | {in_progress} | {in_progress/total:.1%} |",
            f"| 🚧 Blocked | {blocked} | {blocked/total:.1%} |",
            f"| 📋 Planned | {planned} | {planned/total:.1%} |",
            "",
            "### Coverage by Test Type",
            "",
            "| Test Type | Count |",
            "|-----------|-------|",
        ]
        for ttype, count in sorted(by_type.items()):
            lines.append(f"| {ttype.replace('_', ' ').title()} | {count} |")

        if by_module:
            lines += [
                "",
                "### Coverage by SAP Module",
                "",
                "| Module | Total | Passed | Failed | Blocked | Planned |",
                "|--------|-------|--------|--------|---------|---------|",
            ]
            for mod, stats in sorted(by_module.items()):
                m_total = stats.get("total", 0)
                m_passed = stats.get(TestStatus.PASSED.value, 0)
                m_failed = stats.get(TestStatus.FAILED.value, 0)
                m_blocked = stats.get(TestStatus.BLOCKED.value, 0)
                m_planned = stats.get(TestStatus.PLANNED.value, 0)
                lines.append(
                    f"| {mod} | {m_total} | {m_passed} | {m_failed} "
                    f"| {m_blocked} | {m_planned} |"
                )

        # Defect list
        defects = self._test_strategy.get_defects()
        if defects:
            lines += [
                "",
                "### Defect Register",
                "",
                "| Test ID | Title | Module | Defect ID |",
                "|---------|-------|--------|-----------|",
            ]
            for tc in defects:
                lines.append(
                    f"| {tc.id} | {tc.title} | {tc.module} "
                    f"| `{tc.defect_id}` |"
                )

        return "\n".join(lines)

    # ── 8. Lessons Learned ───────────────────────────────────────────

    def _section_lessons_learned(self) -> str:
        lines = ["## 8. Lessons Learned", ""]

        if not self._lessons_collector:
            lines.append("_No lessons-learned data available._")
            return "\n".join(lines)

        all_lessons = self._lessons_collector.all_lessons()
        if not all_lessons:
            lines.append("_No lessons have been recorded._")
            return "\n".join(lines)

        summary = self._lessons_collector.summary()
        lines += [
            f"**Total lessons:** {summary['total']}",
            "",
            "### By Impact",
            "",
            "| Impact | Count |",
            "|--------|-------|",
        ]
        for impact, count in sorted(
            summary["by_impact"].items(),
            key=lambda x: ["HIGH", "MEDIUM", "LOW"].index(x[0])
            if x[0] in ["HIGH", "MEDIUM", "LOW"]
            else 99,
        ):
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(impact, "⚪")
            lines.append(f"| {icon} {impact} | {count} |")

        lines += [
            "",
            "### By Category",
            "",
            "| Category | Count |",
            "|----------|-------|",
        ]
        for cat, count in sorted(summary["by_category"].items()):
            lines.append(f"| {cat} | {count} |")

        # Group by phase
        lines += ["", "### Lessons by Phase", ""]
        for phase in _PHASES_ORDERED:
            phase_lessons = self._lessons_collector.get_by_phase(phase)
            if not phase_lessons:
                continue
            lines += [
                f"#### {phase}",
                "",
                "| ID | Title | Category | Impact | Reported By | Day |",
                "|----|-------|----------|--------|-------------|-----|",
            ]
            for ll in phase_lessons:
                impact_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    ll.impact.upper(), "⚪"
                )
                lines.append(
                    f"| {ll.id} | {ll.title} | {ll.category} "
                    f"| {impact_icon} {ll.impact} | {ll.reported_by} "
                    f"| {ll.reported_at_day} |"
                )
            lines.append("")

        # Also render phases not in the canonical list
        unknown_phases = sorted(
            {ll.phase for ll in all_lessons}
            - {p.lower() for p in _PHASES_ORDERED}
            - {p for p in _PHASES_ORDERED}
        )
        for phase in unknown_phases:
            phase_lessons = self._lessons_collector.get_by_phase(phase)
            if not phase_lessons:
                continue
            lines += [
                f"#### {phase}",
                "",
                "| ID | Title | Category | Impact | Reported By | Day |",
                "|----|-------|----------|--------|-------------|-----|",
            ]
            for ll in phase_lessons:
                impact_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    ll.impact.upper(), "⚪"
                )
                lines.append(
                    f"| {ll.id} | {ll.title} | {ll.category} "
                    f"| {impact_icon} {ll.impact} | {ll.reported_by} "
                    f"| {ll.reported_at_day} |"
                )
            lines.append("")

        return "\n".join(lines)

    # ── 9. Recommendations ──────────────────────────────────────────

    def _section_recommendations(self) -> str:
        lines = ["## 9. Recommendations", ""]

        recs: list[str] = []

        # From HIGH-impact lessons
        if self._lessons_collector:
            high_lessons = self._lessons_collector.get_high_impact()
            for ll in high_lessons:
                if ll.recommendation.strip():
                    recs.append(
                        f"**[{ll.category} / HIGH]** {ll.recommendation.strip()} "
                        f"_(Lesson {ll.id})_"
                    )

        # From open (unresolved) decisions
        if self._decision_board:
            pending = self._decision_board.get_pending()
            for d in pending:
                recs.append(
                    f"**[Open Decision]** Resolve pending decision: "
                    f'"{d.title}" (proposed Day {d.proposed_at_day}) — '
                    f"currently {d.status}."
                )

        # From failed/blocked tests
        if self._test_strategy:
            cov = self._test_strategy.get_coverage_report()
            failed_count = cov["by_status"].get(TestStatus.FAILED.value, 0)
            blocked_count = cov["by_status"].get(TestStatus.BLOCKED.value, 0)
            if failed_count:
                recs.append(
                    f"**[Test Quality]** {failed_count} test case(s) have FAILED. "
                    "Review root causes, fix defects, and re-test before go-live."
                )
            if blocked_count:
                recs.append(
                    f"**[Test Readiness]** {blocked_count} test case(s) are BLOCKED. "
                    "Identify and remove blockers to complete test coverage."
                )

        # From never-used tools
        if self._tool_registry:
            stats = self._tool_registry.get_usage_stats()
            never_used_count = len(stats["never_used"])
            if never_used_count:
                recs.append(
                    f"**[Tool Adoption]** {never_used_count} registered tool(s) were "
                    "never used during the simulation. Validate whether they are still "
                    "needed or can be removed from scope."
                )

        if not recs:
            lines.append(
                "_No specific recommendations generated — "
                "all decisions resolved, no failed tests, no high-impact lessons._"
            )
        else:
            for i, rec in enumerate(recs, start=1):
                lines.append(f"{i}. {rec}")
                lines.append("")

        return "\n".join(lines)

    # ── Footer ───────────────────────────────────────────────────────

    @staticmethod
    def _section_footer(generated_at: str) -> str:
        lines = [
            "---",
            "",
            f"*Final report generated by SAP SIM — Phase 4.5 · {generated_at}*",
            "",
            "_This document is auto-generated from simulation artifacts. "
            "All data reflects the simulated project state, not a real SAP implementation._",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_archived_meetings(self) -> list[MeetingLog]:
        """Return all archived (finalised) meetings from the logger."""
        if not self._meeting_logger:
            return []
        archived_ids = self._meeting_logger.list_archived()
        logs = []
        for mid in archived_ids:
            log = self._meeting_logger.get_log(mid)
            if log is not None:
                logs.append(log)
        return logs

    @staticmethod
    def _progress_bar(pct: float, width: int = 10) -> str:
        """
        Return a simple text progress bar, e.g. ``[████░░░░░░]``.

        Parameters
        ----------
        pct:   Completion percentage (0–100).
        width: Total number of bar characters.
        """
        filled = round((pct / 100) * width)
        filled = max(0, min(filled, width))
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
