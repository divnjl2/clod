"""
Task models for Kanban board.

Модели данных для управления задачами.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid


class TaskStatus(str, Enum):
    """Статус задачи (колонки Kanban)."""
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    ARCHIVED = "archived"


class TaskPriority(str, Enum):
    """Приоритет задачи."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, Enum):
    """Тип задачи."""
    FEATURE = "feature"
    BUG = "bug"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"


@dataclass
class Task:
    """Задача для Kanban."""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    priority: TaskPriority = TaskPriority.MEDIUM
    task_type: TaskType = TaskType.FEATURE
    assigned_agent: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    worktree_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result['status'] = self.status.value
        result['priority'] = self.priority.value
        result['task_type'] = self.task_type.value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        return cls(
            id=data['id'],
            title=data['title'],
            description=data.get('description', ''),
            status=TaskStatus(data.get('status', 'backlog')),
            priority=TaskPriority(data.get('priority', 'medium')),
            task_type=TaskType(data.get('task_type', 'feature')),
            assigned_agent=data.get('assigned_agent'),
            labels=data.get('labels', []),
            affected_files=data.get('affected_files', []),
            subtasks=data.get('subtasks', []),
            parent_id=data.get('parent_id'),
            worktree_path=data.get('worktree_path'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            estimated_hours=data.get('estimated_hours'),
            actual_hours=data.get('actual_hours')
        )

    @classmethod
    def create(
        cls,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        task_type: TaskType = TaskType.FEATURE,
        labels: Optional[List[str]] = None
    ) -> Task:
        """Создать новую задачу."""
        task_id = f"{task_type.value[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"
        return cls(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            task_type=task_type,
            labels=labels or []
        )

    def start(self, agent_id: Optional[str] = None) -> None:
        """Начать работу над задачей."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        if agent_id:
            self.assigned_agent = agent_id

    def complete(self) -> None:
        """Завершить задачу."""
        self.status = TaskStatus.DONE
        self.completed_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

        # Вычисляем actual_hours
        if self.started_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.completed_at)
                self.actual_hours = (end - start).total_seconds() / 3600
            except:
                pass

    def move_to(self, status: TaskStatus) -> None:
        """Переместить в статус."""
        self.status = status
        self.updated_at = datetime.now().isoformat()

        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.now().isoformat()
        elif status == TaskStatus.DONE and not self.completed_at:
            self.complete()

    def assign(self, agent_id: str) -> None:
        """Назначить агента."""
        self.assigned_agent = agent_id
        self.updated_at = datetime.now().isoformat()

    def add_subtask(self, subtask_id: str) -> None:
        """Добавить подзадачу."""
        if subtask_id not in self.subtasks:
            self.subtasks.append(subtask_id)
            self.updated_at = datetime.now().isoformat()

    def add_label(self, label: str) -> None:
        """Добавить метку."""
        if label not in self.labels:
            self.labels.append(label)
            self.updated_at = datetime.now().isoformat()

    @property
    def is_blocked(self) -> bool:
        """Проверить, заблокирована ли задача."""
        return "blocked" in self.labels

    @property
    def is_stale(self) -> bool:
        """Проверить, устарела ли задача (>7 дней без обновлений)."""
        try:
            updated = datetime.fromisoformat(self.updated_at)
            days = (datetime.now() - updated).days
            return days > 7 and self.status not in [TaskStatus.DONE, TaskStatus.ARCHIVED]
        except:
            return False

    def __str__(self) -> str:
        return f"[{self.id}] {self.title} ({self.status.value})"
