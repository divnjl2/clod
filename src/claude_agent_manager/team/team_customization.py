"""
Team Customization System
=========================

Позволяет кастомизировать Team агентов на любом уровне:
- Роли и специализации
- Модели и reasoning patterns
- Tools и MCP серверы
- Communication patterns
- Memory и shared context
- Workflows и dependencies
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
from pathlib import Path


class AgentSpecialization(Enum):
    """Специализации агентов."""
    # Backend
    BACKEND_API = "backend_api"
    BACKEND_DATABASE = "backend_database"
    BACKEND_MICROSERVICES = "backend_microservices"
    
    # Frontend
    FRONTEND_REACT = "frontend_react"
    FRONTEND_UI_UX = "frontend_ui_ux"
    FRONTEND_PERFORMANCE = "frontend_performance"
    
    # DevOps
    DEVOPS_INFRASTRUCTURE = "devops_infrastructure"
    DEVOPS_CI_CD = "devops_cicd"
    DEVOPS_MONITORING = "devops_monitoring"
    
    # Data
    DATA_ENGINEERING = "data_engineering"
    DATA_SCIENCE = "data_science"
    DATA_ANALYTICS = "data_analytics"
    
    # Security
    SECURITY_PENTESTING = "security_pentesting"
    SECURITY_COMPLIANCE = "security_compliance"
    
    # General
    ARCHITECT = "architect"
    TECH_LEAD = "tech_lead"
    QA_TESTER = "qa_tester"
    DOCUMENTATION = "documentation"


class CommunicationStyle(Enum):
    """Стили коммуникации между агентами."""
    ASYNC_MESSAGES = "async_messages"      # AutoGen style
    SEQUENTIAL = "sequential"              # CrewAI style
    BROADCAST = "broadcast"                # MetaGPT style
    HIERARCHICAL = "hierarchical"          # Manager → Workers
    PEER_TO_PEER = "peer_to_peer"         # Равноправные


@dataclass
class ModelConfig:
    """Конфигурация модели для агента."""
    provider: str = "anthropic"  # anthropic, openai, openrouter, local
    model: str = "claude-sonnet-4"
    
    # Auto-selection settings
    auto_select: bool = False
    complexity_mapping: Optional[Dict[str, str]] = None
    
    # Model parameters
    temperature: float = 1.0
    max_tokens: int = 4096
    
    # Cost settings
    budget_limit: Optional[float] = None  # Max $ per task
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReasoningConfig:
    """Конфигурация reasoning для агента."""
    # Pattern selection
    default_pattern: str = "cot"  # cot, tot, self_consistency, reflection, react
    pattern_by_task: Optional[Dict[str, str]] = None
    
    # Quality settings
    min_confidence: float = 0.7
    verification_enabled: bool = True
    max_retries: int = 2
    
    # Advanced settings
    thinking_time: Optional[int] = None  # Seconds for o1-style
    num_samples: int = 1  # For self-consistency
    max_iterations: int = 3  # For reflection
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolsConfig:
    """Конфигурация tools и MCP для агента."""
    # MCP servers
    mcp_servers: List[str] = field(default_factory=list)
    
    # Custom tools
    custom_tools: List[str] = field(default_factory=list)
    
    # Web tools
    web_search_enabled: bool = False
    web_fetch_enabled: bool = False
    
    # Code tools
    code_execution_enabled: bool = True
    file_creation_enabled: bool = True
    
    # Git tools
    git_enabled: bool = True
    worktree_isolation: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryConfig:
    """Конфигурация memory для агента."""
    # Shared memory
    shared_memory_enabled: bool = True
    memory_namespace: Optional[str] = None
    
    # Memory graph
    graph_enabled: bool = True
    interface_tracking: bool = True
    
    # Context
    max_context_messages: int = 50
    summarization_enabled: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CustomAgentConfig:
    """Полная конфигурация custom агента."""
    # Basic info
    name: str
    role: str
    specialization: AgentSpecialization
    
    # Description
    description: str = ""
    responsibilities: List[str] = field(default_factory=list)
    
    # Model & Reasoning
    model: ModelConfig = field(default_factory=ModelConfig)
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)
    
    # Tools & Memory
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    
    # Custom prompts
    system_prompt: Optional[str] = None
    task_prefix: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "role": self.role,
            "specialization": self.specialization.value,
            "description": self.description,
            "responsibilities": self.responsibilities,
            "model": self.model.to_dict(),
            "reasoning": self.reasoning.to_dict(),
            "tools": self.tools.to_dict(),
            "memory": self.memory.to_dict(),
            "system_prompt": self.system_prompt,
            "task_prefix": self.task_prefix
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomAgentConfig":
        """Create from dict."""
        return cls(
            name=data["name"],
            role=data["role"],
            specialization=AgentSpecialization(data["specialization"]),
            description=data.get("description", ""),
            responsibilities=data.get("responsibilities", []),
            model=ModelConfig(**data.get("model", {})),
            reasoning=ReasoningConfig(**data.get("reasoning", {})),
            tools=ToolsConfig(**data.get("tools", {})),
            memory=MemoryConfig(**data.get("memory", {})),
            system_prompt=data.get("system_prompt"),
            task_prefix=data.get("task_prefix")
        )


@dataclass
class TeamWorkflow:
    """Рабочий процесс команды."""
    name: str
    steps: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CustomTeamConfig:
    """Конфигурация custom команды."""
    # Basic info
    name: str
    description: str
    use_case: str  # "web_app", "microservices", "data_pipeline", etc.
    
    # Agents
    agents: List[CustomAgentConfig] = field(default_factory=list)
    
    # Team settings
    communication_style: CommunicationStyle = CommunicationStyle.ASYNC_MESSAGES
    max_parallel_agents: int = 3
    
    # Workflows
    workflows: List[TeamWorkflow] = field(default_factory=list)
    
    # Shared resources
    shared_mcp_servers: List[str] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)
    
    # Budget
    total_budget: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "use_case": self.use_case,
            "agents": [agent.to_dict() for agent in self.agents],
            "communication_style": self.communication_style.value,
            "max_parallel_agents": self.max_parallel_agents,
            "workflows": [w.to_dict() for w in self.workflows],
            "shared_mcp_servers": self.shared_mcp_servers,
            "shared_context": self.shared_context,
            "total_budget": self.total_budget
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CustomTeamConfig":
        """Create from dict."""
        return cls(
            name=data["name"],
            description=data["description"],
            use_case=data["use_case"],
            agents=[CustomAgentConfig.from_dict(a) for a in data.get("agents", [])],
            communication_style=CommunicationStyle(data.get("communication_style", "async_messages")),
            max_parallel_agents=data.get("max_parallel_agents", 3),
            workflows=[TeamWorkflow(**w) for w in data.get("workflows", [])],
            shared_mcp_servers=data.get("shared_mcp_servers", []),
            shared_context=data.get("shared_context", {}),
            total_budget=data.get("total_budget")
        )
    
    def add_agent(self, agent: CustomAgentConfig):
        """Add agent to team."""
        self.agents.append(agent)
    
    def remove_agent(self, name: str):
        """Remove agent by name."""
        self.agents = [a for a in self.agents if a.name != name]
    
    def get_agent(self, name: str) -> Optional[CustomAgentConfig]:
        """Get agent by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None


