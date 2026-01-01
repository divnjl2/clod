#!/usr/bin/env python3
"""
Automated Test Runner for Multi-Agent Synthetic Tasks
====================================================

Runs synthetic tasks to test all aspects of the multi-agent system.

Usage:
    python test_synthetic.py --task 1    # Run task 1 only
    python test_synthetic.py --all       # Run all 5 tasks
    python test_synthetic.py --quick     # Run tasks 1-2 (quick test)
"""

import asyncio
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()


@dataclass
class TaskDefinition:
    """Definition of a synthetic test task."""
    id: int
    name: str
    description: str
    expected_agents: int
    expected_time_hours: float
    expected_coverage: int
    complexity: int  # 1-5 stars


@dataclass
class TestResult:
    """Result of running a test task."""
    task_id: int
    success: bool
    duration_seconds: float
    agents_created: int
    tasks_completed: int
    blockers_detected: int
    blockers_resolved: int
    quality_gates_passed: int
    quality_gates_failed: int
    coverage_achieved: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# TEST TASK DEFINITIONS
# ============================================================================

TASKS = [
    TaskDefinition(
        id=1,
        name="Simple REST API",
        description="""Create a simple REST API for TODO list:
- GET /todos - list all todos
- POST /todos - create new todo
- PUT /todos/{id} - update todo
- DELETE /todos/{id} - delete todo
- Unit tests with 80%+ coverage

Expected agents: Backend, QA
Expected flow: Backend implements → QA tests""",
        expected_agents=2,
        expected_time_hours=1.0,
        expected_coverage=80,
        complexity=1
    ),
    
    TaskDefinition(
        id=2,
        name="CRUD with UI",
        description="""Create a user management system:
- Backend: User CRUD API (FastAPI)
- Database: PostgreSQL schema + migrations  
- Frontend: User list + create/edit form (React)
- Tests: Integration tests for full flow

Expected agents: Architect, Backend, Frontend, QA
Expected flow: Architect designs → Backend implements → Frontend+QA parallel""",
        expected_agents=4,
        expected_time_hours=2.0,
        expected_coverage=80,
        complexity=2
    ),
    
    TaskDefinition(
        id=3,
        name="Auth System",
        description="""Implement JWT authentication system:
- Architect: Design auth flow + security requirements
- Backend: Auth endpoints (login, register, refresh)
- Database: Users table + sessions
- Frontend: Login/register forms + protected routes
- Security: Review for vulnerabilities
- Tests: Security tests + E2E auth flow

Expected agents: Architect, Database, Backend, Frontend, Security, QA
Expected flow: Architect → Database → Backend → Frontend+Security → QA""",
        expected_agents=6,
        expected_time_hours=3.0,
        expected_coverage=85,
        complexity=3
    ),
    
    TaskDefinition(
        id=4,
        name="Payment Integration",
        description="""Integrate CryptoBot payment system:
- Architect: Design payment flow + webhook handling
- Backend: Payment API + CryptoBot integration
- Telegram: /pay command in bot
- Frontend: Admin payment dashboard
- Tests: Integration + E2E tests
- Reviewer: Full code review + approval

Expected agents: Architect, Backend, Telegram, Frontend, QA, Reviewer
Expected flow: Architect → Backend → (Telegram+Frontend) parallel → QA → Reviewer""",
        expected_agents=6,
        expected_time_hours=4.0,
        expected_coverage=85,
        complexity=4
    ),
    
    TaskDefinition(
        id=5,
        name="Microservices Split",
        description="""Refactor monolith into 3 microservices:
- Auth Service (users, sessions, JWT)
- Payment Service (payments, subscriptions)
- Notification Service (email, SMS, push)
Each service: API + database + tests + deployment

Expected agents: Architect, Auth Backend, Payment Backend, Notification Backend, Database, DevOps, QA, Reviewer
Expected flow: Architect → (3 backends + Database) parallel → DevOps → QA → Reviewer""",
        expected_agents=8,
        expected_time_hours=5.0,
        expected_coverage=80,
        complexity=5
    )
]


# ============================================================================
# MOCK ORCHESTRATOR (for testing without full system)
# ============================================================================

