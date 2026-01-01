"""
Team Mode API - REST endpoints for agent management
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
import json

from .orchestrator import TeamOrchestrator
from .shared_context import SharedContext, AgentUpdate, TaskStatus
from ..worktree_manager import WorktreeManager
from ..memory_graph import MemoryGraph


router = APIRouter(prefix="/api/team", tags=["team"])


# ============================================================================
# MODELS
# ============================================================================

class AgentRole(BaseModel):
    """Agent role configuration."""
    id: str
    name: str
    description: str
    tech_stack: List[str]
    system_prompt: str
    mcp_permissions: List[str]
    color: str = "#3B82F6"


class AgentConfig(BaseModel):
    """Agent configuration for team."""
    role: str
    name: Optional[str] = None
    tech_stack: List[str] = []
    custom_prompt: Optional[str] = None
    mcp_servers: List[str] = []
    mcp_tools: List[str] = []
    depends_on: List[str] = []
    max_iterations: int = 10
    auto_commit: bool = True


class TeamConfig(BaseModel):
    """Team configuration."""
    project_path: str
    agents: List[AgentConfig]
    max_parallel: int = 3
    auto_merge: bool = True
    use_graph_memory: bool = True
    shared_mcp_servers: List[str] = ["memory", "filesystem"]


class AgentStatus(BaseModel):
    """Current agent status."""
    agent_id: str
    role: str
    name: str
    status: str  # pending, in_progress, blocked, done, failed
    worktree_path: Optional[str]
    branch: Optional[str]
    progress: float = 0.0
    blockers: List[str] = []
    current_task: Optional[str] = None
    mcp_tools_used: List[str] = []
    memory_context: Dict[str, Any] = {}


class TeamState(BaseModel):
    """Current team state."""
    active: bool
    agents: List[AgentStatus]
    shared_context: Dict[str, Any]
    graph_memory: Dict[str, Any]
    conflicts: List[Dict[str, Any]] = []
    merge_ready: bool = False


# ============================================================================
# PREDEFINED ROLES
# ============================================================================

PREDEFINED_ROLES = {
    "architect": AgentRole(
        id="architect",
        name="Software Architect",
        description="Designs system architecture and API contracts",
        tech_stack=["Architecture", "System Design", "API Design"],
        system_prompt="""You are a Software Architect with 15+ years experience.

Your job:
1. Analyze task and existing codebase
2. Design high-level architecture  
3. Define API contracts between components
4. Design database schema if needed
5. Document everything

Output:
- architecture.md (system design)
- api_contracts.yaml (API specifications)
- db_schema.sql (if database needed)

Rules:
- Think "Why?" before "How?"
- Consider existing patterns
- Design for extensibility
- Document all interfaces between components""",
        mcp_permissions=["memory:read", "memory:write", "filesystem:read", "filesystem:write"],
        color="#8B5CF6"
    ),
    
    "backend": AgentRole(
        id="backend",
        name="Backend Developer",
        description="Implements server-side logic and APIs",
        tech_stack=["Python", "FastAPI", "PostgreSQL", "Redis"],
        system_prompt="""You are a Backend Developer specializing in Python/FastAPI.

Your job:
1. Read architecture/contracts from shared memory
2. Write tests FIRST (TDD approach)
3. Implement API endpoints
4. Handle all error cases
5. Register API in SharedContext

