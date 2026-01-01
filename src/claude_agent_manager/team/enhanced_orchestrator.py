"""
Enhanced Team Orchestrator with MCP and Graph Memory
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from .shared_context import SharedContext, AgentUpdate, TaskStatus, SharedInterface
from ..memory_graph import MemoryGraph, NodeType, EdgeType
from ..worktree_manager import WorktreeManager


@dataclass
class AgentConfig:
    """Enhanced agent configuration with MCP."""
    role: str
    name: Optional[str] = None
    tech_stack: List[str] = None
    custom_prompt: Optional[str] = None
    mcp_servers: List[str] = None
    mcp_tools: List[str] = None
    depends_on: List[str] = None
    max_iterations: int = 10
    auto_commit: bool = True


class EnhancedAgent:
    """Agent with MCP and memory integration."""
    
    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        shared_context: SharedContext,
        memory_graph: MemoryGraph,
        worktree_path: Path
    ):
        self.id = agent_id
        self.config = config
        self.shared_context = shared_context
        self.memory_graph = memory_graph
        self.worktree_path = worktree_path
        
        self.role = config.role
        self.name = config.name or f"{config.role}_{agent_id[:8]}"
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.blockers: List[str] = []
        self.current_task: Optional[str] = None
        self.mcp_tools_used: List[str] = []
        self.memory_context: Dict[str, Any] = {}
        self.branch: Optional[str] = None
    
    async def check_dependencies(self) -> bool:
        """Проверить готовность зависимостей через Graph Memory."""
        if not self.config.depends_on:
            return True
        
        # Проверить через memory graph
        for dep in self.config.depends_on:
            if not await self.memory_graph.check_interface_available(dep):
                # Добавить блокер
                if dep not in self.blockers:
                    self.blockers.append(dep)
                    await self.memory_graph.add_blocker(
                        self.id,
                        dep,
                        f"Waiting for {dep} to be ready"
                    )
                return False
        
        # Все зависимости готовы - разрешить блокеры
        for blocker in self.blockers[:]:
            await self.memory_graph.resolve_blocker(self.id, blocker)
            self.blockers.remove(blocker)
        
        return True
    
    async def execute(self, task_description: str):
        """Выполнить задачу агента с MCP интеграцией."""
        self.current_task = task_description
        self.status = TaskStatus.IN_PROGRESS
        
        # Обновить в graph memory
        await self.memory_graph.update_agent_status(
            self.id,
            status="in_progress",
            current_task=task_description
        )
        
        # Создать worktree
        from ..worktree_manager import WorktreeManager
        wt_manager = WorktreeManager(self.worktree_path.parent)
        
        worktree_info = await wt_manager.create_worktree(
            agent_id=self.id,
            task_name=self.role
        )
        
        self.branch = worktree_info["branch"]
        
        # Получить контекст из memory graph
        dependencies_data = {}
        if self.config.depends_on:
            for dep in self.config.depends_on:
                node = self.memory_graph.get_node(dep)
                if node:
                    dependencies_data[dep] = node.data
        
        # Подготовить промпт с контекстом
        system_prompt = self._build_system_prompt(dependencies_data)
        
        # TODO: Вызов Claude API с MCP tools
        # result = await self._call_claude_with_mcp(system_prompt, task_description)
        
        # Симуляция работы
        await asyncio.sleep(2)
        self.progress = 100.0
        
        # Регистрация результатов в graph memory
        await self._register_outputs()
        
        self.status = TaskStatus.DONE
        await self.memory_graph.update_agent_status(
            self.id,
            status="done",
            progress=100.0
        )
    
    def _build_system_prompt(self, dependencies: Dict[str, Any]) -> str:
        """Построить system prompt с контекстом."""
        # Базовый промпт для роли
        from .api import PREDEFINED_ROLES
        role_config = PREDEFINED_ROLES.get(self.role)
        base_prompt = role_config.system_prompt if role_config else ""
        
        # Добавить контекст зависимостей
        context_section = ""
        if dependencies:
            context_section = "\n\nAvailable Context from Dependencies:\n"
            for dep_id, dep_data in dependencies.items():
                context_section += f"\n{dep_id}:\n{json.dumps(dep_data, indent=2)}\n"
        
        # Добавить MCP tools
        mcp_section = ""
        if self.config.mcp_servers:
            mcp_section = f"\n\nMCP Servers Available: {', '.join(self.config.mcp_servers)}\n"
            mcp_section += "Use these MCP tools to:\n"
            mcp_section += "- memory: Store and retrieve information\n"
            mcp_section += "- filesystem: Read/write files\n"
            mcp_section += "- git: Commit changes\n"
        
        return base_prompt + context_section + mcp_section
    
    async def _register_outputs(self):
        """Регистрировать выходные артефакты в graph memory."""
        # Пример: backend регистрирует API
        if self.role == "backend":
            await self.memory_graph.register_interface(
                f"api_{self.id}",
                owner_agent=self.id,
                interface_type="api",
                spec={
                    "endpoints": ["/users", "/posts"],
                    "base_url": "/api"
                }
            )
        
        # Пример: architect регистрирует contracts
        elif self.role == "architect":
            await self.memory_graph.register_interface(
                "api_contracts",
                owner_agent=self.id,
                interface_type="contracts",
                spec={
                    "contracts_file": "docs/api_contracts.yaml"
                }
            )


class EnhancedTeamOrchestrator:
    """
    Enhanced orchestrator with:
    - Graph Memory для координации
    - MCP integration для tools
    - Real-time dashboard updates
    """
    
    def __init__(
        self,
        project_path: Path,
        max_parallel: int = 3,
        auto_merge: bool = True,
        use_graph_memory: bool = True
    ):
        self.project_path = Path(project_path)
        self.max_parallel = max_parallel
        self.auto_merge = auto_merge
        
        # Core components
        self.shared_context = SharedContext(project_path)
        self.worktree_manager = WorktreeManager(project_path)
        
        # Graph memory
        self.use_graph_memory = use_graph_memory
        if use_graph_memory:
            self.memory_graph = MemoryGraph(str(project_path))
        else:
            self.memory_graph = None
        
        # Agents
        self.agents: List[EnhancedAgent] = []
        self.ready_to_merge = False
    
    async def add_agent(
        self,
        role: str,
        name: Optional[str] = None,
        tech_stack: List[str] = None,
        custom_prompt: Optional[str] = None,
        mcp_servers: List[str] = None,
        mcp_tools: List[str] = None,
        depends_on: List[str] = None
    ) -> EnhancedAgent:
        """Добавить агента в команду."""
        
        agent_id = f"agent_{role}_{len(self.agents)}"
        
        config = AgentConfig(
            role=role,
            name=name,
            tech_stack=tech_stack or [],
            custom_prompt=custom_prompt,
            mcp_servers=mcp_servers or ["memory", "filesystem"],
            mcp_tools=mcp_tools or [],
            depends_on=depends_on or []
        )
        
        agent = EnhancedAgent(
            agent_id=agent_id,
            config=config,
            shared_context=self.shared_context,
            memory_graph=self.memory_graph,
            worktree_path=self.project_path
        )
        
        self.agents.append(agent)
        
        # Регистрировать в graph memory
        if self.memory_graph:
            await self.memory_graph.register_agent(
                agent_id=agent_id,
                role=role,
                tech_stack=tech_stack or [],
                depends_on=depends_on
            )
        
        return agent
    
    async def remove_agent(self, agent_id: str):
        """Удалить агента из команды."""
        self.agents = [a for a in self.agents if a.id != agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[EnhancedAgent]:
        """Получить агента по ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None
    
    async def execute_plan(self):
        """Выполнить план с учетом зависимостей."""
        
        pending_agents = [a for a in self.agents if a.status == TaskStatus.PENDING]
        
        while pending_agents:
            # Найти готовых агентов (без блокеров)
            ready_agents = []
            
            for agent in pending_agents:
                if await agent.check_dependencies():
                    ready_agents.append(agent)
            
            if not ready_agents:
                # Deadlock detection
                print("Warning: No agents ready, possible deadlock")
                await asyncio.sleep(1)
                continue
            
            # Запустить агентов параллельно (до max_parallel)
            batch = ready_agents[:self.max_parallel]
            
            tasks = [
                agent.execute(f"Task for {agent.role}")
                for agent in batch
            ]
            
            await asyncio.gather(*tasks)
            
            # Обновить список pending
            pending_agents = [a for a in self.agents if a.status == TaskStatus.PENDING]
        
        # Все агенты завершили работу
        self.ready_to_merge = True
    
    async def auto_merge(self) -> Dict[str, Any]:
        """Auto-merge всех веток с AI conflict resolution."""
        
        if not self.ready_to_merge:
            return {
                "success": False,
                "error": "Not all agents are done"
            }
        
        # Сортировать агентов по зависимостям (topological sort)
        sorted_agents = self._topological_sort()
        
        merged_branches = []
        conflicts = []
        
        for agent in sorted_agents:
            if not agent.branch:
                continue
            
            try:
                # Merge branch
                import subprocess
                result = subprocess.run(
                    ["git", "merge", agent.branch, "--no-ff", "-m", f"Merge {agent.branch}"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    merged_branches.append(agent.branch)
                else:
                    # Conflict detected
                    conflicts.append({
                        "branch": agent.branch,
                        "error": result.stderr
                    })
                    
                    # TODO: AI conflict resolution
                    # resolved = await self._ai_resolve_conflict(agent.branch)
            
            except Exception as e:
                conflicts.append({
                    "branch": agent.branch,
                    "error": str(e)
                })
        
        return {
            "success": len(conflicts) == 0,
            "merged_branches": merged_branches,
            "conflicts": conflicts
        }
    
    def _topological_sort(self) -> List[EnhancedAgent]:
        """Сортировка агентов по зависимостям."""
        # Простая топологическая сортировка
        sorted_agents = []
        visited = set()
        
        def visit(agent: EnhancedAgent):
            if agent.id in visited:
                return
            
            visited.add(agent.id)
            
            # Сначала обработать зависимости
            if agent.config.depends_on:
                for dep in agent.config.depends_on:
                    dep_agent = self.get_agent(dep)
                    if dep_agent:
                        visit(dep_agent)
            
            sorted_agents.append(agent)
        
        for agent in self.agents:
            visit(agent)
        
        return sorted_agents