# ============================================================================
# TEAM TEMPLATES
# ============================================================================

class TeamTemplates:
    """Pre-defined team templates."""
    
    @staticmethod
    def web_app_fullstack() -> CustomTeamConfig:
        """Full-stack web app team."""
        
        # Backend agent
        backend = CustomAgentConfig(
            name="Backend Developer",
            role="backend",
            specialization=AgentSpecialization.BACKEND_API,
            description="API development and database design",
            responsibilities=[
                "Design and implement REST APIs",
                "Database schema and migrations",
                "Authentication and authorization",
                "Error handling and logging"
            ],
            model=ModelConfig(
                provider="anthropic",
                auto_select=True,
                complexity_mapping={
                    "SIMPLE": "claude-haiku-4",
                    "MEDIUM": "claude-sonnet-4",
                    "COMPLEX": "claude-opus-4"
                }
            ),
            reasoning=ReasoningConfig(
                default_pattern="cot",
                pattern_by_task={
                    "design": "tot",
                    "debug": "react",
                    "review": "self_consistency"
                },
                verification_enabled=True
            ),
            tools=ToolsConfig(
                mcp_servers=["memory", "filesystem", "postgres"],
                code_execution_enabled=True,
                git_enabled=True
            )
        )
        
        # Frontend agent
        frontend = CustomAgentConfig(
            name="Frontend Developer",
            role="frontend",
            specialization=AgentSpecialization.FRONTEND_REACT,
            description="React UI/UX development",
            responsibilities=[
                "Build React components",
                "Implement responsive design",
                "State management",
                "API integration"
            ],
            model=ModelConfig(
                provider="anthropic",
                auto_select=True,
                complexity_mapping={
                    "SIMPLE": "claude-haiku-4",
                    "MEDIUM": "claude-sonnet-4",
                    "COMPLEX": "claude-sonnet-4"
                }
            ),
            reasoning=ReasoningConfig(
                default_pattern="cot",
                pattern_by_task={
                    "design": "tot",
                    "performance": "reflection"
                }
            ),
            tools=ToolsConfig(
                mcp_servers=["memory", "filesystem"],
                code_execution_enabled=True,
                git_enabled=True
            )
        )
        
        # DevOps agent
        devops = CustomAgentConfig(
            name="DevOps Engineer",
            role="devops",
            specialization=AgentSpecialization.DEVOPS_CI_CD,
            description="Deployment and infrastructure",
            responsibilities=[
                "Configure CI/CD pipelines",
                "Docker containerization",
                "Deployment automation",
                "Monitoring setup"
            ],
            model=ModelConfig(
                provider="anthropic",
                model="claude-sonnet-4"
            ),
            tools=ToolsConfig(
                mcp_servers=["memory", "filesystem", "github"],
                code_execution_enabled=True
            )
        )
        
        # Workflow
        workflow = TeamWorkflow(
            name="Feature Development",
            steps=[
                {
                    "step": 1,
                    "agent": "Backend Developer",
                    "task": "Design API endpoints and database schema"
                },
                {
                    "step": 2,
                    "agent": "Frontend Developer",
                    "task": "Design UI components and state management",
                    "depends_on": ["Backend Developer"]
                },
                {
                    "step": 3,
                    "agent": "Backend Developer",
                    "task": "Implement API endpoints"
                },
                {
                    "step": 4,
                    "agent": "Frontend Developer",
                    "task": "Implement UI and connect to API",
                    "depends_on": ["Backend Developer"]
                },
                {
                    "step": 5,
                    "agent": "DevOps Engineer",
                    "task": "Setup deployment pipeline",
                    "depends_on": ["Backend Developer", "Frontend Developer"]
                }
            ],
            dependencies={
                "Frontend Developer": ["Backend Developer"],
                "DevOps Engineer": ["Backend Developer", "Frontend Developer"]
            }
        )
        
        return CustomTeamConfig(
            name="Full-Stack Web App Team",
            description="Complete team for web application development",
            use_case="web_app",
            agents=[backend, frontend, devops],
            communication_style=CommunicationStyle.ASYNC_MESSAGES,
            workflows=[workflow],
            shared_mcp_servers=["memory", "filesystem", "github"]
        )
    
    @staticmethod
    def vpn_service_team() -> CustomTeamConfig:
        """Team for VPN service development."""
        
        backend = CustomAgentConfig(
            name="VPN Backend",
            role="backend",
            specialization=AgentSpecialization.BACKEND_MICROSERVICES,
            description="VPN service backend",
            responsibilities=[
                "Payment integration (CryptoBot, YooMoney)",
                "User management and authentication",
                "VPN server orchestration",
                "Billing and subscriptions"
            ],
            model=ModelConfig(
                provider="openrouter",  # Use OpenRouter for variety
                auto_select=True,
                complexity_mapping={
                    "SIMPLE": "anthropic/claude-haiku-4",
                    "MEDIUM": "anthropic/claude-sonnet-4",
                    "COMPLEX": "openai/o1-preview"
                }
            ),
            reasoning=ReasoningConfig(
                default_pattern="reflection",
                min_confidence=0.85
            )
        )
        
        panel_dev = CustomAgentConfig(
            name="Panel Integration",
            role="integration",
            specialization=AgentSpecialization.BACKEND_API,
            description="VPN panel integration (Marzban, V2Board)",
            responsibilities=[
                "Marzban API integration",
                "V2Board API integration",
                "Panel synchronization",
                "User quota management"
            ],
            model=ModelConfig(
                provider="anthropic",
                model="claude-sonnet-4"
            )
        )
        
        tg_bot = CustomAgentConfig(
            name="Telegram Bot",
            role="bot",
            specialization=AgentSpecialization.BACKEND_API,
            description="Telegram bot for user interaction",
            responsibilities=[
                "Bot commands and handlers",
                "Payment processing via bot",
                "User notifications",
                "Admin controls"
            ],
            model=ModelConfig(
                provider="anthropic",
                model="claude-sonnet-4"
            )
        )
        
        security = CustomAgentConfig(
            name="Security Specialist",
            role="security",
            specialization=AgentSpecialization.SECURITY_PENTESTING,
            description="Security review and testing",
            responsibilities=[
                "Security audit",
                "Penetration testing",
                "Code review for vulnerabilities",
                "Payment security validation"
            ],
            model=ModelConfig(
                provider="openai",
                model="gpt-4o"
            ),
            reasoning=ReasoningConfig(
                default_pattern="self_consistency",
                num_samples=5  # Multiple checks for security
            )
        )
        
        return CustomTeamConfig(
            name="VPN Service Team",
            description="Team for VPN service development (Russia/CIS market)",
            use_case="vpn_service",
            agents=[backend, panel_dev, tg_bot, security],
            communication_style=CommunicationStyle.HIERARCHICAL,
            shared_mcp_servers=["memory", "filesystem", "postgres", "redis"]
        )
    
    @staticmethod
    def data_pipeline_team() -> CustomTeamConfig:
        """Team for data engineering."""
        
        data_engineer = CustomAgentConfig(
            name="Data Engineer",
            role="data_engineer",
            specialization=AgentSpecialization.DATA_ENGINEERING,
            responsibilities=[
                "ETL pipeline design",
                "Data warehouse schema",
                "Data quality checks",
                "Pipeline orchestration"
            ],
            model=ModelConfig(
                provider="anthropic",
                model="claude-sonnet-4"
            ),
            tools=ToolsConfig(
                mcp_servers=["memory", "filesystem", "postgres", "s3"],
                code_execution_enabled=True
            )
        )
        
        data_scientist = CustomAgentConfig(
            name="Data Scientist",
            role="data_scientist",
            specialization=AgentSpecialization.DATA_SCIENCE,
            responsibilities=[
                "Feature engineering",
                "Model development",
                "Experimentation",
                "Model evaluation"
            ],
            model=ModelConfig(
                provider="openai",
                model="gpt-4o"  # Good for data science
            ),
            tools=ToolsConfig(
                mcp_servers=["memory", "filesystem", "jupyter"],
                code_execution_enabled=True
            )
        )
        
        analytics = CustomAgentConfig(
            name="Analytics Engineer",
            role="analytics",
            specialization=AgentSpecialization.DATA_ANALYTICS,
            responsibilities=[
                "Dashboard development",
                "SQL queries",
                "Report generation",
                "KPI tracking"
            ],
            model=ModelConfig(
                provider="anthropic",
                model="claude-haiku-4"  # Cost-effective for queries
            )
        )
        
        return CustomTeamConfig(
            name="Data Pipeline Team",
            description="Complete data engineering and analytics team",
            use_case="data_pipeline",
            agents=[data_engineer, data_scientist, analytics],
            communication_style=CommunicationStyle.SEQUENTIAL
        )


