from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Force UTF-8 encoding on Windows console to support Cyrillic
if sys.platform == "win32":
    try:
        # Set console code page to UTF-8
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
        # Reconfigure stdout/stderr to use UTF-8
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # Silently ignore if it fails

from rich.table import Table

from . import manager
from .config import AppConfig, load_config, save_config
from .core.paths import create_workspace_paths
from .updater import check_updates_background, print_update_notification, do_update, do_update_from_local
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

# Import/Export CLI
from .sharing_cli import preset_app, export_app, import_app, share_command

# Memory tools CLI
from .memory_tools import create_memory_app

# Crew CLI (native clod agents - no external API!)
from .crew import create_crew_app

# Subagents commands
from .subagents import create_subagents_commands

app = typer.Typer(no_args_is_help=True)

# Подключаем подприложения
app.add_typer(preset_app, name="preset")
app.add_typer(export_app, name="export")
app.add_typer(import_app, name="import")
app.add_typer(create_memory_app(), name="memory", help="Memory inspection tools")

# Crew commands (native agents, no API)
app.add_typer(create_crew_app(), name="crew", help="Multi-agent crew (no external API)")

# Subagent commands
enable_cmd, disable_cmd = create_subagents_commands()
app.command("enable-subagents")(enable_cmd)
app.command("disable-subagents")(disable_cmd)

# Команда share как отдельная
app.command("share")(share_command)

console = Console()

# Фоновая проверка обновлений при старте (не блокирует)
_update_available: Optional[str] = None

def _on_update_found(version: str) -> None:
    global _update_available
    _update_available = version

def _show_update_on_exit() -> None:
    """Показать уведомление об обновлении при выходе."""
    if _update_available:
        print_update_notification(_update_available)

# Запускаем проверку в фоне
check_updates_background(callback=_on_update_found)

# Показываем уведомление при выходе
import atexit
atexit.register(_show_update_on_exit)


def _dpi_awareness() -> None:
    """
    Включает DPI awareness для текущего процесса на Windows.
    Сначала пытается использовать Per-Monitor V2, если не получилось — откатывается на SetProcessDPIAware.
    Тихо игнорирует ошибки на не-Windows.
    """
    try:
        import ctypes
        # Per-Monitor V2 (Windows 10 1703+)
        awareness = ctypes.c_int()
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE_V2
    except (AttributeError, OSError):
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass  # Not Windows or old version


def _agent_root(cfg: AppConfig) -> Path:
    paths = create_workspace_paths(Path(cfg.agent_root))
    return paths.agents_dir


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
    enable_subagents: bool = typer.Option(False, "--subagents", "-s", help="Включить создание субагентов"),
    max_subagents: int = typer.Option(5, "--max-subagents", help="Макс. кол-во субагентов"),
) -> None:
    """Создать нового агента (worker+viewer+claude window) с изолированной памятью."""
    cfg = load_config()
    cfg.validate_ready()

    # Auto-check and install all dependencies (silent if ok)
    _ensure_all_dependencies(cfg)

    rec = manager.create_agent(
        purpose=purpose,
        project_path=project,
        agent_id=agent_id,
        port=port,
        use_browser=start_browser,
        cfg=cfg,
    )
    console.print(f"Created agent: {rec.id} (port={rec.port})")

    # Включаем субагентов если запрошено
    if enable_subagents:
        from .subagents import enable_subagents as do_enable_subagents
        do_enable_subagents(rec.id, max_subagents)
        console.print(f"[cyan]Sub-agents enabled (max: {max_subagents})[/cyan]")


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
    profile_root = _agent_root(cfg) / agent_id / "browser-profiles"
    viewer_pid = spawn_browser(url, cfg.browser, agent_id=a.id, headless=True, profiles_root=profile_root)

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
    manager.stop_agent(agent_id, purge=purge, cfg=cfg)
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
            manager.stop_agent(a.id, purge=purge, cfg=cfg)
        except Exception:
            continue

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

    manager.start_agent(agent_id, cfg=cfg, skip_cmd=not reopen_claude, force_viewer=reopen_viewer)
    console.print(f"Opened agent windows: {agent_id}")


@app.command()
def tile(
    count: int = typer.Option(4, "--count"),
) -> None:
    """Раскладка окон последних N агентов (2x2)."""
    _dpi_awareness()

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


@app.command()
def update(
    force: bool = typer.Option(False, "--force", "-f", help="Принудительное обновление"),
    local: Optional[str] = typer.Option(None, "--local", "-l", help="Установить из локальной директории"),
) -> None:
    """Проверить и установить обновления."""
    if local:
        do_update_from_local(local)
    else:
        do_update(force=force)


