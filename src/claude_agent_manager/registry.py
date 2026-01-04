from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


# Permission preset types
PermissionPreset = Literal["default", "strict", "permissive", "autopilot", "custom"]


class PermissionConfig(BaseModel):
    """Permission configuration for Claude Code agent."""
    preset: PermissionPreset = "default"
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)


# Default permission presets
# Format notes (Claude Code syntax):
# - Bash: use "Bash(cmd:*)" for prefix matching, not "Bash(cmd *)"
# - WebFetch: use "WebFetch(domain:hostname)" or just "WebFetch" for all
# - WebSearch: just "WebSearch" (no wildcards supported)
PERMISSION_PRESETS = {
    "default": {
        "allow": [
            "Read(*)",
            "Bash(git:*)",
            "Bash(ls:*)",
            "Bash(cat:*)",
            "Bash(grep:*)",
            "Bash(find:*)",
            "Bash(npm:*)",
            "Bash(pnpm:*)",
            "Bash(yarn:*)",
            "Bash(pip:*)",
            "Bash(python:*)",
            "Bash(node:*)",
            "Bash(curl:*)",
            "mcp__*",
            "Task(*)",
            "WebFetch",
            "WebSearch",
        ],
        "deny": [
            "Bash(rm -rf /*)",
            "Bash(sudo:*)",
            "Bash(chmod 777:*)",
        ]
    },
    "strict": {
        "allow": [
            "Read(*)",
            "Bash(git status:*)",
            "Bash(git diff:*)",
            "Bash(git log:*)",
            "Bash(ls:*)",
            "Bash(cat:*)",
            "Bash(grep:*)",
            "mcp__*",
            "WebFetch",
        ],
        "deny": [
            "Bash(rm:*)",
            "Bash(sudo:*)",
            "Bash(chmod:*)",
            "Bash(curl:*)",
            "Bash(wget:*)",
        ]
    },
    "permissive": {
        "allow": [
            "Read(*)",
            "Write(*)",
            "Edit(*)",
            "Bash(git:*)",
            "Bash(ls:*)",
            "Bash(cat:*)",
            "Bash(grep:*)",
            "Bash(find:*)",
            "Bash(ps:*)",
            "Bash(kill:*)",
            "Bash(pkill:*)",
            "Bash(pgrep:*)",
            "Bash(lsof:*)",
            "Bash(npm:*)",
            "Bash(pnpm:*)",
            "Bash(yarn:*)",
            "Bash(pip:*)",
            "Bash(python:*)",
            "Bash(node:*)",
            "Bash(docker ps:*)",
            "Bash(docker logs:*)",
            "Bash(docker exec:*)",
            "Bash(curl:*)",
            "Bash(wget:*)",
            "Bash(make:*)",
            "Bash(cargo:*)",
            "Bash(go:*)",
            "mcp__*",
            "Task(*)",
            "WebFetch",
            "WebSearch",
        ],
        "deny": [
            "Bash(rm -rf /*)",
            "Bash(sudo rm -rf:*)",
            "Bash(chmod 777 /*)",
        ]
    },
    # Autopilot mode: Full autonomy, no permission prompts
    # Equivalent to --dangerously-skip-permissions CLI flag
    # Use with caution - agent can execute ANY action without confirmation
    "autopilot": {
        "allow": [
            # Universal wildcard - allows ALL tools without prompts
            "*",
            # Explicit tool names for maximum compatibility
            "Read(*)",
            "Write(*)",
            "Edit(*)",
            "Glob(*)",
            "Grep(*)",
            "Bash",  # No parentheses = all commands
            "Task(*)",
            "mcp__*",
            "WebFetch",  # No parentheses = all domains
            "WebSearch",
            "NotebookEdit(*)",
        ],
        "deny": []  # No denials in autopilot mode
    },
    "custom": {
        "allow": [],
        "deny": []
    }
}


def get_permission_preset(preset: PermissionPreset) -> dict:
    """Get permission preset by name."""
    return PERMISSION_PRESETS.get(preset, PERMISSION_PRESETS["default"])


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
    purpose: str = ""
    display_name: Optional[str] = None  # Custom display name (falls back to purpose if None)
    project_path: str = ""

    # Адаптивная система портов
    port_min: int = 37700  # Минимум диапазона
    port_max: int = 37799  # Максимум диапазона
    last_port: Optional[int] = None  # Последний успешно использованный порт

    # Deprecated: старое поле для обратной совместимости
    port: Optional[int] = None  # Будет мигрировано в last_port

    pm2_name: str = ""
    cmd_pid: Optional[int] = None
    viewer_pid: Optional[int] = None
    use_browser: bool = False
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    config: AgentConfigOptions = Field(default_factory=AgentConfigOptions)
    permissions: PermissionConfig = Field(default_factory=PermissionConfig)
    autopilot_enabled: bool = False  # Full autonomy mode - no permission prompts
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    active_run_id: Optional[str] = None

    def get_preferred_port(self) -> Optional[int]:
        """Получить предпочтительный порт (last_port или мигрированный port)."""
        return self.last_port or self.port

    def get_display_name(self) -> str:
        """Get display name, falling back to purpose if not set."""
        return self.display_name if self.display_name else self.purpose

    def get_effective_permissions(self) -> dict:
        """Get effective permissions (preset + custom overrides).

        If autopilot_enabled is True, returns autopilot preset regardless
        of the configured preset. This provides full autonomy mode.
        """
        # Autopilot mode overrides everything
        if self.autopilot_enabled:
            return get_permission_preset("autopilot")

        preset_perms = get_permission_preset(self.permissions.preset)

        if self.permissions.preset == "custom":
            # Custom mode: use only custom allow/deny
            return {
                "allow": self.permissions.allow,
                "deny": self.permissions.deny
            }

        # Preset mode: merge preset with custom additions
        allow = list(preset_perms["allow"])
        deny = list(preset_perms["deny"])

        # Add custom rules
        for rule in self.permissions.allow:
            if rule not in allow:
                allow.append(rule)
        for rule in self.permissions.deny:
            if rule not in deny:
                deny.append(rule)

        return {"allow": allow, "deny": deny}


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


