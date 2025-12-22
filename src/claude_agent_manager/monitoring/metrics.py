"""
Advanced Metrics Collection System.

Собирает и анализирует метрики работы агентов.

Использование:
    from claude_agent_manager.monitoring.metrics import MetricsCollector

    collector = MetricsCollector(db_path="metrics.db")

    # Record metrics
    collector.record_task_start("agent-1", "implement-feature")
    collector.record_tool_call("agent-1", "Read", duration_ms=150)
    collector.record_task_complete("agent-1", success=True)

    # Get analytics
    stats = collector.get_agent_stats("agent-1")
    trends = collector.get_trends(TimeRange.WEEK)
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from contextlib import contextmanager

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class MetricType(str, Enum):
    """Типы метрик."""
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    TOKEN_USAGE = "token_usage"
    LATENCY = "latency"
    VALIDATION = "validation"
    MEMORY_ACCESS = "memory_access"


class TimeRange(str, Enum):
    """Временные диапазоны для аналитики."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


@dataclass
class AgentMetrics:
    """Метрики отдельного агента."""
    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tool_calls: int = 0
    total_errors: int = 0
    avg_task_duration_ms: float = 0.0
    avg_tools_per_task: float = 0.0
    success_rate: float = 0.0
    most_used_tools: List[Tuple[str, int]] = field(default_factory=list)
    total_tokens: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionMetrics:
    """Метрики сессии."""
    session_id: str
    agent_id: str
    start_time: str
    end_time: Optional[str] = None
    tasks_completed: int = 0
    tool_calls: int = 0
    errors: int = 0
    duration_ms: int = 0
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """Метрики производительности."""
    time_range: str
    total_agents: int = 0
    total_tasks: int = 0
    total_tool_calls: int = 0
    avg_task_duration_ms: float = 0.0
    avg_tools_per_task: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    peak_hour: Optional[int] = None
    tool_distribution: Dict[str, int] = field(default_factory=dict)
    error_distribution: Dict[str, int] = field(default_factory=dict)
    tasks_by_day: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class MetricsCollector:
    """
    Сборщик и анализатор метрик.

    Использует SQLite для хранения метрик с возможностью
    агрегации и аналитики.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".claude-agent-manager" / "metrics.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._active_tasks: Dict[str, datetime] = {}
        self._active_tools: Dict[str, datetime] = {}

    def _init_db(self) -> None:
        """Инициализация базы данных."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    value REAL,
                    metadata TEXT,
                    session_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_metrics_agent
                ON metrics(agent_id);

                CREATE INDEX IF NOT EXISTS idx_metrics_type
                ON metrics(metric_type);

                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                ON metrics(timestamp);

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    agent_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    task_name TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    tool_calls INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    session_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_agent
                ON tasks(agent_id);
            """)

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для соединения с БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        """Текущее время в ISO формате."""
        return datetime.now().isoformat()

    def record(
        self,
        agent_id: str,
        metric_type: MetricType,
        value: float = 1.0,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Записать метрику.

        Args:
            agent_id: ID агента
            metric_type: Тип метрики
            value: Значение
            metadata: Дополнительные данные
            session_id: ID сессии
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO metrics (timestamp, agent_id, metric_type, value, metadata, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._now(),
                    agent_id,
                    metric_type.value,
                    value,
                    json.dumps(metadata) if metadata else None,
                    session_id
                )
            )

    def record_task_start(
        self,
        agent_id: str,
        task_name: str,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Записать начало задачи."""
        if task_id is None:
            task_id = f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        self._active_tasks[f"{agent_id}:{task_id}"] = datetime.now()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, agent_id, task_name, start_time, session_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, agent_id, task_name, self._now(), session_id)
            )

        self.record(
            agent_id,
            MetricType.TASK_START,
            metadata={"task_name": task_name, "task_id": task_id},
            session_id=session_id
        )

        return task_id

    def record_task_complete(
        self,
        agent_id: str,
        task_id: str,
        success: bool = True,
        session_id: Optional[str] = None
    ) -> None:
        """Записать завершение задачи."""
        key = f"{agent_id}:{task_id}"
        duration_ms = 0

        if key in self._active_tasks:
            start = self._active_tasks.pop(key)
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        status = "completed" if success else "failed"
        metric_type = MetricType.TASK_COMPLETE if success else MetricType.TASK_FAIL

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET end_time = ?, status = ?
                WHERE task_id = ? AND agent_id = ?
                """,
                (self._now(), status, task_id, agent_id)
            )

        self.record(
            agent_id,
            metric_type,
            value=duration_ms,
            metadata={"task_id": task_id, "duration_ms": duration_ms},
            session_id=session_id
        )

    def record_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        duration_ms: int = 0,
        success: bool = True,
        session_id: Optional[str] = None
    ) -> None:
        """Записать вызов инструмента."""
        self.record(
            agent_id,
            MetricType.TOOL_CALL,
            value=duration_ms,
            metadata={"tool": tool_name, "success": success},
            session_id=session_id
        )

        # Обновляем счётчик в активной задаче
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET tool_calls = tool_calls + 1
                WHERE id = (
                    SELECT id FROM tasks
                    WHERE agent_id = ? AND status = 'running'
                    ORDER BY start_time DESC
                    LIMIT 1
                )
                """,
                (agent_id,)
            )

    def record_error(
        self,
        agent_id: str,
        error_type: str,
        error_message: str,
        session_id: Optional[str] = None
    ) -> None:
        """Записать ошибку."""
        self.record(
            agent_id,
            MetricType.ERROR,
            metadata={"type": error_type, "message": error_message},
            session_id=session_id
        )

        # Обновляем счётчик ошибок
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET errors = errors + 1
                WHERE id = (
                    SELECT id FROM tasks
                    WHERE agent_id = ? AND status = 'running'
                    ORDER BY start_time DESC
                    LIMIT 1
                )
                """,
                (agent_id,)
            )

    def record_token_usage(
        self,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
        session_id: Optional[str] = None
    ) -> None:
        """Записать использование токенов."""
        total = input_tokens + output_tokens
        self.record(
            agent_id,
            MetricType.TOKEN_USAGE,
            value=total,
            metadata={"input": input_tokens, "output": output_tokens},
            session_id=session_id
        )

    def record_validation(
        self,
        agent_id: str,
        passed: bool,
        issues_count: int = 0,
        session_id: Optional[str] = None
    ) -> None:
        """Записать результат валидации."""
        self.record(
            agent_id,
            MetricType.VALIDATION,
            value=1 if passed else 0,
            metadata={"issues": issues_count},
            session_id=session_id
        )

    def get_agent_stats(
        self,
        agent_id: str,
        time_range: TimeRange = TimeRange.ALL
    ) -> AgentMetrics:
        """
        Получить статистику по агенту.

        Args:
            agent_id: ID агента
            time_range: Временной диапазон

        Returns:
            AgentMetrics с агрегированной статистикой
        """
        time_filter = self._get_time_filter(time_range)
        # Для tasks используем start_time вместо timestamp
        task_time_filter = time_filter.replace("timestamp", "start_time")

        with self._get_connection() as conn:
            # Базовая статистика задач
            task_stats = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(tool_calls) as total_tools,
                    SUM(errors) as total_errors
                FROM tasks
                WHERE agent_id = ? {task_time_filter}
                """,
                (agent_id,)
            ).fetchone()

            # Средняя длительность задач
            durations = conn.execute(
                f"""
                SELECT value FROM metrics
                WHERE agent_id = ?
                AND metric_type = 'task_complete'
                {time_filter}
                """,
                (agent_id,)
            ).fetchall()

            avg_duration = 0.0
            if durations:
                values = [r["value"] for r in durations if r["value"]]
                if values:
                    avg_duration = statistics.mean(values)

            # Наиболее используемые инструменты
            tools = conn.execute(
                f"""
                SELECT
                    json_extract(metadata, '$.tool') as tool,
                    COUNT(*) as count
                FROM metrics
                WHERE agent_id = ?
                AND metric_type = 'tool_call'
                AND metadata IS NOT NULL
                {time_filter}
                GROUP BY tool
                ORDER BY count DESC
                LIMIT 10
                """,
                (agent_id,)
            ).fetchall()

            # Токены
            tokens = conn.execute(
                f"""
                SELECT SUM(value) as total FROM metrics
                WHERE agent_id = ? AND metric_type = 'token_usage'
                {time_filter}
                """,
                (agent_id,)
            ).fetchone()

            # Первое и последнее появление
            times = conn.execute(
                """
                SELECT MIN(timestamp) as first, MAX(timestamp) as last
                FROM metrics WHERE agent_id = ?
                """,
                (agent_id,)
            ).fetchone()

            total_tasks = task_stats["total"] or 0
            completed = task_stats["completed"] or 0

            return AgentMetrics(
                agent_id=agent_id,
                total_tasks=total_tasks,
                completed_tasks=completed,
                failed_tasks=task_stats["failed"] or 0,
                total_tool_calls=task_stats["total_tools"] or 0,
                total_errors=task_stats["total_errors"] or 0,
                avg_task_duration_ms=avg_duration,
                avg_tools_per_task=(
                    (task_stats["total_tools"] or 0) / total_tasks
                    if total_tasks > 0 else 0
                ),
                success_rate=(
                    completed / total_tasks * 100
                    if total_tasks > 0 else 0
                ),
                most_used_tools=[
                    (r["tool"], r["count"]) for r in tools if r["tool"]
                ],
                total_tokens=int(tokens["total"] or 0),
                first_seen=times["first"],
                last_seen=times["last"]
            )

    def get_all_agents(self) -> List[str]:
        """Получить список всех агентов."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT agent_id FROM metrics ORDER BY agent_id"
            ).fetchall()
            return [r["agent_id"] for r in rows]

    def get_performance_metrics(
        self,
        time_range: TimeRange = TimeRange.WEEK
    ) -> PerformanceMetrics:
        """
        Получить общие метрики производительности.

        Args:
            time_range: Временной диапазон

        Returns:
            PerformanceMetrics с агрегированной статистикой
        """
        time_filter = self._get_time_filter(time_range)

        with self._get_connection() as conn:
            # Общая статистика
            general = conn.execute(
                f"""
                SELECT
                    COUNT(DISTINCT agent_id) as agents,
                    COUNT(CASE WHEN metric_type IN ('task_complete', 'task_fail')
                          THEN 1 END) as tasks,
                    COUNT(CASE WHEN metric_type = 'tool_call' THEN 1 END) as tools,
                    COUNT(CASE WHEN metric_type = 'task_complete' THEN 1 END) as success,
                    COUNT(CASE WHEN metric_type = 'error' THEN 1 END) as errors
                FROM metrics
                WHERE 1=1 {time_filter}
                """
            ).fetchone()

            # Средняя длительность
            durations = conn.execute(
                f"""
                SELECT AVG(value) as avg_duration FROM metrics
                WHERE metric_type = 'task_complete' {time_filter}
                """
            ).fetchone()

            # Распределение инструментов
            tools_dist = conn.execute(
                f"""
                SELECT
                    json_extract(metadata, '$.tool') as tool,
                    COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'tool_call'
                AND metadata IS NOT NULL
                {time_filter}
                GROUP BY tool
                ORDER BY count DESC
                """
            ).fetchall()

            # Распределение ошибок
            errors_dist = conn.execute(
                f"""
                SELECT
                    json_extract(metadata, '$.type') as error_type,
                    COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'error'
                AND metadata IS NOT NULL
                {time_filter}
                GROUP BY error_type
                ORDER BY count DESC
                """
            ).fetchall()

            # Задачи по дням
            tasks_by_day = conn.execute(
                f"""
                SELECT
                    date(timestamp) as day,
                    COUNT(*) as count
                FROM metrics
                WHERE metric_type IN ('task_complete', 'task_fail')
                {time_filter}
                GROUP BY day
                ORDER BY day
                """
            ).fetchall()

            # Пиковый час
            peak = conn.execute(
                f"""
                SELECT
                    CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                    COUNT(*) as count
                FROM metrics
                WHERE metric_type = 'tool_call'
                {time_filter}
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 1
                """
            ).fetchone()

            total_tasks = general["tasks"] or 0
            success = general["success"] or 0
            errors = general["errors"] or 0

            return PerformanceMetrics(
                time_range=time_range.value,
                total_agents=general["agents"] or 0,
                total_tasks=total_tasks,
                total_tool_calls=general["tools"] or 0,
                avg_task_duration_ms=durations["avg_duration"] or 0,
                avg_tools_per_task=(
                    (general["tools"] or 0) / total_tasks
                    if total_tasks > 0 else 0
                ),
                success_rate=success / total_tasks * 100 if total_tasks > 0 else 0,
                error_rate=errors / total_tasks * 100 if total_tasks > 0 else 0,
                peak_hour=peak["hour"] if peak else None,
                tool_distribution={
                    r["tool"]: r["count"] for r in tools_dist if r["tool"]
                },
                error_distribution={
                    r["error_type"]: r["count"] for r in errors_dist if r["error_type"]
                },
                tasks_by_day={r["day"]: r["count"] for r in tasks_by_day}
            )

    def get_trends(
        self,
        time_range: TimeRange = TimeRange.WEEK,
        metric_type: Optional[MetricType] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить тренды метрик.

        Args:
            time_range: Временной диапазон
            metric_type: Тип метрики (опционально)

        Returns:
            Список точек данных для графика
        """
        time_filter = self._get_time_filter(time_range)
        type_filter = f"AND metric_type = '{metric_type.value}'" if metric_type else ""

        # Определяем группировку по времени
        if time_range == TimeRange.HOUR:
            group_by = "strftime('%Y-%m-%d %H:%M', timestamp)"
            interval = "minute"
        elif time_range == TimeRange.DAY:
            group_by = "strftime('%Y-%m-%d %H:00', timestamp)"
            interval = "hour"
        else:
            group_by = "date(timestamp)"
            interval = "day"

        with self._get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    {group_by} as period,
                    COUNT(*) as count,
                    AVG(value) as avg_value
                FROM metrics
                WHERE 1=1 {time_filter} {type_filter}
                GROUP BY period
                ORDER BY period
                """
            ).fetchall()

            return [
                {
                    "period": r["period"],
                    "count": r["count"],
                    "avg_value": r["avg_value"],
                    "interval": interval
                }
                for r in rows
            ]

    def get_recent_activity(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Получить последнюю активность."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, agent_id, metric_type, value, metadata
                FROM metrics
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

            return [
                {
                    "timestamp": r["timestamp"],
                    "agent_id": r["agent_id"],
                    "type": r["metric_type"],
                    "value": r["value"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {}
                }
                for r in rows
            ]

    def _get_time_filter(self, time_range: TimeRange) -> str:
        """Получить SQL фильтр по времени."""
        if time_range == TimeRange.ALL:
            return ""

        now = datetime.now()

        if time_range == TimeRange.HOUR:
            cutoff = now - timedelta(hours=1)
        elif time_range == TimeRange.DAY:
            cutoff = now - timedelta(days=1)
        elif time_range == TimeRange.WEEK:
            cutoff = now - timedelta(weeks=1)
        elif time_range == TimeRange.MONTH:
            cutoff = now - timedelta(days=30)
        else:
            return ""

        return f"AND timestamp >= '{cutoff.isoformat()}'"

    def cleanup_old_metrics(self, days: int = 90) -> int:
        """
        Удалить старые метрики.

        Args:
            days: Количество дней для хранения

        Returns:
            Количество удалённых записей
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount

            conn.execute(
                "DELETE FROM tasks WHERE start_time < ?",
                (cutoff,)
            )

            return deleted

    def export_metrics(
        self,
        output_path: Path,
        time_range: TimeRange = TimeRange.ALL
    ) -> None:
        """Экспортировать метрики в JSON."""
        time_filter = self._get_time_filter(time_range)

        with self._get_connection() as conn:
            metrics = conn.execute(
                f"SELECT * FROM metrics WHERE 1=1 {time_filter}"
            ).fetchall()

            tasks = conn.execute(
                f"SELECT * FROM tasks WHERE 1=1 {time_filter.replace('timestamp', 'start_time')}"
            ).fetchall()

        data = {
            "exported_at": self._now(),
            "time_range": time_range.value,
            "metrics": [dict(r) for r in metrics],
            "tasks": [dict(r) for r in tasks]
        }

        output_path.write_text(json.dumps(data, indent=2, default=str))