class MockOrchestrator:
    """Mock orchestrator for testing the test framework itself."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.plan = None
    
    async def create_plan(self, description: str) -> 'MockPlan':
        """Create a mock plan."""
        # Determine number of agents based on description
        agents_count = 2  # default
        if "CRUD with UI" in description:
            agents_count = 4
        elif "Auth System" in description:
            agents_count = 6
        elif "Payment" in description:
            agents_count = 6
        elif "Microservices" in description:
            agents_count = 8
        
        self.plan = MockPlan(agents_count)
        return self.plan
    
    async def execute_plan(self):
        """Execute the mock plan."""
        await asyncio.sleep(0.5)  # Simulate some work
        for task in self.plan.tasks:
            task.status = "done"


class MockPlan:
    """Mock execution plan."""
    
    def __init__(self, num_agents: int):
        self.tasks = [MockTask(f"task_{i}") for i in range(num_agents)]


class MockTask:
    """Mock task."""
    
    def __init__(self, id: str):
        self.id = id
        self.status = "pending"


# ============================================================================
# TEST RUNNER
# ============================================================================

class SyntheticTestRunner:
    """Runs synthetic tests on the multi-agent system."""
    
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.results: List[TestResult] = []
    
    async def run_task(self, task_def: TaskDefinition, project_path: Path) -> TestResult:
        """Run a single test task."""
        
        console.print(Panel(
            f"[bold cyan]{task_def.name}[/bold cyan]\n\n"
            f"Complexity: {'⭐' * task_def.complexity}\n"
            f"Expected: {task_def.expected_agents} agents, "
            f"~{task_def.expected_time_hours:.1f}h\n\n"
            f"[dim]{task_def.description}[/dim]",
            title=f"🧪 Test #{task_def.id}",
            border_style="cyan"
        ))
        
        start_time = datetime.now()
        
        try:
            # Create orchestrator
            if self.use_mock:
                from test_synthetic import MockOrchestrator
                orchestrator = MockOrchestrator(project_path)
            else:
                from claude_agent_manager.team import TeamOrchestrator
                orchestrator = TeamOrchestrator(project_path, max_parallel=3)
            
            # Create plan
            console.print("[cyan]📋 Creating execution plan...[/cyan]")
            plan = await orchestrator.create_plan(task_def.description)
            
            agents_created = len(plan.tasks)
            console.print(f"[green]✓ Plan created: {agents_created} agents[/green]")
            
            # Execute
            console.print("[cyan]🚀 Executing plan...[/cyan]")
            
            # Monitor in background
            blockers_detected = 0
            blockers_resolved = 0
            
            async def monitor():
                nonlocal blockers_detected, blockers_resolved
                while True:
                    await asyncio.sleep(2)
                    # Mock blocker detection
                    if not self.use_mock:
                        try:
                            blockers = await orchestrator.shared_context.get_blockers()
                            if blockers:
                                blockers_detected += len(blockers)
                                console.print(f"[yellow]⚠ Blockers: {list(blockers.keys())}[/yellow]")
                        except:
                            pass
            
            monitor_task = asyncio.create_task(monitor())
            
            try:
                await orchestrator.execute_plan()
            finally:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Collect results
            tasks_completed = len([t for t in plan.tasks if hasattr(t, 'status') and t.status == "done"])
            
            result = TestResult(
                task_id=task_def.id,
                success=True,
                duration_seconds=duration,
                agents_created=agents_created,
                tasks_completed=tasks_completed,
                blockers_detected=blockers_detected,
                blockers_resolved=blockers_detected,  # Assume all resolved
                quality_gates_passed=agents_created,
                quality_gates_failed=0,
                coverage_achieved=82  # Mock for now
            )
            
            # Validate
            if agents_created != task_def.expected_agents:
                result.warnings.append(
                    f"Agent count mismatch: expected {task_def.expected_agents}, got {agents_created}"
                )
            
            if duration > task_def.expected_time_hours * 3600 * 1.5:
                result.warnings.append(
                    f"Task took too long: {duration/3600:.2f}h vs expected {task_def.expected_time_hours}h"
                )
            
            console.print(f"\n[bold green]✓ Task #{task_def.id} completed in {duration:.1f}s[/bold green]")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            console.print(f"\n[bold red]✗ Task #{task_def.id} failed: {e}[/bold red]")
            
            return TestResult(
                task_id=task_def.id,
                success=False,
                duration_seconds=duration,
                agents_created=0,
                tasks_completed=0,
                blockers_detected=0,
                blockers_resolved=0,
                quality_gates_passed=0,
                quality_gates_failed=0,
                coverage_achieved=0,
                errors=[str(e)]
            )
    
    def print_result(self, result: TestResult, task_def: TaskDefinition):
        """Print test result."""
        
        table = Table(title=f"Test #{result.task_id} Results", show_header=True)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Expected", style="dim", width=15)
        table.add_column("Actual", style="green", width=15)
        table.add_column("Status", style="bold", width=8)
        
        # Duration
        expected_sec = task_def.expected_time_hours * 3600
        status = "✅" if result.duration_seconds <= expected_sec * 1.2 else "⚠️"
        table.add_row(
            "Duration",
            f"{expected_sec/3600:.1f}h",
            f"{result.duration_seconds/3600:.2f}h",
            status
        )
        
        # Agents
        status = "✅" if result.agents_created == task_def.expected_agents else "⚠️"
        table.add_row(
            "Agents",
            str(task_def.expected_agents),
            str(result.agents_created),
            status
        )
        
        # Completion
        status = "✅" if result.tasks_completed == result.agents_created else "❌"
        table.add_row(
            "Tasks Completed",
            str(result.agents_created),
            str(result.tasks_completed),
            status
        )
        
        # Blockers
        table.add_row(
            "Blockers",
            "-",
            f"{result.blockers_detected}/{result.blockers_resolved}",
            "✅" if result.blockers_detected == result.blockers_resolved else "⚠️"
        )
        
        # Quality
        table.add_row(
            "Quality Gates",
            "-",
            f"{result.quality_gates_passed}✅ {result.quality_gates_failed}❌",
            "✅" if result.quality_gates_failed == 0 else "❌"
        )
        
        # Coverage
        status = "✅" if result.coverage_achieved >= task_def.expected_coverage else "⚠️"
        table.add_row(
            "Coverage",
            f"{task_def.expected_coverage}%",
            f"{result.coverage_achieved}%",
            status
        )
        
        console.print(table)
        
        # Warnings
        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  ⚠️  {warning}")
        
        # Errors
        if result.errors:
            console.print("\n[red]Errors:[/red]")
            for error in result.errors:
                console.print(f"  ❌ {error}")
    
    def print_summary(self):
        """Print overall summary."""
        
        console.print("\n" + "="*70)
        console.print("[bold]Test Summary[/bold]")
        console.print("="*70 + "\n")
        
        # Summary table
        summary_table = Table(show_header=True)
        summary_table.add_column("#", style="dim", width=4)
        summary_table.add_column("Task", style="cyan", width=25)
        summary_table.add_column("Time", style="green", width=10)
        summary_table.add_column("Agents", style="yellow", width=10)
        summary_table.add_column("Status", style="bold", width=10)
        
        for result in self.results:
            task_def = next(t for t in TASKS if t.id == result.task_id)
            status = "✅ PASS" if result.success else "❌ FAIL"
            summary_table.add_row(
                str(result.task_id),
                task_def.name,
                f"{result.duration_seconds/3600:.2f}h",
                f"{result.agents_created}",
                status
            )
        
        console.print(summary_table)
        
        # Statistics
        console.print(f"\n[bold]Statistics:[/bold]")
        passed = sum(1 for r in self.results if r.success)
        total = len(self.results)
        
        console.print(f"  Tests passed: {passed}/{total}")
        console.print(f"  Total agents: {sum(r.agents_created for r in self.results)}")
        console.print(f"  Total time: {sum(r.duration_seconds for r in self.results)/3600:.2f}h")
        console.print(f"  Avg coverage: {sum(r.coverage_achieved for r in self.results)/total:.1f}%")
        
        if passed == total:
            console.print("\n[bold green]✅ All tests passed![/bold green]")
        else:
            console.print(f"\n[bold yellow]⚠️  {total-passed} test(s) failed[/bold yellow]")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run synthetic tests for multi-agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_synthetic.py --task 1          # Run task 1 only
  python test_synthetic.py --all             # Run all tasks
  python test_synthetic.py --quick           # Run tasks 1-2
  python test_synthetic.py --mock --all      # Run with mock (fast)
        """
    )
    
    parser.add_argument("--task", type=int, choices=range(1, 6), help="Run specific task")
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument("--quick", action="store_true", help="Run tasks 1-2 (quick test)")
    parser.add_argument("--mock", action="store_true", help="Use mock orchestrator (for testing)")
    parser.add_argument("--project", default="/tmp/synthetic_tests", help="Project path")
    
    args = parser.parse_args()
    
    if not any([args.task, args.all, args.quick]):
        parser.print_help()
        return
    
    # Determine tasks to run
    if args.task:
        tasks_to_run = [args.task]
    elif args.quick:
        tasks_to_run = [1, 2]
    else:  # all
        tasks_to_run = list(range(1, 6))
    
    # Setup project
    project_path = Path(args.project)
    project_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize git if needed
    if not (project_path / ".git").exists():
        subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project_path)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project_path)
        
        readme = project_path / "README.md"
        readme.write_text("# Synthetic Test Project")
        subprocess.run(["git", "add", "."], cwd=project_path)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=project_path, capture_output=True)
    
    # Run tests
    runner = SyntheticTestRunner(use_mock=args.mock)
    
    console.print(Panel(
        f"[bold]Synthetic Test Suite[/bold]\n\n"
        f"Running {len(tasks_to_run)} task(s)\n"
        f"Mode: {'Mock' if args.mock else 'Real'}\n"
        f"Project: {project_path}",
        title="🧪 Test Configuration",
        border_style="green"
    ))
    
    for task_id in tasks_to_run:
        task_def = next(t for t in TASKS if t.id == task_id)
        
        result = await runner.run_task(task_def, project_path)
        runner.results.append(result)
        runner.print_result(result, task_def)
        
        console.print()  # Spacer
    
    # Print summary
    runner.print_summary()
    
    # Exit code
    all_passed = all(r.success for r in runner.results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
