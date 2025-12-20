#!/usr/bin/env python3
"""
MCP Server: Sub-Agent Orchestration (Python version)

Даёт агенту возможность создавать и управлять субагентами.

Добавить в .mcp.json агента:
{
  "mcpServers": {
    "subagents": {
      "command": "python",
      "args": ["/path/to/subagent_mcp.py"],
      "env": {
        "PARENT_AGENT_ID": "agent-1234"
      }
    }
  }
}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid


# ============================================================================
# CONFIG
# ============================================================================

PARENT_AGENT_ID = os.environ.get("PARENT_AGENT_ID", "unknown")
MAX_SUBAGENTS = int(os.environ.get("MAX_SUBAGENTS", "5"))
AGENT_ROOT = os.environ.get("AGENT_ROOT", str(Path.home() / ".claude-agent-manager"))

def log(*args):
    print(f"[subagent-mcp]", *args, file=sys.stderr)


# ============================================================================
# SUBAGENT STORAGE
# ============================================================================

@dataclass
class SubAgent:
    id: str
    agent_id: str
    role: str
    task: str
    scope: Optional[str] = None
    status: str = "created"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    port: Optional[int] = None


subagents: Dict[str, SubAgent] = {}


def generate_id(role: str) -> str:
    ts = hex(int(time.time()))[2:]
    rand = uuid.uuid4().hex[:4]
    return f"sub-{role}-{ts}-{rand}"


# ============================================================================
# CAM INTEGRATION
# ============================================================================

def run_cam(args: List[str]) -> Dict[str, Any]:
    """Запустить cam команду."""
    try:
        # Находим cam
        cam_path = "cam"
        
        result = subprocess.run(
            [cam_path] + args,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except FileNotFoundError:
        return {"success": False, "error": "cam not found in PATH"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_manager():
    """Получить clod manager напрямую."""
    try:
        # Пробуем импортировать напрямую
        sys.path.insert(0, str(Path(__file__).parent))
        from claude_agent_manager import manager
        return manager
    except ImportError:
        return None


# ============================================================================
# TOOL HANDLERS
# ============================================================================

def tool_create_subagent(params: Dict[str, Any]) -> Dict[str, Any]:
    """Создать субагента."""
    role = params.get("role", "worker")
    task = params.get("task", "")
    scope = params.get("scope")
    instructions = params.get("instructions", "")
    
    if len(subagents) >= MAX_SUBAGENTS:
        return {
            "success": False,
            "error": f"Max {MAX_SUBAGENTS} sub-agents. Remove some first."
        }
    
    sub_id = generate_id(role)
    
    # System prompt для субагента
    system_prompt = f"""# Sub-Agent: {role.upper()}

## Parent: {PARENT_AGENT_ID}

## Task
{task}

{f'## Scope: {scope}' if scope else ''}

{f'## Instructions: {instructions}' if instructions else ''}

