"""
AutoGen Integration - Интеграция с Microsoft AutoGen
===================================================

Использует AutoGen для:
1. Multi-agent conversations
2. Групповые чаты между агентами
3. Автоматическое делегирование
4. Code execution в worktrees
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from autogen import ConversableAgent, GroupChat, GroupChatManager
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    # Warning printed only when actually needed


class WorktreeCodeExecutor:
    """Executor для выполнения кода в worktree агента."""
    
    def __init__(self, worktree_path: Path):
        self.worktree_path = worktree_path
    
    def execute(self, code: str) -> str:
        """Выполнить код в worktree."""
        # Сохраняем во временный файл
        temp_file = self.worktree_path / "_temp_code.py"
        temp_file.write_text(code)
        
        try:
            result = subprocess.run(
                ["python", str(temp_file)],
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout or result.stderr
            return output
        
        except subprocess.TimeoutExpired:
            return "ERROR: Code execution timeout"
        
        except Exception as e:
            return f"ERROR: {str(e)}"
        
        finally:
            if temp_file.exists():
                temp_file.unlink()


class AutoGenTeam:
    """
    Команда агентов на базе AutoGen.
    
    Каждый агент:
    - Работает в своем worktree
    - Общается с другими через GroupChat
    - Может делегировать задачи
    """
    
    def __init__(
        self,
        project_path: Path,
        api_key: Optional[str] = None
    ):
        if not AUTOGEN_AVAILABLE:
            raise ImportError("AutoGen is not installed")
        
        self.project_path = project_path
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.agents: Dict[str, ConversableAgent] = {}
        self.executors: Dict[str, WorktreeCodeExecutor] = {}
    
    def create_agent(
        self,
        role: str,
        worktree_path: Path,
        task_description: str,
        can_execute_code: bool = True
    ) -> ConversableAgent:
        """Создать AutoGen агента для роли."""
        
        # Executor для этого worktree
        if can_execute_code:
            executor = WorktreeCodeExecutor(worktree_path)
            self.executors[role] = executor
        else:
            executor = None
        
        # System message на базе роли
        system_messages = {
            "backend": f"""You are a Backend Developer.
Working directory: {worktree_path}
Task: {task_description}

Your responsibilities:
- Implement server-side logic
- Create API endpoints
- Handle data processing
- Write tests

Always work in your assigned directory: {worktree_path}
Commit changes incrementally with clear messages.""",

            "frontend": f"""You are a Frontend Developer.
Working directory: {worktree_path}
Task: {task_description}

Your responsibilities:
- Implement UI components
- Handle state management
- Consume APIs from backend team
- Create responsive designs

Always work in your assigned directory: {worktree_path}
Wait for backend API specs before implementing API calls.""",

            "database": f"""You are a Database Engineer.
Working directory: {worktree_path}
Task: {task_description}

Your responsibilities:
- Design database schemas
- Write migrations
- Optimize queries
- Provide schema docs to team

Always work in your assigned directory: {worktree_path}""",

            "devops": f"""You are a DevOps Engineer.
Working directory: {worktree_path}
Task: {task_description}

Your responsibilities:
- Setup CI/CD
- Deploy services
- Monitor systems
- Coordinate with all teams

Always work in your assigned directory: {worktree_path}""",

            "architect": f"""You are the Software Architect.
Working directory: {worktree_path}
Task: {task_description}

Your responsibilities:
- Design overall architecture
- Define interfaces between components
- Review team's work
- Ensure consistency

