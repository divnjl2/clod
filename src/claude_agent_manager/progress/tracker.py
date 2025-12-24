"""
Progress Tracker
================

Tracks progress of agent tasks using subtask-based implementation plans.
Supports phases with dependencies, status tracking, and progress statistics.

Integrated from Auto-Claude progress system.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a subtask."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Subtask:
    """A single subtask within a phase."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    agent_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "agent_id": self.agent_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "files_changed": self.files_changed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Subtask":
        """Create from dictionary."""
        status = data.get("status", "pending")
        if isinstance(status, str):
            try:
                status = TaskStatus(status)
            except ValueError:
                status = TaskStatus.PENDING

        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            status=status,
            agent_id=data.get("agent_id"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            files_changed=data.get("files_changed", []),
        )


@dataclass
class Phase:
    """A phase containing multiple subtasks."""
    id: str
    name: str
    phase: int
    subtasks: List[Subtask] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase,
            "description": self.description,
            "depends_on": self.depends_on,
            "subtasks": [s.to_dict() for s in self.subtasks],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Phase":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            phase=data.get("phase", 0),
            description=data.get("description"),
            depends_on=data.get("depends_on", []),
            subtasks=[Subtask.from_dict(s) for s in data.get("subtasks", [])],
        )

    @property
    def completed(self) -> int:
        """Number of completed subtasks."""
        return sum(1 for s in self.subtasks if s.status == TaskStatus.COMPLETED)

    @property
    def total(self) -> int:
        """Total number of subtasks."""
        return len(self.subtasks)

    @property
    def is_complete(self) -> bool:
        """Whether all subtasks are completed."""
        return self.completed == self.total and self.total > 0