## Rules
1. Focus ONLY on your task
2. Work within scope
3. Write clean code
4. Report when done
"""

    # Пробуем через manager напрямую
    mgr = get_manager()
    if mgr:
        try:
            agent = mgr.create_agent(
                purpose=f"[SUB:{role}] {task[:40]}",
                project_path=scope or ".",
                config=mgr.AgentConfigOptions(
                    system_prompt=system_prompt
                )
            )
            agent_id = agent.id
            port = agent.port
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        # Fallback на CLI
        result = run_cam([
            "new",
            "--purpose", f"[SUB:{role}] {task[:40]}",
            "--no-start"
        ])
        
        if not result["success"]:
            return {"success": False, "error": result.get("error", result.get("stderr", "Unknown error"))}
        
        # Парсим agent_id из вывода
        import re
        match = re.search(r'([a-f0-9]{4}-\d+)', result["stdout"])
        agent_id = match.group(1) if match else sub_id
        port = None
    
    sub = SubAgent(
        id=sub_id,
        agent_id=agent_id,
        role=role,
        task=task,
        scope=scope,
        port=port
    )
    subagents[sub_id] = sub
    
    log(f"Created: {sub_id} -> {agent_id}")
    
    return {
        "success": True,
        "subagent_id": sub_id,
        "agent_id": agent_id,
        "role": role,
        "message": f"Sub-agent '{role}' created. Use start_subagent to begin."
    }


def tool_start_subagent(params: Dict[str, Any]) -> Dict[str, Any]:
    """Запустить субагента."""
    sub_id = params.get("subagent_id")
    
    if sub_id not in subagents:
        return {"success": False, "error": f"Not found: {sub_id}"}
    
    sub = subagents[sub_id]
    
    mgr = get_manager()
    if mgr:
        try:
            mgr.start_agent(sub.agent_id)
            sub.status = "running"
            return {"success": True, "subagent_id": sub_id, "status": "running"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    result = run_cam(["start", sub.agent_id])
    if result["success"]:
        sub.status = "running"
        return {"success": True, "subagent_id": sub_id, "status": "running"}
    
    return {"success": False, "error": result.get("error", "Failed to start")}


def tool_stop_subagent(params: Dict[str, Any]) -> Dict[str, Any]:
    """Остановить субагента."""
    sub_id = params.get("subagent_id")
    
    if sub_id not in subagents:
        return {"success": False, "error": f"Not found: {sub_id}"}
    
    sub = subagents[sub_id]
    
    mgr = get_manager()
    if mgr:
        try:
            mgr.stop_agent(sub.agent_id)
        except:
            pass
    else:
        run_cam(["stop", sub.agent_id])
    
    sub.status = "stopped"
    return {"success": True, "subagent_id": sub_id, "status": "stopped"}


def tool_remove_subagent(params: Dict[str, Any]) -> Dict[str, Any]:
    """Удалить субагента."""
    sub_id = params.get("subagent_id")
    
    if sub_id not in subagents:
        return {"success": False, "error": f"Not found: {sub_id}"}
    
    sub = subagents[sub_id]
    
    mgr = get_manager()
    if mgr:
        try:
            mgr.stop_agent(sub.agent_id)
            mgr.remove_agent(sub.agent_id)
        except:
            pass
    else:
        run_cam(["stop", sub.agent_id])
        run_cam(["remove", sub.agent_id, "--force"])
    
    del subagents[sub_id]
    return {"success": True, "subagent_id": sub_id, "message": f"Removed {sub.role}"}


def tool_list_subagents(params: Dict[str, Any]) -> Dict[str, Any]:
    """Список субагентов."""
    return {
        "success": True,
        "count": len(subagents),
        "max_allowed": MAX_SUBAGENTS,
        "subagents": [
            {
                "id": s.id,
                "agent_id": s.agent_id,
                "role": s.role,
                "task": s.task[:50],
                "status": s.status,
                "port": s.port
            }
            for s in subagents.values()
        ]
    }


def tool_cleanup_all(params: Dict[str, Any]) -> Dict[str, Any]:
    """Удалить всех субагентов."""
    if not params.get("confirm"):
        return {"success": False, "error": "Set confirm=true"}
    
    removed = []
    for sub_id, sub in list(subagents.items()):
        try:
            mgr = get_manager()
            if mgr:
                mgr.stop_agent(sub.agent_id)
                mgr.remove_agent(sub.agent_id)
            else:
                run_cam(["stop", sub.agent_id])
                run_cam(["remove", sub.agent_id, "--force"])
            removed.append(sub_id)
        except:
            pass
    
    subagents.clear()
    return {"success": True, "removed": removed}


# ============================================================================
# TOOLS REGISTRY
# ============================================================================

TOOLS = {
    "create_subagent": {
        "description": "Create a sub-agent for a specific task. It will have isolated memory and context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "description": "Role (backend, frontend, tests, docs, etc)"},
                "task": {"type": "string", "description": "Task for this sub-agent"},
                "scope": {"type": "string", "description": "Directory to focus on"},
                "instructions": {"type": "string", "description": "Additional instructions"}
            },
            "required": ["role", "task"]
        },
        "handler": tool_create_subagent
    },
    "start_subagent": {
        "description": "Start a sub-agent",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subagent_id": {"type": "string", "description": "Sub-agent ID"}
            },
            "required": ["subagent_id"]
        },
        "handler": tool_start_subagent
    },
    "stop_subagent": {
        "description": "Stop a sub-agent",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subagent_id": {"type": "string", "description": "Sub-agent ID"}
            },
            "required": ["subagent_id"]
        },
        "handler": tool_stop_subagent
    },
    "remove_subagent": {
        "description": "Remove a sub-agent completely",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subagent_id": {"type": "string", "description": "Sub-agent ID"}
            },
            "required": ["subagent_id"]
        },
        "handler": tool_remove_subagent
    },
    "list_subagents": {
        "description": "List all sub-agents",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_list_subagents
    },
    "cleanup_all": {
        "description": "Remove all sub-agents",
        "inputSchema": {
            "type": "object",
            "properties": {
                "confirm": {"type": "boolean", "description": "Confirm cleanup"}
            },
            "required": ["confirm"]
        },
        "handler": tool_cleanup_all
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
                "serverInfo": {"name": "subagent-mcp", "version": "1.0.0"},
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
        log("Initialized")
        return None
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }


def main():
    log(f"Started for parent: {PARENT_AGENT_ID}")
    
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
    
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        log("Shutting down...")
        for sub in subagents.values():
            try:
                run_cam(["stop", sub.agent_id])
            except:
                pass


if __name__ == "__main__":
    main()
