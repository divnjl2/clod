"""
Agent configuration management for Claude Code.

Handles creation and management of Claude Code configuration files:
- CLAUDE.md (system prompt / memory)
- .mcp.json (MCP server configuration)
- .claude/settings.json (Claude settings)
- Environment variables in run.cmd
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MCP_SERVERS = {
    "sequential-thinking": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/sequential-thinking-server"]
    },
    "filesystem": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/filesystem-server"]
    }
}


def build_default_mcp_servers(port: int, data_dir: Path, claude_mem_root: Optional[str] = None) -> dict:
    """
    Build default MCP servers config for an agent.

    Args:
        port: Agent's memory worker port
        data_dir: Agent's data directory
        claude_mem_root: Path to claude-mem installation (for memory MCP)

    Returns:
        MCP servers configuration dict
    """
    servers = dict(DEFAULT_MCP_SERVERS)

    # Add memory MCP if claude-mem is configured
    if claude_mem_root:
        mcp_server_path = Path(claude_mem_root) / "plugin" / "scripts" / "mcp-server.cjs"
        if mcp_server_path.exists():
            servers["claude-mem"] = {
                "type": "stdio",
                "command": "node",
                "args": [str(mcp_server_path).replace("\\", "/")],
                "env": {
                    "CLAUDE_MEM_WORKER_PORT": str(port),
                    "CLAUDE_MEM_DATA_DIR": str(data_dir).replace("\\", "/")
                }
            }

    return servers

DEFAULT_CLAUDE_SETTINGS = {
    "permissions": {
        "allow": [
            "Read(**)",
            "Glob(**)",
            "Grep(**)"
        ]
    }
}

SYSTEM_PROMPT_TEMPLATE = """# {purpose}

You are a Claude Code agent working on this project.

## Project Context
- Project path: {project_path}
- Agent ID: {agent_id}
- Memory worker port: {port}

## Guidelines
- Follow existing code patterns and conventions
- Write clear, maintainable code
- Add appropriate error handling
- Document significant changes

{custom_instructions}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE.md (System Prompt)
# ═══════════════════════════════════════════════════════════════════════════════

def get_claude_md_path(project_path: Path) -> Path:
    """Get path to CLAUDE.md in project root."""
    return project_path / "CLAUDE.md"


def read_claude_md(project_path: Path) -> Optional[str]:
    """
    Read existing CLAUDE.md content.

    Returns:
        Content string or None if file doesn't exist
    """
    path = get_claude_md_path(project_path)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[AGENT_CONFIG] read_claude_md failed | path={path} error={e}")
    return None


def write_claude_md(project_path: Path, content: str) -> Path:
    """
    Write CLAUDE.md to project root.

    Args:
        project_path: Project directory
        content: System prompt content

    Returns:
        Path to created file
    """
    path = get_claude_md_path(project_path)
    path.write_text(content, encoding="utf-8")
    logger.info(f"[AGENT_CONFIG] write_claude_md | path={path} size={len(content)}")
    return path


def create_default_claude_md(
    project_path: Path,
    purpose: str,
    agent_id: str,
    port: int,
    custom_instructions: str = ""
) -> Path:
    """
    Create CLAUDE.md with default template.

    Args:
        project_path: Project directory
        purpose: Agent purpose description
        agent_id: Agent ID
        port: Memory worker port
        custom_instructions: Additional instructions to append

    Returns:
        Path to created file
    """
    content = SYSTEM_PROMPT_TEMPLATE.format(
        purpose=purpose,
        project_path=str(project_path),
        agent_id=agent_id,
        port=port,
        custom_instructions=custom_instructions
    )
    return write_claude_md(project_path, content)


# ═══════════════════════════════════════════════════════════════════════════════
# .mcp.json (MCP Server Configuration)
# ═══════════════════════════════════════════════════════════════════════════════

def get_mcp_json_path(project_path: Path) -> Path:
    """Get path to .mcp.json in project root."""
    return project_path / ".mcp.json"


