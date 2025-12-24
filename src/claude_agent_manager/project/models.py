"""
Data Models for Project Analysis
================================

Core data structures for representing technology stacks,
custom scripts, and security profiles.

Integrated from Auto-Claude project.
"""

from dataclasses import asdict, dataclass, field
from typing import List, Set


@dataclass
class TechnologyStack:
    """Detected technologies in a project."""

    languages: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    infrastructure: List[str] = field(default_factory=list)
    cloud_providers: List[str] = field(default_factory=list)
    code_quality_tools: List[str] = field(default_factory=list)
    version_managers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TechnologyStack":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CustomScripts:
    """Detected custom scripts in the project."""

    npm_scripts: List[str] = field(default_factory=list)
    make_targets: List[str] = field(default_factory=list)
    poetry_scripts: List[str] = field(default_factory=list)
    cargo_aliases: List[str] = field(default_factory=list)
    shell_scripts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CustomScripts":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SecurityProfile:
    """Complete security profile for a project."""

    # Command sets
    base_commands: Set[str] = field(default_factory=set)
    stack_commands: Set[str] = field(default_factory=set)
    script_commands: Set[str] = field(default_factory=set)
    custom_commands: Set[str] = field(default_factory=set)

    # Detected info
    detected_stack: TechnologyStack = field(default_factory=TechnologyStack)
    custom_scripts: CustomScripts = field(default_factory=CustomScripts)

    # Metadata
    project_dir: str = ""
    created_at: str = ""
    project_hash: str = ""

    def get_all_allowed_commands(self) -> Set[str]:
        """Get the complete set of allowed commands."""
        return (
            self.base_commands
            | self.stack_commands
            | self.script_commands
            | self.custom_commands
        )

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "base_commands": sorted(self.base_commands),
            "stack_commands": sorted(self.stack_commands),
            "script_commands": sorted(self.script_commands),
            "custom_commands": sorted(self.custom_commands),
            "detected_stack": asdict(self.detected_stack),
            "custom_scripts": asdict(self.custom_scripts),
            "project_dir": self.project_dir,
            "created_at": self.created_at,
            "project_hash": self.project_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SecurityProfile":
        """Load from dict."""
        profile = cls(
            base_commands=set(data.get("base_commands", [])),
            stack_commands=set(data.get("stack_commands", [])),
            script_commands=set(data.get("script_commands", [])),
            custom_commands=set(data.get("custom_commands", [])),
            project_dir=data.get("project_dir", ""),
            created_at=data.get("created_at", ""),
            project_hash=data.get("project_hash", ""),
        )

        if "detected_stack" in data:
            profile.detected_stack = TechnologyStack(**data["detected_stack"])
        if "custom_scripts" in data:
            profile.custom_scripts = CustomScripts(**data["custom_scripts"])

        return profile
