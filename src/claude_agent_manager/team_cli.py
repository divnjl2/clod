"""
Team CLI - Полный командный интерфейс для Team Mode
==================================================

Интегрирует все компоненты:
- AutoGen: multi-agent
- CrewAI: dependencies
- SWE-agent: prompts
- Aider: git
- MetaGPT: roles
- Quality Gates

Команды:
    cam team run "task" --project ./path
    cam team plan "task"
    cam team status
    cam team quality
    cam team roles
    cam team clean
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

from .team import (
    TeamOrchestrator,
    run_team_task,
    quick_plan,
    get_available_roles,
    get_role_dependencies,
    QualityGates,
    QualityGateEnforcer,
    AUTOGEN_AVAILABLE,
)

console = Console()

team_app = typer.Typer(
    name="team",
    help="Multi-agent team coordination with best practices from AutoGen, CrewAI, SWE-agent, Aider, MetaGPT"
)


@team_app.command("run")
def team_run(
    task: str = typer.Argument(..., help="Task description for the team"),
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
    max_parallel: int = typer.Option(3, "--parallel", "-n", help="Max parallel agents"),
    no_merge: bool = typer.Option(False, "--no-merge", help="Skip auto-merge"),
    no_quality: bool = typer.Option(False, "--no-quality", help="Skip quality gates"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan only"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Run a team of agents to complete a task.

    Combines:
    - Task decomposition (DevOps-GPT pattern)
    - Role-based agents (MetaGPT pattern)
    - Dependencies (CrewAI pattern)
    - Git worktrees (Aider pattern)
    - Quality gates

    Example:
        cam team run "Add user authentication with JWT"
        cam team run "Implement payment API" --project ./myapp --parallel 4
    """
    project_path = Path(project).resolve()

    if not project_path.exists():
        console.print(f"[red]Project not found: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold cyan]Team Task[/bold cyan]\n\n"
        f"Task: {task}\n"
        f"Project: {project_path}\n"
        f"Max Parallel: {max_parallel}\n"
        f"Auto-merge: {not no_merge}\n"
        f"Quality Gates: {not no_quality}",
        title="Configuration"
    ))

    try:
        orchestrator = TeamOrchestrator(
            project_path,
            max_parallel=max_parallel,
            auto_merge=not no_merge,
            quality_gates=not no_quality
        )

        async def create_and_run():
            # Create plan
            plan = await orchestrator.create_plan(task)

            if dry_run:
                console.print("\n[yellow]Dry run - not executing[/yellow]")
                return

            # Confirmation
            if not yes and not Confirm.ask("\nProceed with execution?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

            # Execute
            await orchestrator.execute_plan()

        asyncio.run(create_and_run())

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@team_app.command("plan")
def team_plan(
    task: str = typer.Argument(..., help="Task description"),
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save plan to file"),
):
    """
    Create execution plan without running.

    Shows how Claude will decompose the task into agent subtasks.

    Example:
        cam team plan "Add crypto payment integration"
        cam team plan "Build REST API" --output plan.json
    """
    project_path = Path(project).resolve()

    try:
        plan = quick_plan(str(project_path), task)

        console.print(Panel(
            f"[bold]Plan created for:[/bold]\n{task}",
            title="Execution Plan"
        ))

        table = Table()
        table.add_column("ID", style="cyan")
        table.add_column("Role", style="magenta")
        table.add_column("Depends On", style="dim")
        table.add_column("Provides", style="green")
        table.add_column("Description")

        for t in plan.tasks:
            table.add_row(
                t.id,
                t.role,
                ", ".join(t.depends_on) or "-",
                ", ".join(t.provides_interfaces) or "-",
                t.description[:40] + "..." if len(t.description) > 40 else t.description
            )

        console.print(table)

        if output:
            output_path = Path(output)
            output_path.write_text(json.dumps(plan.to_dict(), indent=2))
            console.print(f"\n[green]Plan saved to {output_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@team_app.command("status")
def team_status(
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
):
    """Show status of current team."""
    project_path = Path(project).resolve()
    context_file = project_path / ".claude-team" / "shared_context.json"

    if not context_file.exists():
        console.print("[yellow]No team context found in this project[/yellow]")
        console.print("[dim]Run 'cam team run' to start a team task[/dim]")
        return

    context = json.loads(context_file.read_text())

    # Agents status
    agents = context.get("agents", {})
    if agents:
        table = Table(title="Agents")
        table.add_column("Agent", style="cyan")
        table.add_column("Role", style="magenta")
        table.add_column("Status")
        table.add_column("Message", style="dim")

        status_colors = {
            "done": "green",
            "in_progress": "cyan",
            "pending": "dim",
            "blocked": "yellow",
            "failed": "red"
        }

        for agent_id, data in agents.items():
            status = data.get("status", "unknown")
            color = status_colors.get(status, "white")

            table.add_row(
                agent_id,
                data.get("role", "-"),
                f"[{color}]{status}[/{color}]",
                data.get("message", "-")[:50]
            )

        console.print(table)

    # Interfaces
    interfaces = context.get("interfaces", {})
    if interfaces:
        console.print()
        table = Table(title="Interfaces")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Owner")
        table.add_column("Status")

        for name, spec in interfaces.items():
            status = spec.get("status", "unknown")
            color = "green" if status == "ready" else "yellow"

            table.add_row(
                name,
                spec.get("type", "-"),
                spec.get("owner", "-"),
                f"[{color}]{status}[/{color}]"
            )

        console.print(table)


@team_app.command("roles")
def team_roles():
    """Show available agent roles and their dependencies."""
    roles = get_available_roles()
    deps = get_role_dependencies()

    table = Table(title="Available Agent Roles")
    table.add_column("Role", style="cyan")
    table.add_column("Waits For", style="dim")
    table.add_column("Description")

    descriptions = {
        "architect": "Design system architecture, APIs, database schema",
        "backend": "Implement server-side logic and APIs",
        "frontend": "Build UI components and integrate APIs",
        "qa": "Write tests, ensure quality",
        "reviewer": "Code review, security audit",
        "refactoring": "Improve code quality, reduce complexity",
    }

    for role in roles:
        table.add_row(
            role,
            ", ".join(deps.get(role, [])) or "-",
            descriptions.get(role, "")
        )

    console.print(table)


@team_app.command("quality")
def team_quality(
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
    check: Optional[str] = typer.Option(None, "--check", "-c", help="Run specific check only"),
):
    """
    Run quality checks on project.

    Checks:
    - ruff: Linting
    - radon: Complexity
    - bandit: Security
    - mypy: Type checking
    """
    project_path = Path(project).resolve()

    console.print(f"[cyan]Running quality checks on {project_path}...[/cyan]\n")

    try:
        gates = QualityGates(project_path)

        if check:
            # Single check
            check_methods = {
                "lint": gates.run_ruff,
                "ruff": gates.run_ruff,
                "complexity": gates.run_radon,
                "radon": gates.run_radon,
                "security": gates.run_bandit,
                "bandit": gates.run_bandit,
                "types": gates.run_type_check,
                "mypy": gates.run_type_check,
            }

            if check not in check_methods:
                console.print(f"[red]Unknown check: {check}[/red]")
                console.print(f"Available: {', '.join(check_methods.keys())}")
                raise typer.Exit(1)

            result = check_methods[check]()
            _print_check_result(result)

        else:
            # All checks
            report = gates.run_all_checks()

            status_colors = {
                "passed": "green",
                "failed": "red",
                "warning": "yellow",
                "error": "red",
                "skipped": "dim"
            }

            color = status_colors.get(report.overall_status.value, "white")
            console.print(f"Overall: [{color}]{report.overall_status.value.upper()}[/{color}]")
            console.print(f"{report.summary}\n")

            for result in report.checks:
                _print_check_result(result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _print_check_result(result):
    """Print single check result."""
    icon = "?" if result.status.value == "passed" else "?" if result.status.value == "warning" else "?"
    color = "green" if result.status.value == "passed" else "yellow" if result.status.value == "warning" else "red"

    console.print(f"{icon} [{color}]{result.check_name}[/{color}]: {result.message}")

    if result.issues and len(result.issues) <= 5:
        for issue in result.issues[:5]:
            console.print(f"   {issue.file}:{issue.line} - {issue.message[:60]}")
    elif result.issues:
        console.print(f"   ... and {len(result.issues) - 5} more issues")


@team_app.command("autogen")
def team_autogen(
    task: str = typer.Argument(..., help="Task description"),
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
    preset: str = typer.Option("fullstack", "--preset", help="Team preset"),
):
    """
    Run team using AutoGen framework.

    Requires: pip install pyautogen

    Presets:
    - fullstack: Architect, Backend, Frontend
    - microservices: Architect, multiple service devs, DevOps
    """
    if not AUTOGEN_AVAILABLE:
        console.print("[red]AutoGen not installed[/red]")
        console.print("Install with: pip install pyautogen")
        raise typer.Exit(1)

    from .team.autogen_integration import TeamPresets, AutoGenTeam
    import os

    project_path = Path(project).resolve()
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        console.print("[red]ANTHROPIC_API_KEY not set[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Creating AutoGen team ({preset})...[/cyan]")

    if preset == "fullstack":
        team = TeamPresets.fullstack_team(project_path, api_key)

        architect = team.create_agent(
            "architect",
            project_path / ".worktrees" / "architect",
            f"Design architecture for: {task}"
        )

        backend = team.create_agent(
            "backend",
            project_path / ".worktrees" / "backend",
            f"Implement backend for: {task}"
        )

        frontend = team.create_agent(
            "frontend",
            project_path / ".worktrees" / "frontend",
            f"Implement frontend for: {task}"
        )

        console.print("[green]Team: Architect, Backend, Frontend[/green]")
        console.print("[cyan]Starting team task...[/cyan]\n")

        result = team.run_team_task(task, [architect, backend, frontend])

        console.print(f"\n[green]Task completed![/green]")
        console.print(f"Messages: {len(result.get('messages', []))}")

    else:
        console.print(f"[yellow]Unknown preset: {preset}[/yellow]")
        console.print("Available: fullstack, microservices")


@team_app.command("clean")
def team_clean(
    project: str = typer.Option(".", "--project", "-p", help="Project path"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clean up all team worktrees and context."""
    project_path = Path(project).resolve()

    worktrees_dir = project_path / ".worktrees"
    context_dir = project_path / ".claude-team"

    if not worktrees_dir.exists() and not context_dir.exists():
        console.print("[yellow]Nothing to clean[/yellow]")
        return

    if not force:
        console.print("This will remove:")
        if worktrees_dir.exists():
            console.print(f"  - Worktrees: {worktrees_dir}")
        if context_dir.exists():
            console.print(f"  - Team context: {context_dir}")

        if not Confirm.ask("\nProceed?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    import shutil
    import subprocess

    # Remove worktrees via git
    if worktrees_dir.exists():
        for wt in worktrees_dir.iterdir():
            if wt.is_dir():
                subprocess.run(
                    ["git", "worktree", "remove", str(wt), "--force"],
                    cwd=project_path,
                    capture_output=True
                )
        shutil.rmtree(worktrees_dir, ignore_errors=True)
        console.print("[green]Removed worktrees[/green]")

    # Remove context
    if context_dir.exists():
        shutil.rmtree(context_dir, ignore_errors=True)
        console.print("[green]Removed team context[/green]")

    console.print("[bold green]Cleanup complete![/bold green]")


if __name__ == "__main__":
    team_app()