def read_mcp_json(project_path: Path) -> Optional[dict]:
    """
    Read existing .mcp.json configuration.

    Returns:
        Config dict or None if file doesn't exist
    """
    path = get_mcp_json_path(project_path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[AGENT_CONFIG] read_mcp_json failed | path={path} error={e}")
    return None


def write_mcp_json(project_path: Path, config: dict) -> Path:
    """
    Write .mcp.json to project root.

    Args:
        project_path: Project directory
        config: MCP configuration dict

    Returns:
        Path to created file
    """
    path = get_mcp_json_path(project_path)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    logger.info(f"[AGENT_CONFIG] write_mcp_json | path={path} servers={list(config.get('mcpServers', {}).keys())}")
    return path


def create_default_mcp_json(project_path: Path, servers: Optional[dict] = None) -> Path:
    """
    Create .mcp.json with default or custom servers.

    Args:
        project_path: Project directory
        servers: Optional custom servers dict (uses defaults if None)

    Returns:
        Path to created file
    """
    config = {
        "mcpServers": servers or DEFAULT_MCP_SERVERS
    }
    return write_mcp_json(project_path, config)


def add_mcp_server(
    project_path: Path,
    name: str,
    server_config: dict
) -> dict:
    """
    Add or update an MCP server in .mcp.json.

    Args:
        project_path: Project directory
        name: Server name
        server_config: Server configuration dict

    Returns:
        Updated full config
    """
    config = read_mcp_json(project_path) or {"mcpServers": {}}
    config.setdefault("mcpServers", {})
    config["mcpServers"][name] = server_config
    write_mcp_json(project_path, config)
    logger.info(f"[AGENT_CONFIG] add_mcp_server | name={name}")
    return config


def remove_mcp_server(project_path: Path, name: str) -> dict:
    """
    Remove an MCP server from .mcp.json.

    Args:
        project_path: Project directory
        name: Server name to remove

    Returns:
        Updated full config
    """
    config = read_mcp_json(project_path) or {"mcpServers": {}}
    if name in config.get("mcpServers", {}):
        del config["mcpServers"][name]
        write_mcp_json(project_path, config)
        logger.info(f"[AGENT_CONFIG] remove_mcp_server | name={name}")
    return config


# ═══════════════════════════════════════════════════════════════════════════════
# .claude/settings.json (Claude Settings)
# ═══════════════════════════════════════════════════════════════════════════════

def get_claude_settings_dir(project_path: Path) -> Path:
    """Get .claude directory path."""
    return project_path / ".claude"


def get_claude_settings_path(project_path: Path) -> Path:
    """Get path to .claude/settings.json."""
    return get_claude_settings_dir(project_path) / "settings.json"


def read_claude_settings(project_path: Path) -> Optional[dict]:
    """
    Read existing .claude/settings.json.

    Returns:
        Settings dict or None if file doesn't exist
    """
    path = get_claude_settings_path(project_path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[AGENT_CONFIG] read_claude_settings failed | path={path} error={e}")
    return None


def write_claude_settings(project_path: Path, settings: dict) -> Path:
    """
    Write .claude/settings.json.

    Creates .claude directory if needed.

    Args:
        project_path: Project directory
        settings: Settings dict

    Returns:
        Path to created file
    """
    claude_dir = get_claude_settings_dir(project_path)
    claude_dir.mkdir(parents=True, exist_ok=True)

    path = get_claude_settings_path(project_path)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    logger.info(f"[AGENT_CONFIG] write_claude_settings | path={path}")
    return path


def create_default_claude_settings(project_path: Path, settings: Optional[dict] = None) -> Path:
    """
    Create .claude/settings.json with default or custom settings.

    Args:
        project_path: Project directory
        settings: Optional custom settings (uses defaults if None)

    Returns:
        Path to created file
    """
    return write_claude_settings(project_path, settings or DEFAULT_CLAUDE_SETTINGS)


def update_claude_setting(project_path: Path, key: str, value: Any) -> dict:
    """
    Update a single setting in .claude/settings.json.

    Args:
        project_path: Project directory
        key: Setting key (supports dot notation for nested: "env.VAR")
        value: New value

    Returns:
        Updated settings dict
    """
    settings = read_claude_settings(project_path) or {}

    # Handle dot notation for nested keys
    keys = key.split(".")
    target = settings
    for k in keys[:-1]:
        target = target.setdefault(k, {})
    target[keys[-1]] = value

    write_claude_settings(project_path, settings)
    logger.info(f"[AGENT_CONFIG] update_claude_setting | key={key}")
    return settings


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES (run.cmd)
# ═══════════════════════════════════════════════════════════════════════════════

def build_env_lines(env_vars: dict[str, str]) -> str:
    """
    Build environment variable lines for run.cmd.

    Args:
        env_vars: Dict of VAR_NAME -> value

    Returns:
        String with set commands, one per line
    """
    lines = []
    for key, value in env_vars.items():
        # Escape special characters for cmd
        safe_value = str(value).replace("%", "%%")
        lines.append(f"set {key}={safe_value}")
    return "\n".join(lines)


def get_agent_env_vars(
    disable_autoupdate: bool = False,
    max_output_tokens: Optional[int] = None,
    bash_timeout_ms: Optional[int] = None,
    disable_telemetry: bool = False,
    custom_vars: Optional[dict[str, str]] = None
) -> dict[str, str]:
    """
    Build environment variables dict for agent.

    Args:
        disable_autoupdate: Disable Claude auto-update
        max_output_tokens: Max output tokens limit
        bash_timeout_ms: Default bash timeout in ms
        disable_telemetry: Disable telemetry
        custom_vars: Additional custom variables

    Returns:
        Dict of environment variables
    """
    env = {}

    if disable_autoupdate:
        env["DISABLE_AUTOUPDATER"] = "1"

    if max_output_tokens:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_output_tokens)

    if bash_timeout_ms:
        env["BASH_DEFAULT_TIMEOUT_MS"] = str(bash_timeout_ms)

    if disable_telemetry:
        env["DISABLE_TELEMETRY"] = "1"

    if custom_vars:
        env.update(custom_vars)

    return env


# ═══════════════════════════════════════════════════════════════════════════════
# FULL AGENT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Note: AgentConfigOptions is defined in registry.py as a Pydantic model
# Import it from there when needed


def apply_agent_config(
    project_path: Path,
    purpose: str,
    agent_id: str,
    port: int,
    options: Optional[Any] = None
) -> dict[str, Path]:
    """
    Apply full agent configuration to project.

    Creates all necessary config files based on options.

    Args:
        project_path: Project directory
        purpose: Agent purpose description
        agent_id: Agent ID
        port: Memory worker port
        options: AgentConfigOptions from registry.py (uses defaults if None)

    Returns:
        Dict of created file paths by type
    """
    created = {}

    # Handle None options - don't create configs if no options provided
    if options is None:
        return created

    # 1. CLAUDE.md (system prompt)
    if options.system_prompt:
        created["claude_md"] = write_claude_md(project_path, options.system_prompt)
    elif not get_claude_md_path(project_path).exists():
        # Create default only if doesn't exist
        created["claude_md"] = create_default_claude_md(
            project_path, purpose, agent_id, port
        )

    # 2. .mcp.json (MCP servers)
    if options.mcp_servers:
        created["mcp_json"] = write_mcp_json(project_path, {"mcpServers": options.mcp_servers})

    # 3. .claude/settings.json
    if options.claude_settings:
        created["claude_settings"] = write_claude_settings(project_path, options.claude_settings)

    logger.info(f"[AGENT_CONFIG] apply_agent_config | agent_id={agent_id} created={list(created.keys())}")
    return created


def read_agent_config(project_path: Path) -> dict:
    """
    Read all agent configuration from project.

    Args:
        project_path: Project directory

    Returns:
        Dict with all config data
    """
    return {
        "claude_md": read_claude_md(project_path),
        "mcp_json": read_mcp_json(project_path),
        "claude_settings": read_claude_settings(project_path),
        "has_claude_md": get_claude_md_path(project_path).exists(),
        "has_mcp_json": get_mcp_json_path(project_path).exists(),
        "has_claude_settings": get_claude_settings_path(project_path).exists()
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PER-AGENT CONFIG STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def get_agent_claude_md_path(agent_dir: Path) -> Path:
    """Get path to CLAUDE.md in agent directory."""
    return agent_dir / "CLAUDE.md"


def get_agent_mcp_json_path(agent_dir: Path) -> Path:
    """Get path to .mcp.json in agent directory."""
    return agent_dir / ".mcp.json"


def read_agent_local_config(agent_dir: Path) -> dict:
    """
    Read agent-local configuration files.

    Args:
        agent_dir: Agent directory (e.g., ~/.agents/1234-37758/)

    Returns:
        Dict with config data from agent directory
    """
    claude_md_path = get_agent_claude_md_path(agent_dir)
    mcp_json_path = get_agent_mcp_json_path(agent_dir)

    claude_md = None
    if claude_md_path.exists():
        try:
            claude_md = claude_md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[AGENT_CONFIG] read_agent_local_config claude_md failed | error={e}")

    mcp_json = None
    if mcp_json_path.exists():
        try:
            mcp_json = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[AGENT_CONFIG] read_agent_local_config mcp_json failed | error={e}")

    return {
        "claude_md": claude_md,
        "mcp_json": mcp_json,
        "has_claude_md": claude_md_path.exists(),
        "has_mcp_json": mcp_json_path.exists()
    }


def write_agent_local_claude_md(agent_dir: Path, content: str) -> Path:
    """
    Write CLAUDE.md to agent directory.

    Args:
        agent_dir: Agent directory
        content: System prompt content

    Returns:
        Path to created file
    """
    path = get_agent_claude_md_path(agent_dir)
    path.write_text(content, encoding="utf-8")
    logger.info(f"[AGENT_CONFIG] write_agent_local_claude_md | path={path} size={len(content)}")
    return path


def write_agent_local_mcp_json(agent_dir: Path, config: dict) -> Path:
    """
    Write .mcp.json to agent directory.

    Args:
        agent_dir: Agent directory
        config: MCP configuration dict

    Returns:
        Path to created file
    """
    path = get_agent_mcp_json_path(agent_dir)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    logger.info(f"[AGENT_CONFIG] write_agent_local_mcp_json | path={path} servers={list(config.get('mcpServers', {}).keys())}")
    return path


def sync_agent_config_to_project(agent_dir: Path, project_path: Path) -> dict:
    """
    Copy agent-local config files to project directory.

    This allows per-agent isolation: each agent has its own CLAUDE.md and .mcp.json
    stored in agent_dir, which gets copied to project_path on agent start.

    Args:
        agent_dir: Agent directory with config files
        project_path: Project directory to copy to

    Returns:
        Dict of synced files
    """
    synced = {}

    # Sync CLAUDE.md
    agent_claude_md = get_agent_claude_md_path(agent_dir)
    if agent_claude_md.exists():
        try:
            content = agent_claude_md.read_text(encoding="utf-8")
            project_claude_md = get_claude_md_path(project_path)
            project_claude_md.write_text(content, encoding="utf-8")
            synced["claude_md"] = project_claude_md
            logger.info(f"[AGENT_CONFIG] sync_agent_config_to_project | CLAUDE.md synced to {project_claude_md}")
        except Exception as e:
            logger.error(f"[AGENT_CONFIG] sync CLAUDE.md failed | error={e}")

    # Sync .mcp.json
    agent_mcp_json = get_agent_mcp_json_path(agent_dir)
    if agent_mcp_json.exists():
        try:
            content = agent_mcp_json.read_text(encoding="utf-8")
            project_mcp_json = get_mcp_json_path(project_path)
            project_mcp_json.write_text(content, encoding="utf-8")
            synced["mcp_json"] = project_mcp_json
            logger.info(f"[AGENT_CONFIG] sync_agent_config_to_project | .mcp.json synced to {project_mcp_json}")
        except Exception as e:
            logger.error(f"[AGENT_CONFIG] sync .mcp.json failed | error={e}")

    return synced
