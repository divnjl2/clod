from __future__ import annotations

import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import AppConfig, load_config, save_config
from .processes import (
    is_pid_running,
    kill_tree,
    pm2_delete,
    pm2_exists,
    spawn_browser,
    spawn_cmd_window,
    which,
)
from .registry import AgentRecord, iter_agents, load_agent, save_agent
from .tile import tile_two_in_cell
from .worker import pick_port, start_worker

app = typer.Typer(no_args_is_help=True)
console = Console()


def _agent_root(cfg: AppConfig) -> Path:
    p = Path(cfg.agent_root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_run_cmd(agent_dir: Path, title: str, port: int, data_dir: Path, project_path: Path) -> Path:
    run_cmd = agent_dir / "run.cmd"
    content = (
        "@echo off\n"
        "chcp 65001 >nul 2>&1\n"
        f"title {title}\n"
        f"set CLAUDE_MEM_WORKER_PORT={port}\n"
        f"set CLAUDE_MEM_DATA_DIR={data_dir}\n"
        f"cd /d \"{project_path}\"\n"
        "claude\n"
    )
    run_cmd.write_text(content, encoding="utf-8")
    return run_cmd


def _ensure_npm_path() -> None:
    """Добавляет npm global bin в PATH если отсутствует."""
    npm_bin = Path(os.getenv("APPDATA", "")) / "npm"
    if str(npm_bin) not in os.getenv("PATH", ""):
        os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")


def _silent_install_npm_package(package: str, cmd_name: str) -> bool:
    """Тихо устанавливает npm пакет если не установлен. Возвращает True если установлено."""
    if which(cmd_name):
        return True

    console.print(f"[cyan]Installing {cmd_name}...[/cyan]")
    try:
        result = subprocess.run(
            ["npm", "install", "-g", package],
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]{cmd_name} installed[/green]")
            return True
        else:
            console.print(f"[red]Failed to install {cmd_name}[/red]")
            return False
    except Exception:
        return False


def _ensure_all_dependencies(cfg: AppConfig) -> None:
    """
    Автоматическая проверка и установка всех зависимостей.
    Если всё ок — тихо скипается. Если чего-то нет — устанавливает.
    """
    # 1) Ensure npm bin in PATH
    _ensure_npm_path()

    # 2) Check node
    if not which("node"):
        raise RuntimeError(
            "Node.js not found. Please install from https://nodejs.org/"
        )

    # 3) Install pm2 if missing
    _silent_install_npm_package("pm2", "pm2")

    # 4) Install claude-code if missing
    if not _silent_install_npm_package("@anthropic-ai/claude-code", "claude"):
        raise RuntimeError(
            "claude not found and auto-install failed. "
            "Install manually: npm install -g @anthropic-ai/claude-code"
        )

    # 5) Install claude-mem plugin if missing
    _ensure_plugin_installed(cfg)


def _ensure_prereqs() -> None:
    """Legacy check - kept for compatibility."""
    if not which("claude"):
        raise RuntimeError(
            "claude not found in PATH. Install: npm install -g @anthropic-ai/claude-code "
            "and ensure global npm bin is in PATH (often %APPDATA%\\npm)."
        )


def _ensure_plugin_installed(cfg: AppConfig) -> None:
    """Копирует плагин claude-mem в ~/.claude/plugins если не установлен."""
    plugin_dir = Path.home() / ".claude" / "plugins" / "marketplaces" / "thedotmack"
    if plugin_dir.exists():
        return

    if not cfg.claude_mem_root:
        console.print("[yellow]Warning: claude_mem_root not set, skipping plugin install[/yellow]")
        return

    claude_mem_path = Path(cfg.claude_mem_root)
    source_plugin = claude_mem_path / "plugin"
    if not source_plugin.exists():
        console.print(f"[yellow]Warning: plugin folder not found at {source_plugin}[/yellow]")
        return

    console.print("[cyan]Installing claude-mem plugin...[/cyan]")
    try:
        # Create target directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Copy plugin files using shutil (cross-platform)
        for item in source_plugin.iterdir():
            dest = plugin_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        console.print("[green]Plugin installed successfully[/green]")
    except Exception as e:
        console.print(f"[yellow]Plugin install failed: {e}[/yellow]")


@app.command("config")
def config_set(
    claude_mem_root: Optional[str] = typer.Option(None, "--claude-mem-root"),
    worker_script: Optional[str] = typer.Option(None, "--worker-script"),
    agent_root: Optional[str] = typer.Option(None, "--agent-root"),
    browser: Optional[str] = typer.Option(None, "--browser"),
) -> None:
    """Сохранить/обновить конфиг."""
    cfg = load_config()
    data = cfg.model_dump()
    if claude_mem_root is not None:
        data["claude_mem_root"] = claude_mem_root
    if worker_script is not None:
        data["worker_script"] = worker_script
    if agent_root is not None:
        data["agent_root"] = agent_root
    if browser is not None:
        data["browser"] = browser

    save_config(AppConfig(**data))
    console.print("OK")


@app.command()
def config_show() -> None:
    """Показать конфиг."""
    console.print(load_config().model_dump_json(indent=2))


@app.command()
def new(
    purpose: str = typer.Option(..., "--purpose"),
    project: str = typer.Option(..., "--project"),
    agent_id: Optional[str] = typer.Option(None, "--id"),
    port: Optional[int] = typer.Option(None, "--port"),
    start_browser: bool = typer.Option(True, "--browser/--no-browser", help="Открыть viewer в браузере"),
) -> None:
    """Создать нового агента (worker+viewer+claude window) с изолированной памятью."""
    cfg = load_config()
    cfg.validate_ready()

    # Auto-check and install all dependencies (silent if ok)
    _ensure_all_dependencies(cfg)

    agent_root = _agent_root(cfg)
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

    project_path = Path(project).resolve()
    if not project_path.exists():
        raise FileNotFoundError(f"Project path not found: {project_path}")

    # 1) worker (pm2)
    start_worker(cfg, pm2_name=pm2_name, port=port, data_dir=agent_dir)

    # 2) viewer (если start_browser=True)
    viewer_pid = None
    if start_browser:
        url = f"http://localhost:{port}"
        viewer_pid = spawn_browser(url, cfg.browser, agent_id=agent_id, headless=True)

    # 3) claude cmd window (env MUST match worker)
    title = f"Agent {agent_id} @ {port} ({purpose})"
    run_cmd = _write_run_cmd(agent_dir, title=title, port=port, data_dir=agent_dir, project_path=project_path)
    cmd_pid = spawn_cmd_window(run_cmd, workdir=str(project_path))

    rec = AgentRecord(
        id=agent_id,
        purpose=purpose,
        project_path=str(project_path),
        port=port,
        pm2_name=pm2_name,
        cmd_pid=cmd_pid,
        viewer_pid=viewer_pid,
        use_browser=start_browser,
    )
    save_agent(agent_root, rec)
    console.print(f"Created agent: {agent_id} (port={port})")


@app.command()
def list() -> None:
    """Список агентов + статусы."""
    cfg = load_config()
    agent_root = _agent_root(cfg)
    agents = iter_agents(agent_root)

    table = Table(title="Claude Agents")
    table.add_column("id")
    table.add_column("purpose")
    table.add_column("mode")
    table.add_column("port", justify="right")
    table.add_column("pm2")
    table.add_column("cmd")
    table.add_column("viewer")
    table.add_column("project")

    for a in agents:
        pm2_state = "ONLINE" if pm2_exists(a.pm2_name) else "OFFLINE"
        cmd_state = "RUNNING" if is_pid_running(a.cmd_pid) else "STOPPED"
        view_state = "RUNNING" if is_pid_running(a.viewer_pid) else "UNKNOWN/STOPPED"
        browser_state = "With Browser" if a.use_browser else "Headless"
        table.add_row(a.id, a.purpose, browser_state, str(a.port), pm2_state, cmd_state, view_state, a.project_path)

    console.print(table)


@app.command("open-browser")
def open_browser(
    agent_id: str = typer.Argument(...),
) -> None:
    """Открыть viewer в браузере для существующего агента."""
    cfg = load_config()
    agent_root = _agent_root(cfg)
    a = load_agent(agent_root, agent_id)

    if not a.use_browser:
        console.print(f"[yellow]Agent {agent_id} работает без браузера (headless).[/yellow]")
        return

    url = f"http://localhost:{a.port}"
    viewer_pid = spawn_browser(url, cfg.browser, agent_id=a.id, headless=True)

    # Update agent record with new viewer PID
    updated = a.model_copy()
    updated.viewer_pid = viewer_pid
    save_agent(agent_root, updated)

    console.print(f"Opened browser for agent: {a.id} at {url}")


@app.command()
def stop(
    agent_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Удалить агент-директорию (память) после остановки"),
) -> None:
    """Остановить конкретного агента."""
    cfg = load_config()
    agent_root = _agent_root(cfg)
    a = load_agent(agent_root, agent_id)

    pm2_delete(a.pm2_name)

    if a.cmd_pid and is_pid_running(a.cmd_pid):
        kill_tree(a.cmd_pid)

    if a.viewer_pid and is_pid_running(a.viewer_pid):
        kill_tree(a.viewer_pid)

    if purge:
        shutil.rmtree(agent_root / agent_id, ignore_errors=True)

    console.print(f"Stopped agent: {agent_id}")


@app.command("stop-all")
def stop_all(
    purge: bool = typer.Option(False, "--purge", help="Удалить все агент-директории (память) после остановки"),
) -> None:
    """Остановить всех агентов."""
    cfg = load_config()
    agent_root = _agent_root(cfg)
    for a in iter_agents(agent_root):
        try:
            pm2_delete(a.pm2_name)
        except Exception:
            pass
        if a.cmd_pid and is_pid_running(a.cmd_pid):
            try:
                kill_tree(a.cmd_pid)
            except Exception:
                pass
        if a.viewer_pid and is_pid_running(a.viewer_pid):
            try:
                kill_tree(a.viewer_pid)
            except Exception:
                pass
        if purge:
            shutil.rmtree(agent_root / a.id, ignore_errors=True)

    console.print("Stopped all agents")


@app.command()
def open(
    agent_id: str = typer.Argument(...),
    reopen_viewer: bool = typer.Option(True, "--viewer/--no-viewer"),
    reopen_claude: bool = typer.Option(True, "--claude/--no-claude"),
) -> None:
    """Переоткрыть окна для существующего агента (если worker уже поднят)."""
    cfg = load_config()
    cfg.validate_ready()
    _ensure_prereqs()

    agent_root = _agent_root(cfg)
    a = load_agent(agent_root, agent_id)
    agent_dir = agent_root / agent_id

    updated = a.model_copy()

    if reopen_viewer and a.use_browser:
        url = f"http://localhost:{a.port}"
        updated.viewer_pid = spawn_browser(url, cfg.browser, agent_id=a.id, headless=True)
    elif reopen_viewer and not a.use_browser:
        console.print(f"[yellow]Agent {agent_id} is headless; viewer is not required.[/yellow]")

    if reopen_claude:
        title = f"Agent {a.id} @ {a.port} ({a.purpose})"
        run_cmd = agent_dir / "run.cmd"
        if not run_cmd.exists():
            run_cmd = _write_run_cmd(agent_dir, title=title, port=a.port, data_dir=agent_dir, project_path=Path(a.project_path))
        updated.cmd_pid = spawn_cmd_window(run_cmd, workdir=a.project_path)

    save_agent(agent_root, updated)
    console.print(f"Opened agent windows: {agent_id}")


@app.command()
def tile(
    count: int = typer.Option(4, "--count"),
) -> None:
    """Раскладка окон последних N агентов (2x2)."""
    import ctypes
    from ctypes import wintypes

    SPI_GETWORKAREA = 0x0030
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)

    work_x, work_y = rect.left, rect.top
    work_w, work_h = rect.right - rect.left, rect.bottom - rect.top

    cfg = load_config()
    agent_root = _agent_root(cfg)
    agents = iter_agents(agent_root)
    agents.sort(key=lambda a: a.created_at, reverse=True)
    agents = agents[:count]

    cols, rows = 2, 2
    cell_w, cell_h = work_w // cols, work_h // rows

    for i, a in enumerate(agents):
        row = i // cols
        col = i % cols
        if row >= rows:
            break
        x = work_x + col * cell_w
        y = work_y + row * cell_h
        tile_two_in_cell(a.cmd_pid, a.viewer_pid, x, y, cell_w, cell_h)

    console.print(f"Tiled {len(agents)} agents")


