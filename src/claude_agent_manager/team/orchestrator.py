"""
Team Orchestrator - Полная интеграция всех компонентов
=====================================================

Объединяет:
- AutoGen: Multi-agent coordination, GroupChat
- CrewAI: Task dependencies, context passing
- SWE-agent: Coding prompts
- Aider: Git operations, incremental commits
- MetaGPT: Role-based agents
- DevOps-GPT: Task decomposition

Наши уникальные дополнения:
- Git Worktrees для изоляции
- SharedContext для координации
- Smart Merge с AI
- Quality Gates
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout

from anthropic import Anthropic

# Наши модули
from .shared_context import SharedContext, AgentUpdate, SharedInterface
from .task import Task, TaskStatus, TaskOutput, TaskBuilder, topological_sort, get_parallel_groups
from .base_agent import BaseAgent, AgentConfig
from .roles import create_agent, get_role_dependencies, get_available_roles
from .git_operations import GitOperations, MergeResult
from .quality_gates import QualityGates, QualityGateEnforcer, QualityStatus
from .prompts import get_prompt_for_role, CLARIFICATION_PROMPT

console = Console()


class ExecutionMode(Enum):
    """Режим выполнения."""
    SEQUENTIAL = "sequential"  # По очереди
    PARALLEL = "parallel"      # Все сразу
    SMART = "smart"            # Умный - зависимости + параллельность


@dataclass
class TeamPlan:
    """План выполнения команды."""
    project_path: Path
    main_task: str
    tasks: List[Task]
    execution_mode: ExecutionMode = ExecutionMode.SMART
    created_at: datetime = field(default_factory=datetime.now)

    def get_ready_tasks(self, completed: Set[str]) -> List[Task]:
        """Получить задачи готовые к выполнению."""
        return [t for t in self.tasks if t.is_ready(completed)]

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация."""
        return {
            "project_path": str(self.project_path),
            "main_task": self.main_task,
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_mode": self.execution_mode.value,
            "created_at": self.created_at.isoformat()
        }


