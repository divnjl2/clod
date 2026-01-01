"""
Team Templates System
=====================

Система шаблонов команд агентов:
- Pre-built teams для разных задач
- Custom team builder
- Import/Export teams
- Team libraries
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime


class TeamType(Enum):
    """Типы команд."""
    FULL_STACK = "full_stack"           # Frontend + Backend + DevOps
    MICROSERVICES = "microservices"     # Multiple services team
    MOBILE_DEV = "mobile_dev"           # iOS + Android + Backend
    DATA_SCIENCE = "data_science"       # Data + ML + Backend
    SECURITY = "security"               # Security + Pentest + Review
    CONTENT = "content"                 # Writer + Designer + Marketer
    CUSTOM = "custom"                   # User-defined


class CoordinationStrategy(Enum):
    """Стратегии координации команды."""
    SEQUENTIAL = "sequential"           # Последовательно (waterfall)
    PARALLEL = "parallel"               # Параллельно (все сразу)
    LEADER_BASED = "leader_based"       # Через лидера
    PEER_TO_PEER = "peer_to_peer"       # Все общаются со всеми
    STAGED = "staged"                   # По стадиям (design → impl → test)


@dataclass
class AgentTemplate:
    """Шаблон агента в команде."""
    role: str
    name: str
    system_prompt: Optional[str] = None
    mcp_tools: List[str] = field(default_factory=list)
    model_config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # От кого зависит
    outputs: List[str] = field(default_factory=list)      # Что производит
    priority: int = 0  # 0 = highest priority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "system_prompt": self.system_prompt,
            "mcp_tools": self.mcp_tools,
            "model_config": self.model_config,
            "dependencies": self.dependencies,
            "outputs": self.outputs,
            "priority": self.priority
        }


@dataclass
class TeamTemplate:
    """Шаблон команды агентов."""
    id: str
    name: str
    description: str
    team_type: TeamType
    agents: List[AgentTemplate]
    coordination: CoordinationStrategy
    
    # Team configuration
    auto_start: bool = False
    shared_context: Dict[str, Any] = field(default_factory=dict)
    communication_rules: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    author: Optional[str] = None
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "team_type": self.team_type.value,
            "agents": [a.to_dict() for a in self.agents],
            "coordination": self.coordination.value,
            "auto_start": self.auto_start,
            "shared_context": self.shared_context,
            "communication_rules": self.communication_rules,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "author": self.author,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamTemplate":
        """Create from dict."""
        agents = [
            AgentTemplate(**a) for a in data["agents"]
        ]
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            team_type=TeamType(data["team_type"]),
            agents=agents,
            coordination=CoordinationStrategy(data["coordination"]),
            auto_start=data.get("auto_start", False),
            shared_context=data.get("shared_context", {}),
            communication_rules=data.get("communication_rules", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=data.get("tags", []),
            author=data.get("author"),
            version=data.get("version", "1.0")
        )


# ============================================================================
# PRE-BUILT TEAM TEMPLATES
# ============================================================================

class TeamLibrary:
    """Библиотека готовых команд."""
    
    @staticmethod
    def get_full_stack_team() -> TeamTemplate:
        """Full-stack команда для web приложений."""
        
        return TeamTemplate(
            id="team_full_stack_web",
            name="Full-Stack Web Team",
            description="Complete web development team with frontend, backend, and DevOps",
            team_type=TeamType.FULL_STACK,
            coordination=CoordinationStrategy.STAGED,
            tags=["web", "full-stack", "popular"],
            agents=[
                # Stage 1: Architecture
                AgentTemplate(
                    role="architect",
                    name="System Architect",
                    system_prompt="Design system architecture and API contracts",
                    mcp_tools=["memory", "filesystem"],
                    model_config={"model": "claude-opus-4"},
                    outputs=["architecture", "api_contracts"],
                    priority=0
                ),
                
                # Stage 2: Implementation (parallel)
                AgentTemplate(
                    role="frontend",
                    name="Frontend Developer",
                    system_prompt="Build React frontend with best practices",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-sonnet-4"},
                    dependencies=["architecture", "api_contracts"],
                    outputs=["frontend_code"],
                    priority=1
                ),
                
                AgentTemplate(
                    role="backend",
                    name="Backend Developer",
                    system_prompt="Build FastAPI backend with async operations",
                    mcp_tools=["filesystem", "memory", "database"],
                    model_config={"model": "claude-sonnet-4"},
                    dependencies=["architecture", "api_contracts"],
                    outputs=["backend_code"],
                    priority=1
                ),
                
                # Stage 3: Quality & Deployment
                AgentTemplate(
                    role="qa",
                    name="QA Engineer",
                    system_prompt="Write tests and ensure quality",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-haiku-4"},
                    dependencies=["frontend_code", "backend_code"],
                    outputs=["test_suite"],
                    priority=2
                ),
                
                AgentTemplate(
                    role="devops",
                    name="DevOps Engineer",
                    system_prompt="Setup CI/CD and deployment",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-sonnet-4"},
                    dependencies=["backend_code", "frontend_code", "test_suite"],
                    outputs=["deployment_config"],
                    priority=3
                ),
                
                # Stage 4: Review
                AgentTemplate(
                    role="reviewer",
                    name="Code Reviewer",
                    system_prompt="Review all code for quality and security",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-opus-4"},
                    dependencies=["frontend_code", "backend_code", "test_suite"],
                    outputs=["review_report"],
                    priority=4
                )
            ]
        )
    
    @staticmethod
    def get_vpn_service_team() -> TeamTemplate:
        """VPN Service команда (для твоего проекта!)."""
        
        return TeamTemplate(
            id="team_vpn_service",
            name="VPN Service Development Team",
            description="Team specialized in VPN service development with payments",
            team_type=TeamType.CUSTOM,
            coordination=CoordinationStrategy.STAGED,
            tags=["vpn", "payments", "telegram", "russia"],
            agents=[
                # Stage 1: Architecture
                AgentTemplate(
                    role="architect",
                    name="VPN Architect",
                    system_prompt="""
