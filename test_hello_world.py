"""
Test Script - Hello World App Generation
"""

import asyncio
import sys
import os
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_agent_manager.team import TeamOrchestrator, create_agent


async def main():
    print("=" * 60)
    print("Testing Team Mode - Hello World App")
    print("=" * 60)

    # Test project path
    project_path = Path(__file__).parent / "test_project"
    project_path.mkdir(parents=True, exist_ok=True)

    print(f"\nProject path: {project_path}")

    # Test create_agent function
    print("\n1. Testing create_agent()...")
    try:
        agent = create_agent(
            role="backend",
            project_path=project_path,
            config={
                "model": "sonnet",
                "temperature": 0.7,
                "mcp_tools": ["memory", "filesystem"]
            }
        )
        print(f"   [OK] Created agent: {agent.name}")
        print(f"   Model: {agent.config.model} -> {agent.config.get_api_model()}")
        print(f"   Temperature: {agent.config.temperature}")
        print(f"   MCP Tools: {agent.config.mcp_tools}")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test orchestrator
    print("\n2. Testing TeamOrchestrator()...")
    try:
        # Initialize git if needed
        import subprocess
        if not (project_path / ".git").exists():
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project_path, capture_output=True)
            (project_path / "README.md").write_text("# Test Project")
            subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=project_path, capture_output=True)
            print("   Git initialized")

        orchestrator = TeamOrchestrator(project_path, model="sonnet")
        print(f"   [OK] Created orchestrator")
        print(f"   Model: {orchestrator.model}")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test plan creation
    print("\n3. Creating execution plan...")
    print("   (This will call Claude API)")
    try:
        # Add agent to orchestrator (agents is a dict)
        orchestrator.agents["backend"] = agent

        # Create plan
        plan = await orchestrator.create_plan("Create a simple Hello World Python app with a main.py file")
        print(f"   [OK] Plan created!")
        print(f"   Tasks: {len(plan.tasks)}")
        for task in plan.tasks:
            desc = task.description[:50] if hasattr(task, 'description') else str(task)[:50]
            print(f"   - {task.role}: {desc}...")
    except Exception as e:
        print(f"   [ERROR] Error creating plan: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
