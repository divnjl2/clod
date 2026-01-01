"""
Team Manager - Complete team management with UI integration
Manages agents, roles, MCP permissions, and work graph memory
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum

from .shared_context import SharedContext


class AgentStack(str, Enum):
    """Agent technology stack."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    MIXED = "mixed"


class MCPPermission(str, Enum):
    """MCP permissions for agents."""
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    READ_GRAPH = "read_graph"
    WRITE_GRAPH = "write_graph"
    EXECUTE_TOOLS = "execute_tools"
    FILE_SYSTEM = "file_system"
    NETWORK = "network"
    DATABASE = "database"


@dataclass
class AgentRole:
    """Agent role definition."""
    id: str
    name: str  # Display name
    role_type: str  # architect, backend, frontend, qa, etc
    description: str
    stack: AgentStack
    skills: List[str] = field(default_factory=list)
    mcp_permissions: Set[MCPPermission] = field(default_factory=set)
    system_prompt: str = ""
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        data = asdict(self)
        data['mcp_permissions'] = [p.value for p in self.mcp_permissions]
        data['stack'] = self.stack.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentRole':
        """Create from dict."""
        data['stack'] = AgentStack(data['stack'])
        data['mcp_permissions'] = {MCPPermission(p) for p in data.get('mcp_permissions', [])}
        return cls(**data)


