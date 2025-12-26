"""
Memory module for cross-session agent memory.

Provides both SQLite-based and optional Graph DB implementations,
as well as session-based memory for agent insights.

Integrated from Auto-Claude memory system.

Components:
- GraphMemory: Graph-based knowledge storage with nodes and relations
- SessionMemory: Session insights storage (file + graph backend)
- ClaudeMemBridge: Bridge between claude-mem and GraphMemory
"""

from .graph_memory import GraphMemory, MemoryNode, MemoryRelation, NodeType, RelationType, SHARED_AGENT_ID
from .session import (
    SessionMemory,
    SessionInsights,
    save_session_insights,
    get_session_context,
)
from .claude_mem_bridge import ClaudeMemBridge, ClaudeMemObservation, SyncStats

__all__ = [
    # Graph Memory
    "GraphMemory",
    "MemoryNode",
    "MemoryRelation",
    "NodeType",
    "RelationType",
    "SHARED_AGENT_ID",
    # Session Memory
    "SessionMemory",
    "SessionInsights",
    "save_session_insights",
    "get_session_context",
    # Claude-Mem Bridge
    "ClaudeMemBridge",
    "ClaudeMemObservation",
    "SyncStats",
]
