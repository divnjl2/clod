"""
Memory module for cross-session agent memory.

Provides both SQLite-based and optional Graph DB implementations,
as well as session-based memory for agent insights.

Integrated from Auto-Claude memory system.
"""

from .graph_memory import GraphMemory, MemoryNode, MemoryRelation
from .session import (
    SessionMemory,
    SessionInsights,
    save_session_insights,
    get_session_context,
)

__all__ = [
    # Graph Memory
    "GraphMemory",
    "MemoryNode",
    "MemoryRelation",
    # Session Memory
    "SessionMemory",
    "SessionInsights",
    "save_session_insights",
    "get_session_context",
]
