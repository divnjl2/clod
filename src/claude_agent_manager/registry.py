from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Proxy configuration for agent."""
    enabled: bool = False
    type: str = "http"  # http, https, socks5
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None

    def to_url(self) -> Optional[str]:
        """Build proxy URL string."""
        if not self.enabled or not self.host or not self.port:
            return None
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        elif self.username:
            auth = f"{self.username}@"
        return f"{self.type}://{auth}{self.host}:{self.port}"


class AgentConfigOptions(BaseModel):
    """Configuration options for Claude Code agent."""
    system_prompt: Optional[str] = None
    mcp_servers: Optional[dict] = None
    claude_settings: Optional[dict] = None
    disable_autoupdate: bool = False
    max_output_tokens: Optional[int] = None
    bash_timeout_ms: Optional[int] = None
    disable_telemetry: bool = False
    custom_env_vars: dict = Field(default_factory=dict)


class AgentRecord(BaseModel):
    id: str
    purpose: str
    project_path: str
    port: int
    pm2_name: str
    cmd_pid: Optional[int] = None
    viewer_pid: Optional[int] = None
    use_browser: bool = False
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    config: AgentConfigOptions = Field(default_factory=AgentConfigOptions)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def agent_dir(agent_root: Path, agent_id: str) -> Path:
    return agent_root / agent_id


def agent_json_path(agent_root: Path, agent_id: str) -> Path:
    return agent_dir(agent_root, agent_id) / "agent.json"


def load_agent(agent_root: Path, agent_id: str) -> AgentRecord:
    p = agent_json_path(agent_root, agent_id)
    if not p.exists():
        raise FileNotFoundError(f"Agent not found: {agent_id}")
    return AgentRecord(**json.loads(p.read_text(encoding="utf-8")))


def save_agent(agent_root: Path, rec: AgentRecord) -> None:
    d = agent_dir(agent_root, rec.id)
    d.mkdir(parents=True, exist_ok=True)
    agent_json_path(agent_root, rec.id).write_text(rec.model_dump_json(indent=2), encoding="utf-8")


def iter_agents(agent_root: Path) -> list[AgentRecord]:
    if not agent_root.exists():
        return []
    agents: list[AgentRecord] = []
    for d in sorted(agent_root.iterdir()):
        if not d.is_dir():
            continue
        p = d / "agent.json"
        if not p.exists():
            continue
        try:
            agents.append(AgentRecord(**json.loads(p.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return agents