Coordinate all teams and make architectural decisions."""
        }
        
        system_message = system_messages.get(role, f"You are a {role} developer working on: {task_description}")
        
        # Конфиг для Claude через Anthropic API
        llm_config = {
            "config_list": [{
                "model": "claude-sonnet-4-20250514",
                "api_key": self.api_key,
                "api_type": "anthropic"
            }],
            "temperature": 0.7
        }
        
        # Создаем агента
        agent = ConversableAgent(
            name=role,
            system_message=system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",  # Полная автономность
            max_consecutive_auto_reply=10,
            code_execution_config={
                "work_dir": str(worktree_path),
                "use_docker": False,
                "executor": executor.execute if executor else None
            }
        )
        
        self.agents[role] = agent
        return agent
    
    def create_group_chat(
        self,
        agents: List[ConversableAgent],
        max_round: int = 50
    ) -> GroupChat:
        """Создать групповой чат между агентами."""
        
        group_chat = GroupChat(
            agents=agents,
            messages=[],
            max_round=max_round,
            speaker_selection_method="auto"  # Автоматический выбор следующего спикера
        )
        
        return group_chat
    
    def run_team_task(
        self,
        task: str,
        agents: List[ConversableAgent],
        max_round: int = 50
    ) -> Dict[str, Any]:
        """Запустить командную задачу."""
        
        # Создаем группу
        group_chat = self.create_group_chat(agents, max_round)
        
        # Менеджер группы
        manager = GroupChatManager(
            groupchat=group_chat,
            llm_config=self.agents[list(self.agents.keys())[0]].llm_config
        )
        
        # Стартуем задачу
        initiator = agents[0]
        
        result = initiator.initiate_chat(
            manager,
            message=f"""Team task: {task}

Each agent should:
1. Review the task
2. Identify your part of work
3. Coordinate with others
4. Execute in your worktree
5. Share progress

Let's start!"""
        )
        
        return {
            "messages": group_chat.messages,
            "summary": result
        }


# ============================================================================
# PRESET CONFIGURATIONS
# ============================================================================

class TeamPresets:
    """Готовые конфигурации команд."""
    
    @staticmethod
    def fullstack_team(
        project_path: Path,
        api_key: str
    ) -> AutoGenTeam:
        """
        Fullstack команда:
        - Architect
        - Backend
        - Frontend
        - Database
        - DevOps
        """
        team = AutoGenTeam(project_path, api_key)
        
        # Создаем worktrees для каждого
        worktrees = {
            "architect": project_path / ".worktrees" / "architect",
            "backend": project_path / ".worktrees" / "backend",
            "frontend": project_path / ".worktrees" / "frontend",
            "database": project_path / ".worktrees" / "database",
            "devops": project_path / ".worktrees" / "devops"
        }
        
        for role, wt_path in worktrees.items():
            wt_path.mkdir(parents=True, exist_ok=True)
        
        return team
    
    @staticmethod
    def microservices_team(
        project_path: Path,
        api_key: str,
        services: List[str]
    ) -> AutoGenTeam:
        """
        Microservices команда:
        - Architect
        - Service developer per service
        - DevOps
        """
        team = AutoGenTeam(project_path, api_key)
        
        # Архитектор
        arch_wt = project_path / ".worktrees" / "architect"
        arch_wt.mkdir(parents=True, exist_ok=True)
        
        # По агенту на сервис
        for service in services:
            service_wt = project_path / ".worktrees" / service
            service_wt.mkdir(parents=True, exist_ok=True)
        
        # DevOps
        devops_wt = project_path / ".worktrees" / "devops"
        devops_wt.mkdir(parents=True, exist_ok=True)
        
        return team


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_fullstack_task():
    """Пример: Fullstack фича."""
    
    project_path = Path("/path/to/project")
    team = TeamPresets.fullstack_team(project_path, "your-api-key")
    
    # Создаем агентов
    architect = team.create_agent(
        "architect",
        project_path / ".worktrees" / "architect",
        "Design payment system architecture"
    )
    
    backend = team.create_agent(
        "backend",
        project_path / ".worktrees" / "backend",
        "Implement payment API"
    )
    
    frontend = team.create_agent(
        "frontend",
        project_path / ".worktrees" / "frontend",
        "Build payment UI"
    )
    
    # Запускаем командную задачу
    result = team.run_team_task(
        "Add cryptocurrency payment with CryptoBot integration",
        [architect, backend, frontend]
    )
    
    return result


def example_code_review():
    """Пример: Код ревью между агентами."""
    
    project_path = Path("/path/to/project")
    team = AutoGenTeam(project_path, "your-api-key")
    
    # Developer
    developer = team.create_agent(
        "backend",
        project_path / ".worktrees" / "backend",
        "Implement feature"
    )
    
    # Reviewer
    reviewer = team.create_agent(
        "architect",
        project_path / ".worktrees" / "review",
        "Review code quality"
    )
    
    # Групповой чат
    chat = team.create_group_chat([developer, reviewer], max_round=10)
    manager = GroupChatManager(groupchat=chat)
    
    developer.initiate_chat(
        manager,
        message="I've implemented the payment API. Please review."
    )
    
    return chat.messages
