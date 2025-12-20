"""
Инструменты для работы с памятью агентов.

Функции:
- Просмотр всех записей памяти
- Поиск по содержимому
- Просмотр последних записей
- Статистика по памяти
- Сравнение памяти между агентами (для проверки изоляции)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Iterator
import re

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree
from rich.progress import Progress

console = Console()


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class MemoryEntry:
    """Запись в памяти агента."""
    id: str
    content: str
    embedding_preview: str = ""  # первые N значений вектора
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # откуда запись (conversation, file, etc)
    
    @property
    def preview(self) -> str:
        """Короткий preview контента."""
        text = self.content[:100]
        if len(self.content) > 100:
            text += "..."
        return text.replace("\n", " ")


@dataclass 
class MemoryStats:
    """Статистика памяти агента."""
    agent_id: str
    total_entries: int = 0
    db_size_bytes: int = 0
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    avg_content_length: float = 0.0
    sources: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# MEMORY READER
# ============================================================================

class AgentMemoryReader:
    """
    Чтение памяти агента из sqlite базы claude-mem.
    
    claude-mem хранит данные в:
    - vectors.db (sqlite с векторами)
    - memories.json (backup)
    """
    
    def __init__(self, agent_dir: Path):
        self.agent_dir = agent_dir
        self.db_path = self._find_db()
    
    def _find_db(self) -> Optional[Path]:
        """Найти файл базы данных памяти."""
        # Возможные пути
        candidates = [
            self.agent_dir / "vectors.db",
            self.agent_dir / "memory" / "vectors.db",
            self.agent_dir / "data" / "vectors.db",
            self.agent_dir / "claude-mem.db",
            self.agent_dir / "memories.db",
        ]
        
        for path in candidates:
            if path.exists():
                return path
        
        # Поиск любого .db файла
        for db in self.agent_dir.glob("**/*.db"):
            return db
        
        return None
    
    @property
    def has_memory(self) -> bool:
        """Есть ли база памяти."""
        return self.db_path is not None and self.db_path.exists()
    
    def get_stats(self) -> MemoryStats:
        """Получить статистику памяти."""
        stats = MemoryStats(agent_id=self.agent_dir.name)
        
        if not self.has_memory:
            return stats
        
        stats.db_size_bytes = self.db_path.stat().st_size
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Пробуем разные схемы таблиц
            tables = self._get_tables(cursor)
            
            for table in ["memories", "vectors", "entries", "documents"]:
                if table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        stats.total_entries = cursor.fetchone()[0]
                        break
                    except:
                        continue
            
            conn.close()
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read stats: {e}[/yellow]")
        
        return stats
    
    def _get_tables(self, cursor) -> List[str]:
        """Получить список таблиц в базе."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    
    def _get_columns(self, cursor, table: str) -> List[str]:
        """Получить список колонок таблицы."""
        cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]
    
    def iter_entries(self, limit: int = 100) -> Iterator[MemoryEntry]:
        """Итератор по записям памяти."""
        if not self.has_memory:
            return
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            tables = self._get_tables(cursor)
            
            # Пробуем разные схемы
            for table in ["memories", "vectors", "entries", "documents"]:
                if table not in tables:
                    continue
                
                columns = self._get_columns(cursor, table)
                
                # Определяем колонку с контентом
                content_col = None
                for col in ["content", "text", "data", "document", "memory"]:
                    if col in columns:
                        content_col = col
                        break
                
                if not content_col:
                    continue
                
                # ID колонка
                id_col = "id" if "id" in columns else "rowid"
                
                # Timestamp колонка
                ts_col = None
                for col in ["timestamp", "created_at", "date", "time"]:
                    if col in columns:
                        ts_col = col
                        break
                
                # Запрос
                query = f"SELECT {id_col}, {content_col}"
                if ts_col:
                    query += f", {ts_col}"
                query += f" FROM {table} LIMIT {limit}"
                
                cursor.execute(query)
                
                for row in cursor.fetchall():
                    entry = MemoryEntry(
                        id=str(row[0]),
                        content=str(row[1]) if row[1] else "",
                    )
                    
                    if ts_col and len(row) > 2 and row[2]:
                        try:
                            entry.timestamp = datetime.fromisoformat(str(row[2]))
                        except:
                            pass
                    
                    yield entry
                
                break  # Нашли таблицу, выходим
            
            conn.close()
            
        except Exception as e:
            console.print(f"[red]Error reading memories: {e}[/red]")
    
    def search(self, query: str, limit: int = 20) -> List[MemoryEntry]:
        """Поиск по содержимому памяти."""
        results = []
        query_lower = query.lower()
        
        for entry in self.iter_entries(limit=1000):  # Больший лимит для поиска
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        """Получить последние N записей."""
        entries = list(self.iter_entries(limit=n))
        # Сортируем по timestamp если есть
        entries.sort(key=lambda e: e.timestamp or datetime.min, reverse=True)
        return entries[:n]
    
    def get_all(self) -> List[MemoryEntry]:
        """Получить все записи."""
        return list(self.iter_entries(limit=10000))
    
    def export_json(self, output_path: Path) -> int:
        """Экспортировать память в JSON."""
        entries = self.get_all()
        
        data = {
            "agent_id": self.agent_dir.name,
            "exported_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "content": e.content,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "metadata": e.metadata,
                }
                for e in entries
            ]
        }
        
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(entries)


