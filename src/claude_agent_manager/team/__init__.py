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
]

__version__ = "1.0.0"
