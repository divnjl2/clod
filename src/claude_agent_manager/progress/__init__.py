"""
Progress Tracking Module for Claude Agent Manager
==================================================

Provides progress tracking capabilities for agent tasks:
- Subtask-based implementation plans
- Phase tracking with dependencies
- Progress statistics and summaries
- Duration tracking

Integrated from Auto-Claude progress system.
"""

from .tracker import (
    ProgressTracker,
    TaskStatus,
    Subtask,
    Phase,
    ImplementationPlan,
    count_subtasks,
    get_progress_percentage,
    is_build_complete,
    get_next_subtask,
    get_plan_summary,
    format_duration,
)

__all__ = [
    "ProgressTracker",
    "TaskStatus",
    "Subtask",
    "Phase",
    "ImplementationPlan",
    "count_subtasks",
    "get_progress_percentage",
    "is_build_complete",
    "get_next_subtask",
    "get_plan_summary",
    "format_duration",
]
