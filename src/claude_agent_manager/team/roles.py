"""
Agent Roles - Специализированные роли агентов на основе MetaGPT
==============================================================

Источник: MetaGPT (roles/*.py)
- Architect role
- Engineer role
- QA Engineer role

Дополнения:
- Frontend/Backend разделение
- Reviewer role
- Refactoring specialist
- DevOps engineer

Каждая роль:
1. Имеет специфичный system prompt
2. Знает свой workflow
3. Понимает зависимости от других ролей
4. Производит определённые артефакты
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .base_agent import BaseAgent, AgentConfig, Message, MessageRole
from .prompts import get_prompt_for_role, build_agent_prompt, get_clarification_prompt
from .git_operations import WorktreeGitOps

if TYPE_CHECKING:
    from .shared_context import SharedContext


@dataclass
class RoleCapabilities:
    """Возможности роли."""
    can_create_files: bool = True
    can_modify_files: bool = True
    can_delete_files: bool = False
    can_execute_code: bool = True
    can_access_network: bool = False
    can_use_git: bool = True
    file_types: List[str] = field(default_factory=list)  # Какие файлы может менять


# =============================================================================
# SPECIALIZED AGENTS (MetaGPT pattern)
# =============================================================================

class ArchitectAgent(BaseAgent):
    """
    Архитектор - дизайн системы.

    Источник: MetaGPT architect.py

    Responsibilities:
    - Анализ требований
    - Дизайн архитектуры
    - Определение интерфейсов
    - Документация

    Output:
    - architecture.md
    - api_contracts.yaml
    - db_schema.sql
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="Architect",
            role="architect",
            system_prompt=get_prompt_for_role("architect", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=8000,  # Больше для архитектуры
            temperature=0.5   # Более детерминированный
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context
        self.capabilities = RoleCapabilities(
            can_delete_files=False,
            can_execute_code=False,
            file_types=[".md", ".yaml", ".yml", ".sql", ".json"]
        )

        # Регистрируем trigger для уточняющих вопросов
        self.register_reply(
            "clarify",
            lambda msg: get_clarification_prompt()
        )

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Выполнить задачу архитектора.

        Workflow (GPT-Engineer pattern):
        1. Анализ задачи
        2. Уточняющие вопросы (если нужно)
        3. Дизайн архитектуры
        4. Создание документов
        5. Регистрация интерфейсов
        """
        # Формируем промпт
        prompt = build_agent_prompt(
            role="architect",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        # Получаем архитектуру
        response = await self.receive(prompt)

        # Парсим артефакты
        artifacts = self._parse_artifacts(response)

        # Регистрируем интерфейсы в shared context
        if self.shared_context and artifacts.get("interfaces"):
            for interface in artifacts["interfaces"]:
                await self.shared_context.register_interface(interface)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": artifacts.get("summary", "Architecture designed"),
            "artifacts": artifacts,
            "interfaces_provided": artifacts.get("interfaces", []),
            "timestamp": datetime.now().isoformat()
        }

    def _parse_artifacts(self, response: str) -> Dict[str, Any]:
        """Извлечь артефакты из ответа."""
        artifacts = {
            "architecture": None,
            "api_contracts": None,
            "database": None,
            "interfaces": [],
            "summary": ""
        }

        # Пытаемся найти YAML блоки
        import re

        yaml_blocks = re.findall(r"```yaml\n(.*?)```", response, re.DOTALL)

        for block in yaml_blocks:
            if "architecture:" in block:
                artifacts["architecture"] = block
            elif "api_contracts:" in block or "endpoints:" in block:
                artifacts["api_contracts"] = block
            elif "database:" in block or "tables:" in block:
                artifacts["database"] = block

        # Извлекаем интерфейсы
        interface_matches = re.findall(
            r"interfaces_provided:\s*\n(.*?)(?=\n\w|$)",
            response,
            re.DOTALL
        )
        if interface_matches:
            for match in interface_matches:
                interfaces = re.findall(r"- name: (\w+)", match)
                artifacts["interfaces"].extend(interfaces)

        return artifacts


class BackendAgent(BaseAgent):
    """
    Backend Developer.

    Источник: MetaGPT engineer.py + SWE-agent prompts

    Responsibilities:
    - Implement API endpoints
    - Database operations
    - Business logic
    - Unit tests

    Output:
    - Python/Node.js code
    - Tests
    - Migrations
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="Backend",
            role="backend",
            system_prompt=get_prompt_for_role("backend", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.7
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context

        if worktree_path:
            from .git_operations import GitOperations
            try:
                self.git = GitOperations(worktree_path)
            except ValueError:
                self.git = None
        else:
            self.git = None

        self.capabilities = RoleCapabilities(
            can_delete_files=True,
            can_execute_code=True,
            can_access_network=True,
            file_types=[".py", ".js", ".ts", ".sql", ".json", ".yaml"]
        )

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Выполнить backend задачу.

        Workflow (TDD):
        1. Прочитать архитектуру из context
        2. Написать тест
        3. Реализовать код
        4. Запустить тесты
        5. Commit
        """
        # Проверяем зависимости от архитектуры
        if context and "architect" in str(context):
            arch_data = self._extract_architecture(context)
            if arch_data:
                task_description += f"\n\nArchitecture:\n{arch_data}"

        prompt = build_agent_prompt(
            role="backend",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        response = await self.receive(prompt)

        # Парсим созданные файлы
        files_info = self._parse_file_operations(response)

        # Коммитим если есть git
        if self.git:
            try:
                self.git.incremental_commit(
                    f"Backend: {task_description[:50]}",
                    agent_name=self.name
                )
            except Exception:
                pass

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": f"Backend implementation: {task_description[:100]}",
            "artifacts": {
                "files_created": files_info.get("created", []),
                "files_modified": files_info.get("modified", []),
                "tests_added": files_info.get("tests", [])
            },
            "timestamp": datetime.now().isoformat()
        }

    def _extract_architecture(self, context: Dict[str, Any]) -> Optional[str]:
        """Извлечь архитектуру из контекста."""
        for key, value in context.items():
            if "architect" in key.lower():
                if isinstance(value, dict):
                    return value.get("output", "")
        return None

    def _parse_file_operations(self, response: str) -> Dict[str, List[str]]:
        """Извлечь информацию о файловых операциях."""
        import re

        result = {
            "created": [],
            "modified": [],
            "tests": []
        }

        # Ищем упоминания файлов
        file_patterns = [
            r"creat(?:e|ed|ing)\s+(?:file\s+)?['\"]?(\S+\.(?:py|js|ts))['\"]?",
            r"modif(?:y|ied|ying)\s+(?:file\s+)?['\"]?(\S+\.(?:py|js|ts))['\"]?",
            r"test[s]?['\"]?(\S+\.(?:py|js|ts))['\"]?"
        ]

        for i, pattern in enumerate(file_patterns):
            matches = re.findall(pattern, response, re.IGNORECASE)
            if i == 0:
                result["created"].extend(matches)
            elif i == 1:
                result["modified"].extend(matches)
            else:
                result["tests"].extend(matches)

        return result


class FrontendAgent(BaseAgent):
    """
    Frontend Developer.

    Responsibilities:
    - UI components
    - State management
    - API integration
    - Responsive design
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="Frontend",
            role="frontend",
            system_prompt=get_prompt_for_role("frontend", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.7
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context
        self.capabilities = RoleCapabilities(
            file_types=[".tsx", ".jsx", ".ts", ".js", ".css", ".scss", ".html"]
        )

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполнить frontend задачу."""
        # Проверяем готовность backend API
        if self.shared_context:
            blockers = await self._check_api_dependencies(context)
            if blockers:
                return {
                    "agent": self.name,
                    "role": self.role,
                    "status": "blocked",
                    "blockers": blockers,
                    "message": f"Waiting for APIs: {', '.join(blockers)}"
                }

        prompt = build_agent_prompt(
            role="frontend",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        response = await self.receive(prompt)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": f"Frontend implementation: {task_description[:100]}",
            "artifacts": {},
            "timestamp": datetime.now().isoformat()
        }

    async def _check_api_dependencies(self, context: Dict[str, Any]) -> List[str]:
        """Проверить готовность API зависимостей."""
        blockers = []

        if not self.shared_context:
            return blockers

        # Ищем упоминания API в задаче
        ctx = await self.shared_context.read()
        interfaces = ctx.get("interfaces", {})

        for name, spec in interfaces.items():
            if spec.get("type") == "api" and spec.get("status") != "ready":
                blockers.append(name)

        return blockers


class QAAgent(BaseAgent):
    """
    QA Engineer.

    Источник: MetaGPT qa_engineer.py

    Responsibilities:
    - Write tests
    - Integration testing
    - E2E testing
    - Security testing
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="QA",
            role="qa",
            system_prompt=get_prompt_for_role("qa", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.5  # Более детерминированный для тестов
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context
        self.capabilities = RoleCapabilities(
            can_execute_code=True,
            file_types=[".py", ".js", ".ts"]  # Test files
        )

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполнить QA задачу."""
        prompt = build_agent_prompt(
            role="qa",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        response = await self.receive(prompt)

        # Парсим результаты тестов
        test_results = self._parse_test_results(response)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": f"Tests: {test_results.get('passed', 0)} passed, {test_results.get('failed', 0)} failed",
            "artifacts": {
                "test_results": test_results
            },
            "timestamp": datetime.now().isoformat()
        }

    def _parse_test_results(self, response: str) -> Dict[str, Any]:
        """Парсить результаты тестов."""
        import re

        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "coverage": 0
        }

        # Ищем числа в ответе
        passed_match = re.search(r"passed:\s*(\d+)", response, re.IGNORECASE)
        failed_match = re.search(r"failed:\s*(\d+)", response, re.IGNORECASE)
        coverage_match = re.search(r"coverage:\s*(\d+)%?", response, re.IGNORECASE)

        if passed_match:
            results["passed"] = int(passed_match.group(1))
        if failed_match:
            results["failed"] = int(failed_match.group(1))
        if coverage_match:
            results["coverage"] = int(coverage_match.group(1))

        results["total"] = results["passed"] + results["failed"]

        return results


class ReviewerAgent(BaseAgent):
    """
    Code Reviewer.

    Responsibilities:
    - Code review
    - Security audit
    - Performance review
    - Best practices check
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="Reviewer",
            role="reviewer",
            system_prompt=get_prompt_for_role("reviewer", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.3  # Консервативный для ревью
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context
        self.capabilities = RoleCapabilities(
            can_create_files=False,
            can_modify_files=False,
            can_execute_code=False
        )

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполнить code review."""
        prompt = build_agent_prompt(
            role="reviewer",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        response = await self.receive(prompt)

        # Парсим решение
        decision = self._parse_review_decision(response)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": f"Review: {decision['decision']}",
            "artifacts": {
                "review": decision
            },
            "timestamp": datetime.now().isoformat()
        }

    def _parse_review_decision(self, response: str) -> Dict[str, Any]:
        """Парсить решение ревью."""
        decision = {
            "decision": "REQUEST_CHANGES",
            "issues": [],
            "security_score": 0,
            "quality_score": 0
        }

        if "APPROVE" in response.upper():
            decision["decision"] = "APPROVE"
        elif "REQUEST_CHANGES" in response.upper():
            decision["decision"] = "REQUEST_CHANGES"

        # Ищем scores
        import re

        security_match = re.search(r"security:\s*(\d+)", response, re.IGNORECASE)
        quality_match = re.search(r"quality:\s*(\d+)", response, re.IGNORECASE)

        if security_match:
            decision["security_score"] = int(security_match.group(1))
        if quality_match:
            decision["quality_score"] = int(quality_match.group(1))

        return decision


class RefactoringAgent(BaseAgent):
    """
    Refactoring Specialist.

    Responsibilities:
    - Code smell detection
    - Refactoring
    - Complexity reduction
    - DRY enforcement
    """

    def __init__(
        self,
        worktree_path: Optional[Path] = None,
        shared_context: Optional['SharedContext'] = None
    ):
        config = AgentConfig(
            name="Refactoring",
            role="refactoring",
            system_prompt=get_prompt_for_role("refactoring", str(worktree_path or "")),
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            temperature=0.5
        )
        super().__init__(config)

        self.worktree_path = worktree_path
        self.shared_context = shared_context

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполнить рефакторинг."""
        prompt = build_agent_prompt(
            role="refactoring",
            task=task_description,
            worktree_path=str(self.worktree_path or "."),
            context=context
        )

        response = await self.receive(prompt)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "summary": "Refactoring completed",
            "artifacts": {},
            "timestamp": datetime.now().isoformat()
        }


# =============================================================================
# FACTORY
# =============================================================================

def create_agent(
    role: str,
    worktree_path: Optional[Path] = None,
    shared_context: Optional['SharedContext'] = None,
    config: Optional[Dict[str, Any]] = None,
    project_path: Optional[Path] = None
) -> BaseAgent:
    """
    Фабрика агентов.

    Args:
        role: Роль агента
        worktree_path: Путь к worktree
        shared_context: Shared context для координации
        config: Per-agent configuration (model, temperature, system_prompt, etc.)
        project_path: Project path (alternative to worktree_path)
    """
    agents = {
        "architect": ArchitectAgent,
        "backend": BackendAgent,
        "frontend": FrontendAgent,
        "qa": QAAgent,
        "reviewer": ReviewerAgent,
        "refactoring": RefactoringAgent,
        # Additional roles (using BaseAgent with custom config)
        "telegram": None,
        "database": None,
        "security": None,
        "devops": None,
    }

    agent_class = agents.get(role.lower())

    # Use worktree_path or project_path
    path = worktree_path or project_path

    if agent_class is None:
        # For roles without specific class, create SimpleAgent with config
        from .base_agent import SimpleAgent, AgentConfig
        agent_config = AgentConfig(
            role=role.lower(),
            model=config.get("model", "sonnet") if config else "sonnet",
            temperature=config.get("temperature", 0.7) if config else 0.7,
            max_tokens=config.get("max_tokens", 4000) if config else 4000,
            system_prompt=config.get("system_prompt", f"You are a {role} specialist.") if config else None,
        )
        return SimpleAgent(
            config=agent_config,
            worktree_path=path,
            shared_context=shared_context
        )

    if not agent_class:
        raise ValueError(f"Unknown role: {role}. Available: {list(agents.keys())}")

    # Create agent with optional config override
    agent = agent_class(
        worktree_path=path,
        shared_context=shared_context
    )

    # Apply config overrides if provided
    if config:
        if hasattr(agent, 'config'):
            if "model" in config:
                agent.config.model = config["model"]
            if "temperature" in config:
                agent.config.temperature = config["temperature"]
            if "max_tokens" in config:
                agent.config.max_tokens = config["max_tokens"]
            if "system_prompt" in config:
                agent.config.system_prompt = config["system_prompt"]

    return agent


def get_available_roles() -> List[str]:
    """Получить список доступных ролей."""
    return [
        "architect",
        "backend",
        "frontend",
        "qa",
        "reviewer",
        "refactoring"
    ]


def get_role_dependencies() -> Dict[str, List[str]]:
    """
    Получить зависимости между ролями.

    Определяет какие роли должны завершиться перед другими.
    """
    return {
        "architect": [],
        "backend": ["architect"],
        "frontend": ["architect", "backend"],
        "database": ["architect"],
        "qa": ["backend", "frontend"],
        "reviewer": ["qa"],
        "refactoring": ["reviewer"]
    }