Design VPN service architecture considering:
- Multiple VPN panels (Marzban, V2Board, Remnawave)
- Payment integration (CryptoBot, YooMoney)
- Telegram bot interface
- User management
- Russian market compliance
""",
                    mcp_tools=["memory", "filesystem"],
                    model_config={"model": "claude-opus-4"},
                    outputs=["architecture", "api_design"],
                    priority=0
                ),
                
                # Stage 2: Backend Implementation
                AgentTemplate(
                    role="backend",
                    name="Backend Developer",
                    system_prompt="""
Implement VPN service backend:
- FastAPI async endpoints
- VPN panel integration
- Payment processing
- User management
- Subscription handling
""",
                    mcp_tools=["filesystem", "memory", "database"],
                    model_config={
                        "model": "claude-sonnet-4",
                        "auto_select": True,
                        "mapping": {
                            "SIMPLE": "claude-haiku-4",
                            "MEDIUM": "claude-sonnet-4",
                            "COMPLEX": "claude-opus-4"
                        }
                    },
                    dependencies=["architecture", "api_design"],
                    outputs=["backend_api", "payment_integration"],
                    priority=1
                ),
                
                # Stage 2: Telegram Bot (parallel)
                AgentTemplate(
                    role="telegram",
                    name="Telegram Bot Developer",
                    system_prompt="""
Create Telegram bot for VPN service:
- aiogram framework
- Russian language
- Payment commands (/pay)
- Subscription management
- User-friendly interface
""",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-sonnet-4"},
                    dependencies=["architecture", "api_design"],
                    outputs=["telegram_bot"],
                    priority=1
                ),
                
                # Stage 3: Testing
                AgentTemplate(
                    role="qa",
                    name="QA Engineer",
                    system_prompt="""
Test VPN service:
- Payment flows (CryptoBot, YooMoney)
- VPN connection
- Telegram bot commands
- Edge cases and errors
""",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-haiku-4"},
                    dependencies=["backend_api", "telegram_bot"],
                    outputs=["test_results"],
                    priority=2
                ),
                
                # Stage 4: Deployment
                AgentTemplate(
                    role="devops",
                    name="DevOps Engineer",
                    system_prompt="""
