"""
Claude Agent Manager - Team Mode
================================

Multi-agent orchestration system combining best practices from:
- Microsoft AutoGen (multi-agent coordination)
- CrewAI (task dependencies)
- SWE-agent (coding prompts)
- Aider (git integration)
- MetaGPT (role-based agents)
- DevOps-GPT (task decomposition)

Unique features:
- Git Worktrees for isolation
- SharedContext for coordination
- Smart Merge with AI
- Quality Gates

Quick Start:
    from claude_agent_manager.team import TeamOrchestrator

    orchestrator = TeamOrchestrator("~/my-project")
    await orchestrator.create_plan("Add user authentication")
    await orchestrator.execute_plan()
"""

# Core components
from .shared_context import (
    SharedContext,
    AgentUpdate,
    SharedInterface,
)

from .task import (
    Task,
    TaskStatus,
    TaskOutput,
    TaskBuilder,
    TaskPriority,
    topological_sort,
    get_parallel_groups,
)

from .base_agent import (
    BaseAgent,
    AgentConfig,
    Message,
    MessageRole,
    SimpleAgent,
)

from .roles import (
    ArchitectAgent,
    BackendAgent,
    FrontendAgent,
    QAAgent,
    ReviewerAgent,
    RefactoringAgent,
    create_agent,
    get_available_roles,
    get_role_dependencies,
)

from .orchestrator import (
    TeamOrchestrator,
    TeamPlan,
    ExecutionMode,
    run_team_task,
    quick_plan,
)

from .git_operations import (
    GitOperations,
    WorktreeGitOps,
    MergeResult,
)

from .quality_gates import (
    QualityGates,
    QualityGateEnforcer,
    QualityReport,
    QualityCheckResult,
    QualityStatus,
    quick_lint,
    quick_security_scan,
    full_quality_check,
)

from .prompts import (
    get_prompt_for_role,
    build_agent_prompt,
    get_clarification_prompt,
    get_self_validation_prompt,
    CODING_COMMANDS,
)

# AutoGen integration (optional)
try:
    from .autogen_integration import (
        AutoGenTeam,
        TeamPresets,
        AUTOGEN_AVAILABLE
    )
except ImportError:
    AUTOGEN_AVAILABLE = False
    AutoGenTeam = None
    TeamPresets = None

# Enhanced orchestrator with MCP and Graph Memory
try:
    from .enhanced_orchestrator import (
        EnhancedTeamOrchestrator,
        EnhancedAgent,
        AgentConfig as EnhancedAgentConfig,
    )
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False
    EnhancedTeamOrchestrator = None
    EnhancedAgent = None
    EnhancedAgentConfig = None

# Team Manager with dashboard integration
try:
    from .team_manager import (
        TeamManager,
        AgentRole,
        AgentStack,
        MCPPermission,
        WorkGraphMemory,
    )
    TEAM_MANAGER_AVAILABLE = True
except ImportError:
    TEAM_MANAGER_AVAILABLE = False
    TeamManager = None
    AgentRole = None
    AgentStack = None
    MCPPermission = None
    WorkGraphMemory = None

# REST API (requires FastAPI)
try:
    from .api import (
        router as team_api_router,
        PREDEFINED_ROLES,
        TeamState,
        AgentStatus as APIAgentStatus,
    )
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    team_api_router = None
    PREDEFINED_ROLES = None
    TeamState = None
    APIAgentStatus = None

# Team Templates
try:
    from ..team_templates import (
        TeamType,
        CoordinationStrategy,
        AgentTemplate,
        TeamTemplate,
        TeamLibrary,
        TeamBuilder,
        TeamTemplateManager,
    )
    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False
    TeamType = None
    CoordinationStrategy = None
    AgentTemplate = None
    TeamTemplate = None
    TeamLibrary = None
    TeamBuilder = None
    TeamTemplateManager = None

# Templates API (requires FastAPI)
try:
    from .templates_api import router as templates_api_router
    TEMPLATES_API_AVAILABLE = True
except ImportError:
    TEMPLATES_API_AVAILABLE = False
    templates_api_router = None

__all__ = [
    # Orchestrator
    "TeamOrchestrator",
    "TeamPlan",
    "ExecutionMode",
    "run_team_task",
    "quick_plan",

    # Tasks
    "Task",
    "TaskOutput",
    "TaskBuilder",
    "TaskStatus",
    "TaskPriority",
    "topological_sort",
    "get_parallel_groups",

    # Agents
    "BaseAgent",
    "AgentConfig",
    "SimpleAgent",
    "Message",
    "MessageRole",

    # Roles
    "ArchitectAgent",
    "BackendAgent",
    "FrontendAgent",
    "QAAgent",
    "ReviewerAgent",
    "RefactoringAgent",
    "create_agent",
    "get_available_roles",
    "get_role_dependencies",

    # Context
    "SharedContext",
    "AgentUpdate",
    "SharedInterface",

    # Git
    "GitOperations",
    "WorktreeGitOps",
    "MergeResult",

    # Quality
    "QualityGates",
    "QualityGateEnforcer",
    "QualityReport",
    "QualityCheckResult",
    "QualityStatus",
    "quick_lint",
    "quick_security_scan",
    "full_quality_check",

    # Prompts
    "get_prompt_for_role",
    "build_agent_prompt",
    "get_clarification_prompt",
    "get_self_validation_prompt",
    "CODING_COMMANDS",

    # AutoGen (optional)
    "AutoGenTeam",
    "TeamPresets",
    "AUTOGEN_AVAILABLE",

    # Enhanced orchestrator
    "EnhancedTeamOrchestrator",
    "EnhancedAgent",
    "EnhancedAgentConfig",
    "ENHANCED_AVAILABLE",

    # Team Manager
    "TeamManager",
    "AgentRole",
    "AgentStack",
    "MCPPermission",
    "WorkGraphMemory",
    "TEAM_MANAGER_AVAILABLE",

    # REST API
    "team_api_router",
    "PREDEFINED_ROLES",
    "TeamState",
    "APIAgentStatus",
    "API_AVAILABLE",

    # Team Templates
    "TeamType",
    "CoordinationStrategy",
    "AgentTemplate",
    "TeamTemplate",
    "TeamLibrary",
    "TeamBuilder",
    "TeamTemplateManager",
    "TEMPLATES_AVAILABLE",

    # Templates API
    "templates_api_router",
    "TEMPLATES_API_AVAILABLE",
]

__version__ = "1.0.0"
