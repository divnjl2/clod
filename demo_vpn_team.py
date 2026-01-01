"""
Пример использования Team Mode для VPN проекта
==============================================

Сценарий: Добавить CryptoBot payment в VPN сервис

Команда создаст 3 агента:
1. Backend - API для CryptoBot webhook
2. Telegram - /pay команда в боте
3. Admin - UI для просмотра платежей
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_agent_manager.team import (
    TeamOrchestrator,
    TeamPlan,
    AgentTask,
    ExecutionMode
)

from rich.console import Console
from rich.panel import Panel

console = Console()


async def demo_vpn_payment_feature():
    """
    Демо: Добавление CryptoBot payment в VPN сервис.
    
    Создается команда из 3 агентов которые работают параллельно:
    - Backend: FastAPI endpoints для CryptoBot
    - Telegram: команда /pay в боте
    - Admin: UI для просмотра платежей
    """
    
    console.print(Panel(
        "[bold cyan]VPN Service - CryptoBot Payment Integration[/bold cyan]\n\n"
        "This demo creates a team of 3 agents:\n"
        "• Backend: Payment API with CryptoBot webhook\n"
        "• Telegram: /pay command in bot\n"
        "• Admin: Payment management UI",
        title="🚀 Team Mode Demo"
    ))
    
    # Создаем временный проект для демо
    project_path = Path("/tmp/vpn_demo_project")
    project_path.mkdir(parents=True, exist_ok=True)
    
    # Инициализируем git
    import subprocess
    
    console.print("\n[dim]Initializing git repository...[/dim]")
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Demo"], cwd=project_path)
    subprocess.run(["git", "config", "user.email", "demo@vpn.com"], cwd=project_path)
    
    # Создаем базовую структуру
    (project_path / "api").mkdir(exist_ok=True)
    (project_path / "bot").mkdir(exist_ok=True)
    (project_path / "admin").mkdir(exist_ok=True)
    
    readme = project_path / "README.md"
    readme.write_text("# VPN Service\n\nCryptocurrency payments via CryptoBot")
    
    subprocess.run(["git", "add", "."], cwd=project_path)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=project_path,
        capture_output=True
    )
    
    console.print("[green]✓ Git repository initialized[/green]")
    
    # Создаем оркестратор
    orchestrator = TeamOrchestrator(
        project_path=project_path,
        max_parallel=3,
        auto_merge=False  # Для демо отключим автомерж
    )
    
    # Создаем план вручную (в реальности через Claude API)
    console.print("\n[cyan]Creating execution plan...[/cyan]")
    
    tasks = [
        AgentTask(
            id="backend_payment",
            role="backend",
            description="Create payment API with CryptoBot webhook handling",
            worktree_path=project_path / ".worktrees" / "backend",
            branch="agent/backend/cryptobot-api",
            provides_interfaces=["payment_api", "webhook_api"],
            scope=[
                "api/payments.py",
                "api/webhooks.py",
                "models/payment.py"
            ]
        ),
        
        AgentTask(
            id="telegram_bot",
            role="telegram",
            description="Add /pay command to Telegram bot for crypto payments",
            worktree_path=project_path / ".worktrees" / "telegram",
            branch="agent/telegram/pay-command",
            depends_on=["backend_payment"],
            required_interfaces=["payment_api"],
            scope=[
                "bot/handlers/payment.py",
                "bot/keyboards/payment.py"
            ]
        ),
        
        AgentTask(
            id="admin_panel",
            role="frontend",
            description="Build admin panel for viewing and managing payments",
            worktree_path=project_path / ".worktrees" / "admin",
            branch="agent/admin/payment-management",
            depends_on=["backend_payment"],
            required_interfaces=["payment_api"],
            scope=[
                "admin/components/PaymentList.tsx",
                "admin/pages/payments.tsx"
            ]
        )
    ]
    
    orchestrator.plan = TeamPlan(
        project_path=project_path,
        main_task="Add CryptoBot payment integration",
        tasks=tasks,
        execution_mode=ExecutionMode.SMART
    )
    
    # Показываем план
    console.print("\n[bold]Execution Plan:[/bold]")
    orchestrator.print_status()
    
    # Симулируем работу агентов
    console.print("\n[cyan]Simulating agent work...[/cyan]\n")
    
    from claude_agent_manager.team import TaskStatus
    from datetime import datetime
    import time
    
    # Backend начинает первым (нет зависимостей)
    console.print("[yellow]⚙️  Backend agent:[/yellow] Starting payment API development...")
    tasks[0].status = TaskStatus.IN_PROGRESS
    tasks[0].started_at = datetime.now()
    
    await asyncio.sleep(1)
    
    # Регистрируем интерфейс
    from claude_agent_manager.team import SharedInterface
    
    await orchestrator.shared_context.register_interface(
        SharedInterface(
            name="payment_api",
            type="api",
            owner="backend_payment",
            spec={
                "endpoints": [
                    {"method": "POST", "path": "/api/payment/create"},
                    {"method": "POST", "path": "/api/payment/webhook"},
                    {"method": "GET", "path": "/api/payment/{id}"}
                ]
            },
            status="draft"
        )
    )
    
    console.print("  [green]✓[/green] Created API endpoints")
    console.print("  [green]✓[/green] Registered payment_api interface (draft)")
    
    await asyncio.sleep(1)
    
    # Frontend и Telegram блокированы
    console.print("\n[yellow]⏸️  Telegram agent:[/yellow] Blocked - waiting for payment_api")
    console.print("[yellow]⏸️  Admin agent:[/yellow] Blocked - waiting for payment_api")
    
    tasks[1].status = TaskStatus.BLOCKED
    tasks[2].status = TaskStatus.BLOCKED
    
    await asyncio.sleep(1)
    
    # Backend завершил
    console.print("\n[yellow]⚙️  Backend agent:[/yellow] Finalizing API...")
    
    # Обновляем статус интерфейса
    interface_data = await orchestrator.shared_context.get_interface("payment_api")
    interface_data["status"] = "ready"
    
    from claude_agent_manager.team import SharedInterface
    await orchestrator.shared_context.register_interface(
        SharedInterface(
            name="payment_api",
            type="api",
            owner="backend_payment",
            spec=interface_data["spec"],
            status="ready"
        )
    )
    
    tasks[0].status = TaskStatus.DONE
    tasks[0].completed_at = datetime.now()
    
    console.print("  [green]✓[/green] Payment API completed")
    console.print("  [green]✓[/green] payment_api interface is READY")
    
    await asyncio.sleep(1)
    
    # Разблокируем зависимые агенты
    console.print("\n[green]🚀 Telegram & Admin agents unblocked![/green]")
    
    tasks[1].status = TaskStatus.IN_PROGRESS
    tasks[2].status = TaskStatus.IN_PROGRESS
    
    console.print("\n[yellow]⚙️  Telegram agent:[/yellow] Implementing /pay command...")
    console.print("[yellow]⚙️  Admin agent:[/yellow] Building payment management UI...")
    
    await asyncio.sleep(2)
    
    # Завершение
    tasks[1].status = TaskStatus.DONE
    tasks[1].completed_at = datetime.now()
    tasks[2].status = TaskStatus.DONE
    tasks[2].completed_at = datetime.now()
    
    console.print("  [green]✓[/green] Telegram bot updated")
    console.print("  [green]✓[/green] Admin panel ready")
    
    # Финальный статус
    console.print("\n[bold]Final Status:[/bold]")
    orchestrator.print_status()
    
    # Информация о worktrees
    console.print("\n[bold]Created Worktrees:[/bold]")
    console.print(f"  • {project_path}/.worktrees/backend/")
    console.print(f"  • {project_path}/.worktrees/telegram/")
    console.print(f"  • {project_path}/.worktrees/admin/")
    
    console.print("\n[bold]Created Branches:[/bold]")
    console.print("  • agent/backend/cryptobot-api")
    console.print("  • agent/telegram/pay-command")
    console.print("  • agent/admin/payment-management")
    
    console.print("\n[bold green]✨ Team task completed successfully![/bold green]")
    
    console.print("\n[dim]Next steps:[/dim]")
    console.print("  1. Each agent has made changes in its worktree")
    console.print("  2. Run: cam team merge --project /tmp/vpn_demo_project")
    console.print("  3. All branches will be merged to main")
    console.print("  4. Feature is ready! 🎉")


async def main():
    try:
        await demo_vpn_payment_feature()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
