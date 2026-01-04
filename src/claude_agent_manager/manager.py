"""
Agent Manager - core functions for agent lifecycle management.

This module provides the business logic for creating, starting, stopping,
and managing agents. It is used by both CLI and GUI.
"""
from __future__ import annotations

import json
import logging
import os
import random
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from .config import AppConfig, load_config
from .processes import (
    is_pid_running,
    kill_tree,
    pm2_delete,
    pm2_exists,
    pm2_status,
    spawn_browser,
    spawn_cmd_window,
    which,
)
from .core import WorkspacePaths, atomic_write_json, create_workspace_paths, ensure_dir
from .core.locks import FileLock
from .core.models import AgentSpec, RunSpec
from .core.registry import Registry
from .core.runner_env import RunnerEnv, build_run_sandbox_env
from .registry import (
    AgentConfigOptions,
    AgentRecord,
    ProxyConfig,
    iter_agents,
    load_agent,
    save_agent,
    update_agent_autopilot,
)
from .agent_config import (
    apply_agent_config,
    build_default_mcp_servers,
    get_agent_env_vars,
    build_env_lines,
    sync_agent_config_to_project,
    write_agent_local_claude_md,
    write_agent_local_mcp_json,
)
from .worker import pick_port, start_worker

logger = logging.getLogger(__name__)


@dataclass
class AgentStatus:
    """Status of an agent."""
    id: str
    purpose: str
    port: int
    worker_online: bool
    cmd_running: bool
    viewer_running: bool
    use_browser: bool
    project_path: str
    proxy: Optional[dict] = None  # Proxy config as dict for serialization
    display_name: Optional[str] = None  # Custom display name
    autopilot_enabled: bool = False  # Full autonomy mode


def get_agent_root(cfg: Optional[AppConfig] = None) -> Path:
    """Get the agents directory within the workspace, creating if needed."""
    return get_workspace_paths(cfg).agents_dir


def get_workspace_paths(cfg: Optional[AppConfig] = None) -> WorkspacePaths:
    """Build workspace paths rooted at configured agent_root."""
    if cfg is None:
        cfg = load_config()
    paths = create_workspace_paths(Path(cfg.agent_root))
    return paths


def _write_run_cmd(
    agent_dir: Path,
    title: str,
    port: int,
    data_dir: Path,
    project_path: Path,
    proxy: Optional[ProxyConfig] = None,
    config: Optional[AgentConfigOptions] = None,
    runner_env: Optional[RunnerEnv] = None,
    workdir: Optional[Path] = None,
    autopilot: bool = False,
) -> Path:
    """Write the run.cmd script for an agent."""
    run_cmd = agent_dir / "run.cmd"

    # Build proxy env vars if enabled
    proxy_lines = ""
    if proxy and proxy.enabled:
        proxy_url = proxy.to_url()
        if proxy_url:
            proxy_lines = (
                f"set HTTP_PROXY={proxy_url}\n"
                f"set HTTPS_PROXY={proxy_url}\n"
                f"set ALL_PROXY={proxy_url}\n"
            )

    # Build config env vars
    config_lines = ""
    if config:
        env_vars = get_agent_env_vars(
            disable_autoupdate=config.disable_autoupdate,
            max_output_tokens=config.max_output_tokens,
            bash_timeout_ms=config.bash_timeout_ms,
            disable_telemetry=config.disable_telemetry,
            custom_vars=config.custom_env_vars
        )
        if env_vars:
            config_lines = build_env_lines(env_vars) + "\n"

    # Escape special chars in title for cmd
    safe_title = title.replace("|", "^|").replace("&", "^&")

    env_lines = ""
    merged_env = {}
    if runner_env:
        for key in (
            "HOME",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "AGENT_RUN_DIR",
            "AGENT_HOME",
        ):
            if key in runner_env.env:
                merged_env[key] = runner_env.env[key]
    if merged_env:
        env_lines = "".join(f'set "{k}={v}"\n' for k, v in merged_env.items())

    # Build claude command with optional autopilot flag
    claude_cmd = "claude --dangerously-skip-permissions" if autopilot else "claude"

    content = (
        "@echo off\n"
        "chcp 65001 >nul 2>&1\n"
        f"title {safe_title}\n"
        f"{env_lines}"
        f"set CLAUDE_MEM_WORKER_PORT={port}\n"
        f"set CLAUDE_MEM_DATA_DIR={data_dir}\n"
        f"{proxy_lines}"
        f"{config_lines}"
        f"cd /d \"{workdir if workdir else project_path}\"\n"
        f"{claude_cmd}\n"
    )
    run_cmd.write_text(content, encoding="utf-8")
    return run_cmd


