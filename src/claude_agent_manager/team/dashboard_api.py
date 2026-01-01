"""
Team Mode Dashboard API - FastAPI endpoints for dashboard integration
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import json

from .team_manager import TeamManager, AgentStack, MCPPermission


# Pydantic models
class AgentCreateRequest(BaseModel):
    role_type: str
    name: str
    description: str
    stack: str
    skills: List[str] = []
    mcp_permissions: List[str] = []
    system_prompt: str = ""
    enabled: bool = True


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


# FastAPI app
dashboard_app = FastAPI(title="Team Mode Dashboard API")

dashboard_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_team_manager: Optional[TeamManager] = None


def get_manager(project_path: str = ".") -> TeamManager:
    global _team_manager
    if _team_manager is None:
        _team_manager = TeamManager(Path(project_path))
    return _team_manager


@dashboard_app.post("/api/team/activate")
async def activate(project_path: str = "."):
    manager = get_manager(project_path)
    return await manager.activate_team_mode()


@dashboard_app.get("/api/team/dashboard")
async def dashboard(project_path: str = "."):
    manager = get_manager(project_path)
    return await manager.get_dashboard_state()


@dashboard_app.get("/api/agents")
async def list_agents(project_path: str = "."):
    manager = get_manager(project_path)
    return [a.to_dict() for a in manager.list_agents()]


@dashboard_app.post("/api/agents")
async def create_agent(request: AgentCreateRequest, project_path: str = "."):
    manager = get_manager(project_path)

    stack = AgentStack(request.stack.lower())
    perms = {MCPPermission(p) for p in request.mcp_permissions}

    agent = await manager.add_agent(
        role_type=request.role_type,
        name=request.name,
        description=request.description,
        stack=stack,
        skills=request.skills,
        mcp_permissions=perms,
        system_prompt=request.system_prompt,
        enabled=request.enabled
    )

    return agent.to_dict()


@dashboard_app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str, project_path: str = "."):
    manager = get_manager(project_path)
    success = await manager.remove_agent(agent_id)
    if not success:
        raise HTTPException(404, "Agent not found")
    return {"success": True}


@dashboard_app.post("/api/agents/{agent_id}/toggle")
async def toggle_agent(agent_id: str, enabled: bool, project_path: str = "."):
    manager = get_manager(project_path)
    success = await manager.toggle_agent(agent_id, enabled)
    if not success:
        raise HTTPException(404, "Agent not found")
    return {"success": True, "enabled": enabled}