def print_metrics_summary(collector: MetricsCollector, agent_id: Optional[str] = None) -> None:
    """
    Красиво вывести сводку метрик.

    Args:
        collector: MetricsCollector
        agent_id: ID агента (опционально, для глобальной сводки)
    """
    if agent_id:
        stats = collector.get_agent_stats(agent_id)

        console.print(Panel(
            f"[bold]Agent:[/bold] {stats.agent_id}\n"
            f"[bold]First seen:[/bold] {stats.first_seen or 'N/A'}\n"
            f"[bold]Last seen:[/bold] {stats.last_seen or 'N/A'}",
            title="Agent Metrics",
            border_style="cyan"
        ))

        table = Table(title="Task Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Tasks", str(stats.total_tasks))
        table.add_row("Completed", str(stats.completed_tasks))
        table.add_row("Failed", str(stats.failed_tasks))
        table.add_row("Success Rate", f"{stats.success_rate:.1f}%")
        table.add_row("Total Tool Calls", str(stats.total_tool_calls))
        table.add_row("Avg Duration", f"{stats.avg_task_duration_ms:.0f}ms")
        table.add_row("Avg Tools/Task", f"{stats.avg_tools_per_task:.1f}")
        table.add_row("Total Tokens", str(stats.total_tokens))

        console.print(table)

        if stats.most_used_tools:
            console.print("\n[bold]Most Used Tools:[/bold]")
            for tool, count in stats.most_used_tools[:5]:
                console.print(f"  {tool}: {count}")
    else:
        perf = collector.get_performance_metrics()

        console.print(Panel(
            f"[bold]Time Range:[/bold] {perf.time_range}\n"
            f"[bold]Total Agents:[/bold] {perf.total_agents}\n"
            f"[bold]Peak Hour:[/bold] {perf.peak_hour or 'N/A'}:00",
            title="Global Performance Metrics",
            border_style="green"
        ))

        table = Table(title="Overview")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Tasks", str(perf.total_tasks))
        table.add_row("Total Tool Calls", str(perf.total_tool_calls))
        table.add_row("Success Rate", f"{perf.success_rate:.1f}%")
        table.add_row("Error Rate", f"{perf.error_rate:.1f}%")
        table.add_row("Avg Duration", f"{perf.avg_task_duration_ms:.0f}ms")
        table.add_row("Avg Tools/Task", f"{perf.avg_tools_per_task:.1f}")

        console.print(table)

        if perf.tool_distribution:
            console.print("\n[bold]Tool Distribution:[/bold]")
            for tool, count in list(perf.tool_distribution.items())[:5]:
                console.print(f"  {tool}: {count}")