@dataclass
class WorkGraphMemory:
    """Work graph memory for team coordination."""
    graph_id: str
    nodes: Dict[str, dict] = field(default_factory=dict)  # agent_id -> node_data
    edges: List[dict] = field(default_factory=list)  # dependencies
    shared_memory: Dict[str, any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_node(self, agent_id: str, data: dict):
        """Add agent node to graph."""
        self.nodes[agent_id] = {
            **data,
            'added_at': datetime.now().isoformat()
        }
    
    def add_edge(self, from_agent: str, to_agent: str, edge_type: str = "depends_on"):
        """Add dependency edge."""
        self.edges.append({
            'from': from_agent,
            'to': to_agent,
            'type': edge_type,
            'created_at': datetime.now().isoformat()
        })
    
    def get_dependencies(self, agent_id: str) -> List[str]:
        """Get agent dependencies."""
        return [
            edge['to'] 
            for edge in self.edges 
            if edge['from'] == agent_id
        ]


class TeamManager:
    """
    Complete team management system.
    
    Features:
    - CRUD operations on agents
    - Role customization
    - MCP permissions management
    - Work graph memory
    - Team mode state
    - Dashboard integration
    """
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.team_dir = project_path / ".claude-team"
        self.team_dir.mkdir(exist_ok=True)
        
        self.config_file = self.team_dir / "team_config.json"
        self.agents_file = self.team_dir / "agents.json"
        self.graph_file = self.team_dir / "work_graph.json"
        
        self.shared_context = SharedContext(self.team_dir)
        self.agents: Dict[str, AgentRole] = {}
        self.work_graph: Optional[WorkGraphMemory] = None
        self.team_mode_active: bool = False
        
        self._load_state()
    
    def _load_state(self):
        """Load team state from disk."""
        # Load agents
        if self.agents_file.exists():
            data = json.loads(self.agents_file.read_text())
            self.agents = {
                agent_id: AgentRole.from_dict(agent_data)
                for agent_id, agent_data in data.items()
            }
        else:
            # Initialize with default roles
            self._create_default_roles()
        
        # Load work graph
        if self.graph_file.exists():
            data = json.loads(self.graph_file.read_text())
            self.work_graph = WorkGraphMemory(**data)
        else:
            self.work_graph = WorkGraphMemory(graph_id="default")
        
        # Load config
        if self.config_file.exists():
            config = json.loads(self.config_file.read_text())
            self.team_mode_active = config.get('team_mode_active', False)
    
    def _save_state(self):
        """Save team state to disk."""
        # Save agents
        agents_data = {
            agent_id: agent.to_dict()
            for agent_id, agent in self.agents.items()
        }
        self.agents_file.write_text(json.dumps(agents_data, indent=2))
        
        # Save work graph
        graph_data = {
            'graph_id': self.work_graph.graph_id,
            'nodes': self.work_graph.nodes,
            'edges': self.work_graph.edges,
            'shared_memory': self.work_graph.shared_memory,
            'created_at': self.work_graph.created_at
        }
        self.graph_file.write_text(json.dumps(graph_data, indent=2))
        
        # Save config
        config = {
            'team_mode_active': self.team_mode_active,
            'updated_at': datetime.now().isoformat()
        }
        self.config_file.write_text(json.dumps(config, indent=2))
    
    def _create_default_roles(self):
        """Create default agent roles."""
        default_roles = [
            AgentRole(
                id="architect",
                name="Architect",
                role_type="architect",
                description="Software architect - designs system architecture",
                stack=AgentStack.MIXED,
                skills=["architecture", "system_design", "api_design"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.WRITE_GRAPH
                },
                system_prompt="You are a Software Architect with 15+ years experience."
            ),
            AgentRole(
                id="backend",
                name="Backend Developer",
                role_type="backend",
                description="Backend developer - implements server-side logic",
                stack=AgentStack.PYTHON,
                skills=["fastapi", "sqlalchemy", "pytest"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.FILE_SYSTEM,
                    MCPPermission.DATABASE
                },
                system_prompt="You are a Backend Developer specializing in Python/FastAPI."
            ),
            AgentRole(
                id="frontend",
                name="Frontend Developer",
                role_type="frontend",
                description="Frontend developer - builds UI components",
                stack=AgentStack.TYPESCRIPT,
                skills=["react", "typescript", "tailwind"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.FILE_SYSTEM
                },
                system_prompt="You are a Frontend Developer specializing in React/TypeScript."
            ),
            AgentRole(
                id="qa",
                name="QA Engineer",
                role_type="qa",
                description="Quality assurance - comprehensive testing",
                stack=AgentStack.PYTHON,
                skills=["pytest", "selenium", "coverage"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.FILE_SYSTEM,
                    MCPPermission.EXECUTE_TOOLS
                },
                system_prompt="You are a QA Engineer focused on comprehensive testing."
            ),
            AgentRole(
                id="reviewer",
                name="Code Reviewer",
                role_type="reviewer",
                description="Code reviewer - quality gate and security",
                stack=AgentStack.MIXED,
                skills=["code_review", "security", "best_practices"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH
                },
                system_prompt="You are a Senior Code Reviewer with security expertise."
            ),
            AgentRole(
                id="database",
                name="Database Engineer",
                role_type="database",
                description="Database engineer - schema design and optimization",
                stack=AgentStack.PYTHON,
                skills=["postgresql", "migrations", "optimization"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.DATABASE
                },
                system_prompt="You are a Database Engineer specializing in PostgreSQL.",
                enabled=False  # Disabled by default
            ),
            AgentRole(
                id="telegram",
                name="Telegram Bot Developer",
                role_type="telegram",
                description="Telegram bot developer - bot handlers and integrations",
                stack=AgentStack.PYTHON,
                skills=["aiogram", "telegram_api", "fsm"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.FILE_SYSTEM,
                    MCPPermission.NETWORK
                },
                system_prompt="You are a Telegram Bot Developer specializing in aiogram.",
                enabled=False  # Disabled by default
            ),
            AgentRole(
                id="security",
                name="Security Auditor",
                role_type="security",
                description="Security auditor - vulnerability scanning and OWASP",
                stack=AgentStack.MIXED,
                skills=["security", "owasp", "penetration_testing"],
                mcp_permissions={
                    MCPPermission.READ_MEMORY,
                    MCPPermission.WRITE_MEMORY,
                    MCPPermission.READ_GRAPH,
                    MCPPermission.EXECUTE_TOOLS
                },
                system_prompt="You are a Security Auditor focused on OWASP Top 10.",
                enabled=False  # Disabled by default
            )
        ]
        
        for role in default_roles:
            self.agents[role.id] = role
        
        self._save_state()
    
    # ========================================================================
    # Team Mode Management
    # ========================================================================
    
    async def activate_team_mode(self) -> dict:
        """Activate team mode and update dashboard."""
        self.team_mode_active = True
        self._save_state()
        
        # Initialize work graph
        self.work_graph = WorkGraphMemory(
            graph_id=f"team_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Add enabled agents to graph
        for agent_id, agent in self.agents.items():
            if agent.enabled:
                self.work_graph.add_node(agent_id, {
                    'name': agent.name,
                    'role_type': agent.role_type,
                    'status': 'ready'
                })
        
        self._save_state()
        
        return {
            'status': 'active',
            'team_mode': True,
            'active_agents': [a.id for a in self.agents.values() if a.enabled],
            'work_graph_id': self.work_graph.graph_id
        }
    
    async def deactivate_team_mode(self) -> dict:
        """Deactivate team mode."""
        self.team_mode_active = False
        self._save_state()
        
        return {
            'status': 'inactive',
            'team_mode': False
        }
    
    def is_team_mode_active(self) -> bool:
        """Check if team mode is active."""
        return self.team_mode_active
    
    # ========================================================================
    # Agent CRUD Operations
    # ========================================================================
    
    async def add_agent(
        self,
        role_type: str,
        name: str,
        description: str,
        stack: AgentStack,
        skills: List[str] = None,
        mcp_permissions: Set[MCPPermission] = None,
        system_prompt: str = "",
        enabled: bool = True
    ) -> AgentRole:
        """Add new agent to team."""
        agent_id = f"{role_type}_{len([a for a in self.agents.values() if a.role_type == role_type])}"
        
        agent = AgentRole(
            id=agent_id,
            name=name,
            role_type=role_type,
            description=description,
            stack=stack,
            skills=skills or [],
            mcp_permissions=mcp_permissions or set(),
            system_prompt=system_prompt,
            enabled=enabled
        )
        
        self.agents[agent_id] = agent
        
        # Add to work graph if team mode is active
        if self.team_mode_active and enabled:
            self.work_graph.add_node(agent_id, {
                'name': agent.name,
                'role_type': agent.role_type,
                'status': 'ready'
            })
        
        self._save_state()
        return agent
    
    async def remove_agent(self, agent_id: str) -> bool:
        """Remove agent from team."""
        if agent_id not in self.agents:
            return False
        
        del self.agents[agent_id]
        
        # Remove from work graph
        if agent_id in self.work_graph.nodes:
            del self.work_graph.nodes[agent_id]
        
        # Remove edges
        self.work_graph.edges = [
            edge for edge in self.work_graph.edges
            if edge['from'] != agent_id and edge['to'] != agent_id
        ]
        
        self._save_state()
        return True
    
    async def update_agent(
        self,
        agent_id: str,
        **updates
    ) -> Optional[AgentRole]:
        """Update agent configuration."""
        if agent_id not in self.agents:
            return None
        
        agent = self.agents[agent_id]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        agent.updated_at = datetime.now().isoformat()
        
        # Update work graph if needed
        if agent_id in self.work_graph.nodes:
            self.work_graph.nodes[agent_id].update({
                'name': agent.name,
                'role_type': agent.role_type,
                'updated_at': agent.updated_at
            })
        
        self._save_state()
        return agent
    
    async def toggle_agent(self, agent_id: str, enabled: bool) -> bool:
        """Enable or disable agent."""
        if agent_id not in self.agents:
            return False
        
        self.agents[agent_id].enabled = enabled
        
        if self.team_mode_active:
            if enabled and agent_id not in self.work_graph.nodes:
                # Add to graph
                agent = self.agents[agent_id]
                self.work_graph.add_node(agent_id, {
                    'name': agent.name,
                    'role_type': agent.role_type,
                    'status': 'ready'
                })
            elif not enabled and agent_id in self.work_graph.nodes:
                # Remove from graph
                del self.work_graph.nodes[agent_id]
        
        self._save_state()
        return True
    
    def get_agent(self, agent_id: str) -> Optional[AgentRole]:
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def list_agents(self, enabled_only: bool = False) -> List[AgentRole]:
        """List all agents."""
        agents = list(self.agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents
    
    # ========================================================================
    # MCP Permissions Management
    # ========================================================================
    
    async def grant_permission(self, agent_id: str, permission: MCPPermission) -> bool:
        """Grant MCP permission to agent."""
        if agent_id not in self.agents:
            return False
        
        self.agents[agent_id].mcp_permissions.add(permission)
        self._save_state()
        return True
    
    async def revoke_permission(self, agent_id: str, permission: MCPPermission) -> bool:
        """Revoke MCP permission from agent."""
        if agent_id not in self.agents:
            return False
        
        self.agents[agent_id].mcp_permissions.discard(permission)
        self._save_state()
        return True
    
    def has_permission(self, agent_id: str, permission: MCPPermission) -> bool:
        """Check if agent has permission."""
        agent = self.agents.get(agent_id)
        return agent and permission in agent.mcp_permissions
    
    # ========================================================================
    # Work Graph Memory
    # ========================================================================
    
    async def add_dependency(self, from_agent: str, to_agent: str):
        """Add dependency between agents."""
        self.work_graph.add_edge(from_agent, to_agent, "depends_on")
        self._save_state()
    
    async def get_agent_dependencies(self, agent_id: str) -> List[str]:
        """Get agent dependencies."""
        return self.work_graph.get_dependencies(agent_id)
    
    async def update_shared_memory(self, key: str, value: any):
        """Update shared memory in work graph."""
        self.work_graph.shared_memory[key] = value
        self._save_state()
    
    async def get_shared_memory(self, key: str) -> any:
        """Get value from shared memory."""
        return self.work_graph.shared_memory.get(key)
    
    async def get_work_graph_state(self) -> dict:
        """Get current work graph state."""
        return {
            'graph_id': self.work_graph.graph_id,
            'nodes': self.work_graph.nodes,
            'edges': self.work_graph.edges,
            'shared_memory': self.work_graph.shared_memory
        }
    
    # ========================================================================
    # Dashboard Integration
    # ========================================================================
    
    async def get_dashboard_state(self) -> dict:
        """Get state for dashboard UI."""
        return {
            'team_mode_active': self.team_mode_active,
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'work_graph': await self.get_work_graph_state() if self.team_mode_active else None,
            'active_agents': [a.id for a in self.agents.values() if a.enabled],
            'total_agents': len(self.agents),
            'enabled_agents': len([a for a in self.agents.values() if a.enabled])
        }
    
    async def get_agent_status(self, agent_id: str) -> dict:
        """Get detailed agent status."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {'error': 'Agent not found'}
        
        status = {
            **agent.to_dict(),
            'dependencies': await self.get_agent_dependencies(agent_id),
            'in_work_graph': agent_id in self.work_graph.nodes
        }
        
        if agent_id in self.work_graph.nodes:
            status['graph_status'] = self.work_graph.nodes[agent_id]
        
        return status