def write_claude_settings(project_path: Path, agent: AgentRecord) -> Path:
    """
    Write .claude/settings.json to project directory with agent permissions.

    Args:
        project_path: Path to project directory
        agent: Agent record with permissions config

    Returns:
        Path to written settings.json file
    """
    claude_dir = project_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_path = claude_dir / "settings.json"

    # Get effective permissions
    perms = agent.get_effective_permissions()

    settings = {
        "permissions": {
            "allow": perms["allow"],
            "deny": perms["deny"]
        }
    }

    # Add bypassPermissions mode for autopilot
    if agent.autopilot_enabled:
        settings["permissions"]["defaultMode"] = "bypassPermissions"

    # Preserve existing settings if any
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            # Merge - our permissions override
            existing["permissions"] = settings["permissions"]
            settings = existing
        except (json.JSONDecodeError, KeyError):
            pass

    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings_path


def update_agent_permissions(agent_root: Path, agent_id: str, permissions: PermissionConfig) -> AgentRecord:
    """
    Update agent permissions and write to .claude/settings.json.

    Args:
        agent_root: Path to agents root directory
        agent_id: Agent ID
        permissions: New permission configuration

    Returns:
        Updated agent record
    """
    agent = load_agent(agent_root, agent_id)
    agent.permissions = permissions
    save_agent(agent_root, agent)

    # Write to project .claude/settings.json
    project_path = Path(agent.project_path)
    write_claude_settings(project_path, agent)

    return agent


def update_agent_autopilot(agent_root: Path, agent_id: str, enabled: bool) -> AgentRecord:
    """
    Update agent autopilot mode and write to .claude/settings.json.

    When autopilot is enabled, the agent gets full autonomy - all tools
    are allowed without permission prompts. This is equivalent to running
    Claude Code with --dangerously-skip-permissions flag.

    Args:
        agent_root: Path to agents root directory
        agent_id: Agent ID
        enabled: Whether to enable autopilot mode

    Returns:
        Updated agent record
    """
    agent = load_agent(agent_root, agent_id)
    agent.autopilot_enabled = enabled
    save_agent(agent_root, agent)

    # Write to project .claude/settings.json with updated permissions
    project_path = Path(agent.project_path)
    write_claude_settings(project_path, agent)

    # Also write to agent's isolated config (for isolated runs)
    # Claude Code on Windows may look in USERPROFILE/.claude/ or APPDATA/.claude/
    agent_dir = agent_root / agent_id
    runs_dir = agent_dir / "runs"
    if runs_dir.exists():
        # Find latest run directory
        run_dirs = sorted(runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        for run_dir in run_dirs[:1]:  # Only latest run
            perms = agent.get_effective_permissions()
            settings = {"permissions": {"allow": perms["allow"], "deny": perms["deny"]}}
            # Write to .config/.claude/ (APPDATA)
            for subdir in [".config", ".home"]:
                isolated_config = run_dir / subdir / ".claude"
                isolated_config.mkdir(parents=True, exist_ok=True)
                settings_path = isolated_config / "settings.json"
                settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
                print(f"[AUTOPILOT] Wrote settings: {settings_path}")

    # Update run.cmd to add/remove --dangerously-skip-permissions flag
    try:
        agent_dir = agent_root / agent_id
        run_cmd_path = agent_dir / "run.cmd"
        if run_cmd_path.exists():
            content = run_cmd_path.read_text(encoding="utf-8")
            # Replace the claude command line
            if enabled:
                # Add flag if not present
                content = content.replace("\nclaude\n", "\nclaude --dangerously-skip-permissions\n")
            else:
                # Remove flag
                content = content.replace("\nclaude --dangerously-skip-permissions\n", "\nclaude\n")
            run_cmd_path.write_text(content, encoding="utf-8")
            print(f"[AUTOPILOT] Updated run.cmd: autopilot={enabled}")
    except Exception as e:
        print(f"[AUTOPILOT] Failed to update run.cmd: {e}")

    return agent
