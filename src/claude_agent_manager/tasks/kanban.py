"""
Kanban Board для управления задачами агентов.

Использование:
    from claude_agent_manager.tasks import KanbanBoard, Task

    board = KanbanBoard(project_path)

    # Создать задачу
    task = board.create_task("Add user auth", priority=TaskPriority.HIGH)

    # Начать работу
    board.start_task(task.id, agent_id="agent-123")

    # Завершить
    board.complete_task(task.id)

    # Показать доску
    print_board(board)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from .models import Task, TaskStatus, TaskPriority, TaskType

console = Console()


class KanbanBoard:
    """
    Kanban доска для управления задачами.

    Поддерживает:
    - Создание/удаление задач
    - Перемещение между статусами
    - Назначение агентов
    - Фильтрация и поиск
    - Персистентность в JSON
    """

    BOARD_FILE = "kanban.json"

    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()
        self.board_dir = self.project_path / ".clod"
        self.board_dir.mkdir(parents=True, exist_ok=True)
        self.board_file = self.board_dir / self.BOARD_FILE

        self.tasks: Dict[str, Task] = {}
        self._load()

    def _load(self) -> None:
        """Загрузить доску из файла."""
        if not self.board_file.exists():
            return

        try:
            with open(self.board_file, encoding='utf-8') as f:
                data = json.load(f)

            for task_data in data.get('tasks', []):
                task = Task.from_dict(task_data)
                self.tasks[task.id] = task
        except (json.JSONDecodeError, KeyError):
            pass

    def _save(self) -> None:
        """Сохранить доску в файл."""
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'tasks': [task.to_dict() for task in self.tasks.values()]
        }

        with open(self.board_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        task_type: TaskType = TaskType.FEATURE,
        labels: Optional[List[str]] = None
    ) -> Task:
        """
        Создать новую задачу.

        Args:
            title: Название задачи
            description: Описание
            priority: Приоритет
            task_type: Тип задачи
            labels: Метки

        Returns:
            Созданная Task
        """
        task = Task.create(title, description, priority, task_type, labels)
        self.tasks[task.id] = task
        self._save()

        console.print(f"[green]Created task: {task}[/green]")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Получить задачу по ID."""
        return self.tasks.get(task_id)

    def update_task(self, task: Task) -> None:
        """Обновить задачу."""
        task.updated_at = datetime.now().isoformat()
        self.tasks[task.id] = task
        self._save()

    def delete_task(self, task_id: str) -> bool:
        """Удалить задачу."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            console.print(f"[red]Deleted task: {task_id}[/red]")
            return True
        return False

    def move_task(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """
        Переместить задачу в другой статус.

        Args:
            task_id: ID задачи
            status: Новый статус

        Returns:
            Обновлённая Task или None
        """
        task = self.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            return None

        old_status = task.status
        task.move_to(status)
        self._save()

        console.print(f"[cyan]Moved {task_id}: {old_status.value} → {status.value}[/cyan]")
        return task

    def start_task(self, task_id: str, agent_id: Optional[str] = None) -> Optional[Task]:
        """
        Начать работу над задачей.

        Args:
            task_id: ID задачи
            agent_id: ID агента (опционально)

        Returns:
            Task или None
        """
        task = self.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            return None

        task.start(agent_id)
        self._save()

        agent_str = f" by {agent_id}" if agent_id else ""
        console.print(f"[green]Started task: {task}{agent_str}[/green]")
        return task

    def complete_task(self, task_id: str) -> Optional[Task]:
        """
        Завершить задачу.

        Args:
            task_id: ID задачи

        Returns:
            Task или None
        """
        task = self.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            return None

        task.complete()
        self._save()

        duration = ""
        if task.actual_hours:
            duration = f" ({task.actual_hours:.1f}h)"

        console.print(f"[green]Completed task: {task}{duration}[/green]")
        return task

    def assign_task(self, task_id: str, agent_id: str) -> Optional[Task]:
        """
        Назначить задачу агенту.

        Args:
            task_id: ID задачи
            agent_id: ID агента

        Returns:
            Task или None
        """
        task = self.get_task(task_id)
        if not task:
            console.print(f"[red]Task not found: {task_id}[/red]")
            return None

        task.assign(agent_id)
        self._save()

        console.print(f"[cyan]Assigned {task_id} to {agent_id}[/cyan]")
        return task

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Получить задачи по статусу."""
        return [t for t in self.tasks.values() if t.status == status]

    def get_tasks_by_agent(self, agent_id: str) -> List[Task]:
        """Получить задачи агента."""
        return [t for t in self.tasks.values() if t.assigned_agent == agent_id]

    def get_tasks_by_priority(self, priority: TaskPriority) -> List[Task]:
        """Получить задачи по приоритету."""
        return [t for t in self.tasks.values() if t.priority == priority]

    def search_tasks(self, query: str) -> List[Task]:
        """Поиск задач по тексту."""
        query_lower = query.lower()
        return [
            t for t in self.tasks.values()
            if query_lower in t.title.lower() or query_lower in t.description.lower()
        ]

    def get_column_counts(self) -> Dict[TaskStatus, int]:
        """Получить количество задач по колонкам."""
        counts = {status: 0 for status in TaskStatus}
        for task in self.tasks.values():
            counts[task.status] += 1
        return counts

    def get_stale_tasks(self) -> List[Task]:
        """Получить устаревшие задачи."""
        return [t for t in self.tasks.values() if t.is_stale]

    def get_blocked_tasks(self) -> List[Task]:
        """Получить заблокированные задачи."""
        return [t for t in self.tasks.values() if t.is_blocked]

    def archive_completed(self, older_than_days: int = 30) -> int:
        """
        Архивировать завершённые задачи.

        Args:
            older_than_days: Архивировать старше N дней

        Returns:
            Количество архивированных
        """
        count = 0
        for task in self.tasks.values():
            if task.status == TaskStatus.DONE and task.completed_at:
                try:
                    completed = datetime.fromisoformat(task.completed_at)
                    days = (datetime.now() - completed).days
                    if days > older_than_days:
                        task.status = TaskStatus.ARCHIVED
                        count += 1
                except:
                    pass

        if count > 0:
            self._save()
            console.print(f"[yellow]Archived {count} tasks[/yellow]")

        return count

    def get_summary(self) -> Dict:
        """Получить сводку по доске."""
        counts = self.get_column_counts()
        total = len(self.tasks)
        done = counts.get(TaskStatus.DONE, 0)
        in_progress = counts.get(TaskStatus.IN_PROGRESS, 0)

        # Средняя длительность завершённых задач
        completed_tasks = [t for t in self.tasks.values() if t.actual_hours]
        avg_hours = sum(t.actual_hours for t in completed_tasks) / len(completed_tasks) if completed_tasks else 0

        return {
            "total_tasks": total,
            "by_status": {s.value: c for s, c in counts.items()},
            "in_progress": in_progress,
            "done": done,
            "done_percent": (done / total * 100) if total > 0 else 0,
            "stale_count": len(self.get_stale_tasks()),
            "blocked_count": len(self.get_blocked_tasks()),
            "avg_completion_hours": avg_hours
        }