class TeamOrchestrator:
    """
    Главный оркестратор команды агентов.

    Интеграция лучших практик:
    - AutoGen: GroupChat, speaker selection
    - CrewAI: Task dependencies, context
    - Aider: Git worktrees, incremental commits
    - MetaGPT: Roles, structured workflow
    - DevOps-GPT: Task decomposition
    """

    # Model mapping for UI -> API
    MODEL_MAPPING = {
        "auto": "claude-sonnet-4-20250514",  # Default to balanced
        "haiku": "claude-3-haiku-20240307",
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "local": "llama3:70b",  # For Ollama
    }

    def __init__(
        self,
        project_path: Path,
        max_parallel: int = 3,
        auto_merge: bool = True,
        quality_gates: bool = True,
        model: str = "auto"
    ):
        self.project_path = Path(project_path).resolve()
        self.max_parallel = max_parallel
        self.auto_merge = auto_merge
        self.use_quality_gates = quality_gates

        # Resolve model name
        self.model = self.MODEL_MAPPING.get(model, model)

        # Check if git repo exists
        self.is_git_repo = (self.project_path / ".git").exists()

        # Git операции (только если это git репозиторий)
        if self.is_git_repo:
            self.git = GitOperations(self.project_path)
            self.base_branch = self.git.get_base_branch()
        else:
            self.git = None
            self.base_branch = None
            console.print("[yellow]Note: Not a git repository. Working in local mode (no worktrees/branches).[/yellow]")

        # Shared context
        context_dir = self.project_path / ".claude-team"
        context_dir.mkdir(exist_ok=True)
        self.shared_context = SharedContext(context_dir / "shared_context.json")

        # Quality gates
        if quality_gates:
            self.quality = QualityGates(self.project_path)
            self.enforcer = QualityGateEnforcer(self.quality)
        else:
            self.quality = None
            self.enforcer = None

        # Claude client
        self.client = Anthropic()

        # Состояние
        self.plan: Optional[TeamPlan] = None
        self.agents: Dict[str, BaseAgent] = {}
        self.completed_tasks: Set[str] = set()
        self.worktrees: Dict[str, Path] = {}

    # =========================================================================
    # PLANNING (DevOps-GPT pattern)
    # =========================================================================

    async def create_plan(self, task_description: str) -> TeamPlan:
        """
        Создать план выполнения.

        Источник: DevOps-GPT task decomposition
        """
        console.print(Panel(
            f"[bold cyan]Creating execution plan...[/bold cyan]\n\n{task_description}",
            title="Planning"
        ))

        # Анализируем проект
        analysis = self._analyze_project()

        # Промпт для планирования
        planning_prompt = f"""Analyze this development task and create an execution plan.

TASK: {task_description}

PROJECT ANALYSIS:
{json.dumps(analysis, indent=2)}

AVAILABLE ROLES:
{json.dumps(get_available_roles(), indent=2)}

ROLE DEPENDENCIES (who waits for whom):
{json.dumps(get_role_dependencies(), indent=2)}

Create a JSON plan with this EXACT structure:
{{
  "tasks": [
    {{
      "id": "unique_task_id",
      "role": "architect|backend|frontend|qa|reviewer",
      "description": "Clear description of what this agent will do",
      "depends_on": ["task_id_that_must_complete_first"],
      "required_interfaces": ["api_spec", "db_schema"],
      "provides_interfaces": ["payment_api", "user_schema"],
      "scope": ["files or directories this agent will work on"]
    }}
  ]
}}

RULES:
1. Start with architect for design tasks
2. Backend before frontend if they share API
3. QA after implementation
4. Reviewer last
5. Break into parallel tasks when possible
6. Each task should be focused (single responsibility)
7. Define clear interfaces between agents

Output ONLY valid JSON, no explanations."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": planning_prompt}]
        )
        console.print(f"[dim]Using model: {self.model}[/dim]")

        # Парсим план
        try:
            plan_text = response.content[0].text
            # Убираем markdown если есть
            if "```json" in plan_text:
                plan_text = plan_text.split("```json")[1].split("```")[0]
            elif "```" in plan_text:
                plan_text = plan_text.split("```")[1].split("```")[0]

            plan_json = json.loads(plan_text)
        except json.JSONDecodeError as e:
            console.print(f"[red]Failed to parse plan: {e}[/red]")
            # Fallback план
            plan_json = {
                "tasks": [
                    {
                        "id": "architect_design",
                        "role": "architect",
                        "description": f"Design architecture for: {task_description}",
                        "depends_on": [],
                        "provides_interfaces": ["architecture"]
                    },
                    {
                        "id": "backend_impl",
                        "role": "backend",
                        "description": f"Implement backend for: {task_description}",
                        "depends_on": ["architect_design"],
                        "required_interfaces": ["architecture"]
                    }
                ]
            }

        # Создаем Task объекты
        tasks = []
        task_map: Dict[str, Task] = {}

        for task_data in plan_json.get("tasks", []):
            task = Task(
                id=task_data["id"],
                role=task_data["role"],
                description=task_data["description"],
                depends_on=task_data.get("depends_on", []),
                required_interfaces=task_data.get("required_interfaces", []),
                provides_interfaces=task_data.get("provides_interfaces", []),
                scope=task_data.get("scope", [])
            )
            tasks.append(task)
            task_map[task.id] = task

        # Связываем context (CrewAI pattern)
        for task in tasks:
            task.context = [
                task_map[dep_id]
                for dep_id in task.depends_on
                if dep_id in task_map
            ]

        self.plan = TeamPlan(
            project_path=self.project_path,
            main_task=task_description,
            tasks=tasks,
            execution_mode=ExecutionMode.SMART
        )

        # Показываем план
        self._display_plan()

        return self.plan

    def _analyze_project(self) -> Dict[str, Any]:
        """Быстрый анализ проекта."""
        analysis = {
            "frameworks": [],
            "languages": [],
            "has_frontend": False,
            "has_backend": False,
            "has_tests": False,
            "files_count": 0
        }

        # Python
        if (self.project_path / "pyproject.toml").exists():
            analysis["languages"].append("python")
        if (self.project_path / "requirements.txt").exists():
            analysis["languages"].append("python")

        # JavaScript/TypeScript
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            analysis["languages"].append("javascript")
            try:
                pkg = json.loads(pkg_json.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in deps:
                    analysis["frameworks"].append("react")
                if "vue" in deps:
                    analysis["frameworks"].append("vue")
                if "express" in deps or "fastify" in deps:
                    analysis["frameworks"].append("node-backend")
            except Exception:
                pass

        # Структура
        for item in self.project_path.iterdir():
            if item.name.startswith(".") or item.name in ["node_modules", "__pycache__", ".git"]:
                continue

            name_lower = item.name.lower()
            if name_lower in ["src", "frontend", "client", "ui", "app"]:
                analysis["has_frontend"] = True
            if name_lower in ["api", "backend", "server", "services"]:
                analysis["has_backend"] = True
            if name_lower in ["tests", "test", "__tests__"]:
                analysis["has_tests"] = True

        # Считаем файлы
        try:
            if self.is_git_repo and self.git:
                analysis["files_count"] = len(self.git.get_tracked_files())
            else:
                # Count files manually for non-git repos
                analysis["files_count"] = sum(1 for _ in self.project_path.rglob("*") if _.is_file())
        except Exception:
            pass

        return analysis

    def _display_plan(self):
        """Отобразить план."""
        if not self.plan:
            return

        table = Table(title="Execution Plan")
        table.add_column("Task", style="cyan")
        table.add_column("Role", style="magenta")
        table.add_column("Depends On", style="dim")
        table.add_column("Provides", style="green")

        for task in self.plan.tasks:
            table.add_row(
                task.id,
                task.role,
                ", ".join(task.depends_on) or "-",
                ", ".join(task.provides_interfaces) or "-"
            )

        console.print(table)

    # =========================================================================
    # WORKTREE MANAGEMENT (Aider + Auto-Claude pattern)
    # =========================================================================

    def setup_worktree(self, task: Task) -> Path:
        """Создать worktree для задачи (или работать локально если не git repo)."""
        # Если не git репозиторий - работаем прямо в project_path
        if not self.is_git_repo or not self.git:
            task.worktree_path = self.project_path
            task.branch = None
            return self.project_path

        worktree_dir = self.project_path / ".worktrees"
        worktree_dir.mkdir(exist_ok=True)

        worktree_path = worktree_dir / task.id
        branch_name = f"agent/{task.role}/{task.id}"

        if worktree_path.exists():
            # Уже существует
            return worktree_path

        try:
            self.git.create_worktree(worktree_path, branch_name, self.base_branch)
            self.worktrees[task.id] = worktree_path
            task.worktree_path = worktree_path
            task.branch = branch_name
            console.print(f"[green]Created worktree: {worktree_path}[/green]")
            return worktree_path
        except Exception as e:
            console.print(f"[red]Failed to create worktree: {e}[/red]")
            # Fallback - работаем в основном репозитории
            return self.project_path

    def cleanup_worktrees(self):
        """Очистить worktrees."""
        if not self.is_git_repo or not self.git:
            return  # Нечего чистить в локальном режиме

        for task_id, path in self.worktrees.items():
            try:
                self.git.remove_worktree(path)
                console.print(f"[dim]Removed worktree: {path}[/dim]")
            except Exception:
                pass
        self.worktrees.clear()

    # =========================================================================
    # AGENT MANAGEMENT
    # =========================================================================

    async def spawn_agent(self, task: Task) -> BaseAgent:
        """Создать агента для задачи."""
        # Создаём worktree
        worktree_path = self.setup_worktree(task)

        # Создаём агента нужной роли
        agent = create_agent(
            role=task.role,
            worktree_path=worktree_path,
            shared_context=self.shared_context
        )

        task.agent = agent
        self.agents[task.id] = agent

        # Обновляем shared context
        await self.shared_context.update_agent_status(AgentUpdate(
            agent_id=task.id,
            role=task.role,
            timestamp=datetime.now().isoformat(),
            status=TaskStatus.PENDING,
            message=f"Agent spawned for: {task.description[:50]}"
        ))

        return agent

    async def run_agent_task(self, task: Task) -> TaskOutput:
        """Запустить агента на выполнение задачи."""
        # Spawn agent если нет
        if not task.agent:
            await self.spawn_agent(task)

        # Обновляем статус
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        await self.shared_context.update_agent_status(AgentUpdate(
            agent_id=task.id,
            role=task.role,
            timestamp=datetime.now().isoformat(),
            status=TaskStatus.IN_PROGRESS,
            message=f"Working on: {task.description[:50]}"
        ))

        console.print(f"[cyan]{task.role}[/cyan] started: {task.description[:60]}...")

        try:
            # Получаем контекст от зависимостей (CrewAI pattern)
            context = task.get_context_output()

            # Добавляем team status
            team_status = await self.shared_context.export_summary()
            if team_status:
                context["_team_status"] = team_status

            # Выполняем задачу
            result = await task.agent.execute_task(task.description, context)

            # Формируем output
            output = TaskOutput(
                raw=result.get("response", ""),
                summary=result.get("summary", ""),
                artifacts=result.get("artifacts", {}),
                interfaces_provided=task.provides_interfaces
            )

            # Регистрируем интерфейсы
            for interface_name in task.provides_interfaces:
                await self.shared_context.register_interface(SharedInterface(
                    name=interface_name,
                    type="output",
                    owner=task.id,
                    spec={"task": task.description},
                    status="ready"
                ))

            # Обновляем статус
            task.status = TaskStatus.DONE
            task.output = output
            task.completed_at = datetime.now()

            await self.shared_context.update_agent_status(AgentUpdate(
                agent_id=task.id,
                role=task.role,
                timestamp=datetime.now().isoformat(),
                status=TaskStatus.DONE,
                message=f"Completed: {task.description[:50]}",
                artifacts=result.get("artifacts", {})
            ))

            console.print(f"[green]?[/green] {task.role} completed: {task.id}")

            return output

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

            await self.shared_context.update_agent_status(AgentUpdate(
                agent_id=task.id,
                role=task.role,
                timestamp=datetime.now().isoformat(),
                status=TaskStatus.FAILED,
                message=f"Failed: {str(e)}"
            ))

            console.print(f"[red]?[/red] {task.role} failed: {str(e)}")
            raise

    # =========================================================================
    # EXECUTION (CrewAI + AutoGen patterns)
    # =========================================================================

    async def execute_plan(self) -> Dict[str, Any]:
        """
        Выполнить план.

        Использует:
        - CrewAI: Task dependencies, context passing
        - AutoGen: Parallel execution, coordination
        """
        if not self.plan:
            raise ValueError("No plan created. Call create_plan() first.")

        console.print(Panel(
            f"[bold]Executing:[/bold] {self.plan.main_task}\n"
            f"[dim]Tasks: {len(self.plan.tasks)} | Mode: {self.plan.execution_mode.value}[/dim]",
            title="Execution Started"
        ))

        results = {}

        if self.plan.execution_mode == ExecutionMode.SEQUENTIAL:
            # Последовательное выполнение
            for task in self.plan.tasks:
                output = await self.run_agent_task(task)
                results[task.id] = output
                self.completed_tasks.add(task.id)

        elif self.plan.execution_mode == ExecutionMode.PARALLEL:
            # Параллельное выполнение (до max_parallel)
            batch = self.plan.tasks[:self.max_parallel]
            outputs = await asyncio.gather(*[
                self.run_agent_task(task) for task in batch
            ], return_exceptions=True)

            for task, output in zip(batch, outputs):
                if isinstance(output, Exception):
                    results[task.id] = {"error": str(output)}
                else:
                    results[task.id] = output
                    self.completed_tasks.add(task.id)

        else:  # SMART mode
            # Умное выполнение с учётом зависимостей
            results = await self._execute_smart()

        # Quality gates перед мержом
        if self.use_quality_gates and self.enforcer:
            console.print("\n[cyan]Running quality gates...[/cyan]")
            can_merge, message = self.enforcer.check_before_merge()
            console.print(f"Quality: {message}")

            if not can_merge:
                console.print("[yellow]Warning: Quality gates failed, merge may have issues[/yellow]")

        # Auto-merge
        if self.auto_merge:
            await self.merge_all_branches()

        # Cleanup
        console.print("\n[dim]Cleaning up worktrees...[/dim]")
        self.cleanup_worktrees()

        console.print(Panel(
            f"[bold green]Team task completed![/bold green]\n"
            f"Tasks: {len(self.completed_tasks)}/{len(self.plan.tasks)} completed",
            title="Done"
        ))

        return results

    async def _execute_smart(self) -> Dict[str, Any]:
        """Умное выполнение с зависимостями."""
        results = {}
        pending_tasks = set(t.id for t in self.plan.tasks)

        while pending_tasks:
            # Находим готовые задачи
            ready_tasks = [
                t for t in self.plan.tasks
                if t.id in pending_tasks and t.is_ready(self.completed_tasks)
            ]

            if not ready_tasks:
                # Проверяем на deadlock
                blocked = [t for t in self.plan.tasks if t.id in pending_tasks]
                if blocked:
                    console.print(f"[yellow]Warning: {len(blocked)} tasks blocked[/yellow]")
                    for t in blocked:
                        console.print(f"  - {t.id} waiting for: {t.depends_on}")
                break

            # Берём batch
            batch = ready_tasks[:self.max_parallel]
            console.print(f"\n[cyan]Executing batch: {[t.id for t in batch]}[/cyan]")

            # Параллельное выполнение
            outputs = await asyncio.gather(*[
                self.run_agent_task(task) for task in batch
            ], return_exceptions=True)

            for task, output in zip(batch, outputs):
                pending_tasks.discard(task.id)

                if isinstance(output, Exception):
                    results[task.id] = {"error": str(output)}
                    console.print(f"[red]Task {task.id} failed: {output}[/red]")
                else:
                    results[task.id] = output
                    self.completed_tasks.add(task.id)

        return results

    # =========================================================================
    # MERGE (Aider pattern + наше)
    # =========================================================================

    async def merge_all_branches(self):
        """Мержинг всех веток агентов."""
        if not self.plan:
            return

        # В локальном режиме нечего мержить
        if not self.is_git_repo or not self.git:
            console.print("[yellow]Local mode: No branches to merge[/yellow]")
            return

        console.print("\n[cyan]Merging agent branches...[/cyan]")

        # Переключаемся на base branch
        self.git.checkout(self.base_branch)

        # Сортируем по зависимостям
        sorted_tasks = topological_sort(self.plan.tasks)
        merged = set()

        for task in sorted_tasks:
            if task.status != TaskStatus.DONE:
                continue

            if not task.branch:
                continue

            # Проверяем зависимости
            deps_merged = all(
                dep_id in merged or dep_id not in [t.id for t in self.plan.tasks]
                for dep_id in task.depends_on
            )

            if not deps_merged:
                console.print(f"[yellow]Skipping {task.branch}: dependencies not merged[/yellow]")
                continue

            console.print(f"Merging {task.branch}...")
            result = self.git.merge(
                task.branch,
                message=f"Merge {task.role}: {task.description[:50]}"
            )

            if result == MergeResult.SUCCESS:
                merged.add(task.id)
                console.print(f"[green]?[/green] Merged {task.branch}")
            elif result == MergeResult.CONFLICT:
                console.print(f"[yellow]Conflict in {task.branch}[/yellow]")
                # TODO: AI conflict resolution
                self.git.abort_merge()
            else:
                console.print(f"[red]Failed to merge {task.branch}[/red]")

        console.print(f"\n[green]Merged {len(merged)}/{len(self.plan.tasks)} branches[/green]")

    # =========================================================================
    # STATUS & MONITORING
    # =========================================================================

    def print_status(self):
        """Показать статус."""
        if not self.plan:
            console.print("[yellow]No active plan[/yellow]")
            return

        table = Table(title="Team Status")
        table.add_column("Task", style="cyan")
        table.add_column("Role")
        table.add_column("Status")
        table.add_column("Branch", style="dim")

        status_colors = {
            TaskStatus.PENDING: "dim",
            TaskStatus.WAITING: "yellow",
            TaskStatus.IN_PROGRESS: "cyan",
            TaskStatus.BLOCKED: "red",
            TaskStatus.DONE: "green",
            TaskStatus.FAILED: "red bold"
        }

        for task in self.plan.tasks:
            color = status_colors.get(task.status, "white")
            table.add_row(
                task.id,
                task.role,
                f"[{color}]{task.status.value}[/{color}]",
                task.branch or "-"
            )

        console.print(table)

    async def get_team_summary(self) -> Dict[str, Any]:
        """Получить summary команды."""
        context = await self.shared_context.read()

        return {
            "plan": self.plan.to_dict() if self.plan else None,
            "completed": list(self.completed_tasks),
            "agents": context.get("agents", {}),
            "interfaces": context.get("interfaces", {}),
            "worktrees": {k: str(v) for k, v in self.worktrees.items()}
        }


# =============================================================================
# QUICK START FUNCTIONS
# =============================================================================

async def run_team_task(
    project_path: str,
    task: str,
    max_parallel: int = 3,
    model: str = "auto"
) -> Dict[str, Any]:
    """
    Быстрый запуск командной задачи.

    Пример:
        results = await run_team_task(
            "~/my-project",
            "Add user authentication with JWT",
            model="sonnet"  # или "haiku", "opus", "local"
        )
    """
    orchestrator = TeamOrchestrator(
        Path(project_path).expanduser(),
        max_parallel=max_parallel,
        model=model
    )

    await orchestrator.create_plan(task)
    results = await orchestrator.execute_plan()

    return results


def quick_plan(project_path: str, task: str, model: str = "auto") -> TeamPlan:
    """Быстрое создание плана (синхронно)."""
    orchestrator = TeamOrchestrator(Path(project_path).expanduser(), model=model)
    return asyncio.run(orchestrator.create_plan(task))