@dataclass
class ImplementationPlan:
    """Full implementation plan with phases and subtasks."""
    phases: List[Phase] = field(default_factory=list)
    workflow_type: str = "standard"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    agent_id: Optional[str] = None
    task_name: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "workflow_type": self.workflow_type,
            "phases": [p.to_dict() for p in self.phases],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "agent_id": self.agent_id,
            "task_name": self.task_name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ImplementationPlan":
        """Create from dictionary."""
        return cls(
            workflow_type=data.get("workflow_type", "standard"),
            phases=[Phase.from_dict(p) for p in data.get("phases", [])],
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            agent_id=data.get("agent_id"),
            task_name=data.get("task_name"),
        )

    def save(self, path: Path) -> None:
        """Save plan to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now().isoformat()

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> Optional["ImplementationPlan"]:
        """Load plan from file."""
        path = Path(path)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load plan: {e}")
            return None


class ProgressTracker:
    """
    Tracks progress of implementation plans.

    Usage:
        tracker = ProgressTracker(plan_dir)
        tracker.load_or_create(agent_id, task_name)

        # Add phases and subtasks
        tracker.add_phase("setup", "Project Setup", 1)
        tracker.add_subtask("setup", "s1", "Install dependencies")

        # Update status
        tracker.start_subtask("s1", agent_id)
        tracker.complete_subtask("s1", files_changed=["package.json"])

        # Get progress
        completed, total = tracker.count_subtasks()
        percentage = tracker.get_progress_percentage()
    """

    PLAN_FILENAME = "implementation_plan.json"

    def __init__(self, plan_dir: Path):
        """
        Initialize progress tracker.

        Args:
            plan_dir: Directory to store implementation plan
        """
        self.plan_dir = Path(plan_dir)
        self.plan: Optional[ImplementationPlan] = None

    @property
    def plan_path(self) -> Path:
        """Path to implementation plan file."""
        return self.plan_dir / self.PLAN_FILENAME

    def load_or_create(
        self,
        agent_id: Optional[str] = None,
        task_name: Optional[str] = None,
    ) -> ImplementationPlan:
        """Load existing plan or create new one."""
        self.plan = ImplementationPlan.load(self.plan_path)

        if self.plan is None:
            self.plan = ImplementationPlan(
                created_at=datetime.now().isoformat(),
                agent_id=agent_id,
                task_name=task_name,
            )
            self.save()

        return self.plan

    def save(self) -> None:
        """Save current plan to disk."""
        if self.plan:
            self.plan.save(self.plan_path)

    def add_phase(
        self,
        phase_id: str,
        name: str,
        phase_num: int,
        depends_on: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Phase:
        """Add a new phase to the plan."""
        if self.plan is None:
            self.load_or_create()

        phase = Phase(
            id=phase_id,
            name=name,
            phase=phase_num,
            depends_on=depends_on or [],
            description=description,
        )
        self.plan.phases.append(phase)
        self.save()
        return phase

    def add_subtask(
        self,
        phase_id: str,
        subtask_id: str,
        description: str,
    ) -> Optional[Subtask]:
        """Add a subtask to a phase."""
        if self.plan is None:
            return None

        for phase in self.plan.phases:
            if phase.id == phase_id:
                subtask = Subtask(id=subtask_id, description=description)
                phase.subtasks.append(subtask)
                self.save()
                return subtask

        return None

    def start_subtask(self, subtask_id: str, agent_id: Optional[str] = None) -> bool:
        """Mark a subtask as in progress."""
        if self.plan is None:
            return False

        for phase in self.plan.phases:
            for subtask in phase.subtasks:
                if subtask.id == subtask_id:
                    subtask.status = TaskStatus.IN_PROGRESS
                    subtask.started_at = datetime.now().isoformat()
                    subtask.agent_id = agent_id
                    self.save()
                    return True

        return False

    def complete_subtask(
        self,
        subtask_id: str,
        files_changed: Optional[List[str]] = None,
    ) -> bool:
        """Mark a subtask as completed."""
        if self.plan is None:
            return False

        for phase in self.plan.phases:
            for subtask in phase.subtasks:
                if subtask.id == subtask_id:
                    subtask.status = TaskStatus.COMPLETED
                    subtask.completed_at = datetime.now().isoformat()
                    if files_changed:
                        subtask.files_changed = files_changed
                    self.save()
                    return True

        return False

    def fail_subtask(self, subtask_id: str, error: str) -> bool:
        """Mark a subtask as failed."""
        if self.plan is None:
            return False

        for phase in self.plan.phases:
            for subtask in phase.subtasks:
                if subtask.id == subtask_id:
                    subtask.status = TaskStatus.FAILED
                    subtask.completed_at = datetime.now().isoformat()
                    subtask.error = error
                    self.save()
                    return True

        return False

    def count_subtasks(self) -> Tuple[int, int]:
        """
        Count completed and total subtasks.

        Returns:
            (completed_count, total_count)
        """
        if self.plan is None:
            return 0, 0

        total = 0
        completed = 0

        for phase in self.plan.phases:
            for subtask in phase.subtasks:
                total += 1
                if subtask.status == TaskStatus.COMPLETED:
                    completed += 1

        return completed, total

    def get_progress_percentage(self) -> float:
        """Get progress as a percentage (0-100)."""
        completed, total = self.count_subtasks()
        if total == 0:
            return 0.0
        return (completed / total) * 100

    def is_complete(self) -> bool:
        """Check if all subtasks are completed."""
        completed, total = self.count_subtasks()
        return total > 0 and completed == total

    def get_next_subtask(self) -> Optional[Dict]:
        """
        Find the next subtask to work on, respecting dependencies.

        Returns:
            Dict with subtask info or None if all complete
        """
        if self.plan is None:
            return None

        # Build map of phase completion
        phase_complete = {}
        for phase in self.plan.phases:
            phase_complete[phase.id] = phase.is_complete

        # Find next available subtask
        for phase in self.plan.phases:
            # Check if dependencies are satisfied
            deps_satisfied = all(
                phase_complete.get(dep, False) for dep in phase.depends_on
            )
            if not deps_satisfied:
                continue

            # Find first pending subtask
            for subtask in phase.subtasks:
                if subtask.status == TaskStatus.PENDING:
                    return {
                        "phase_id": phase.id,
                        "phase_name": phase.name,
                        "phase_num": phase.phase,
                        **subtask.to_dict(),
                    }

        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get a detailed summary of progress."""
        if self.plan is None:
            return {
                "workflow_type": None,
                "total_phases": 0,
                "total_subtasks": 0,
                "completed_subtasks": 0,
                "pending_subtasks": 0,
                "in_progress_subtasks": 0,
                "failed_subtasks": 0,
                "phases": [],
            }

        summary = {
            "workflow_type": self.plan.workflow_type,
            "total_phases": len(self.plan.phases),
            "total_subtasks": 0,
            "completed_subtasks": 0,
            "pending_subtasks": 0,
            "in_progress_subtasks": 0,
            "failed_subtasks": 0,
            "phases": [],
        }

        for phase in self.plan.phases:
            phase_info = {
                "id": phase.id,
                "name": phase.name,
                "phase": phase.phase,
                "depends_on": phase.depends_on,
                "completed": 0,
                "total": 0,
                "subtasks": [],
            }

            for subtask in phase.subtasks:
                summary["total_subtasks"] += 1
                phase_info["total"] += 1

                status = subtask.status
                if isinstance(status, str):
                    try:
                        status = TaskStatus(status)
                    except ValueError:
                        status = TaskStatus.PENDING

                if status == TaskStatus.COMPLETED:
                    summary["completed_subtasks"] += 1
                    phase_info["completed"] += 1
                elif status == TaskStatus.IN_PROGRESS:
                    summary["in_progress_subtasks"] += 1
                elif status == TaskStatus.FAILED:
                    summary["failed_subtasks"] += 1
                else:
                    summary["pending_subtasks"] += 1

                phase_info["subtasks"].append({
                    "id": subtask.id,
                    "description": subtask.description,
                    "status": status.value if isinstance(status, TaskStatus) else status,
                })

            summary["phases"].append(phase_info)

        return summary


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def count_subtasks(plan_dir: Path) -> Tuple[int, int]:
    """
    Count completed and total subtasks in a plan directory.

    Args:
        plan_dir: Directory containing implementation_plan.json

    Returns:
        (completed_count, total_count)
    """
    tracker = ProgressTracker(plan_dir)
    tracker.load_or_create()
    return tracker.count_subtasks()


