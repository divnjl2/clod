#!/usr/bin/env python3
"""
MCP Server: Agent Memory Operations

Даёт агенту возможность работать с долговременной памятью:
- Сохранять знания (факты, решения, паттерны)
- Искать по памяти
- Создавать связи между сущностями
- Получать контекст из прошлых сессий

Добавить в .mcp.json агента:
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["/path/to/memory_mcp.py"],
      "env": {
        "AGENT_ID": "agent-1234",
        "MEMORY_DIR": "/path/to/memory"
      }
    }
  }
}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from memory.graph_memory import GraphMemory, NodeType, RelationType, MemoryNode
from memory.session import SessionMemory, SessionInsights
from memory.claude_mem_bridge import ClaudeMemBridge


# ============================================================================
# CONFIG
# ============================================================================

AGENT_ID = os.environ.get("AGENT_ID", "default")
MEMORY_DIR = os.environ.get("MEMORY_DIR", str(Path.cwd() / ".clod"))


def log(*args):
    print(f"[memory-mcp]", *args, file=sys.stderr)


# ============================================================================
# MEMORY INSTANCES
# ============================================================================

_graph_memory: Optional[GraphMemory] = None
_session_memory: Optional[SessionMemory] = None


def get_graph_memory() -> GraphMemory:
    global _graph_memory
    if _graph_memory is None:
        _graph_memory = GraphMemory(agent_id=AGENT_ID)
    return _graph_memory


def get_session_memory() -> SessionMemory:
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory(
            base_dir=Path(MEMORY_DIR),
            agent_id=AGENT_ID,
            use_graph_memory=True,
        )
    return _session_memory


# ============================================================================
# TOOL HANDLERS
# ============================================================================

def tool_store_knowledge(params: Dict[str, Any]) -> Dict[str, Any]:
    """Store a piece of knowledge in memory."""
    content = params.get("content", "")
    node_type = params.get("type", "fact")
    importance = params.get("importance", 0.5)
    related_to = params.get("related_to")
    metadata = params.get("metadata", {})

    if not content:
        return {"success": False, "error": "Content is required"}

    try:
        memory = get_graph_memory()

        # Map string type to NodeType
        type_map = {
            "fact": NodeType.FACT,
            "decision": NodeType.DECISION,
            "task": NodeType.TASK,
            "file": NodeType.FILE,
            "function": NodeType.FUNCTION,
            "class": NodeType.CLASS,
            "error": NodeType.ERROR,
            "pattern": NodeType.PATTERN,
        }
        nt = type_map.get(node_type.lower(), NodeType.FACT)

        node = memory.store(
            content=content,
            node_type=nt,
            importance=importance,
            metadata=metadata,
            related_to=related_to,
        )

        return {
            "success": True,
            "node_id": node.id,
            "type": nt.value,
            "importance": importance,
            "message": f"Stored: {content[:50]}..."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_query_memory(params: Dict[str, Any]) -> Dict[str, Any]:
    """Query memory for relevant knowledge."""
    search_term = params.get("query", "")
    node_type = params.get("type")
    min_importance = params.get("min_importance", 0.0)
    limit = params.get("limit", 10)

    try:
        memory = get_graph_memory()

        nt = None
        if node_type:
            type_map = {
                "fact": NodeType.FACT,
                "decision": NodeType.DECISION,
                "pattern": NodeType.PATTERN,
                "error": NodeType.ERROR,
            }
            nt = type_map.get(node_type.lower())

        nodes = memory.query(
            search_term=search_term if search_term else None,
            node_type=nt,
            min_importance=min_importance,
            limit=limit,
        )

        return {
            "success": True,
            "count": len(nodes),
            "results": [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "content": n.content,
                    "importance": n.importance,
                    "access_count": n.access_count,
                }
                for n in nodes
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_create_relation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a relation between two nodes."""
    source_id = params.get("source_id")
    target_id = params.get("target_id")
    relation_type = params.get("relation_type", "related_to")

    if not source_id or not target_id:
        return {"success": False, "error": "source_id and target_id are required"}

    try:
        memory = get_graph_memory()

        type_map = {
            "related_to": RelationType.RELATED_TO,
            "depends_on": RelationType.DEPENDS_ON,
            "part_of": RelationType.PART_OF,
            "caused_by": RelationType.CAUSED_BY,
            "fixed_by": RelationType.FIXED_BY,
            "implements": RelationType.IMPLEMENTS,
            "uses": RelationType.USES,
            "contains": RelationType.CONTAINS,
        }
        rt = type_map.get(relation_type.lower(), RelationType.RELATED_TO)

        relation = memory.relate(source_id, rt, target_id)

        return {
            "success": True,
            "relation": f"{source_id} --[{rt.value}]--> {target_id}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_get_related(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get nodes related to a given node."""
    node_id = params.get("node_id")
    direction = params.get("direction", "both")

    if not node_id:
        return {"success": False, "error": "node_id is required"}

    try:
        memory = get_graph_memory()

        results = memory.get_related(node_id, direction=direction)

        return {
            "success": True,
            "count": len(results),
            "related": [
                {
                    "node": {
                        "id": node.id,
                        "type": node.node_type.value,
                        "content": node.content,
                    },
                    "relation": rel.relation_type.value,
                }
                for node, rel in results
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_save_session_insights(params: Dict[str, Any]) -> Dict[str, Any]:
    """Save session insights for future reference."""
    session_number = params.get("session_number", 1)
    subtasks_completed = params.get("subtasks_completed", [])
    what_worked = params.get("what_worked", [])
    what_failed = params.get("what_failed", [])
    patterns_found = params.get("patterns_found", [])
    gotchas = params.get("gotchas", [])
    recommendations = params.get("recommendations", [])

    try:
        memory = get_session_memory()

        insights = SessionInsights(
            session_number=session_number,
            agent_id=AGENT_ID,
            subtasks_completed=subtasks_completed,
            what_worked=what_worked,
            what_failed=what_failed,
            patterns_found=patterns_found,
            gotchas_encountered=gotchas,
            recommendations_for_next_session=recommendations,
        )

        success, storage_type = memory.save_session(insights)

        return {
            "success": success,
            "storage_type": storage_type,
            "session_number": session_number,
            "message": f"Saved {len(subtasks_completed)} subtasks, {len(patterns_found)} patterns"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_get_session_context(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get context from previous sessions."""
    subtask_description = params.get("subtask_description", "")

    try:
        memory = get_session_memory()

        context = memory.get_context_for_subtask(subtask_description)
        recommendations = memory.get_recommendations()
        patterns = memory.get_patterns()
        gotchas = memory.get_gotchas()

        return {
            "success": True,
            "context": context,
            "recommendations": recommendations[:5],
            "patterns": patterns[:5],
            "gotchas": gotchas[:5],
            "total_sessions": memory.get_total_sessions(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_memory_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get memory statistics."""
    try:
        graph_memory = get_graph_memory()
        session_memory = get_session_memory()

        graph_stats = graph_memory.get_stats()

        return {
            "success": True,
            "agent_id": AGENT_ID,
            "graph_memory": {
                "total_nodes": graph_stats["total_nodes"],
                "total_relations": graph_stats["total_relations"],
                "nodes_by_type": graph_stats["nodes_by_type"],
            },
            "session_memory": {
                "total_sessions": session_memory.get_total_sessions(),
                "total_subtasks_completed": session_memory.get_total_subtasks_completed(),
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# CLAUDE-MEM BRIDGE HANDLERS
# ============================================================================

_bridge: Optional[ClaudeMemBridge] = None


def get_bridge() -> ClaudeMemBridge:
    global _bridge
    if _bridge is None:
        _bridge = ClaudeMemBridge(
            agent_id=AGENT_ID,
            graph_memory=get_graph_memory(),
        )
    return _bridge


def tool_sync_claude_mem(params: Dict[str, Any]) -> Dict[str, Any]:
    """Sync observations from claude-mem to GraphMemory."""
    limit = params.get("limit", 100)
    project = params.get("project")

    try:
        bridge = get_bridge()
        stats = bridge.sync_from_claude_mem(limit=limit, project=project)

        return {
            "success": True,
            "observations_synced": stats.observations_synced,
            "nodes_created": stats.nodes_created,
            "relations_created": stats.relations_created,
            "errors": stats.errors,
            "skipped": stats.skipped,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_unified_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """Search across both claude-mem and GraphMemory."""
    query = params.get("query", "")
    limit = params.get("limit", 10)
    include_claude_mem = params.get("include_claude_mem", True)
    include_graph_memory = params.get("include_graph_memory", True)

    if not query:
        return {"success": False, "error": "Query is required"}

    try:
        bridge = get_bridge()
        context = bridge.get_unified_context(
            query=query,
            include_claude_mem=include_claude_mem,
            include_graph_memory=include_graph_memory,
            limit=limit,
        )

        return {
            "success": True,
            "query": query,
            "graph_memory_results": len(context["graph_memory"]),
            "claude_mem_results": len(context["claude_mem"]),
            "results": {
                "graph_memory": context["graph_memory"],
                "claude_mem": context["claude_mem"],
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_bridge_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get bridge statistics."""
    try:
        bridge = get_bridge()
        stats = bridge.get_stats()
        return {"success": True, **stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# TOOLS REGISTRY
# ============================================================================

TOOLS = {
    "store_knowledge": {
        "description": "Store a piece of knowledge (fact, decision, pattern, error) in long-term memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The knowledge to store"},
                "type": {"type": "string", "enum": ["fact", "decision", "task", "file", "function", "class", "error", "pattern"], "description": "Type of knowledge"},
                "importance": {"type": "number", "description": "Importance 0.0-1.0 (higher = more important)"},
                "related_to": {"type": "string", "description": "ID of related node"},
                "metadata": {"type": "object", "description": "Additional metadata"}
            },
            "required": ["content"]
        },
        "handler": tool_store_knowledge
    },
    "query_memory": {
        "description": "Search memory for relevant knowledge",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "type": {"type": "string", "description": "Filter by type"},
                "min_importance": {"type": "number", "description": "Minimum importance"},
                "limit": {"type": "integer", "description": "Max results"}
            }
        },
        "handler": tool_query_memory
    },
    "create_relation": {
        "description": "Create a relation between two knowledge nodes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "Source node ID"},
                "target_id": {"type": "string", "description": "Target node ID"},
                "relation_type": {"type": "string", "enum": ["related_to", "depends_on", "part_of", "caused_by", "fixed_by", "implements", "uses", "contains"]}
            },
            "required": ["source_id", "target_id"]
        },
        "handler": tool_create_relation
    },
    "get_related": {
        "description": "Get nodes related to a given node",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID"},
                "direction": {"type": "string", "enum": ["outgoing", "incoming", "both"]}
            },
            "required": ["node_id"]
        },
        "handler": tool_get_related
    },
    "save_session_insights": {
        "description": "Save insights from current session for future reference",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_number": {"type": "integer", "description": "Session number"},
                "subtasks_completed": {"type": "array", "items": {"type": "string"}, "description": "Completed subtasks"},
                "what_worked": {"type": "array", "items": {"type": "string"}, "description": "What worked well"},
                "what_failed": {"type": "array", "items": {"type": "string"}, "description": "What failed"},
                "patterns_found": {"type": "array", "items": {"type": "string"}, "description": "Discovered patterns"},
                "gotchas": {"type": "array", "items": {"type": "string"}, "description": "Gotchas encountered"},
                "recommendations": {"type": "array", "items": {"type": "string"}, "description": "Recommendations for next session"}
            }
        },
        "handler": tool_save_session_insights
    },
    "get_session_context": {
        "description": "Get context and recommendations from previous sessions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subtask_description": {"type": "string", "description": "Current subtask for context relevance"}
            }
        },
        "handler": tool_get_session_context
    },
    "memory_stats": {
        "description": "Get memory statistics",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_memory_stats
    },
    # Claude-Mem Bridge tools
    "sync_claude_mem": {
        "description": "Sync observations from claude-mem to GraphMemory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max observations to sync (default 100)"},
                "project": {"type": "string", "description": "Filter by project name"}
            }
        },
        "handler": tool_sync_claude_mem
    },
    "unified_search": {
        "description": "Search across both claude-mem history and GraphMemory knowledge",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results per source"},
                "include_claude_mem": {"type": "boolean", "description": "Include claude-mem results"},
                "include_graph_memory": {"type": "boolean", "description": "Include GraphMemory results"}
            },
            "required": ["query"]
        },
        "handler": tool_unified_search
    },
    "bridge_stats": {
        "description": "Get claude-mem bridge statistics",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_bridge_stats
    }
}


# ============================================================================
# MCP PROTOCOL
# ============================================================================

def handle_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "memory-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": tool["description"],
                        "inputSchema": tool["inputSchema"]
                    }
                    for name, tool in TOOLS.items()
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool = TOOLS.get(tool_name)

        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }

        result = tool["handler"](params.get("arguments", {}))

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            }
        }

    elif method == "notifications/initialized":
        log(f"Initialized for agent: {AGENT_ID}")
        return None

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }


def main():
    log(f"Started for agent: {AGENT_ID}, memory_dir: {MEMORY_DIR}")

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = handle_request(request)

                if response:
                    print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                log(f"JSON error: {e}")
            except Exception as e:
                log(f"Error: {e}")
                import traceback
                traceback.print_exc(file=sys.stderr)

    except KeyboardInterrupt:
        pass
    finally:
        log("Shutting down...")
        if _graph_memory:
            _graph_memory.close()


if __name__ == "__main__":
    main()
