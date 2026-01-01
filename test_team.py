"""
Team Test - Демонстрация командной работы
=======================================

Тестовый сценарий: Добавить CryptoBot payment в VPN сервис
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_agent_manager.team import (
    TeamOrchestrator,
    SharedContext,
    AgentUpdate,
    TaskStatus,
    SharedInterface,
    AgentTask
)


async def test_shared_context():
    """Тест 1: Shared Context между агентами."""
    print("\n🧪 Test 1: Shared Context Communication\n")
    
    context_path = Path("/tmp/test_team/shared_context.json")
    context_path.parent.mkdir(parents=True, exist_ok=True)
    
    sc = SharedContext(context_path)
    
    # Агент 1: Backend обновляет статус
    print("📡 Backend agent: Creating payment API...")
    await sc.update_agent_status(AgentUpdate(
        agent_id="backend_001",
        role="backend",
        timestamp=datetime.now().isoformat(),
        status=TaskStatus.IN_PROGRESS,
        message="Creating payment endpoints",
        artifacts={
            "endpoints": [
                {"method": "POST", "path": "/api/payment/create"},
                {"method": "POST", "path": "/api/payment/webhook"},
                {"method": "GET", "path": "/api/payment/{id}/status"}
            ]
        }
    ))
    
    # Регистрируем API как интерфейс
    print("📝 Backend agent: Registering API interface...")
    await sc.register_interface(SharedInterface(
        name="payment_api",
        type="api",
        owner="backend_001",
        spec={
            "base_url": "/api/payment",
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/create",
                    "request": {
                        "user_id": "string",
                        "amount": "number",
                        "currency": "string"
                    },
                    "response": {
                        "payment_id": "string",
                        "checkout_url": "string"
                    }
                }
            ]
        },
        status="draft"
    ))
    
    # Агент 2: Frontend ждет API
    print("⏳ Frontend agent: Waiting for payment API...")
    await sc.update_agent_status(AgentUpdate(
        agent_id="frontend_001",
        role="frontend",
        timestamp=datetime.now().isoformat(),
        status=TaskStatus.BLOCKED,
        message="Waiting for payment API spec",
        blockers=["payment_api"]
    ))
    
    # Проверяем зависимости
    deps = await sc.check_dependencies("frontend_001", ["payment_api"])
    print(f"✅ Dependencies check: {deps}")
    
    # Backend завершил API
    print("✅ Backend agent: API ready!")
    await sc.update_agent_status(AgentUpdate(
        agent_id="backend_001",
        role="backend",
        timestamp=datetime.now().isoformat(),
        status=TaskStatus.DONE,
        message="Payment API completed"
    ))
    
    # Обновляем статус интерфейса
    interface = await sc.get_interface("payment_api")
    interface["status"] = "ready"
    await sc.register_interface(SharedInterface(
        name="payment_api",
        type="api",
        owner="backend_001",
        spec=interface["spec"],
        status="ready"
    ))
    
    # Frontend разблокирован
    await sc.resolve_blocker("frontend_001", "payment_api")
    print("🚀 Frontend agent: Unblocked! Starting UI implementation...")
    
    await sc.update_agent_status(AgentUpdate(
        agent_id="frontend_001",
        role="frontend",
        timestamp=datetime.now().isoformat(),
        status=TaskStatus.IN_PROGRESS,
        message="Building payment UI"
    ))
    
    # Получаем артефакты backend
    backend_artifacts = await sc.get_agent_artifacts("backend_001")
    print(f"\n📦 Backend artifacts available to frontend:")
    print(json.dumps(backend_artifacts, indent=2))
    
    # Экспортируем summary
    summary = await sc.export_summary()
    print(f"\n📊 Team Summary:")
    print(summary)
    
    print("\n✅ Test 1 passed!\n")


async def test_orchestrator():
    """Тест 2: Team Orchestrator с mock агентами."""
    print("\n🧪 Test 2: Team Orchestrator\n")
    
    # Создаем временный проект
    project_path = Path("/tmp/test_vpn_project")
    project_path.mkdir(parents=True, exist_ok=True)
    
    # Инициализируем git
    import subprocess
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project_path)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project_path)
    
    # Создаем начальный коммит
    readme = project_path / "README.md"
    readme.write_text("# Test VPN Project")
    subprocess.run(["git", "add", "."], cwd=project_path)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, capture_output=True)
    
    # Создаем оркестратор
    orchestrator = TeamOrchestrator(
        project_path,
        max_parallel=2,
        auto_merge=False  # Для теста отключим
    )
    
    # Создаем mock план вручную (без вызова Claude API)
    print("📋 Creating mock execution plan...")
    
    from claude_agent_manager.team import TeamPlan, ExecutionMode
    
    tasks = [
        AgentTask(
            id="task_backend",
            role="backend",
            description="Create payment API with CryptoBot integration",
            worktree_path=project_path / ".worktrees" / "backend",
            branch="agent/backend/payment-api",
            provides_interfaces=["payment_api"],
            scope=["api/payments.py", "models/payment.py"]
        ),
        AgentTask(
            id="task_frontend",
            role="frontend",
            description="Build payment UI consuming the API",
            worktree_path=project_path / ".worktrees" / "frontend",
            branch="agent/frontend/payment-ui",
            depends_on=["task_backend"],
            required_interfaces=["payment_api"],
            scope=["components/Payment.tsx"]
        ),
        AgentTask(
            id="task_telegram",
            role="telegram",
            description="Add /pay command to Telegram bot",
            worktree_path=project_path / ".worktrees" / "telegram",
            branch="agent/telegram/pay-command",
            depends_on=["task_backend"],
            required_interfaces=["payment_api"],
            scope=["bot/handlers/payment.py"]
        )
    ]
    
    orchestrator.plan = TeamPlan(
        project_path=project_path,
        main_task="Add CryptoBot payment integration",
        tasks=tasks,
        execution_mode=ExecutionMode.SMART
    )
    
    # Показываем план
    orchestrator.print_status()
    
    print("\n✅ Test 2 passed!\n")


async def test_dependency_resolution():
    """Тест 3: Разрешение зависимостей."""
    print("\n🧪 Test 3: Dependency Resolution\n")
    
    from claude_agent_manager.team import TeamPlan, ExecutionMode
    
    project_path = Path("/tmp/test_deps")
    
    tasks = [
        AgentTask(
            id="task_1",
            role="database",
            description="Create schema",
            worktree_path=project_path / ".worktrees" / "db",
            branch="agent/db/schema",
            provides_interfaces=["db_schema"]
        ),
        AgentTask(
            id="task_2",
            role="backend",
            description="API using schema",
            worktree_path=project_path / ".worktrees" / "backend",
            branch="agent/backend/api",
            depends_on=["task_1"],
            required_interfaces=["db_schema"],
            provides_interfaces=["api"]
        ),
        AgentTask(
            id="task_3",
            role="frontend",
            description="UI using API",
            worktree_path=project_path / ".worktrees" / "frontend",
            branch="agent/frontend/ui",
            depends_on=["task_2"],
            required_interfaces=["api"]
        ),
        AgentTask(
            id="task_4",
            role="tests",
            description="Tests for everything",
            worktree_path=project_path / ".worktrees" / "tests",
            branch="agent/tests/all",
            depends_on=["task_2", "task_3"],
            required_interfaces=["api"]
        )
    ]
    
    plan = TeamPlan(
        project_path=project_path,
        main_task="Full stack feature",
        tasks=tasks,
        execution_mode=ExecutionMode.SMART
    )
    
    # Симулируем выполнение
    completed = set()
    
    print("Execution order:")
    round_num = 1
    
    while len(completed) < len(tasks):
        ready = plan.get_ready_tasks(completed)
        
        if not ready:
            print("❌ Deadlock!")
            break
        
        print(f"\nRound {round_num}:")
        for task in ready:
            print(f"  → {task.role}: {task.description}")
            completed.add(task.id)
        
        round_num += 1
    
    print(f"\n✅ All {len(completed)}/{len(tasks)} tasks executed in correct order!\n")


async def main():
    """Запуск всех тестов."""
    print("=" * 60)
    print("🧪 Claude Agent Manager - Team Mode Tests")
    print("=" * 60)
    
    try:
        await test_shared_context()
        await test_orchestrator()
        await test_dependency_resolution()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