def get_progress_percentage(plan_dir: Path) -> float:
    """
    Get progress as a percentage.

    Args:
        plan_dir: Directory containing implementation_plan.json

    Returns:
        Percentage (0-100)
    """
    tracker = ProgressTracker(plan_dir)
    tracker.load_or_create()
    return tracker.get_progress_percentage()


def is_build_complete(plan_dir: Path) -> bool:
    """
    Check if all subtasks are completed.

    Args:
        plan_dir: Directory containing implementation_plan.json

    Returns:
        True if all complete
    """
    tracker = ProgressTracker(plan_dir)
    tracker.load_or_create()
    return tracker.is_complete()


def get_next_subtask(plan_dir: Path) -> Optional[Dict]:
    """
    Find the next subtask to work on.

    Args:
        plan_dir: Directory containing implementation_plan.json

    Returns:
        Dict with subtask info or None
    """
    tracker = ProgressTracker(plan_dir)
    tracker.load_or_create()
    return tracker.get_next_subtask()


def get_plan_summary(plan_dir: Path) -> Dict[str, Any]:
    """
    Get a detailed summary of the implementation plan.

    Args:
        plan_dir: Directory containing implementation_plan.json

    Returns:
        Summary dict
    """
    tracker = ProgressTracker(plan_dir)
    tracker.load_or_create()
    return tracker.get_summary()


def format_duration(seconds: float) -> str:
    """Format a duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
