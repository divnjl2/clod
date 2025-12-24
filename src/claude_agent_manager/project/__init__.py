"""
Project Analysis Module for Claude Agent Manager
=================================================

Provides intelligent project analysis capabilities including:
- Technology stack detection (languages, frameworks, databases)
- Package manager detection
- Infrastructure detection (Docker, K8s, etc.)
- Custom scripts detection (npm scripts, Makefile targets)
- Security profile generation

Integrated from Auto-Claude project analyzer.
"""

from .models import TechnologyStack, CustomScripts, SecurityProfile
from .analyzer import ProjectAnalyzer, get_or_create_profile, is_command_allowed

__all__ = [
    "ProjectAnalyzer",
    "TechnologyStack",
    "CustomScripts",
    "SecurityProfile",
    "get_or_create_profile",
    "is_command_allowed",
]
