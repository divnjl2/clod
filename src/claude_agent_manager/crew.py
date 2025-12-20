"""
Оркестрация через clod агентов (без внешних API).

Главный агент анализирует задачу и создаёт субагентов через наш manager.
Каждый субагент — реальный Claude Code с изолированной памятью.

Использование:
    cam crew "Добавить OAuth авторизацию" --project ./my-app
"""

from __future__ import annotations

import json
import os
import time
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
import threading
import queue

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.layout import Layout

console = Console()


# ============================================================================
# AGENT ROLES
# ============================================================================

class AgentRole(Enum):
    """Роли агентов."""
    ORCHESTRATOR = "orchestrator"
    ARCHITECT = "architect"
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    TESTS = "tests"
    DEVOPS = "devops"
    DOCS = "docs"
    REVIEWER = "reviewer"


ROLE_PROMPTS = {
    AgentRole.ORCHESTRATOR: """You are the Lead Orchestrator. Your job is to:
1. Analyze the task and break it into subtasks
2. Coordinate other agents
3. Merge results and resolve conflicts
4. Ensure the final solution is complete

You have access to other specialized agents. Delegate work appropriately.""",

    AgentRole.ARCHITECT: """You are the Software Architect. Your job is to:
1. Analyze the codebase structure
2. Design the solution architecture
3. Define interfaces between components
4. Ensure consistency and best practices

Focus on high-level design, not implementation details.""",

    AgentRole.BACKEND: """You are the Backend Developer. Your job is to:
1. Implement server-side logic
2. Create API endpoints
3. Handle data processing
4. Ensure security and performance

Focus on: {scope}""",

    AgentRole.FRONTEND: """You are the Frontend Developer. Your job is to:
1. Implement UI components
2. Handle state management
3. Create responsive designs
4. Ensure good UX

Focus on: {scope}""",

    AgentRole.DATABASE: """You are the Database Engineer. Your job is to:
1. Design database schemas
2. Write migrations
3. Optimize queries
4. Ensure data integrity

Focus on: {scope}""",

    AgentRole.TESTS: """You are the QA Engineer. Your job is to:
1. Write unit tests
2. Create integration tests
3. Test edge cases
4. Ensure code coverage

Focus on: {scope}""",

    AgentRole.DEVOPS: """You are the DevOps Engineer. Your job is to:
1. Setup CI/CD pipelines
2. Configure deployments
3. Manage infrastructure
4. Ensure reliability

Focus on: {scope}""",

    AgentRole.DOCS: """You are the Technical Writer. Your job is to:
1. Write documentation
2. Create API docs
3. Update README
4. Add code comments

Focus on: {scope}""",

    AgentRole.REVIEWER: """You are the Code Reviewer. Your job is to:
1. Review all changes
2. Check for bugs
3. Ensure best practices
4. Approve or request changes

Be thorough but constructive.""",
}


# ============================================================================
# SUBTASK DEFINITION
# ============================================================================

@dataclass
class SubTask:
    """Подзадача для субагента."""
    id: str
    role: AgentRole
    description: str
    scope: List[str]  # Файлы/директории для работы
    prompt: str = ""
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, done, failed
    result: str = ""
    agent_id: Optional[str] = None


