"""
Task System - Задачи с зависимостями на основе CrewAI
====================================================

Источник: CrewAI (task.py)
- Task с context (dependencies)
- Sequential/Parallel execution
- Output passing между задачами

Дополнения:
- Интеграция с SharedContext
- Quality gates проверки
- Git worktree привязка
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_agent import BaseAgent


class TaskStatus(Enum):
    """Статус задачи."""
    PENDING = "pending"
    WAITING = "waiting"       # Ждёт зависимости
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"       # Заблокирована
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Приоритет задачи."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskOutput:
    """
    Выходные данные задачи (из CrewAI pattern).

    Содержит результат выполнения и артефакты.
    """
    raw: str                                    # Сырой output
    summary: Optional[str] = None               # Краткое описание
    artifacts: Dict[str, Any] = field(default_factory=dict)  # Артефакты
    files_created: List[str] = field(default_factory=list)   # Созданные файлы
    files_modified: List[str] = field(default_factory=list)  # Изменённые файлы
    interfaces_provided: List[str] = field(default_factory=list)  # Предоставленные интерфейсы


@dataclass
class Task:
    """
    Задача с зависимостями - основа системы координации.

    Источник: CrewAI task.py
    - context: список задач-зависимостей
    - async_execution: параллельное выполнение
    - callback: уведомление о завершении

    Дополнения наши:
    - worktree_path: привязка к git worktree
    - quality_checks: проверки качества
    - interfaces: требуемые/предоставляемые интерфейсы
    """

    id: str
    description: str
    agent: Optional['BaseAgent'] = None
    role: str = ""

    # Dependencies (CrewAI pattern) - КЛЮЧЕВАЯ ФИЧА
    context: List['Task'] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # ID задач

    # Interfaces (наше дополнение)
    required_interfaces: List[str] = field(default_factory=list)
    provides_interfaces: List[str] = field(default_factory=list)

    # Execution
    async_execution: bool = True
    timeout: int = 3600  # секунды
    callback: Optional[Callable[['Task', TaskOutput], None]] = None

    # Git worktree
    worktree_path: Optional[Path] = None
    branch: str = ""

    # Quality
    quality_checks: List[str] = field(default_factory=lambda: [
        "lint", "type_check", "test"
    ])

    # Scope
    scope: List[str] = field(default_factory=list)  # Файлы/директории

    # State
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    output: Optional[TaskOutput] = None
    error: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Events
    _completion_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        """Инициализация после создания."""
        if not self.role and self.agent:
            self.role = self.agent.role

    async def wait_for_dependencies(self) -> bool:
        """
        Ожидание завершения зависимостей (CrewAI pattern).

        Returns:
            True если все зависимости выполнены успешно
        """
        if not self.context:
            return True

        self.status = TaskStatus.WAITING

        # Ждём все зависимости
        for dep_task in self.context:
            if dep_task.status == TaskStatus.FAILED:
                self.status = TaskStatus.BLOCKED
                self.error = f"Dependency {dep_task.id} failed"
                return False

            if dep_task.status != TaskStatus.DONE:
                await dep_task.wait_until_complete()

                if dep_task.status == TaskStatus.FAILED:
                    self.status = TaskStatus.BLOCKED
                    self.error = f"Dependency {dep_task.id} failed"
                    return False

        return True

    async def wait_until_complete(self, timeout: Optional[float] = None) -> bool:
        """
        Ожидание завершения задачи.

        Args:
            timeout: Таймаут в секундах

        Returns:
            True если завершена успешно
        """
        try:
            await asyncio.wait_for(
                self._completion_event.wait(),
                timeout=timeout or self.timeout
            )
            return self.status == TaskStatus.DONE
        except asyncio.TimeoutError:
            self.status = TaskStatus.FAILED
            self.error = "Timeout waiting for completion"
            return False

    def get_context_output(self) -> Dict[str, Any]:
        """
        Получить output всех зависимостей (CrewAI context pattern).

        Агент получает результаты работы предыдущих агентов.
        """
        context_data = {}

        for dep_task in self.context:
            if dep_task.output:
                context_data[dep_task.id] = {
                    "role": dep_task.role,
                    "description": dep_task.description,
                    "output": dep_task.output.raw,
                    "summary": dep_task.output.summary,
                    "artifacts": dep_task.output.artifacts,
                    "interfaces": dep_task.output.interfaces_provided
                }

        return context_data

    async def execute(self) -> TaskOutput:
        """
        Выполнить задачу.

        1. Ждём зависимости
        2. Получаем context от зависимостей
        3. Выполняем через агента
        4. Сохраняем output
        5. Уведомляем о завершении
        """
        # Проверяем агента
        if not self.agent:
            self.status = TaskStatus.FAILED
            self.error = "No agent assigned"
            self._completion_event.set()
            raise ValueError("Task has no agent assigned")

        # Ждём зависимости
        deps_ok = await self.wait_for_dependencies()
        if not deps_ok:
            self._completion_event.set()
            raise RuntimeError(f"Dependencies failed: {self.error}")

        # Получаем context
        context = self.get_context_output()

        # Запускаем
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

        try:
            # Выполняем через агента
            result = await asyncio.wait_for(
                self.agent.execute_task(self.description, context),
                timeout=self.timeout
            )

            # Формируем output
            self.output = TaskOutput(
                raw=result.get("response", ""),
                summary=result.get("summary"),
                artifacts=result.get("artifacts", {}),
                files_created=result.get("files_created", []),
                files_modified=result.get("files_modified", []),
                interfaces_provided=self.provides_interfaces
            )

            self.status = TaskStatus.DONE
            self.completed_at = datetime.now()

            # Callback
            if self.callback:
                self.callback(self, self.output)

        except asyncio.TimeoutError:
            self.status = TaskStatus.FAILED
            self.error = f"Task execution timeout ({self.timeout}s)"

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)

        finally:
            self._completion_event.set()

        if self.status == TaskStatus.FAILED:
            raise RuntimeError(f"Task failed: {self.error}")

        return self.output

    def mark_complete(self, output: TaskOutput):
        """Пометить задачу как выполненную."""
        self.output = output
        self.status = TaskStatus.DONE
        self.completed_at = datetime.now()
        self._completion_event.set()

    def mark_failed(self, error: str):
        """Пометить задачу как проваленную."""
        self.error = error
        self.status = TaskStatus.FAILED
        self._completion_event.set()

    def is_ready(self, completed_task_ids: set) -> bool:
        """
        Проверка готовности к выполнению.

        Задача готова если все её зависимости выполнены.
        """
        if self.status != TaskStatus.PENDING:
            return False

        # Проверяем depends_on
        for dep_id in self.depends_on:
            if dep_id not in completed_task_ids:
                return False

        # Проверяем context tasks
        for dep_task in self.context:
            if dep_task.status != TaskStatus.DONE:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            "id": self.id,
            "description": self.description,
            "role": self.role,
            "status": self.status.value,
            "priority": self.priority.value,
            "depends_on": self.depends_on,
            "required_interfaces": self.required_interfaces,
            "provides_interfaces": self.provides_interfaces,
            "worktree_path": str(self.worktree_path) if self.worktree_path else None,
            "branch": self.branch,
            "scope": self.scope,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def __repr__(self) -> str:
        return f"<Task id={self.id} role={self.role} status={self.status.value}>"


class TaskBuilder:
    """
    Builder для создания задач (fluent interface).

    Пример:
        task = TaskBuilder("implement_api") \
            .description("Implement REST API") \
            .role("backend") \
            .depends_on(["design_task"]) \
            .provides(["payment_api"]) \
            .build()
    """

    def __init__(self, task_id: str):
        self._id = task_id
        self._description = ""
        self._role = ""
        self._agent = None
        self._depends_on = []
        self._context = []
        self._required = []
        self._provides = []
        self._scope = []
        self._worktree = None
        self._branch = ""
        self._priority = TaskPriority.MEDIUM

    def description(self, desc: str) -> 'TaskBuilder':
        self._description = desc
        return self

    def role(self, role: str) -> 'TaskBuilder':
        self._role = role
        return self

    def agent(self, agent: 'BaseAgent') -> 'TaskBuilder':
        self._agent = agent
        return self

    def depends_on(self, task_ids: List[str]) -> 'TaskBuilder':
        self._depends_on = task_ids
        return self

    def context(self, tasks: List[Task]) -> 'TaskBuilder':
        self._context = tasks
        return self

    def requires(self, interfaces: List[str]) -> 'TaskBuilder':
        self._required = interfaces
        return self

    def provides(self, interfaces: List[str]) -> 'TaskBuilder':
        self._provides = interfaces
        return self

    def scope(self, paths: List[str]) -> 'TaskBuilder':
        self._scope = paths
        return self

    def worktree(self, path: Path, branch: str = "") -> 'TaskBuilder':
        self._worktree = path
        self._branch = branch
        return self

    def priority(self, p: TaskPriority) -> 'TaskBuilder':
        self._priority = p
        return self

    def build(self) -> Task:
        return Task(
            id=self._id,
            description=self._description,
            role=self._role,
            agent=self._agent,
            depends_on=self._depends_on,
            context=self._context,
            required_interfaces=self._required,
            provides_interfaces=self._provides,
            scope=self._scope,
            worktree_path=self._worktree,
            branch=self._branch,
            priority=self._priority
        )


def create_task_graph(tasks: List[Task]) -> Dict[str, List[str]]:
    """
    Создать граф зависимостей задач.

    Returns:
        Dict где key=task_id, value=список task_id от которых зависит
    """
    graph = {}

    for task in tasks:
        graph[task.id] = task.depends_on.copy()

        # Добавляем context dependencies
        for ctx_task in task.context:
            if ctx_task.id not in graph[task.id]:
                graph[task.id].append(ctx_task.id)

    return graph


def topological_sort(tasks: List[Task]) -> List[Task]:
    """
    Топологическая сортировка задач (порядок выполнения).

    Используется для определения правильного порядка мержинга.
    """
    graph = create_task_graph(tasks)
    task_map = {t.id: t for t in tasks}

    # Kahn's algorithm
    in_degree = {task_id: 0 for task_id in graph}

    for task_id, deps in graph.items():
        for dep_id in deps:
            if dep_id in in_degree:
                in_degree[task_id] += 1

    queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        task_id = queue.pop(0)
        if task_id in task_map:
            result.append(task_map[task_id])

        for other_id, deps in graph.items():
            if task_id in deps:
                in_degree[other_id] -= 1
                if in_degree[other_id] == 0 and other_id not in [t.id for t in result]:
                    queue.append(other_id)

    return result


def get_parallel_groups(tasks: List[Task]) -> List[List[Task]]:
    """
    Группировка задач для параллельного выполнения.

    Задачи в одной группе могут выполняться параллельно.

    Returns:
        Список групп задач
    """
    sorted_tasks = topological_sort(tasks)
    completed = set()
    groups = []

    while sorted_tasks:
        # Находим все задачи, готовые к выполнению
        ready = [t for t in sorted_tasks if t.is_ready(completed)]

        if not ready:
            # Deadlock или все выполнены
            break

        groups.append(ready)

        # Помечаем как выполненные (для следующей итерации)
        for task in ready:
            completed.add(task.id)
            sorted_tasks.remove(task)

    return groups