# ============================================================================
# MULTI-AGENT COMPARISON
# ============================================================================

def compare_agent_memories(agent_dirs: List[Path]) -> Dict[str, Any]:
    """
    Сравнить память между агентами для проверки изоляции.
    
    Возвращает:
    - Уникальные записи для каждого агента
    - Пересекающиеся записи (НЕ ДОЛЖНО БЫТЬ при правильной изоляции)
    - Статистику
    """
    result = {
        "agents": {},
        "overlaps": [],  # Записи которые есть у нескольких агентов
        "isolation_ok": True,
    }
    
    all_contents: Dict[str, List[str]] = {}  # content -> [agent_ids]
    
    for agent_dir in agent_dirs:
        agent_id = agent_dir.name
        reader = AgentMemoryReader(agent_dir)
        
        if not reader.has_memory:
            result["agents"][agent_id] = {"status": "no_memory", "entries": 0}
            continue
        
        entries = reader.get_all()
        result["agents"][agent_id] = {
            "status": "ok",
            "entries": len(entries),
            "db_size": reader.db_path.stat().st_size if reader.db_path else 0,
        }
        
        # Проверяем пересечения
        for entry in entries:
            content_hash = entry.content[:200]  # Первые 200 символов как ключ
            if content_hash not in all_contents:
                all_contents[content_hash] = []
            all_contents[content_hash].append(agent_id)
    
    # Ищем пересечения
    for content, agents in all_contents.items():
        if len(agents) > 1:
            result["overlaps"].append({
                "content_preview": content[:100],
                "found_in_agents": agents,
            })
            result["isolation_ok"] = False
    
    return result


# ============================================================================
# CLI COMMANDS
# ============================================================================

def cmd_memory_list(agent_id: str, limit: int = 50, full: bool = False):
    """Показать все записи памяти агента."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return
    
    reader = AgentMemoryReader(agent_dir)
    
    if not reader.has_memory:
        console.print(f"[yellow]No memory database found for {agent_id}[/yellow]")
        console.print(f"[dim]Checked: {agent_dir}[/dim]")
        return
    
    # Stats
    stats = reader.get_stats()
    console.print(Panel(
        f"Agent: [cyan]{agent_id}[/cyan]\n"
        f"Entries: [green]{stats.total_entries}[/green]\n"
        f"DB Size: [blue]{stats.db_size_bytes / 1024:.1f} KB[/blue]\n"
        f"DB Path: [dim]{reader.db_path}[/dim]",
        title="Memory Stats"
    ))
    
    # Entries
    entries = list(reader.iter_entries(limit=limit))
    
    if not entries:
        console.print("[yellow]No entries found[/yellow]")
        return
    
    table = Table(title=f"Memory Entries (showing {len(entries)})")
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Content", style="white", width=60 if not full else None)
    table.add_column("Timestamp", style="dim", width=19)
    
    for entry in entries:
        content = entry.content if full else entry.preview
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "-"
        table.add_row(entry.id[:8], content, ts)
    
    console.print(table)


def cmd_memory_search(agent_id: str, query: str, limit: int = 20):
    """Поиск по памяти агента."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return
    
    reader = AgentMemoryReader(agent_dir)
    
    if not reader.has_memory:
        console.print(f"[yellow]No memory database found[/yellow]")
        return
    
    console.print(f"[cyan]Searching for:[/cyan] {query}")
    
    results = reader.search(query, limit=limit)
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    console.print(f"[green]Found {len(results)} results[/green]\n")
    
    for i, entry in enumerate(results, 1):
        # Highlight query in content
        highlighted = entry.content.replace(
            query, f"[bold red]{query}[/bold red]"
        )
        
        console.print(Panel(
            highlighted[:500] + ("..." if len(entry.content) > 500 else ""),
            title=f"[{i}] ID: {entry.id[:8]}",
            border_style="blue"
        ))