def _check_npm_path() -> bool:
    """Check if global npm bin is in PATH."""
    npm_bin = Path(os.getenv("APPDATA", "")) / "npm"
    return str(npm_bin) in os.getenv("PATH", "")


def _install_global_npm(package: str, name: str) -> bool:
    """Install a global npm package if not present."""
    if which(name):
        console.print(f"[green]✓[/green] {name} already installed")
        return True

    console.print(f"[cyan]Installing {package}...[/cyan]")
    try:
        result = subprocess.run(
            ["npm", "install", "-g", package],
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]✓[/green] {name} installed")
            return True
        else:
            console.print(f"[red]✗[/red] Failed to install {name}: {result.stderr}")
            return False
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to install {name}: {e}")
        return False


@app.command()
def bootstrap() -> None:
    """Установить/проверить все зависимости: node, pm2, claude, claude-mem plugin."""
    console.print("[bold]Claude Agent Manager Bootstrap[/bold]\n")

    # Check Node.js
    if which("node"):
        console.print("[green]✓[/green] Node.js installed")
    else:
        console.print("[red]✗[/red] Node.js not found. Please install from https://nodejs.org/")
        return

    # Check npm PATH
    if _check_npm_path():
        console.print("[green]✓[/green] npm global bin in PATH")
    else:
        npm_bin = Path(os.getenv("APPDATA", "")) / "npm"
        console.print(f"[yellow]![/yellow] npm global bin not in PATH. Add: {npm_bin}")

    # Install pm2
    _install_global_npm("pm2", "pm2")

    # Install claude-code
    _install_global_npm("@anthropic-ai/claude-code", "claude")

    # Install claude-mem plugin
    cfg = load_config()
    _ensure_plugin_installed(cfg)

    console.print("\n[bold green]Bootstrap complete![/bold green]")