@app.command("check-update")
def check_update() -> None:
    """Проверить наличие обновлений (без установки)."""
    from .updater import check_for_updates, get_current_version
    
    console.print(f"[dim]Текущая версия: {get_current_version()}[/dim]")
    console.print("[cyan]Проверяю...[/cyan]")
    
    new_version = check_for_updates(silent=False)
    if new_version:
        print_update_notification(new_version)
    else:
        console.print("[green]✓[/green] Установлена последняя версия")


@app.command("memory-doctor")
def memory_doctor(
    agent_id: Optional[str] = typer.Argument(None, help="ID агента (все если не указан)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный вывод"),
) -> None:
    """Диагностика изоляции памяти агентов."""
    from .memory_diagnostics import (
        diagnose_agent_memory,
        diagnose_all_agents,
        print_diagnostics_report,
        print_agent_detail,
    )
    
    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agents = [a.model_dump() for a in iter_agents(agent_root)]

    if not agents:
        console.print("[yellow]No agents found[/yellow]")
        return

    if agent_id:
        # Диагностика одного агента
        agent = next((a for a in agents if a["id"] == agent_id), None)
        if not agent:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
            return

        diag = diagnose_agent_memory(
            agent_id=agent["id"],
            port=agent["port"],
            agent_dir=agent_root / agent["id"],
            project_path=Path(agent["project_path"]),
            pm2_name=agent.get("pm2_name", f"agent-{agent_id}"),
            all_agents=agents
        )
        print_agent_detail(diag)
    else:
        # Диагностика всех агентов
        console.print(f"[bold]Diagnosing {len(agents)} agents...[/bold]\n")
        diagnostics = diagnose_all_agents(agent_root, agents)
        print_diagnostics_report(diagnostics)

        if verbose:
            console.print("\n[bold]Detailed Reports:[/bold]")
            for agent_id, diag in diagnostics.items():
                console.print()
                print_agent_detail(diag)


@app.command("memory-verify")
def memory_verify() -> None:
    """Live-проверка изоляции памяти между агентами."""
    from .memory_diagnostics import verify_isolation_live

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agents = [a.model_dump() for a in iter_agents(agent_root)]

    if not agents:
        console.print("[yellow]No agents found[/yellow]")
        return

    verify_isolation_live(agents, agent_root)


@app.command("claude-mem-setup")
def claude_mem_setup(
    start_worker: bool = typer.Option(True, "--start/--no-start", help="Запустить worker"),
) -> None:
    """Настройка и запуск claude-mem (автоустановка Bun + worker)."""
    from .claude_mem_setup import (
        diagnose_claude_mem, install_bun, start_worker as do_start_worker,
        is_worker_running, get_worker_port,
    )
    console.print("[bold]Claude-mem Setup[/bold]\n")
    diag = diagnose_claude_mem()
    if not diag["plugin_installed"]:
        console.print("[red]Plugin not installed. Run: /plugin install claude-mem[/red]")
        raise typer.Exit(1)
    console.print("[green]✓[/green] Plugin installed")
    if not diag["bun_installed"]:
        console.print("[yellow]○[/yellow] Installing Bun...")
        if not install_bun(silent=False):
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] Bun installed")
    if start_worker and not is_worker_running():
        console.print("[yellow]○[/yellow] Starting worker...")
        if not do_start_worker(silent=False):
            raise typer.Exit(1)
    console.print(f"[green]✓[/green] Worker running on port {get_worker_port()}")
    console.print("[bold green]Setup complete![/bold green]")


@app.command("claude-mem-test")
def claude_mem_test(no_cleanup: bool = typer.Option(False, "--no-cleanup")) -> None:
    """Синтетический тест claude-mem."""
    from .claude_mem_test import run_synthetic_test, run_and_cleanup
    console.print("[bold]Claude-mem Synthetic Test[/bold]")
    results = run_synthetic_test(verbose=True) if no_cleanup else run_and_cleanup(verbose=True)
    if results["success"]:
        console.print("[bold green]TEST PASSED[/bold green]")
    else:
        console.print("[bold red]TEST FAILED[/bold red]")
        raise typer.Exit(1)


@app.command("claude-mem-status")
def claude_mem_status() -> None:
    """Статус claude-mem системы."""
    from .claude_mem_setup import diagnose_claude_mem, get_worker_stats
    diag = diagnose_claude_mem()
    console.print("[bold]Claude-mem Status[/bold]")
    ok = lambda x: "[green]✓[/green]" if x else "[red]✗[/red]"
    console.print(f"{ok(diag['plugin_installed'])} Plugin | {ok(diag['bun_installed'])} Bun | {ok(diag['worker_running'])} Worker (:{diag['worker_port']})")
    if diag["worker_running"]:
        stats = get_worker_stats()
        if stats and "database" in stats:
            db = stats["database"]
            console.print(f"Observations: {db.get('observations', 0)} | Sessions: {db.get('sessions', 0)} | DB: {db.get('size', 0)//1024}KB")
    health = "[green]HEALTHY[/green]" if diag["healthy"] else "[red]UNHEALTHY[/red]"
    console.print(f"Overall: {health}")