def _ensure_npm_path() -> None:
    """Add npm global bin to PATH if missing."""
    npm_bin = Path(os.getenv("APPDATA", "")) / "npm"
    if str(npm_bin) not in os.getenv("PATH", ""):
        os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")


def _registry(cfg: AppConfig) -> Registry:
    paths = get_workspace_paths(cfg)
    reg = Registry(paths.registry_path)
    reg.init()
    return reg


def _new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run-{ts}-{random.randint(1000, 9999)}"


def _record_pids(run_dir: Path, pids: dict[str, int]) -> None:
    atomic_write_json(run_dir / "pids.json", pids)


def ensure_claude_mem_worker() -> bool:
    """
    Ensure claude-mem worker is running for memory UI access.

    Checks if claude-mem-worker PM2 process is running and starts it if not.
    The worker provides the web UI at http://localhost:37777 (or dynamic port).

    Returns:
        True if worker is running (or was started), False if failed
    """
    try:
        # Check if already running
        if pm2_exists("claude-mem-worker"):
            logger.debug("[CLAUDE-MEM] worker already running")
            return True

        # Find the worker script
        claude_mem_paths = [
            Path.home() / "Desktop" / "claude-mem" / "plugin" / "scripts" / "worker-service.cjs",
            Path.home() / ".claude" / "plugins" / "marketplaces" / "thedotmack" / "scripts" / "worker-service.cjs",
        ]

        worker_script = None
        for p in claude_mem_paths:
            if p.exists():
                worker_script = p
                break

        if not worker_script:
            logger.warning("[CLAUDE-MEM] worker script not found, skipping")
            return False

        # Start the worker via PM2
        import subprocess
        result = subprocess.run(
            ["pm2", "start", str(worker_script), "--name", "claude-mem-worker"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            logger.info(f"[CLAUDE-MEM] worker started | script={worker_script}")
            return True
        else:
            logger.error(f"[CLAUDE-MEM] failed to start worker | error={result.stderr}")
            return False

    except Exception as e:
        logger.error(f"[CLAUDE-MEM] error starting worker | error={e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

def create_agent(
    purpose: str,
    project_path: str,
    agent_id: Optional[str] = None,
    port: Optional[int] = None,
    use_browser: bool = False,
    proxy: Optional[ProxyConfig] = None,
    config: Optional[AgentConfigOptions] = None,
    cfg: Optional[AppConfig] = None,
) -> AgentRecord:
    """
    Create a new agent with worker, viewer (optional), and claude window.

    Args:
        purpose: Description of the agent's purpose
        project_path: Path to the project directory
        agent_id: Optional custom agent ID
        port: Optional custom port (will auto-pick if not provided)
        use_browser: Whether to open browser viewer
        proxy: Optional proxy configuration
        config: Optional Claude Code configuration options
        cfg: Optional config (will load default if not provided)

    Returns:
        The created AgentRecord

    Raises:
        FileNotFoundError: If project path doesn't exist
        RuntimeError: If agent already exists or pm2 fails
    """
    if cfg is None:
        cfg = load_config()
        cfg.validate_ready()

    _ensure_npm_path()

    paths = get_workspace_paths(cfg)
    registry = _registry(cfg)

    with FileLock(paths.manager_app_lock, stale_ttl_sec=30, timeout_sec=0.5):
        agent_root = paths.agents_dir
        used_ports = {a.port for a in iter_agents(agent_root)}
        try:
            used_ports |= registry.get_allocated_ports()
        except Exception:
            # Fallback if registry fetch fails
            pass

        if port is None:
            port = pick_port(cfg, used_ports)

        if agent_id is None:
            agent_id = f"{random.randint(1000, 9999)}-{port}"

        agent_dir = paths.agent_dir(agent_id)
        ensure_dir(agent_dir)

        pm2_name = f"agent-{agent_id}"
        if pm2_exists(pm2_name):
            raise RuntimeError(f"Agent already exists in pm2: {pm2_name}")

        project = Path(project_path).resolve()
        if not project.exists():
            raise FileNotFoundError(f"Project path not found: {project}")

        # Default proxy config if not provided
        if proxy is None:
            proxy = ProxyConfig()

        # Default config options if not provided
        if config is None:
            config = AgentConfigOptions()

        logger.info(f"[AGENT] create_agent | id={agent_id} port={port} purpose={purpose} proxy={proxy.enabled}")

        with FileLock(paths.agent_lock_path(agent_id), stale_ttl_sec=60, timeout_sec=2):
            try:
                registry.allocate_port(
                    name=f"agent:{agent_id}:port",
                    port=port,
                    run_id=None,
                    allocated_at_iso=datetime.now(timezone.utc).isoformat(),
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeError(f"Port {port} already allocated") from exc

            registry.upsert_agent(AgentSpec(agent_id=agent_id, name=purpose, role="agent"))

            if config.system_prompt:
                write_agent_local_claude_md(agent_dir, config.system_prompt)

            mcp_servers = config.mcp_servers
            if not mcp_servers:
                mcp_servers = build_default_mcp_servers(
                    port=port,
                    data_dir=agent_dir,
                    claude_mem_root=cfg.claude_mem_root
                )
            write_agent_local_mcp_json(agent_dir, {"mcpServers": mcp_servers})

            sync_agent_config_to_project(agent_dir, project)

            rec = AgentRecord(
                id=agent_id,
                purpose=purpose,
                project_path=str(project),
                port=port,
                pm2_name=pm2_name,
                cmd_pid=None,
                viewer_pid=None,
                use_browser=use_browser,
                proxy=proxy,
                config=config,
                active_run_id=None,
            )
            save_agent(agent_root, rec)

        logger.info(f"[AGENT] created | id={agent_id} port={port}")
    # Start initial run outside the manager lock to avoid holding it during process startup
    return start_agent(agent_id, cfg=cfg, skip_cmd=False)


def start_agent(agent_id: str, cfg: Optional[AppConfig] = None, skip_cmd: bool = False, force_viewer: Optional[bool] = None) -> AgentRecord:
    """
    Start an existing agent (restart worker, open windows).

    Args:
        agent_id: The agent ID to start
        cfg: Optional config
        skip_cmd: If True, don't spawn cmd window (for embedded terminal)

    Returns:
        Updated AgentRecord
    """
    if cfg is None:
        cfg = load_config()

    paths = get_workspace_paths(cfg)
    registry = _registry(cfg)
    agent_root = paths.agents_dir
    agent = load_agent(agent_root, agent_id)
    agent_dir = paths.agent_dir(agent_id)

    logger.info(f"[AGENT] start_agent | id={agent_id} skip_cmd={skip_cmd}")

    ensure_claude_mem_worker()

    with FileLock(paths.manager_app_lock, stale_ttl_sec=30, timeout_sec=0.5):
        run_id = _new_run_id()
        run_dir = paths.run_dir(agent_id, run_id)
        run_state_dir = paths.run_state_dir(agent_id, run_id)
        run_logs_dir = paths.run_logs_dir(agent_id, run_id)
        run_artifacts_dir = paths.run_artifacts_dir(agent_id, run_id)
        run_worktree_dir = paths.run_worktree_dir(agent_id, run_id)
        ensure_dir(run_dir)
        ensure_dir(run_state_dir)
        ensure_dir(run_logs_dir)
        ensure_dir(run_artifacts_dir)
        ensure_dir(run_worktree_dir)

        runner_env = build_run_sandbox_env(run_dir)
        heartbeat_path = run_state_dir / "heartbeat.json"
        atomic_write_json(
            heartbeat_path,
            {"agent_id": agent_id, "run_id": run_id, "ts": datetime.now(timezone.utc).isoformat()},
        )

        run_spec = RunSpec(
            run_id=run_id,
            agent_id=agent_id,
            status="starting",
            run_dir=run_dir,
            worktree_dir=Path(agent.project_path),
        )
        registry.create_run(run_spec)

        with FileLock(paths.agent_lock_path(agent_id), stale_ttl_sec=60, timeout_sec=2), FileLock(
            paths.run_lock_path(agent_id, run_id), stale_ttl_sec=60, timeout_sec=2
        ):
            project_path = Path(agent.project_path)
            synced = sync_agent_config_to_project(agent_dir, project_path)
            if synced:
                logger.info(f"[AGENT] start_agent | synced config files: {list(synced.keys())}")

            if not pm2_exists(agent.pm2_name):
                start_worker(cfg, pm2_name=agent.pm2_name, port=agent.port, data_dir=agent_dir, base_env=runner_env.env)

            viewer_pid = agent.viewer_pid
            open_viewer = agent.use_browser if force_viewer is None else force_viewer
            if open_viewer and not is_pid_running(viewer_pid):
                url = f"http://localhost:{agent.port}"
                viewer_pid = spawn_browser(
                    url,
                    cfg.browser,
                    agent_id=agent.id,
                    headless=True,
                    profiles_root=paths.agent_dir(agent_id) / "browser-profiles",
                )
                if viewer_pid:
                    registry.attach_pid(run_id, "viewer", viewer_pid)

            cmd_pid = agent.cmd_pid
            if not skip_cmd and not is_pid_running(cmd_pid):
                title = f"{agent.purpose} | :{agent.port}"
                run_cmd = _write_run_cmd(
                    agent_dir,
                    title=title,
                    port=agent.port,
                    data_dir=agent_dir,
                    project_path=project_path,
                    proxy=agent.proxy,
                    config=agent.config,
                    runner_env=runner_env,
                    workdir=project_path,
                    autopilot=agent.autopilot_enabled,
                )
                cmd_pid = spawn_cmd_window(run_cmd, workdir=str(project_path), env=runner_env.env)
                registry.attach_pid(run_id, "cmd", cmd_pid)

        updated = agent.model_copy()
        updated.cmd_pid = cmd_pid
        updated.viewer_pid = viewer_pid
        updated.active_run_id = run_id
        save_agent(agent_root, updated)

        _record_pids(run_dir, {"cmd": cmd_pid or 0, "viewer": viewer_pid or 0})
        registry.set_run_status(run_id, "running")

    return updated


def stop_agent(agent_id: str, purge: bool = False, cfg: Optional[AppConfig] = None) -> None:
    """
    Stop an agent (kill worker, close windows).

    Args:
        agent_id: The agent ID to stop
        purge: If True, delete agent directory (memory) after stopping
        cfg: Optional config
    """
    if cfg is None:
        cfg = load_config()

    paths = get_workspace_paths(cfg)
    registry = _registry(cfg)
    agent_root = paths.agents_dir
    agent = load_agent(agent_root, agent_id)

    logger.info(f"[AGENT] stop_agent | id={agent_id} purge={purge}")

    with FileLock(paths.manager_app_lock, stale_ttl_sec=30, timeout_sec=0.5):
        with FileLock(paths.agent_lock_path(agent_id), stale_ttl_sec=60, timeout_sec=2):
            pm2_delete(agent.pm2_name)

            if agent.cmd_pid and is_pid_running(agent.cmd_pid):
                kill_tree(agent.cmd_pid)

            if agent.viewer_pid and is_pid_running(agent.viewer_pid):
                kill_tree(agent.viewer_pid)

            if agent.active_run_id:
                registry.set_run_status(agent.active_run_id, "stopped")

            updated = agent.model_copy()
            updated.active_run_id = None
            save_agent(agent_root, updated)

            if purge:
                shutil.rmtree(agent_root / agent_id, ignore_errors=True)
                try:
                    registry.release_port(f"agent:{agent_id}:port")
                except Exception:
                    pass
                logger.info(f"[AGENT] purged | id={agent_id}")


def delete_agent(agent_id: str, cfg: Optional[AppConfig] = None) -> None:
    """Delete an agent completely (stop + purge)."""
    stop_agent(agent_id, purge=True, cfg=cfg)


def open_viewer(agent_id: str, cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Open browser viewer for an agent.

    Opens browser regardless of use_browser setting - this is an explicit user action.
    The use_browser flag only controls auto-open on agent start.

    Args:
        agent_id: The agent ID
        cfg: Optional config

    Returns:
        Updated AgentRecord with new viewer_pid
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    url = f"http://localhost:{agent.port}"
    # Open in visible mode (not headless) since user explicitly requested viewer
    viewer_pid = spawn_browser(url, cfg.browser, agent_id=agent.id, headless=False)

    updated = agent.model_copy()
    updated.viewer_pid = viewer_pid
    save_agent(agent_root, updated)

    logger.info(f"[AGENT] open_viewer | id={agent_id} url={url}")
    return updated


def close_viewer(agent_id: str, cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Close browser viewer for an agent (without stopping worker).

    Args:
        agent_id: The agent ID
        cfg: Optional config

    Returns:
        Updated AgentRecord with viewer_pid=None
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    if agent.viewer_pid and is_pid_running(agent.viewer_pid):
        kill_tree(agent.viewer_pid)
        logger.info(f"[AGENT] close_viewer | id={agent_id}")

    updated = agent.model_copy()
    updated.viewer_pid = None
    save_agent(agent_root, updated)

    return updated


def update_proxy(agent_id: str, proxy: ProxyConfig, cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Update proxy settings for an agent.

    The new settings will apply on next agent restart.

    Args:
        agent_id: The agent ID
        proxy: New proxy configuration
        cfg: Optional config

    Returns:
        Updated AgentRecord
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    updated = agent.model_copy()
    updated.proxy = proxy
    save_agent(agent_root, updated)

    logger.info(f"[AGENT] update_proxy | id={agent_id} enabled={proxy.enabled} type={proxy.type}")
    return updated


def update_display_name(agent_id: str, display_name: Optional[str], cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Update display name for an agent.

    Args:
        agent_id: The agent ID
        display_name: New display name (None to reset to purpose)
        cfg: Optional config

    Returns:
        Updated AgentRecord
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    updated = agent.model_copy()
    updated.display_name = display_name if display_name else None
    save_agent(agent_root, updated)

    logger.info(f"[AGENT] update_display_name | id={agent_id} display_name={display_name}")
    return updated


def update_autopilot(agent_id: str, enabled: bool, cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Update autopilot mode for an agent.

    When autopilot is enabled, the agent gets full autonomy - all tools
    are allowed without permission prompts. This is equivalent to running
    Claude Code with --dangerously-skip-permissions flag.

    IMPORTANT: Changes take effect on next agent restart. The settings are
    written to .claude/settings.json immediately, but Claude Code only
    reads this file on startup.

    Args:
        agent_id: The agent ID
        enabled: Whether to enable autopilot mode
        cfg: Optional config

    Returns:
        Updated AgentRecord
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)

    # Use registry function to update and sync settings
    updated = update_agent_autopilot(agent_root, agent_id, enabled)

    logger.info(f"[AGENT] update_autopilot | id={agent_id} enabled={enabled}")
    return updated


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS & LISTING
# ═══════════════════════════════════════════════════════════════════════════════

def get_status(agent_id: str, cfg: Optional[AppConfig] = None) -> AgentStatus:
    """Get status of a specific agent."""
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    worker_online = pm2_exists(agent.pm2_name)
    pm2_info = pm2_status(agent.pm2_name)
    if pm2_info:
        worker_online = pm2_info.get("status") == "online"

    return AgentStatus(
        id=agent.id,
        purpose=agent.purpose,
        port=agent.port,
        worker_online=worker_online,
        cmd_running=is_pid_running(agent.cmd_pid),
        viewer_running=is_pid_running(agent.viewer_pid),
        use_browser=agent.use_browser,
        project_path=agent.project_path,
        display_name=agent.display_name,
        autopilot_enabled=agent.autopilot_enabled,
    )


def list_agents(cfg: Optional[AppConfig] = None) -> List[AgentStatus]:
    """List all agents with their status."""
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agents = iter_agents(agent_root)

    result = []
    for agent in agents:
        worker_online = False
        pm2_info = pm2_status(agent.pm2_name)
        if pm2_info:
            worker_online = pm2_info.get("status") == "online"

        result.append(AgentStatus(
            id=agent.id,
            purpose=agent.purpose,
            port=agent.port,
            worker_online=worker_online,
            cmd_running=is_pid_running(agent.cmd_pid),
            viewer_running=is_pid_running(agent.viewer_pid),
            use_browser=agent.use_browser,
            project_path=agent.project_path,
            proxy=agent.proxy.model_dump() if agent.proxy else None,
            display_name=agent.display_name,
            autopilot_enabled=agent.autopilot_enabled,
        ))

    return result


def stop_all_agents(purge: bool = False, cfg: Optional[AppConfig] = None) -> int:
    """
    Stop all agents.

    Returns:
        Number of agents stopped
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agents = iter_agents(agent_root)
    count = 0

    for agent in agents:
        try:
            stop_agent(agent.id, purge=purge, cfg=cfg)
            count += 1
        except Exception as e:
            logger.error(f"[AGENT] stop_all failed for {agent.id}: {e}")

    return count