Output:
- api/routes/*.py (endpoints)
- services/*.py (business logic)
- models/*.py (data models)
- tests/unit/*.py (unit tests)

Rules:
- Follow TDD (tests first!)
- Cyclomatic complexity < 10
- Test coverage > 80%
- Type hints everywhere
- No hardcoded secrets
- Register interfaces in SharedContext when done""",
        mcp_permissions=["memory:read", "memory:write", "filesystem:read", "filesystem:write", "git:read", "git:write"],
        color="#10B981"
    ),
    
    "frontend": AgentRole(
        id="frontend",
        name="Frontend Developer", 
        description="Builds user interfaces",
        tech_stack=["React", "TypeScript", "Tailwind CSS"],
        system_prompt="""You are a Frontend Developer specializing in React/TypeScript.

Your job:
1. Wait for Backend API (check SharedContext)
2. Build UI components
3. Integrate with API
4. Handle loading/error states
5. Test components

Output:
- components/*.tsx (React components)
- pages/*.tsx (pages)
- hooks/*.ts (custom hooks)
- tests/*.test.tsx (component tests)

Rules:
- Atomic design principles
- Component size < 300 lines
- Accessibility (a11y) mandatory
- Mobile-first responsive
- Error boundaries for all pages
- Check SharedContext for API availability before starting""",
        mcp_permissions=["memory:read", "filesystem:read", "filesystem:write"],
        color="#F59E0B"
    ),
    
    "telegram": AgentRole(
        id="telegram",
        name="Telegram Bot Developer",
        description="Creates Telegram bot functionality",
        tech_stack=["Python", "aiogram", "Telegram API"],
        system_prompt="""You are a Telegram Bot Developer specializing in aiogram.

Your job:
1. Wait for Backend API (check SharedContext)
2. Implement bot handlers
3. Create keyboards/buttons
4. Handle user states
5. Test interactions

Output:
- bot/handlers/*.py (command handlers)
- bot/keyboards/*.py (inline/reply keyboards)
- bot/states/*.py (FSM states)
- tests/test_handlers.py (handler tests)

Rules:
- Use FSM for complex flows
- Handle errors gracefully
- Log all user actions
- Test all commands
- Check SharedContext for API endpoints""",
        mcp_permissions=["memory:read", "filesystem:read", "filesystem:write"],
        color="#0EA5E9"
    ),
    
    "qa": AgentRole(
        id="qa",
        name="QA Engineer",
        description="Tests and validates quality",
        tech_stack=["pytest", "Playwright", "Coverage"],
        system_prompt="""You are a QA Engineer focused on comprehensive testing.

Your job:
1. Wait for all components (check SharedContext)
2. Write integration tests
3. Write E2E tests
4. Check coverage (must be >80%)
5. Test edge cases and errors

Output:
- tests/integration/*.py (integration tests)
- tests/e2e/*.py (end-to-end tests)
- coverage_report.txt (coverage results)

Rules:
- Test happy path AND error scenarios
- Test boundary conditions
- Security testing
- Performance testing
- Coverage must exceed 80%""",
        mcp_permissions=["memory:read", "filesystem:read", "filesystem:write"],
        color="#EF4444"
    ),
    
    "reviewer": AgentRole(
        id="reviewer",
        name="Code Reviewer",
        description="Reviews code quality and security",
        tech_stack=["Code Review", "Security", "Best Practices"],
        system_prompt="""You are a Senior Code Reviewer with security expertise.

Your job:
1. Wait for all development done
2. Review code quality
3. Check security vulnerabilities
4. Verify test coverage
5. Approve or request changes

Output:
- review.md (detailed review)
- security_audit.md (security findings)

Checklist:
✓ Security (no vulnerabilities)
✓ Code quality (complexity < 10)
✓ Architecture compliance
✓ Test coverage (>80%)
✓ Performance
✓ Best practices

Set review_approved in SharedContext when done.""",
        mcp_permissions=["memory:read", "memory:write", "filesystem:read"],
        color="#EC4899"
    ),
    
    "database": AgentRole(
        id="database",
        name="Database Engineer",
        description="Designs schemas and migrations",
        tech_stack=["PostgreSQL", "SQLAlchemy", "Migrations"],
        system_prompt="""You are a Database Engineer specializing in PostgreSQL.

Your job:
1. Read architecture requirements
2. Design normalized schema (3NF+)
3. Create migrations
4. Add indexes for foreign keys
5. Add constraints

Output:
- migrations/*.sql (database migrations)
- models/schemas.py (SQLAlchemy models)

Rules:
- Normalize to 3NF minimum
- Index all foreign keys
- Add constraints (NOT NULL, CHECK, UNIQUE)
- Reversible migrations
- Register schema in SharedContext""",
        mcp_permissions=["memory:read", "memory:write", "filesystem:read", "filesystem:write"],
        color="#6366F1"
    ),
    
    "security": AgentRole(
        id="security",
        name="Security Auditor",
        description="Audits security vulnerabilities",
        tech_stack=["OWASP", "Security Scanning", "Penetration Testing"],
        system_prompt="""You are a Security Auditor focused on OWASP Top 10.

Your job:
1. Wait for backend implementation
2. Scan for vulnerabilities
3. Check authentication/crypto
4. Verify input validation
5. Report findings

Output:
- security_audit.md (findings)

Checks:
✓ No SQL injection
✓ No XSS
✓ No hardcoded secrets
✓ Proper authentication
✓ HTTPS enforced
✓ Rate limiting

Create blockers in SharedContext for critical issues.""",
        mcp_permissions=["memory:read", "memory:write", "filesystem:read"],
        color="#DC2626"
    ),
    
    "devops": AgentRole(
        id="devops",
        name="DevOps Engineer",
        description="Handles deployment and infrastructure",
        tech_stack=["Docker", "Kubernetes", "CI/CD"],
        system_prompt="""You are a DevOps Engineer specializing in containerization.

Your job:
1. Wait for all services ready
2. Create Docker configs
3. Create K8s manifests
4. Setup CI/CD pipeline
5. Document deployment

Output:
- Dockerfile (for each service)
- docker-compose.yml (local dev)
- k8s/*.yaml (Kubernetes manifests)
- .github/workflows/ci.yml (CI/CD)

Rules:
- Multi-stage builds
- Health checks
- Resource limits
- Security scanning in CI""",
        mcp_permissions=["memory:read", "filesystem:read", "filesystem:write"],
        color="#059669"
    )
}


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class TeamManager:
    """Manages team state and agents."""
    
    def __init__(self):
        self.teams: Dict[str, TeamOrchestrator] = {}
        self.configs: Dict[str, TeamConfig] = {}
        self.memory_graphs: Dict[str, MemoryGraph] = {}
    
    def create_team(self, project_path: str, config: TeamConfig) -> str:
        """Create new team."""
        project_key = str(Path(project_path).resolve())
        
        orchestrator = TeamOrchestrator(
            Path(project_path),
            max_parallel=config.max_parallel,
            auto_merge=config.auto_merge
        )
        
        # Setup graph memory if enabled
        if config.use_graph_memory:
            memory_graph = MemoryGraph(project_path)
            self.memory_graphs[project_key] = memory_graph
        
        self.teams[project_key] = orchestrator
        self.configs[project_key] = config
        
        return project_key
    
    def get_team(self, project_path: str) -> Optional[TeamOrchestrator]:
        """Get team orchestrator."""
        project_key = str(Path(project_path).resolve())
        return self.teams.get(project_key)
    
    def get_team_state(self, project_path: str) -> TeamState:
        """Get current team state."""
        project_key = str(Path(project_path).resolve())
        orchestrator = self.teams.get(project_key)
        
        if not orchestrator:
            return TeamState(active=False, agents=[], shared_context={}, graph_memory={})
        
        # Get agent statuses
        agent_statuses = []
        for agent in orchestrator.agents:
            status = AgentStatus(
                agent_id=agent.id,
                role=agent.role,
                name=agent.name,
                status=agent.status.value,
                worktree_path=str(agent.worktree_path) if agent.worktree_path else None,
                branch=agent.branch,
                progress=agent.progress,
                blockers=agent.blockers,
                current_task=agent.current_task,
                mcp_tools_used=agent.mcp_tools_used,
                memory_context=agent.memory_context
            )
            agent_statuses.append(status)
        
        # Get shared context
        shared_ctx = {}
        if orchestrator.shared_context:
            shared_ctx = orchestrator.shared_context.to_dict()
        
        # Get graph memory
        graph_mem = {}
        if project_key in self.memory_graphs:
            graph_mem = self.memory_graphs[project_key].to_dict()
        
        return TeamState(
            active=True,
            agents=agent_statuses,
            shared_context=shared_ctx,
            graph_memory=graph_mem,
            merge_ready=orchestrator.ready_to_merge
        )


# Global team manager
team_manager = TeamManager()


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/roles")
async def get_available_roles() -> Dict[str, AgentRole]:
    """Get all predefined agent roles."""
    return PREDEFINED_ROLES


@router.get("/roles/{role_id}")
async def get_role(role_id: str) -> AgentRole:
    """Get specific role configuration."""
    if role_id not in PREDEFINED_ROLES:
        raise HTTPException(404, f"Role {role_id} not found")
    return PREDEFINED_ROLES[role_id]


@router.post("/roles/{role_id}")
async def update_role(role_id: str, role: AgentRole) -> AgentRole:
    """Update or create custom role."""
    PREDEFINED_ROLES[role_id] = role
    return role


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str):
    """Delete custom role."""
    if role_id in ["architect", "backend", "frontend", "qa"]:
        raise HTTPException(400, "Cannot delete built-in roles")
    
    if role_id in PREDEFINED_ROLES:
        del PREDEFINED_ROLES[role_id]
    
    return {"deleted": True}


@router.post("/create")
async def create_team(config: TeamConfig) -> Dict[str, Any]:
    """Create new team."""
    project_key = team_manager.create_team(config.project_path, config)
    
    return {
        "project_key": project_key,
        "agents": len(config.agents),
        "status": "created"
    }


@router.get("/status/{project_path:path}")
async def get_team_status(project_path: str) -> TeamState:
    """Get current team status."""
    return team_manager.get_team_state(project_path)


@router.post("/agents/add")
async def add_agent(
    project_path: str,
    agent_config: AgentConfig
) -> Dict[str, Any]:
    """Add agent to team."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    # Create agent
    agent = await orchestrator.add_agent(
        role=agent_config.role,
        name=agent_config.name,
        tech_stack=agent_config.tech_stack,
        custom_prompt=agent_config.custom_prompt,
        mcp_servers=agent_config.mcp_servers,
        mcp_tools=agent_config.mcp_tools,
        depends_on=agent_config.depends_on
    )
    
    return {
        "agent_id": agent.id,
        "role": agent.role,
        "status": "added"
    }


@router.delete("/agents/{agent_id}")
async def remove_agent(project_path: str, agent_id: str):
    """Remove agent from team."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    await orchestrator.remove_agent(agent_id)
    
    return {"deleted": True}


@router.put("/agents/{agent_id}")
async def update_agent(
    project_path: str,
    agent_id: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update agent configuration."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    
    # Update agent
    for key, value in updates.items():
        if hasattr(agent, key):
            setattr(agent, key, value)
    
    return {
        "agent_id": agent_id,
        "updated": list(updates.keys())
    }


@router.get("/agents/{agent_id}/memory")
async def get_agent_memory(project_path: str, agent_id: str) -> Dict[str, Any]:
    """Get agent's memory context."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    
    return agent.memory_context


@router.post("/agents/{agent_id}/memory")
async def update_agent_memory(
    project_path: str,
    agent_id: str,
    memory: Dict[str, Any]
) -> Dict[str, Any]:
    """Update agent's memory context."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    agent = orchestrator.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    
    agent.memory_context.update(memory)
    
    # Also update graph memory if enabled
    project_key = str(Path(project_path).resolve())
    if project_key in team_manager.memory_graphs:
        graph = team_manager.memory_graphs[project_key]
        await graph.add_node(agent_id, memory)
    
    return {"updated": True}


@router.get("/graph")
async def get_memory_graph(project_path: str) -> Dict[str, Any]:
    """Get team's memory graph."""
    project_key = str(Path(project_path).resolve())
    
    if project_key not in team_manager.memory_graphs:
        raise HTTPException(404, "Graph memory not enabled")
    
    graph = team_manager.memory_graphs[project_key]
    return graph.to_dict()


@router.post("/execute")
async def execute_team(project_path: str) -> Dict[str, Any]:
    """Execute team workflow."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    # Start execution in background
    import asyncio
    asyncio.create_task(orchestrator.execute_plan())
    
    return {
        "status": "executing",
        "agents": len(orchestrator.agents)
    }


@router.post("/merge")
async def merge_team_work(project_path: str) -> Dict[str, Any]:
    """Merge all agent branches."""
    orchestrator = team_manager.get_team(project_path)
    if not orchestrator:
        raise HTTPException(404, "Team not found")
    
    result = await orchestrator.auto_merge()
    
    return {
        "merged": result.success,
        "conflicts": result.conflicts,
        "branches": result.merged_branches
    }