@app.command()
def doctor() -> None:
    """Диагностика: проверить worker, db, plugin статус."""
    console.print("[bold]Claude Agent Manager Doctor[/bold]\n")

    cfg = load_config()

    # Check config
    console.print("[bold]Config:[/bold]")
    if cfg.claude_mem_root:
        console.print(f"  claude_mem_root: {cfg.claude_mem_root}")
    else:
        console.print("  [red]✗[/red] claude_mem_root not set")

    if cfg.worker_script:
        console.print(f"  worker_script: {cfg.worker_script}")
    else:
        console.print("  [red]✗[/red] worker_script not set")

    # Check prerequisites
    console.print("\n[bold]Prerequisites:[/bold]")
    for cmd in ["node", "npm", "pm2", "claude"]:
        path = which(cmd)
        if path:
            console.print(f"  [green]✓[/green] {cmd}: {path}")
        else:
            console.print(f"  [red]✗[/red] {cmd} not found")

    # Check plugin
    console.print("\n[bold]Plugin:[/bold]")
    plugin_dir = Path.home() / ".claude" / "plugins" / "marketplaces" / "thedotmack"
    if plugin_dir.exists():
        console.print(f"  [green]✓[/green] claude-mem plugin installed")
    else:
        console.print(f"  [red]✗[/red] claude-mem plugin not installed")

    # Check pm2 workers
    console.print("\n[bold]PM2 Workers:[/bold]")
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            import json
            processes = json.loads(result.stdout)
            agent_processes = [p for p in processes if p.get("name", "").startswith("agent-")]
            if agent_processes:
                for p in agent_processes:
                    status = p.get("pm2_env", {}).get("status", "unknown")
                    name = p.get("name", "unknown")
                    color = "green" if status == "online" else "red"
                    console.print(f"  [{color}]●[/{color}] {name}: {status}")
            else:
                console.print("  No agent workers running")
        else:
            console.print("  [yellow]![/yellow] Could not get pm2 status")
    except Exception as e:
        console.print(f"  [red]✗[/red] PM2 check failed: {e}")

    # Check database
    console.print("\n[bold]Database:[/bold]")
    db_path = Path.home() / ".claude-mem" / "claude-mem.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        console.print(f"  [green]✓[/green] {db_path} ({size_mb:.2f} MB)")
    else:
        console.print(f"  [yellow]![/yellow] Database not found (will be created on first use)")