@dataclass
class CrewPlan:
    """План выполнения задачи командой агентов."""
    task: str
    project_path: Path
    subtasks: List[SubTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


# ============================================================================
# CODEBASE ANALYSIS (simplified from orchestrator.py)
# ============================================================================

def quick_analyze(project_path: Path) -> Dict[str, Any]:
    """Быстрый анализ кодовой базы."""
    result = {
        "has_frontend": False,
        "has_backend": False,
        "has_tests": False,
        "has_database": False,
        "tech_stack": [],
        "frameworks": [],
        "structure": {}
    }
    
    ignore = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
    
    # Определяем технологии по конфигам
    if (project_path / "package.json").exists():
        result["tech_stack"].append("nodejs")
        try:
            pkg = json.loads((project_path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps: result["frameworks"].append("react")
            if "vue" in deps: result["frameworks"].append("vue")
            if "next" in deps: result["frameworks"].append("nextjs")
            if "express" in deps: result["frameworks"].append("express")
        except: pass
    
    if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
        result["tech_stack"].append("python")
        for f in ["requirements.txt", "pyproject.toml"]:
            if (project_path / f).exists():
                try:
                    content = (project_path / f).read_text().lower()
                    if "fastapi" in content: result["frameworks"].append("fastapi")
                    if "django" in content: result["frameworks"].append("django")
                    if "flask" in content: result["frameworks"].append("flask")
                except: pass
    
    # Анализируем структуру
    for item in project_path.iterdir():
        if item.name in ignore or item.name.startswith("."):
            continue
        
        name = item.name.lower()
        
        if item.is_dir():
            if name in ["src", "app", "components", "pages", "ui", "frontend", "client"]:
                result["has_frontend"] = True
                result["structure"]["frontend"] = str(item)
            
            if name in ["api", "routes", "controllers", "services", "backend", "server"]:
                result["has_backend"] = True
                result["structure"]["backend"] = str(item)
            
            if name in ["tests", "test", "__tests__", "spec", "e2e"]:
                result["has_tests"] = True
                result["structure"]["tests"] = str(item)
            
            if name in ["models", "schemas", "migrations", "db", "database"]:
                result["has_database"] = True
                result["structure"]["database"] = str(item)
    
    return result


# ============================================================================
# CREW MANAGER
# ============================================================================

class CrewManager:
    """
    Управляет командой clod агентов для выполнения задачи.
    
    Использует существующий clod manager для создания реальных агентов.
    """
    
    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()
        self.agents: Dict[str, str] = {}  # role -> agent_id
        self.plan: Optional[CrewPlan] = None
        self._manager = None
        
    def _get_manager(self):
        """Получить clod manager."""
        if self._manager is None:
            try:
                from . import manager
                self._manager = manager
            except ImportError:
                console.print("[red]clod manager not available[/red]")
                return None
        return self._manager
    
    def analyze_and_plan(self, task: str) -> CrewPlan:
        """
        Анализировать задачу и создать план.
        
        Это делается локально, без API вызовов.
        """
        analysis = quick_analyze(self.project_path)
        
        plan = CrewPlan(task=task, project_path=self.project_path)
        
        # Всегда нужен архитектор для планирования
        plan.subtasks.append(SubTask(
            id="architect",
            role=AgentRole.ARCHITECT,
            description=f"Analyze codebase and design solution for: {task}",
            scope=[str(self.project_path)],
            prompt=ROLE_PROMPTS[AgentRole.ARCHITECT]
        ))
        
        # Backend если есть
        if analysis["has_backend"]:
            scope = analysis["structure"].get("backend", str(self.project_path))
            plan.subtasks.append(SubTask(
                id="backend",
                role=AgentRole.BACKEND,
                description=f"Implement backend changes for: {task}",
                scope=[scope],
                prompt=ROLE_PROMPTS[AgentRole.BACKEND].format(scope=scope),
                depends_on=["architect"]
            ))
        
        # Frontend если есть
        if analysis["has_frontend"]:
            scope = analysis["structure"].get("frontend", str(self.project_path))
            plan.subtasks.append(SubTask(
                id="frontend",
                role=AgentRole.FRONTEND,
                description=f"Implement frontend changes for: {task}",
                scope=[scope],
                prompt=ROLE_PROMPTS[AgentRole.FRONTEND].format(scope=scope),
                depends_on=["architect"]
            ))
        
        # Database если есть
        if analysis["has_database"]:
            scope = analysis["structure"].get("database", str(self.project_path))
            plan.subtasks.append(SubTask(
                id="database",
                role=AgentRole.DATABASE,
                description=f"Implement database changes for: {task}",
                scope=[scope],
                prompt=ROLE_PROMPTS[AgentRole.DATABASE].format(scope=scope),
                depends_on=["architect"]
            ))
        
        # Тесты если есть
        if analysis["has_tests"]:
            scope = analysis["structure"].get("tests", str(self.project_path))
            deps = ["backend", "frontend", "database"]
            deps = [d for d in deps if any(s.id == d for s in plan.subtasks)]
            plan.subtasks.append(SubTask(
                id="tests",
                role=AgentRole.TESTS,
                description=f"Write tests for: {task}",
                scope=[scope],
                prompt=ROLE_PROMPTS[AgentRole.TESTS].format(scope=scope),
                depends_on=deps or ["architect"]
            ))
        
        # Всегда reviewer в конце
        all_ids = [s.id for s in plan.subtasks]
        plan.subtasks.append(SubTask(
            id="reviewer",
            role=AgentRole.REVIEWER,
            description=f"Review all changes for: {task}",
            scope=[str(self.project_path)],
            prompt=ROLE_PROMPTS[AgentRole.REVIEWER],
            depends_on=all_ids
        ))
        
        self.plan = plan
        return plan
    
    def spawn_agent(self, subtask: SubTask) -> Optional[str]:
        """
        Создать clod агента для подзадачи.
        
        Возвращает agent_id или None при ошибке.
        """
        mgr = self._get_manager()
        if not mgr:
            return None
        
        try:
            # Создаём агента через clod manager
            agent = mgr.create_agent(
                purpose=f"[{subtask.role.value}] {subtask.description[:50]}",
                project_path=str(self.project_path),
                config=mgr.AgentConfigOptions(
                    system_prompt=f"""# Task: {self.plan.task}

## Your Role: {subtask.role.value.upper()}

{subtask.prompt}

## Your Subtask
{subtask.description}

## Scope
Work within: {', '.join(subtask.scope)}

## Instructions
1. Focus only on your specific subtask
2. Write clean, production-ready code
3. Document your changes
4. Report when done
"""
                )
            )
            
            subtask.agent_id = agent.id
            self.agents[subtask.id] = agent.id
            
            return agent.id
            
        except Exception as e:
            console.print(f"[red]Failed to spawn {subtask.role.value}: {e}[/red]")
            return None
    
    def spawn_all(self) -> Dict[str, str]:
        """Создать всех агентов по плану."""
        if not self.plan:
            raise ValueError("No plan created. Call analyze_and_plan first.")
        
        for subtask in self.plan.subtasks:
            console.print(f"[cyan]Spawning {subtask.role.value}...[/cyan]")
            agent_id = self.spawn_agent(subtask)
            if agent_id:
                console.print(f"[green]✓ {subtask.role.value}[/green] → {agent_id}")
            else:
                console.print(f"[red]✗ {subtask.role.value} failed[/red]")
        
        return self.agents
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус всех агентов."""
        mgr = self._get_manager()
        if not mgr:
            return {}
        
        status = {}
        for subtask_id, agent_id in self.agents.items():
            try:
                # Получаем статус через pm2
                from .processes import pm2_status
                pm2_name = f"agent-{agent_id}"
                pm2_info = pm2_status(pm2_name)
                status[subtask_id] = {
                    "agent_id": agent_id,
                    "status": pm2_info.get("status", "unknown") if pm2_info else "stopped"
                }
            except:
                status[subtask_id] = {"agent_id": agent_id, "status": "unknown"}
        
        return status
    
    def stop_all(self):
        """Остановить всех агентов."""
        mgr = self._get_manager()
        if not mgr:
            return
        
        for subtask_id, agent_id in self.agents.items():
            try:
                mgr.stop_agent(agent_id)
                console.print(f"[dim]Stopped {subtask_id}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: {e}[/yellow]")
    
    def cleanup(self):
        """Удалить всех созданных агентов."""
        mgr = self._get_manager()
        if not mgr:
            return
        
        for subtask_id, agent_id in self.agents.items():
            try:
                mgr.remove_agent(agent_id)
                console.print(f"[dim]Removed {subtask_id}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: {e}[/yellow]")
        
        self.agents.clear()


# ============================================================================
# CLI COMMANDS
# ============================================================================

def print_plan(plan: CrewPlan, analysis: Dict[str, Any]):
    """Красиво вывести план."""
    
    # Анализ
    console.print(Panel(
        f"[bold]Project:[/bold] {plan.project_path.name}\n"
        f"[bold]Tech:[/bold] {', '.join(analysis['tech_stack']) or 'unknown'}\n"
        f"[bold]Frameworks:[/bold] {', '.join(analysis['frameworks']) or 'none'}\n"
        f"[bold]Components:[/bold] "
        f"{'Frontend ' if analysis['has_frontend'] else ''}"
        f"{'Backend ' if analysis['has_backend'] else ''}"
        f"{'Tests ' if analysis['has_tests'] else ''}"
        f"{'Database' if analysis['has_database'] else ''}",
        title="📁 Project Analysis"
    ))
    
    # План
    table = Table(title="🎯 Execution Plan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Role", style="cyan", width=12)
    table.add_column("Description", width=40)
    table.add_column("Depends On", style="dim", width=15)
    
    for i, subtask in enumerate(plan.subtasks, 1):
        deps = ", ".join(subtask.depends_on) if subtask.depends_on else "-"
        table.add_row(
            str(i),
            subtask.role.value,
            subtask.description[:40] + "..." if len(subtask.description) > 40 else subtask.description,
            deps
        )
    
    console.print(table)


def cmd_crew(
    task: str,
    project: str = ".",
    dry_run: bool = False,
    auto_start: bool = True,
    keep_agents: bool = False
):
    """
    Создать команду агентов для задачи.
    
    Args:
        task: Описание задачи
        project: Путь к проекту
        dry_run: Только показать план
        auto_start: Автоматически запустить агентов
        keep_agents: Не удалять агентов после завершения
    """
    project_path = Path(project).resolve()
    
    if not project_path.exists():
        console.print(f"[red]Project not found: {project_path}[/red]")
        return
    
    console.print(Panel(f"[bold]{task}[/bold]", title="🚀 Task"))
    
    # Анализ и планирование
    crew = CrewManager(project_path)
    analysis = quick_analyze(project_path)
    plan = crew.analyze_and_plan(task)
    
    print_plan(plan, analysis)
    
    if dry_run:
        console.print("\n[yellow]Dry run - agents not created[/yellow]")
        return
    
    # Создаём агентов
    console.print("\n[bold]Creating agents...[/bold]")
    agents = crew.spawn_all()
    
    if not agents:
        console.print("[red]No agents created[/red]")
        return
    
    # Статус
    console.print("\n[bold green]✓ Crew ready![/bold green]")
    
    status_table = Table(title="Agent Status")
    status_table.add_column("Role", style="cyan")
    status_table.add_column("Agent ID")
    status_table.add_column("Status")
    
    status = crew.get_status()
    for subtask_id, info in status.items():
        status_table.add_row(
            subtask_id,
            info["agent_id"][:12],
            f"[green]{info['status']}[/green]" if info['status'] == 'online' else info['status']
        )
    
    console.print(status_table)
    
    console.print(f"""
[bold]Next steps:[/bold]
1. Open each agent's terminal: [cyan]cam terminal {list(agents.values())[0][:8]}[/cyan]
2. Or open dashboard: [cyan]cam ui[/cyan]
3. Agents are ready to work on their subtasks

[dim]Tip: Each agent has its own memory and scope[/dim]
""")
    
    if not keep_agents:
        console.print("\n[dim]Press Ctrl+C to stop and cleanup agents[/dim]")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping agents...[/yellow]")
            crew.stop_all()
            crew.cleanup()
            console.print("[green]Done[/green]")


def cmd_crew_status():
    """Показать статус текущей команды."""
    # TODO: Сохранять crew state и показывать
    console.print("[yellow]Not implemented yet[/yellow]")


def create_crew_app():
    """Создать Typer app для crew команд."""
    import typer
    
    crew_app = typer.Typer(help="Multi-agent crew management (no external API)")
    
    @crew_app.command("run")
    def run_cmd(
        task: str = typer.Argument(..., help="Task description"),
        project: str = typer.Option(".", "--project", "-p", help="Project path"),
        dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Only show plan"),
        keep: bool = typer.Option(False, "--keep", "-k", help="Keep agents after Ctrl+C"),
    ):
        """Create and run a crew of agents for a task."""
        cmd_crew(task, project, dry_run, auto_start=True, keep_agents=keep)
    
    @crew_app.command("plan")
    def plan_cmd(
        task: str = typer.Argument(..., help="Task description"),
        project: str = typer.Option(".", "--project", "-p", help="Project path"),
    ):
        """Show execution plan without creating agents."""
        cmd_crew(task, project, dry_run=True)
    
    @crew_app.command("status")
    def status_cmd():
        """Show status of current crew."""
        cmd_crew_status()
    
    return crew_app


# ============================================================================
# STANDALONE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        console.print("Usage: python crew.py <task> [project_path]")
        console.print("Example: python crew.py 'Add OAuth' ./my-app")
        sys.exit(1)
    
    task = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else "."
    
    cmd_crew(task, project)