def cmd_memory_recent(agent_id: str, n: int = 10):
    """Показать последние N записей."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return
    
    reader = AgentMemoryReader(agent_dir)
    
    if not reader.has_memory:
        console.print(f"[yellow]No memory database found[/yellow]")
        return
    
    entries = reader.get_recent(n)
    
    console.print(f"[bold]Last {len(entries)} memories for {agent_id}[/bold]\n")
    
    for entry in entries:
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "unknown"
        console.print(f"[dim]{ts}[/dim] [cyan]#{entry.id[:8]}[/cyan]")
        console.print(f"  {entry.preview}")
        console.print()


def cmd_memory_export(agent_id: str, output: Optional[str] = None):
    """Экспортировать память в JSON."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return
    
    reader = AgentMemoryReader(agent_dir)
    
    if not reader.has_memory:
        console.print(f"[yellow]No memory database found[/yellow]")
        return
    
    output_path = Path(output) if output else Path(f"memory-{agent_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    
    count = reader.export_json(output_path)
    console.print(f"[green]✓[/green] Exported {count} entries to {output_path}")


def cmd_memory_compare(agent_ids: List[str]):
    """Сравнить память между агентами (проверка изоляции)."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)

    agent_dirs = []
    for aid in agent_ids:
        agent_dir = agent_root / aid
        if agent_dir.exists():
            agent_dirs.append(agent_dir)
        else:
            console.print(f"[yellow]Agent not found: {aid}[/yellow]")
    
    if len(agent_dirs) < 2:
        console.print("[red]Need at least 2 agents to compare[/red]")
        return
    
    console.print(f"[bold]Comparing memory isolation for {len(agent_dirs)} agents...[/bold]\n")
    
    result = compare_agent_memories(agent_dirs)
    
    # Agent stats
    table = Table(title="Agent Memory Stats")
    table.add_column("Agent", style="cyan")
    table.add_column("Status")
    table.add_column("Entries", justify="right")
    table.add_column("Size", justify="right")
    
    for agent_id, info in result["agents"].items():
        status = "[green]OK[/green]" if info["status"] == "ok" else "[yellow]No Memory[/yellow]"
        entries = str(info.get("entries", 0))
        size = f"{info.get('db_size', 0) / 1024:.1f} KB"
        table.add_row(agent_id, status, entries, size)
    
    console.print(table)
    
    # Isolation check
    if result["isolation_ok"]:
        console.print(Panel(
            "[green]✓ Memory isolation is correct![/green]\n"
            "No overlapping entries found between agents.",
            title="Isolation Check",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[red]✗ ISOLATION VIOLATION![/red]\n"
            f"Found {len(result['overlaps'])} overlapping entries!",
            title="Isolation Check",
            border_style="red"
        ))
        
        for overlap in result["overlaps"][:5]:
            console.print(f"\n[red]Overlap:[/red] Found in agents: {overlap['found_in_agents']}")
            console.print(f"[dim]Content: {overlap['content_preview']}[/dim]")


def cmd_memory_all():
    """Показать память всех агентов."""
    from .config import load_config
    from .registry import iter_agents

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agents = list(iter_agents(agent_root))

    if not agents:
        console.print("[yellow]No agents found[/yellow]")
        return

    table = Table(title="All Agents Memory")
    table.add_column("Agent", style="cyan")
    table.add_column("Port", justify="right")
    table.add_column("Entries", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("DB Path", style="dim")

    total_entries = 0
    total_size = 0

    for agent in agents:
        agent_dir = agent_root / agent.id
        reader = AgentMemoryReader(agent_dir)

        if reader.has_memory:
            stats = reader.get_stats()
            entries = str(stats.total_entries)
            size = f"{stats.db_size_bytes / 1024:.1f} KB"
            db_path = str(reader.db_path.relative_to(agent_root)) if reader.db_path else "-"
            total_entries += stats.total_entries
            total_size += stats.db_size_bytes
        else:
            entries = "-"
            size = "-"
            db_path = "[yellow]not found[/yellow]"

        port = agent.get_preferred_port() or agent.last_port or 0
        table.add_row(
            agent.id[:15],
            str(port),
            entries,
            size,
            db_path
        )

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {total_entries} entries, {total_size / 1024:.1f} KB")


# ============================================================================
# TYPER CLI APP
# ============================================================================

def create_memory_app():
    """Создать Typer app для команд памяти."""
    import typer
    
    memory_app = typer.Typer(help="Memory inspection and debugging tools")
    
    @memory_app.command("list")
    def list_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID"),
        limit: int = typer.Option(50, "--limit", "-n", help="Max entries to show"),
        full: bool = typer.Option(False, "--full", "-f", help="Show full content"),
    ):
        """List all memory entries for an agent."""
        cmd_memory_list(agent_id, limit, full)
    
    @memory_app.command("search")
    def search_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID"),
        query: str = typer.Argument(..., help="Search query"),
        limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    ):
        """Search memory entries by content."""
        cmd_memory_search(agent_id, query, limit)
    
    @memory_app.command("recent")
    def recent_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID"),
        n: int = typer.Option(10, "--count", "-n", help="Number of recent entries"),
    ):
        """Show most recent memory entries."""
        cmd_memory_recent(agent_id, n)
    
    @memory_app.command("export")
    def export_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    ):
        """Export memory to JSON file."""
        cmd_memory_export(agent_id, output)
    
    @memory_app.command("compare")
    def compare_cmd(
        agent_ids: List[str] = typer.Argument(..., help="Agent IDs to compare"),
    ):
        """Compare memory between agents (isolation check)."""
        cmd_memory_compare(agent_ids)
    
    @memory_app.command("all")
    def all_cmd():
        """Show memory stats for all agents."""
        cmd_memory_all()
    
    return memory_app