Deploy VPN service:
- Docker setup
- Nginx configuration
- SSL certificates
- Monitoring setup
""",
                    mcp_tools=["filesystem", "memory"],
                    model_config={"model": "claude-sonnet-4"},
                    dependencies=["backend_api", "telegram_bot", "test_results"],
                    outputs=["deployment_ready"],
                    priority=3
                )
            ],
            shared_context={
                "target_market": "Russia and CIS",
                "payment_methods": ["CryptoBot", "YooMoney"],
                "vpn_panels": ["Marzban", "V2Board", "Remnawave"],
                "language": "Russian"
            }
        )
    
    @staticmethod
    def get_mobile_app_team() -> TeamTemplate:
        """Mobile app команда."""
        
        return TeamTemplate(
            id="team_mobile_app",
            name="Mobile App Development Team",
            description="Cross-platform mobile development with backend",
            team_type=TeamType.MOBILE_DEV,
            coordination=CoordinationStrategy.STAGED,
            tags=["mobile", "ios", "android", "react-native"],
            agents=[
                AgentTemplate(
                    role="architect",
                    name="Mobile Architect",
                    system_prompt="Design mobile app architecture",
                    outputs=["architecture", "api_design"],
                    priority=0
                ),
                
                AgentTemplate(
                    role="mobile",
                    name="React Native Developer",
                    system_prompt="Build cross-platform mobile app",
                    dependencies=["architecture"],
                    outputs=["mobile_app"],
                    priority=1
                ),
                
                AgentTemplate(
                    role="backend",
                    name="Backend Developer",
                    system_prompt="Build mobile backend API",
                    dependencies=["api_design"],
                    outputs=["backend_api"],
                    priority=1
                ),
                
                AgentTemplate(
                    role="qa",
                    name="Mobile QA",
                    system_prompt="Test on iOS and Android",
                    dependencies=["mobile_app", "backend_api"],
                    outputs=["test_results"],
                    priority=2
                )
            ]
        )
    
    @staticmethod
    def get_all_templates() -> List[TeamTemplate]:
        """Получить все готовые шаблоны."""
        return [
            TeamLibrary.get_full_stack_team(),
            TeamLibrary.get_vpn_service_team(),
            TeamLibrary.get_mobile_app_team(),
        ]


# ============================================================================
# TEAM BUILDER
# ============================================================================

class TeamBuilder:
    """
    Builder для создания кастомных команд.
    
    Usage:
        builder = TeamBuilder()
        team = (builder
            .set_name("My Team")
            .add_agent(role="frontend", name="Frontend Dev")
            .add_agent(role="backend", name="Backend Dev")
            .set_coordination("staged")
            .build())
    """
    
    def __init__(self):
        self.team_id = f"team_custom_{datetime.now().timestamp()}"
        self.name = "Custom Team"
        self.description = ""
        self.team_type = TeamType.CUSTOM
        self.agents: List[AgentTemplate] = []
        self.coordination = CoordinationStrategy.SEQUENTIAL
        self.shared_context = {}
        self.communication_rules = {}
        self.tags = []
        self.author = None
    
    def set_name(self, name: str) -> "TeamBuilder":
        """Set team name."""
        self.name = name
        return self
    
    def set_description(self, description: str) -> "TeamBuilder":
        """Set team description."""
        self.description = description
        return self
    
    def set_type(self, team_type: TeamType) -> "TeamBuilder":
        """Set team type."""
        self.team_type = team_type
        return self
    
    def add_agent(
        self,
        role: str,
        name: str,
        system_prompt: str = None,
        mcp_tools: List[str] = None,
        model_config: Dict[str, Any] = None,
        dependencies: List[str] = None,
        outputs: List[str] = None,
        priority: int = 0
    ) -> "TeamBuilder":
        """Add agent to team."""
        
        agent = AgentTemplate(
            role=role,
            name=name,
            system_prompt=system_prompt,
            mcp_tools=mcp_tools or [],
            model_config=model_config or {},
            dependencies=dependencies or [],
            outputs=outputs or [],
            priority=priority
        )
        
        self.agents.append(agent)
        return self
    
    def set_coordination(self, strategy: str) -> "TeamBuilder":
        """Set coordination strategy."""
        self.coordination = CoordinationStrategy(strategy)
        return self
    
    def add_shared_context(self, key: str, value: Any) -> "TeamBuilder":
        """Add shared context."""
        self.shared_context[key] = value
        return self
    
    def add_tag(self, tag: str) -> "TeamBuilder":
        """Add tag."""
        self.tags.append(tag)
        return self
    
    def set_author(self, author: str) -> "TeamBuilder":
        """Set author."""
        self.author = author
        return self
    
    def build(self) -> TeamTemplate:
        """Build team template."""
        
        return TeamTemplate(
            id=self.team_id,
            name=self.name,
            description=self.description,
            team_type=self.team_type,
            agents=self.agents,
            coordination=self.coordination,
            shared_context=self.shared_context,
            communication_rules=self.communication_rules,
            tags=self.tags,
            author=self.author
        )


# ============================================================================
# TEAM TEMPLATE MANAGER
# ============================================================================

class TeamTemplateManager:
    """
    Управление шаблонами команд.
    
    - Load/Save templates
    - Import/Export
    - Template library
    """
    
    def __init__(self, storage_path: str = "team_templates"):
        self.storage_path = storage_path
        self.templates: Dict[str, TeamTemplate] = {}
        
        # Load built-in templates
        for template in TeamLibrary.get_all_templates():
            self.templates[template.id] = template
    
    def add_template(self, template: TeamTemplate):
        """Add template to library."""
        self.templates[template.id] = template
    
    def get_template(self, template_id: str) -> Optional[TeamTemplate]:
        """Get template by ID."""
        return self.templates.get(template_id)
    
    def list_templates(self, filter_tags: List[str] = None) -> List[TeamTemplate]:
        """List all templates, optionally filtered by tags."""
        
        templates = list(self.templates.values())
        
        if filter_tags:
            templates = [
                t for t in templates
                if any(tag in t.tags for tag in filter_tags)
            ]
        
        return templates
    
    def save_template(self, template: TeamTemplate, filepath: str):
        """Save template to file."""
        
        with open(filepath, 'w') as f:
            json.dump(template.to_dict(), f, indent=2)
    
    def load_template(self, filepath: str) -> TeamTemplate:
        """Load template from file."""
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        template = TeamTemplate.from_dict(data)
        self.add_template(template)
        return template
    
    def export_template(self, template_id: str) -> str:
        """Export template as JSON string."""
        
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return json.dumps(template.to_dict(), indent=2)
    
    def import_template(self, json_str: str) -> TeamTemplate:
        """Import template from JSON string."""
        
        data = json.loads(json_str)
        template = TeamTemplate.from_dict(data)
        self.add_template(template)
        return template
    
    def clone_template(
        self,
        template_id: str,
        new_name: str,
        new_id: str = None
    ) -> TeamTemplate:
        """Clone existing template."""
        
        original = self.get_template(template_id)
        if not original:
            raise ValueError(f"Template {template_id} not found")
        
        # Create copy
        data = original.to_dict()
        data["id"] = new_id or f"{template_id}_copy_{datetime.now().timestamp()}"
        data["name"] = new_name
        
        cloned = TeamTemplate.from_dict(data)
        self.add_template(cloned)
        return cloned


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Examples of using team templates."""
    
    # Example 1: Use pre-built template
    manager = TeamTemplateManager()
    
    vpn_team = manager.get_template("team_vpn_service")
    print(f"VPN Team: {vpn_team.name}")
    print(f"Agents: {len(vpn_team.agents)}")
    
    # Example 2: Build custom team
    builder = TeamBuilder()
    
    custom_team = (builder
        .set_name("E-commerce Team")
        .set_description("Build online store")
        .add_agent(
            role="frontend",
            name="Frontend Dev",
            system_prompt="Build React e-commerce frontend",
            mcp_tools=["filesystem", "memory"],
            priority=1
        )
        .add_agent(
            role="backend",
            name="Backend Dev",
            system_prompt="Build FastAPI e-commerce backend",
            dependencies=["api_design"],
            priority=1
        )
        .add_agent(
            role="payment",
            name="Payment Integration",
            system_prompt="Integrate Stripe payments",
            dependencies=["backend_api"],
            priority=2
        )
        .set_coordination("staged")
        .add_tag("e-commerce")
        .set_author("Your Name")
        .build())
    
    # Add to library
    manager.add_template(custom_team)
    
    # Example 3: Clone and modify
    cloned = manager.clone_template(
        "team_vpn_service",
        "My VPN Team"
    )
    
    # Example 4: Export/Import
    json_export = manager.export_template("team_vpn_service")
    
    # Save to file
    manager.save_template(vpn_team, "vpn_team.json")
    
    # Load from file
    loaded = manager.load_template("vpn_team.json")
    
    print("Done!")


if __name__ == "__main__":
    example_usage()