@app.command("claude-mem-sync")
def claude_mem_sync(
    agent_id: str = typer.Option("default", "--agent", "-a", help="Agent ID for graph memory"),
    project: str = typer.Option(None, "--project", "-p", help="Filter by project"),
    limit: int = typer.Option(500, "--limit", "-l", help="Max observations to sync"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Sync claude-mem observations to GraphMemory (graph layer)."""
    from .memory.claude_mem_bridge import ClaudeMemBridge

    console.print("[bold]Claude-mem -> GraphMemory Sync[/bold]\n")

    bridge = ClaudeMemBridge(agent_id=agent_id)

    # Check claude-mem DB
    if not bridge.claude_mem_db or not bridge.claude_mem_db.exists():
        console.print("[red]Claude-mem database not found[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Source:[/cyan] {bridge.claude_mem_db}")
    console.print(f"[cyan]Target:[/cyan] GraphMemory (agent_id={agent_id})")

    if project:
        console.print(f"[cyan]Filter:[/cyan] project={project}")

    # Get stats before sync
    pre_stats = bridge.get_stats()
    cm_obs = pre_stats.get("claude_mem", {}).get("total_observations", 0)
    gm_nodes = pre_stats.get("graph_memory", {}).get("total_nodes", 0)

    console.print(f"\n[yellow]Before sync:[/yellow] {cm_obs} observations -> {gm_nodes} graph nodes")

    # Do sync
    console.print("\n[yellow]Syncing...[/yellow]")
    stats = bridge.sync_from_claude_mem(limit=limit, project=project)

    # Show results
    console.print(f"\n[bold]Sync Results:[/bold]")
    console.print(f"  Observations synced: {stats.observations_synced}")
    console.print(f"  Nodes created: {stats.nodes_created}")
    console.print(f"  Relations created: {stats.relations_created}")
    console.print(f"  Skipped (already synced): {stats.skipped}")
    console.print(f"  Errors: {stats.errors}")

    # Get stats after sync
    post_stats = bridge.get_stats()
    gm_nodes_after = post_stats.get("graph_memory", {}).get("total_nodes", 0)
    console.print(f"\n[green]After sync:[/green] {gm_nodes_after} graph nodes total")

    if verbose:
        # Show sample nodes
        nodes = bridge.graph_memory.query(limit=5)
        if nodes:
            console.print("\n[bold]Recent graph nodes:[/bold]")
            for n in nodes:
                console.print(f"  [{n.node_type.value}] {n.content[:60]}...")

    bridge.close()
    console.print("\n[bold green]Sync complete![/bold green]")


@app.command("memory-promote")
def memory_promote(
    node_id: str = typer.Argument(..., help="Node ID to promote to shared memory"),
    agent_id: str = typer.Option("default", "--agent", "-a", help="Source agent ID"),
    boost: float = typer.Option(0.1, "--boost", "-b", help="Importance boost on promote"),
) -> None:
    """Promote a node from agent memory to shared (project-wide) memory."""
    from .memory.graph_memory import GraphMemory

    console.print(f"[bold]Promoting node to shared memory[/bold]")

    graph = GraphMemory(agent_id=agent_id)

    # First show the node
    node = graph.get(node_id)
    if not node:
        console.print(f"[red]Node not found: {node_id}[/red]")
        console.print(f"[dim]Looking in agent_id={agent_id}[/dim]")
        graph.close()
        raise typer.Exit(1)

    console.print(f"[cyan]Node:[/cyan] [{node.node_type.value}] {node.content[:80]}...")
    console.print(f"[cyan]Current importance:[/cyan] {node.importance}")

    # Promote
    success = graph.promote_to_shared(node_id, boost_importance=boost)

    if success:
        new_importance = min(1.0, node.importance + boost)
        console.print(f"[green]Promoted to shared memory[/green]")
        console.print(f"[cyan]New importance:[/cyan] {new_importance}")
    else:
        console.print(f"[red]Failed to promote node[/red]")

    graph.close()


@app.command("memory-demote")
def memory_demote(
    node_id: str = typer.Argument(..., help="Node ID to demote from shared memory"),
    target_agent: str = typer.Option("default", "--agent", "-a", help="Target agent ID"),
) -> None:
    """Demote a node from shared memory back to agent-specific memory."""
    from .memory.graph_memory import GraphMemory, SHARED_AGENT_ID

    console.print(f"[bold]Demoting node from shared memory[/bold]")

    # Use shared agent to access shared nodes
    graph = GraphMemory(agent_id=target_agent)

    success = graph.demote_from_shared(node_id, target_agent_id=target_agent)

    if success:
        console.print(f"[green]Demoted to agent {target_agent}[/green]")
    else:
        console.print(f"[red]Node not found in shared memory: {node_id}[/red]")

    graph.close()


@app.command("memory-shared")
def memory_shared(
    search: str = typer.Option(None, "--search", "-s", help="Search term"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max results"),
) -> None:
    """List all shared (project-wide) memory nodes."""
    from .memory.graph_memory import GraphMemory, SHARED_AGENT_ID

    console.print("[bold]Shared Memory (Project-wide)[/bold]\n")

    # Create graph with any agent_id to query shared
    graph = GraphMemory(agent_id="viewer")
    nodes = graph.query_shared_only(search_term=search, limit=limit)

    if not nodes:
        console.print("[yellow]No shared memory nodes found[/yellow]")
        graph.close()
        return

    console.print(f"[cyan]Total shared nodes:[/cyan] {len(nodes)}\n")

    for node in nodes:
        imp = f"[{'green' if node.importance >= 0.7 else 'yellow' if node.importance >= 0.4 else 'dim'}]{node.importance:.2f}[/]"
        console.print(f"  {imp} [{node.node_type.value}] {node.id[:8]} | {node.content[:60]}...")

    graph.close()


@app.command("memory-stats")
def memory_stats(
    agent_id: str = typer.Option("default", "--agent", "-a", help="Agent ID"),
) -> None:
    """Show memory statistics including shared memory."""
    from .memory.graph_memory import GraphMemory

    graph = GraphMemory(agent_id=agent_id)
    stats = graph.get_stats()

    console.print(f"[bold]Memory Stats for agent: {agent_id}[/bold]\n")

    # Agent's own memory
    console.print("[cyan]Agent Memory:[/cyan]")
    console.print(f"  Nodes: {stats['total_nodes']}")
    console.print(f"  Relations: {stats['total_relations']}")
    if stats['nodes_by_type']:
        types_str = ", ".join(f"{t}={c}" for t, c in stats['nodes_by_type'].items())
        console.print(f"  By type: {types_str}")

    # Shared memory
    shared = stats.get('shared', {})
    console.print("\n[cyan]Shared Memory (project-wide):[/cyan]")
    console.print(f"  Nodes: {shared.get('total_nodes', 0)}")
    console.print(f"  Relations: {shared.get('total_relations', 0)}")
    if shared.get('nodes_by_type'):
        types_str = ", ".join(f"{t}={c}" for t, c in shared['nodes_by_type'].items())
        console.print(f"  By type: {types_str}")

    # Combined
    total = stats['total_nodes'] + shared.get('total_nodes', 0)
    console.print(f"\n[green]Total accessible:[/green] {total} nodes")
    console.print(f"[dim]DB: {stats['db_path']}[/dim]")

    graph.close()


# ==============================================================================
# Git Worktrees Commands
# ==============================================================================

@app.command("worktree-create")
def worktree_create(
    agent_id: str = typer.Argument(..., help="ID агента"),
    task_name: str = typer.Argument(..., help="Название задачи"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту (default: cwd)"),
    base_branch: str = typer.Option("main", "--base", "-b", help="Базовая ветка"),
) -> None:
    """Создать изолированный worktree для задачи агента."""
    from .worktree_manager import WorktreeManager

    project = Path(project_path) if project_path else Path.cwd()

    try:
        wm = WorktreeManager(project)
        worktree = wm.create_task_worktree(agent_id, task_name, base_branch)
        console.print(f"[green]Agent {agent_id} now working in worktree: {worktree.path}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("worktree-list")
def worktree_list(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту (default: cwd)"),
) -> None:
    """Показать все активные worktrees."""
    from .worktree_manager import WorktreeManager

    project = Path(project_path) if project_path else Path.cwd()

    try:
        wm = WorktreeManager(project)
        worktrees = wm.list_worktrees()

        if not worktrees:
            console.print("[yellow]No worktrees found[/yellow]")
            return

        table = Table(title="Active Worktrees")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Task", style="green")
        table.add_column("Branch", style="yellow")
        table.add_column("Path", style="blue")
        table.add_column("Status", style="magenta")

        for wt in worktrees:
            status = wm.get_worktree_status(wt)
            status_text = f"{status['commits_ahead']} commits, {status['uncommitted_files']} files"

            table.add_row(
                wt.agent_id,
                wt.task_name,
                wt.branch_name,
                str(wt.path),
                status_text
            )

        console.print(table)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("worktree-merge")
def worktree_merge(
    agent_id: str = typer.Argument(..., help="ID агента"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    target_branch: str = typer.Option("main", "--target", "-t", help="Целевая ветка"),
    squash: bool = typer.Option(False, "--squash", "-s", help="Squash merge"),
) -> None:
    """Смёржить изменения из worktree агента в main."""
    from .worktree_manager import WorktreeManager

    project = Path(project_path) if project_path else Path.cwd()

    try:
        wm = WorktreeManager(project)
        worktrees = wm.list_worktrees()

        agent_worktree = None
        for wt in worktrees:
            if wt.agent_id == agent_id:
                agent_worktree = wt
                break

        if not agent_worktree:
            console.print(f"[red]No worktree found for agent {agent_id}[/red]")
            raise typer.Exit(1)

        success = wm.merge_worktree(agent_worktree, target_branch, squash=squash)

        if success:
            console.print(f"[green]Successfully merged and cleaned up worktree[/green]")
        else:
            console.print(f"[red]Merge failed - check conflicts[/red]")
            raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("worktree-discard")
def worktree_discard(
    agent_id: str = typer.Argument(..., help="ID агента"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    force: bool = typer.Option(False, "--force", "-f", help="Принудительное удаление"),
) -> None:
    """Удалить worktree агента без merge."""
    from .worktree_manager import WorktreeManager

    project = Path(project_path) if project_path else Path.cwd()

    try:
        wm = WorktreeManager(project)
        worktrees = wm.list_worktrees()

        for wt in worktrees:
            if wt.agent_id == agent_id:
                wm.discard_worktree(wt, force=force)
                console.print(f"[green]Worktree discarded for agent {agent_id}[/green]")
                return

        console.print(f"[yellow]No worktree found for agent {agent_id}[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ==============================================================================
# Validation Commands
# ==============================================================================

@app.command("validate")
def validate_agent(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту (default: cwd)"),
    run_tests: bool = typer.Option(True, "--tests/--no-tests", help="Запускать тесты"),
    check_types: bool = typer.Option(True, "--types/--no-types", help="Проверять типы (mypy)"),
    check_style: bool = typer.Option(True, "--style/--no-style", help="Проверять стиль (ruff)"),
    check_security: bool = typer.Option(True, "--security/--no-security", help="Проверять безопасность (bandit)"),
) -> None:
    """Валидировать код проекта (mypy, ruff, bandit, pytest)."""
    import asyncio
    from .validation import ValidationAgent, print_validation_report

    project = Path(project_path) if project_path else Path.cwd()

    # Получаем изменённые файлы через git
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=project,
            capture_output=True,
            text=True,
            check=True
        )

        changed_files = [
            project / line.strip()
            for line in result.stdout.split('\n')
            if line.strip()
        ]
    except:
        # Если не git repo или нет изменений, проверяем все .py файлы
        changed_files = list(project.rglob("*.py"))

    if not changed_files:
        console.print("[yellow]No files to validate[/yellow]")
        return

    console.print(f"[cyan]Validating {len(changed_files)} files...[/cyan]")

    # Запускаем валидацию
    validator = ValidationAgent("cli-validation", project)
    report = asyncio.run(validator.validate_changes(
        changed_files,
        run_tests=run_tests,
        check_types=check_types,
        check_style=check_style,
        check_security=check_security
    ))

    # Показываем результаты
    print_validation_report(report)

    # Exit code
    if report.has_errors():
        raise typer.Exit(1)


# ==============================================================================
# Context Engineering Commands
# ==============================================================================

@app.command("analyze-project")
def analyze_project_cmd(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту (default: cwd)"),
    force: bool = typer.Option(False, "--force", "-f", help="Игнорировать кеш"),
) -> None:
    """Анализировать проект и показать context."""
    import asyncio
    from .context.analyzer import CodebaseAnalyzer, print_context

    project = Path(project_path) if project_path else Path.cwd()

    analyzer = CodebaseAnalyzer(project)
    context = asyncio.run(analyzer.analyze(force_refresh=force))

    print_context(context)

    console.print(f"\n[green]Context saved to {analyzer.cache_path}[/green]")


# ==============================================================================
# Task Workflow Commands (worktree + validation + context)
# ==============================================================================

@app.command("task-start")
def task_start(
    agent_id: str = typer.Argument(..., help="ID агента"),
    task_name: str = typer.Argument(..., help="Название задачи"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту (default: cwd)"),
    base_branch: str = typer.Option("main", "--base", "-b", help="Базовая ветка"),
) -> None:
    """
    Начать новую задачу с полной автоматизацией.

    1. Анализирует проект (context engineering)
    2. Создаёт worktree для изоляции
    3. Готовит окружение для агента
    """
    import asyncio
    from rich.panel import Panel
    from .worktree_manager import WorktreeManager
    from .context.analyzer import CodebaseAnalyzer

    project = Path(project_path) if project_path else Path.cwd()

    # 1. Analyze project
    console.print("[cyan]Step 1: Analyzing project...[/cyan]")
    analyzer = CodebaseAnalyzer(project)
    context = asyncio.run(analyzer.analyze())

    # 2. Create worktree
    console.print("[cyan]Step 2: Creating isolated worktree...[/cyan]")
    try:
        wm = WorktreeManager(project)
        worktree = wm.create_task_worktree(agent_id, task_name, base_branch)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # 3. Summary
    tech_stack_str = ', '.join(f'{k}: {v}' for k, v in context.tech_stack.items())
    architecture = context.structure.get('architecture', 'unknown')
    deps_count = len(context.dependencies.get('production', []))

    console.print(Panel(
        f"Task started successfully!\n\n"
        f"Agent: {agent_id}\n"
        f"Task: {task_name}\n"
        f"Worktree: {worktree.path}\n"
        f"Branch: {worktree.branch_name}\n\n"
        f"Project Context:\n"
        f"  Tech Stack: {tech_stack_str}\n"
        f"  Architecture: {architecture}\n"
        f"  Dependencies: {deps_count} packages\n\n"
        f"When ready, use:\n"
        f"  cam task-complete {agent_id} --project \"{project}\"",
        title="Task Started",
        border_style="green"
    ))


@app.command("task-complete")
def task_complete(
    agent_id: str = typer.Argument(..., help="ID агента"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    auto_merge: bool = typer.Option(False, "--auto-merge", "-y", help="Автоматический merge без подтверждения"),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Пропустить валидацию"),
) -> None:
    """
    Завершить задачу с валидацией и merge.

    1. Запускает валидацию (опционально)
    2. Если OK - мержит worktree в main
    3. Удаляет worktree
    """
    import asyncio
    from rich.panel import Panel
    from .worktree_manager import WorktreeManager
    from .validation import ValidationAgent, print_validation_report

    project = Path(project_path) if project_path else Path.cwd()

    try:
        wm = WorktreeManager(project)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    worktrees = wm.list_worktrees()

    agent_worktree = None
    for wt in worktrees:
        if wt.agent_id == agent_id:
            agent_worktree = wt
            break

    if not agent_worktree:
        console.print(f"[red]No worktree found for agent {agent_id}[/red]")
        raise typer.Exit(1)

    # 1. Validate (optional)
    if not skip_validation:
        console.print("[cyan]Step 1: Validating changes...[/cyan]")

        # Get changed files
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main"],
                cwd=agent_worktree.path,
                capture_output=True,
                text=True
            )

            changed_files = [
                agent_worktree.path / line.strip()
                for line in result.stdout.split('\n')
                if line.strip() and line.strip().endswith('.py')
            ]
        except:
            changed_files = list(agent_worktree.path.rglob("*.py"))

        if changed_files:
            validator = ValidationAgent(agent_id, agent_worktree.path)
            report = asyncio.run(validator.validate_changes(
                changed_files,
                run_tests=False,  # Skip tests for speed
                check_types=True,
                check_style=True,
                check_security=True
            ))

            print_validation_report(report)

            if report.has_critical_errors():
                console.print("\n[red]Critical errors found! Cannot merge.[/red]")
                console.print("[yellow]Fix errors and try again, or use --skip-validation to merge anyway[/yellow]")
                raise typer.Exit(1)

    # 2. Confirm merge
    if not auto_merge:
        import typer
        confirm = typer.confirm("Validation passed. Merge to main?")
        if not confirm:
            console.print("[yellow]Merge cancelled[/yellow]")
            return

    # 3. Merge
    console.print("[cyan]Step 2: Merging to main...[/cyan]")

    success = wm.merge_worktree(agent_worktree, "main", delete_after=True)

    if success:
        console.print(Panel(
            "Task completed successfully!\n\n"
            "Changes validated and merged to main.\n"
            "Worktree cleaned up.",
            title="Task Complete",
            border_style="green"
        ))
    else:
        console.print("[red]Merge failed - resolve conflicts manually[/red]")
        raise typer.Exit(1)


# ==============================================================================
# Changelog Commands
# ==============================================================================

@app.command("changelog")
def changelog_cmd(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    from_tag: str = typer.Option("", "--from", "-f", help="Начальный тег"),
    to_tag: str = typer.Option("HEAD", "--to", "-t", help="Конечный тег"),
    version: str = typer.Option("Unreleased", "--version", "-v", help="Название версии"),
    output: str = typer.Option(None, "--output", "-o", help="Сохранить в файл"),
    github_release: bool = typer.Option(False, "--github-release", help="Создать GitHub Release"),
) -> None:
    """Сгенерировать changelog из git history."""
    from .git.changelog import ChangelogGenerator, print_changelog

    project = Path(project_path) if project_path else Path.cwd()

    generator = ChangelogGenerator(project)
    changelog = generator.generate(version, from_tag, to_tag)

    print_changelog(changelog)

    if output:
        generator.save_changelog(changelog, output)

    if github_release and version != "Unreleased":
        generator.create_github_release(changelog, f"v{version}")


# ==============================================================================
# Conflict Resolution Commands
# ==============================================================================

@app.command("resolve-conflicts")
def resolve_conflicts_cmd(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    file_path: str = typer.Option(None, "--file", "-f", help="Конкретный файл"),
    auto_apply: bool = typer.Option(False, "--apply", "-a", help="Автоматически применить"),
) -> None:
    """AI-powered разрешение git конфликтов."""
    from .git.conflict_resolver import ConflictResolver, print_conflict

    project = Path(project_path) if project_path else Path.cwd()

    resolver = ConflictResolver(project)

    if file_path:
        # Разрешаем конфликты в одном файле
        result = resolver.resolve_file_conflicts(project / file_path)

        if result.success:
            console.print(f"[green]✓ Resolved {len(result.conflicts_resolved)} conflicts[/green]")

            if auto_apply and result.merged_content:
                (project / file_path).write_text(result.merged_content, encoding='utf-8')
                console.print(f"[green]Applied to {file_path}[/green]")
        else:
            console.print(f"[yellow]Need manual review for {len(result.conflicts_remaining)} conflicts[/yellow]")
            for conflict in result.conflicts_remaining:
                print_conflict(conflict)
    else:
        # Разрешаем все конфликты
        results = resolver.resolve_all(auto_apply=auto_apply)

        success_count = sum(1 for r in results if r.success)
        console.print(f"\n[green]Resolved: {success_count}/{len(results)} files[/green]")


# ==============================================================================
# Ideation / Feature Anticipation Commands
# ==============================================================================

@app.command("anticipate")
def anticipate_cmd(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    types: str = typer.Option(None, "--types", "-t", help="Типы идей (comma-separated)"),
    max_per_type: int = typer.Option(5, "--max", "-m", help="Макс. идей каждого типа"),
) -> None:
    """Сгенерировать идеи для улучшения проекта."""
    from .ideation import IdeaGenerator, IdeaType, print_ideas

    project = Path(project_path) if project_path else Path.cwd()

    # Парсим типы
    idea_types = None
    if types:
        type_names = [t.strip() for t in types.split(',')]
        idea_types = []
        for name in type_names:
            try:
                idea_types.append(IdeaType(name))
            except ValueError:
                console.print(f"[yellow]Unknown type: {name}[/yellow]")

    generator = IdeaGenerator(project)
    ideas = generator.generate_ideas(idea_types, max_per_type)

    if ideas:
        print_ideas(ideas)
        console.print(f"\n[green]Generated {len(ideas)} ideas. Saved to .clod/ideas.json[/green]")
    else:
        console.print("[yellow]No improvement ideas found[/yellow]")


# ==============================================================================
# Kanban Board Commands
# ==============================================================================

@app.command("board")
def board_cmd(
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    show_archived: bool = typer.Option(False, "--archived", "-a", help="Показать архивные"),
) -> None:
    """Показать Kanban доску."""
    from .tasks.kanban import KanbanBoard, print_board

    project = Path(project_path) if project_path else Path.cwd()
    board = KanbanBoard(project)
    print_board(board, show_archived)


@app.command("task-create")
def task_create_cmd(
    title: str = typer.Argument(..., help="Название задачи"),
    description: str = typer.Option("", "--desc", "-d", help="Описание"),
    priority: str = typer.Option("medium", "--priority", "-p", help="Приоритет: low/medium/high/urgent"),
    task_type: str = typer.Option("feature", "--type", "-t", help="Тип: feature/bug/refactor/docs/test/chore"),
    labels: str = typer.Option("", "--labels", "-l", help="Метки (comma-separated)"),
    project_path: str = typer.Option(None, "--project", help="Путь к проекту"),
) -> None:
    """Создать новую задачу."""
    from .tasks import KanbanBoard, TaskPriority, TaskType

    project = Path(project_path) if project_path else Path.cwd()
    board = KanbanBoard(project)

    try:
        prio = TaskPriority(priority.lower())
    except ValueError:
        prio = TaskPriority.MEDIUM

    try:
        ttype = TaskType(task_type.lower())
    except ValueError:
        ttype = TaskType.FEATURE

    label_list = [l.strip() for l in labels.split(',') if l.strip()] if labels else []

    task = board.create_task(title, description, prio, ttype, label_list)
    console.print(f"[green]Created: {task}[/green]")


@app.command("task-move")
def task_move_cmd(
    task_id: str = typer.Argument(..., help="ID задачи"),
    status: str = typer.Argument(..., help="Статус: backlog/todo/in_progress/in_review/done"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
) -> None:
    """Переместить задачу в другой статус."""
    from .tasks import KanbanBoard, TaskStatus

    project = Path(project_path) if project_path else Path.cwd()
    board = KanbanBoard(project)

    try:
        new_status = TaskStatus(status.lower())
    except ValueError:
        console.print(f"[red]Invalid status: {status}[/red]")
        raise typer.Exit(1)

    board.move_task(task_id, new_status)


@app.command("task-assign")
def task_assign_cmd(
    task_id: str = typer.Argument(..., help="ID задачи"),
    agent_id: str = typer.Argument(..., help="ID агента"),
    start: bool = typer.Option(False, "--start", "-s", help="Также начать работу"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
) -> None:
    """Назначить задачу агенту."""
    from .tasks import KanbanBoard

    project = Path(project_path) if project_path else Path.cwd()
    board = KanbanBoard(project)

    board.assign_task(task_id, agent_id)

    if start:
        board.start_task(task_id, agent_id)


@app.command("task-done")
def task_done_cmd(
    task_id: str = typer.Argument(..., help="ID задачи"),
    project_path: str = typer.Option(None, "--project", "-p", help="Путь к проекту"),
) -> None:
    """Отметить задачу как выполненную."""
    from .tasks import KanbanBoard

    project = Path(project_path) if project_path else Path.cwd()
    board = KanbanBoard(project)

    board.complete_task(task_id)


# =============================================================================
# Phase 3: Metrics & Dashboard commands
# =============================================================================

@app.command("metrics")
def metrics_cmd(
    agent_id: str = typer.Option(None, "--agent", "-a", help="ID агента (опционально)"),
    time_range: str = typer.Option("day", "--range", "-r", help="Период: hour/day/week/month/all"),
    export_path: str = typer.Option(None, "--export", "-e", help="Экспортировать в JSON"),
) -> None:
    """Показать метрики (глобальные или агента)."""
    from .monitoring.metrics import MetricsCollector, TimeRange, print_metrics_summary

    collector = MetricsCollector()

    try:
        tr = TimeRange(time_range.lower())
    except ValueError:
        console.print(f"[red]Invalid time range: {time_range}[/red]")
        raise typer.Exit(1)

    if export_path:
        collector.export_metrics(Path(export_path), tr)
        console.print(f"[green]✓[/green] Metrics exported to {export_path}")
    else:
        print_metrics_summary(collector, agent_id)


@app.command("metrics-dashboard")
def metrics_dashboard_cmd(
    time_range: str = typer.Option("day", "--range", "-r", help="Период: hour/day/week/month"),
    live: bool = typer.Option(False, "--live", "-l", help="Live-режим с обновлением"),
) -> None:
    """Показать терминальный дашборд метрик."""
    from .monitoring.metrics import MetricsCollector, TimeRange
    from .monitoring.dashboard import render_dashboard

    collector = MetricsCollector()

    try:
        tr = TimeRange(time_range.lower())
    except ValueError:
        console.print(f"[red]Invalid time range: {time_range}[/red]")
        raise typer.Exit(1)

    render_dashboard(collector, tr, live=live)


@app.command("metrics-cleanup")
def metrics_cleanup_cmd(
    days: int = typer.Option(90, "--days", "-d", help="Хранить метрики за N дней"),
) -> None:
    """Очистить старые метрики."""
    from .monitoring.metrics import MetricsCollector

    collector = MetricsCollector()
    deleted = collector.cleanup_old_metrics(days)
    console.print(f"[green]✓[/green] Deleted {deleted} old metrics records")


@app.command("web")
def web_cmd(
    port: int = typer.Option(8080, "--port", "-p", help="Порт"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Хост"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Режим отладки"),
) -> None:
    """Запустить веб-дашборд."""
    try:
        from .web import run_server
    except ImportError:
        console.print("[red]FastAPI not installed![/red]")
        console.print("Install with: pip install fastapi uvicorn websockets")
        raise typer.Exit(1)

    console.print(f"[green]Starting web dashboard on http://{host}:{port}[/green]")
    run_server(port=port, host=host, debug=debug)

