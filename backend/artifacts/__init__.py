"""
SAP SIM — Artifacts Package
Phase: 4.1+

Public exports for all artifact types generated during the simulation.
Import from here to keep consumers decoupled from module internals.

Example:
    from artifacts import MeetingLog, MeetingLogger, TranscriptTurn
    from artifacts import SimulatedTool, ToolRegistry
    from artifacts import TestCase, TestStrategy, TestType, TestStatus
    from artifacts import Lesson, LessonsCollector
    from artifacts import FinalReportGenerator
"""

from artifacts.meeting_logger import MeetingLog, MeetingLogger, TranscriptTurn
from artifacts.decision_board import Decision, DecisionBoard
from artifacts.tool_registry import SimulatedTool, ToolRegistry, ToolUsageEvent
from artifacts.test_strategy import TestCase, TestStrategy, TestType, TestStatus
from artifacts.lessons_learned import Lesson, LessonsCollector
from artifacts.final_report import FinalReportGenerator

__all__ = [
    # Meeting Logger (Phase 4.1)
    "MeetingLog",
    "MeetingLogger",
    "TranscriptTurn",
    # Decision Board (Phase 4.2)
    "Decision",
    "DecisionBoard",
    # Tool Registry (Phase 4.3)
    "SimulatedTool",
    "ToolRegistry",
    "ToolUsageEvent",
    # Test Strategy (Phase 4.4)
    "TestCase",
    "TestStrategy",
    "TestType",
    "TestStatus",
    # Lessons Learned (Phase 4.4)
    "Lesson",
    "LessonsCollector",
    # Final Report Generator (Phase 4.5)
    "FinalReportGenerator",
]
