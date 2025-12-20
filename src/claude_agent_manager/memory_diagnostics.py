"""
Диагностика изоляции памяти агентов.

Проверяет:
- Каждый агент имеет уникальный порт
- Каждый агент имеет изолированную директорию данных
- MCP сервер claude-mem правильно сконфигурирован
- Worker процесс запущен с правильными env переменными
- Данные памяти пишутся в правильное место
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree


console = Console()


@dataclass
class MemoryDiagnostics:
    """Результаты диагностики памяти агента."""
    agent_id: str
    port: int
    data_dir: Path

    # Статусы проверок
    port_unique: bool = True
    port_conflict_with: Optional[str] = None

    data_dir_exists: bool = False
    data_dir_writable: bool = False

    mcp_configured: bool = False
    mcp_port_correct: bool = False
    mcp_data_dir_correct: bool = False

    worker_running: bool = False
    worker_port_env: Optional[str] = None
    worker_data_dir_env: Optional[str] = None

    # Данные памяти
    memory_files: List[str] = field(default_factory=list)
    memory_size_kb: float = 0.0
    last_memory_update: Optional[datetime] = None

    # Ошибки
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return (
            self.port_unique and
            self.data_dir_exists and
            self.mcp_configured and
            self.mcp_port_correct and
            self.mcp_data_dir_correct and
            len(self.errors) == 0
        )


def diagnose_agent_memory(
    agent_id: str,
    port: int,
    agent_dir: Path,
    project_path: Path,
    pm2_name: str,
    all_agents: List[Dict]
) -> MemoryDiagnostics:
    """
    Провести полную диагностику изоляции памяти агента.

    Args:
        agent_id: ID агента
        port: Порт агента
        agent_dir: Директория агента (~/.cam/agents/{id}/)
        project_path: Путь к проекту
        pm2_name: Имя PM2 процесса
        all_agents: Список всех агентов для проверки конфликтов

    Returns:
        MemoryDiagnostics с результатами
    """
    diag = MemoryDiagnostics(
        agent_id=agent_id,
        port=port,
        data_dir=agent_dir
    )

    # 1. Проверка уникальности порта
    for other in all_agents:
        if other["id"] != agent_id and other["port"] == port:
            diag.port_unique = False
            diag.port_conflict_with = other["id"]
            diag.errors.append(f"Port {port} conflict with agent {other['id']}")
            break

    # 2. Проверка директории данных
    diag.data_dir_exists = agent_dir.exists()
    if diag.data_dir_exists:
        try:
            test_file = agent_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            diag.data_dir_writable = True
        except Exception as e:
            diag.data_dir_writable = False
            diag.errors.append(f"Data dir not writable: {e}")
    else:
        diag.errors.append(f"Data dir does not exist: {agent_dir}")

    # 3. Проверка MCP конфигурации
    mcp_json_path = agent_dir / ".mcp.json"
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text(encoding="utf-8"))
            servers = mcp_config.get("mcpServers", {})

            if "claude-mem" in servers:
                diag.mcp_configured = True
                mem_server = servers["claude-mem"]
                env = mem_server.get("env", {})

                # Проверка порта
                mcp_port = env.get("CLAUDE_MEM_WORKER_PORT")
                diag.mcp_port_correct = str(port) == str(mcp_port)
                if not diag.mcp_port_correct:
                    diag.errors.append(f"MCP port mismatch: expected {port}, got {mcp_port}")

                # Проверка data_dir
                mcp_data_dir = env.get("CLAUDE_MEM_DATA_DIR", "")
                expected_dir = str(agent_dir).replace("\\", "/")
                diag.mcp_data_dir_correct = mcp_data_dir == expected_dir
                if not diag.mcp_data_dir_correct:
                    diag.warnings.append(f"MCP data_dir mismatch: expected {expected_dir}, got {mcp_data_dir}")
            else:
                diag.warnings.append("claude-mem MCP server not configured")
        except Exception as e:
            diag.errors.append(f"Failed to read MCP config: {e}")
    else:
        diag.warnings.append("No .mcp.json in agent directory")

    # 4. Проверка worker процесса через PM2
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            shell=True,
            timeout=5
        )

        if result.returncode == 0:
            processes = json.loads(result.stdout)
            for proc in processes:
                if proc.get("name") == pm2_name:
                    diag.worker_running = True

                    # Проверяем env переменные
                    pm2_env = proc.get("pm2_env", {})
                    diag.worker_port_env = pm2_env.get("CLAUDE_MEM_WORKER_PORT")
                    diag.worker_data_dir_env = pm2_env.get("CLAUDE_MEM_DATA_DIR")

                    if diag.worker_port_env != str(port):
                        diag.errors.append(
                            f"Worker port env mismatch: expected {port}, got {diag.worker_port_env}"
                        )

                    break
    except Exception as e:
        diag.warnings.append(f"Could not check PM2 worker: {e}")

    # 5. Проверка файлов памяти
    memory_patterns = ["*.db", "*.sqlite", "*.json", "memory/*", "vectors/*"]
    total_size = 0
    latest_mtime = None

    for pattern in memory_patterns:
        for f in agent_dir.glob(pattern):
            if f.is_file():
                diag.memory_files.append(str(f.relative_to(agent_dir)))
                size = f.stat().st_size
                total_size += size
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

    diag.memory_size_kb = total_size / 1024
    diag.last_memory_update = latest_mtime

    return diag


def diagnose_all_agents(agent_root: Path, agents: List[Dict]) -> Dict[str, MemoryDiagnostics]:
    """
    Диагностика всех агентов.

    Args:
        agent_root: Корневая директория агентов
        agents: Список агентов

    Returns:
        Dict agent_id -> MemoryDiagnostics
    """
    results = {}

    for agent in agents:
        agent_id = agent["id"]
        port = agent["port"]
        agent_dir = agent_root / agent_id
        project_path = Path(agent["project_path"])
        pm2_name = agent.get("pm2_name", f"agent-{agent_id}")

        results[agent_id] = diagnose_agent_memory(
            agent_id=agent_id,
            port=port,
            agent_dir=agent_dir,
            project_path=project_path,
            pm2_name=pm2_name,
            all_agents=agents
        )

    return results


def print_diagnostics_report(diagnostics: Dict[str, MemoryDiagnostics]) -> None:
    """Вывести отчёт диагностики."""

    # Summary table
    table = Table(title="Memory Isolation Diagnostics")
    table.add_column("Agent", style="cyan")
    table.add_column("Port", justify="right")
    table.add_column("Port OK", justify="center")
    table.add_column("Dir OK", justify="center")
    table.add_column("MCP OK", justify="center")
    table.add_column("Worker", justify="center")
    table.add_column("Memory", justify="right")
    table.add_column("Status", justify="center")

    for agent_id, diag in diagnostics.items():
        port_ok = "✓" if diag.port_unique else "✗"
        dir_ok = "✓" if diag.data_dir_exists and diag.data_dir_writable else "✗"
        mcp_ok = "✓" if diag.mcp_configured and diag.mcp_port_correct else "✗"
        worker = "✓" if diag.worker_running else "○"
        memory = f"{diag.memory_size_kb:.1f}KB" if diag.memory_size_kb > 0 else "empty"
        status = "[green]OK[/green]" if diag.is_healthy else "[red]ISSUES[/red]"

        table.add_row(
            agent_id[:15],
            str(diag.port),
            f"[green]{port_ok}[/green]" if port_ok == "✓" else f"[red]{port_ok}[/red]",
            f"[green]{dir_ok}[/green]" if dir_ok == "✓" else f"[red]{dir_ok}[/red]",
            f"[green]{mcp_ok}[/green]" if mcp_ok == "✓" else f"[yellow]{mcp_ok}[/yellow]",
            f"[green]{worker}[/green]" if worker == "✓" else f"[dim]{worker}[/dim]",
            memory,
            status
        )

    console.print(table)

    # Detailed issues
    has_issues = False
    for agent_id, diag in diagnostics.items():
        if diag.errors or diag.warnings:
            has_issues = True
            break

    if has_issues:
        console.print("\n[bold]Issues Found:[/bold]")
        for agent_id, diag in diagnostics.items():
            if diag.errors or diag.warnings:
                tree = Tree(f"[cyan]{agent_id}[/cyan]")

                if diag.errors:
                    errors = tree.add("[red]Errors[/red]")
                    for err in diag.errors:
                        errors.add(f"[red]✗[/red] {err}")

                if diag.warnings:
                    warnings = tree.add("[yellow]Warnings[/yellow]")
                    for warn in diag.warnings:
                        warnings.add(f"[yellow]![/yellow] {warn}")

                console.print(tree)


def print_agent_detail(diag: MemoryDiagnostics) -> None:
    """Вывести детальную информацию об агенте."""

    # Build detail tree
    tree = Tree(f"[bold cyan]Agent: {diag.agent_id}[/bold cyan]")

    # Port info
    port_node = tree.add("Port Configuration")
    port_status = "[green]✓[/green]" if diag.port_unique else "[red]✗[/red]"
    port_node.add(f"{port_status} Port: {diag.port}")
    if diag.port_conflict_with:
        port_node.add(f"[red]Conflict with: {diag.port_conflict_with}[/red]")

    # Data directory
    dir_node = tree.add("Data Directory")
    dir_node.add(f"Path: {diag.data_dir}")
    dir_node.add(f"Exists: {'[green]✓[/green]' if diag.data_dir_exists else '[red]✗[/red]'}")
    dir_node.add(f"Writable: {'[green]✓[/green]' if diag.data_dir_writable else '[red]✗[/red]'}")

    # MCP Configuration
    mcp_node = tree.add("MCP Configuration")
    mcp_node.add(f"claude-mem configured: {'[green]✓[/green]' if diag.mcp_configured else '[yellow]✗[/yellow]'}")
    if diag.mcp_configured:
        mcp_node.add(f"Port correct: {'[green]✓[/green]' if diag.mcp_port_correct else '[red]✗[/red]'}")
        mcp_node.add(f"Data dir correct: {'[green]✓[/green]' if diag.mcp_data_dir_correct else '[yellow]![/yellow]'}")

    # Worker process
    worker_node = tree.add("Worker Process")
    worker_node.add(f"Running: {'[green]✓[/green]' if diag.worker_running else '[dim]○[/dim]'}")
    if diag.worker_running:
        worker_node.add(f"CLAUDE_MEM_WORKER_PORT: {diag.worker_port_env}")
        worker_node.add(f"CLAUDE_MEM_DATA_DIR: {diag.worker_data_dir_env}")

    # Memory files
    mem_node = tree.add("Memory Data")
    mem_node.add(f"Size: {diag.memory_size_kb:.2f} KB")
    mem_node.add(f"Files: {len(diag.memory_files)}")
    if diag.last_memory_update:
        mem_node.add(f"Last update: {diag.last_memory_update.strftime('%Y-%m-%d %H:%M:%S')}")
    if diag.memory_files:
        files_node = mem_node.add("Files")
        for f in diag.memory_files[:10]:
            files_node.add(f"[dim]{f}[/dim]")
        if len(diag.memory_files) > 10:
            files_node.add(f"[dim]... and {len(diag.memory_files) - 10} more[/dim]")

    console.print(tree)

    # Overall status
    if diag.is_healthy:
        console.print(Panel("[green]✓ Agent memory isolation is healthy[/green]", border_style="green"))
    else:
        console.print(Panel("[red]✗ Issues detected with memory isolation[/red]", border_style="red"))


def verify_isolation_live(agents: List[Dict], agent_root: Path) -> bool:
    """
    Интерактивная проверка изоляции памяти.

    Создаёт тестовый файл в каждой директории агента
    и проверяет что они не пересекаются.

    Returns:
        True если изоляция в порядке
    """
    console.print("[bold]Live Isolation Verification[/bold]\n")

    # Create test files
    test_files = {}
    for agent in agents:
        agent_dir = agent_root / agent["id"]
        if agent_dir.exists():
            test_file = agent_dir / f".isolation_test_{agent['id']}"
            test_file.write_text(f"agent:{agent['id']}")
            test_files[agent["id"]] = test_file

    console.print(f"Created {len(test_files)} test files")

    # Verify each agent can only see its own file
    all_ok = True
    for agent_id, test_file in test_files.items():
        agent_dir = agent_root / agent_id

        # Check own file exists
        if not test_file.exists():
            console.print(f"[red]✗[/red] Agent {agent_id}: own test file missing")
            all_ok = False
            continue

        # Check content is correct
        content = test_file.read_text()
        if content != f"agent:{agent_id}":
            console.print(f"[red]✗[/red] Agent {agent_id}: test file corrupted")
            all_ok = False
            continue

        # Check no other agent's files are visible
        for other_id, other_file in test_files.items():
            if other_id == agent_id:
                continue

            # Check if other file is somehow in our directory
            other_in_ours = agent_dir / other_file.name
            if other_in_ours.exists():
                console.print(f"[red]✗[/red] Agent {agent_id}: can see {other_id}'s file!")
                all_ok = False

        if all_ok:
            console.print(f"[green]✓[/green] Agent {agent_id}: isolation OK")

    # Cleanup
    for test_file in test_files.values():
        try:
            test_file.unlink()
        except:
            pass

    console.print()
    if all_ok:
        console.print(Panel("[green]✓ All agents are properly isolated[/green]", border_style="green"))
    else:
        console.print(Panel("[red]✗ Isolation issues detected![/red]", border_style="red"))

    return all_ok