def print_board(board: KanbanBoard, show_archived: bool = False) -> None:
    """
    Красиво вывести Kanban доску.

    Args:
        board: KanbanBoard
        show_archived: Показывать ли архивные задачи
    """
    columns_to_show = [
        TaskStatus.BACKLOG,
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.IN_REVIEW,
        TaskStatus.DONE
    ]

    if show_archived:
        columns_to_show.append(TaskStatus.ARCHIVED)

    column_panels = []

    priority_colors = {
        TaskPriority.URGENT: "red",
        TaskPriority.HIGH: "orange1",
        TaskPriority.MEDIUM: "yellow",
        TaskPriority.LOW: "dim"
    }

    type_icons = {
        TaskType.FEATURE: "✨",
        TaskType.BUG: "🐛",
        TaskType.REFACTOR: "🔧",
        TaskType.DOCS: "📝",
        TaskType.TEST: "🧪",
        TaskType.CHORE: "🔨"
    }

    for status in columns_to_show:
        tasks = board.get_tasks_by_status(status)

        # Сортируем по приоритету
        priority_order = [TaskPriority.URGENT, TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]
        tasks.sort(key=lambda t: priority_order.index(t.priority))

        lines = []
        for task in tasks[:10]:  # Показываем до 10 задач в колонке
            color = priority_colors.get(task.priority, "white")
            icon = type_icons.get(task.task_type, "")

            # Форматируем строку задачи
            title = task.title[:25] + "..." if len(task.title) > 25 else task.title
            line = f"[{color}]{icon} {task.id}[/{color}]\n  {title}"

            if task.assigned_agent:
                line += f"\n  [dim]→ {task.assigned_agent}[/dim]"

            lines.append(line)

        if len(tasks) > 10:
            lines.append(f"[dim]... +{len(tasks) - 10} more[/dim]")

        content = "\n\n".join(lines) if lines else "[dim]No tasks[/dim]"

        # Цвет рамки колонки
        border_colors = {
            TaskStatus.BACKLOG: "dim",
            TaskStatus.TODO: "blue",
            TaskStatus.IN_PROGRESS: "yellow",
            TaskStatus.IN_REVIEW: "magenta",
            TaskStatus.DONE: "green",
            TaskStatus.ARCHIVED: "dim"
        }

        column_panels.append(Panel(
            content,
            title=f"{status.value.replace('_', ' ').title()} ({len(tasks)})",
            border_style=border_colors.get(status, "white"),
            width=35
        ))

    console.print(Columns(column_panels))

    # Сводка
    summary = board.get_summary()
    console.print(f"\n[dim]Total: {summary['total_tasks']} tasks | "
                  f"Done: {summary['done_percent']:.0f}% | "
                  f"Stale: {summary['stale_count']} | "
                  f"Blocked: {summary['blocked_count']}[/dim]")


def print_task_detail(task: Task) -> None:
    """Вывести детали задачи."""
    priority_colors = {
        TaskPriority.URGENT: "red",
        TaskPriority.HIGH: "orange1",
        TaskPriority.MEDIUM: "yellow",
        TaskPriority.LOW: "dim"
    }

    content = f"""
**ID:** {task.id}
**Title:** {task.title}
**Status:** {task.status.value}
**Priority:** [{priority_colors.get(task.priority, 'white')}]{task.priority.value}[/{priority_colors.get(task.priority, 'white')}]
**Type:** {task.task_type.value}
**Assigned:** {task.assigned_agent or 'Unassigned'}

**Description:**
{task.description or 'No description'}

**Labels:** {', '.join(task.labels) if task.labels else 'None'}
**Files:** {', '.join(task.affected_files[:5]) if task.affected_files else 'None'}

**Created:** {task.created_at[:19]}
**Updated:** {task.updated_at[:19]}
"""

    if task.started_at:
        content += f"**Started:** {task.started_at[:19]}\n"
    if task.completed_at:
        content += f"**Completed:** {task.completed_at[:19]}\n"
    if task.actual_hours:
        content += f"**Duration:** {task.actual_hours:.1f} hours\n"

    console.print(Panel(content, title=f"Task: {task.id}", border_style="cyan"))