# ============================================================================
# TEAM MANAGER
# ============================================================================

class TeamConfigManager:
    """Manage team configurations."""
    
    def __init__(self, config_dir: str = "~/.clod/teams"):
        self.config_dir = Path(config_dir).expanduser()
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def save_team(self, team: CustomTeamConfig) -> str:
        """Save team configuration to file."""
        
        filename = f"{team.name.lower().replace(' ', '_')}.json"
        filepath = self.config_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(team.to_dict(), f, indent=2)
        
        return str(filepath)
    
    def load_team(self, name: str) -> Optional[CustomTeamConfig]:
        """Load team configuration from file."""
        
        filename = f"{name.lower().replace(' ', '_')}.json"
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath) as f:
            data = json.load(f)
        
        return CustomTeamConfig.from_dict(data)
    
    def list_teams(self) -> List[str]:
        """List all saved teams."""
        
        return [
            f.stem.replace('_', ' ').title()
            for f in self.config_dir.glob("*.json")
        ]
    
    def delete_team(self, name: str) -> bool:
        """Delete team configuration."""
        
        filename = f"{name.lower().replace(' ', '_')}.json"
        filepath = self.config_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            return True
        
        return False


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Example 1: Create custom team
    manager = TeamConfigManager()
    
    # Get template
    vpn_team = TeamTemplates.vpn_service_team()
    
    # Customize
    vpn_team.total_budget = 10.0  # $10 budget
    vpn_team.max_parallel_agents = 2
    
    # Add custom agent
    custom_agent = CustomAgentConfig(
        name="Payment Specialist",
        role="payment",
        specialization=AgentSpecialization.BACKEND_API,
        description="Payment gateway integration expert",
        model=ModelConfig(
            provider="anthropic",
            model="claude-opus-4"  # Best model for critical payments
        ),
        reasoning=ReasoningConfig(
            default_pattern="reflection",
            min_confidence=0.95,
            verification_enabled=True
        )
    )
    vpn_team.add_agent(custom_agent)
    
    # Save
    filepath = manager.save_team(vpn_team)
    print(f"Team saved to: {filepath}")
    
    # Load
    loaded = manager.load_team("VPN Service Team")
    print(f"Loaded team: {loaded.name}")
    print(f"Agents: {[a.name for a in loaded.agents]}")
