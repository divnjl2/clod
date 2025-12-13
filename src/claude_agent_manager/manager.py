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
from dataclasses import dataclass
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
from .registry import AgentRecord, ProxyConfig, iter_agents, load_agent, save_agent
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


def get_agent_root(cfg: Optional[AppConfig] = None) -> Path:
    """Get the agent root directory, creating if needed."""
    if cfg is None:
        cfg = load_config()
    p = Path(cfg.agent_root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_run_cmd(
    agent_dir: Path,
    title: str,
    port: int,
    data_dir: Path,
    project_path: Path,
    proxy: Optional[ProxyConfig] = None
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

    content = (
        "@echo off\n"
        "chcp 65001 >nul 2>&1\n"
        f"title {title}\n"
        f"set CLAUDE_MEM_WORKER_PORT={port}\n"
        f"set CLAUDE_MEM_DATA_DIR={data_dir}\n"
        f"{proxy_lines}"
        f"cd /d \"{project_path}\"\n"
        "claude\n"
    )
    run_cmd.write_text(content, encoding="utf-8")
    return run_cmd


def _ensure_npm_path() -> None:
    """Add npm global bin to PATH if missing."""
    npm_bin = Path(os.getenv("APPDATA", "")) / "npm"
    if str(npm_bin) not in os.getenv("PATH", ""):
        os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")


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

    agent_root = get_agent_root(cfg)
    used_ports = {a.port for a in iter_agents(agent_root)}

    if port is None:
        port = pick_port(cfg, used_ports)

    if agent_id is None:
        agent_id = f"{random.randint(1000, 9999)}-{port}"

    agent_dir = agent_root / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    pm2_name = f"agent-{agent_id}"
    if pm2_exists(pm2_name):
        raise RuntimeError(f"Agent already exists in pm2: {pm2_name}")

    project = Path(project_path).resolve()
    if not project.exists():
        raise FileNotFoundError(f"Project path not found: {project}")

    # Default proxy config if not provided
    if proxy is None:
        proxy = ProxyConfig()

    logger.info(f"[AGENT] create_agent | id={agent_id} port={port} purpose={purpose} proxy={proxy.enabled}")

    # 1) Start worker (pm2)
    start_worker(cfg, pm2_name=pm2_name, port=port, data_dir=agent_dir)

    # 2) Start viewer (if use_browser=True)
    viewer_pid = None
    if use_browser:
        url = f"http://localhost:{port}"
        viewer_pid = spawn_browser(url, cfg.browser, agent_id=agent_id, headless=True)

    # 3) Start claude cmd window
    title = f"{purpose} | :{port}"
    run_cmd = _write_run_cmd(agent_dir, title=title, port=port, data_dir=agent_dir, project_path=project, proxy=proxy)
    cmd_pid = spawn_cmd_window(run_cmd, workdir=str(project))

    # Save agent record
    rec = AgentRecord(
        id=agent_id,
        purpose=purpose,
        project_path=str(project),
        port=port,
        pm2_name=pm2_name,
        cmd_pid=cmd_pid,
        viewer_pid=viewer_pid,
        use_browser=use_browser,
        proxy=proxy,
    )
    save_agent(agent_root, rec)

    logger.info(f"[AGENT] created | id={agent_id} port={port}")
    return rec


def start_agent(agent_id: str, cfg: Optional[AppConfig] = None) -> AgentRecord:
    """
    Start an existing agent (restart worker, open windows).

    Args:
        agent_id: The agent ID to start
        cfg: Optional config

    Returns:
        Updated AgentRecord
    """
    if cfg is None:
        cfg = load_config()

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)
    agent_dir = agent_root / agent_id

    logger.info(f"[AGENT] start_agent | id={agent_id}")

    # Ensure worker is running
    if not pm2_exists(agent.pm2_name):
        start_worker(cfg, pm2_name=agent.pm2_name, port=agent.port, data_dir=agent_dir)

    # Open viewer if needed
    viewer_pid = agent.viewer_pid
    if agent.use_browser and not is_pid_running(viewer_pid):
        url = f"http://localhost:{agent.port}"
        viewer_pid = spawn_browser(url, cfg.browser, agent_id=agent.id, headless=True)

    # Open claude window if needed
    cmd_pid = agent.cmd_pid
    if not is_pid_running(cmd_pid):
        title = f"{agent.purpose} | :{agent.port}"
        # Always regenerate run.cmd to apply latest proxy settings
        run_cmd = _write_run_cmd(
            agent_dir, title=title, port=agent.port,
            data_dir=agent_dir, project_path=Path(agent.project_path),
            proxy=agent.proxy
        )
        cmd_pid = spawn_cmd_window(run_cmd, workdir=agent.project_path)

    # Update record
    updated = agent.model_copy()
    updated.cmd_pid = cmd_pid
    updated.viewer_pid = viewer_pid
    save_agent(agent_root, updated)

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

    agent_root = get_agent_root(cfg)
    agent = load_agent(agent_root, agent_id)

    logger.info(f"[AGENT] stop_agent | id={agent_id} purge={purge}")

    # Stop pm2 worker
    pm2_delete(agent.pm2_name)

    # Kill cmd window
    if agent.cmd_pid and is_pid_running(agent.cmd_pid):
        kill_tree(agent.cmd_pid)

    # Kill viewer
    if agent.viewer_pid and is_pid_running(agent.viewer_pid):
        kill_tree(agent.viewer_pid)

    # Purge if requested
    if purge:
        shutil.rmtree(agent_root / agent_id, ignore_errors=True)
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
