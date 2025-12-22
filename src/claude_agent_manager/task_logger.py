"""
Task Logger - система логирования задач агентов.

Адаптировано из Auto-Claude для claude-agent-manager.

Использование:
    from claude_agent_manager.task_logger import TaskLogger, LogPhase

    logger = TaskLogger(agent_id="agent-123", task_name="add-oauth")
    logger.start_phase(LogPhase.PLANNING)
    logger.log("Analyzing requirements...")
    logger.tool_start("Read", "config.py")
    logger.tool_end("Read", success=True)
    logger.end_phase(LogPhase.PLANNING, success=True)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class LogPhase(str, Enum):
    """Фазы выполнения задачи."""
    ANALYSIS = "analysis"      # Анализ проекта
    PLANNING = "planning"      # Планирование
    CODING = "coding"          # Написание кода
    VALIDATION = "validation"  # Валидация
    REVIEW = "review"          # Review
    MERGE = "merge"            # Merge


class LogEntryType(str, Enum):
    """Типы записей лога."""
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    ERROR = "error"
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"


@dataclass
class LogEntry:
    """Запись в логе."""
    timestamp: str
    type: str
    content: str
    phase: str
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    detail: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict:
        """Конвертировать в словарь."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PhaseStats:
    """Статистика фазы."""
    phase: str
    status: str = "pending"  # pending, active, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    tool_calls: int = 0
    errors: int = 0
    warnings: int = 0
    entries: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "warnings": self.warnings,
            "entries_count": len(self.entries)
        }


@dataclass
class TaskLog:
    """Полный лог задачи."""
    agent_id: str
    task_name: str
    created_at: str
    updated_at: str
    current_phase: Optional[str] = None
    phases: Dict[str, PhaseStats] = field(default_factory=dict)
    total_tool_calls: int = 0
    total_errors: int = 0
    status: str = "running"  # running, completed, failed

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "task_name": self.task_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_phase": self.current_phase,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "total_tool_calls": self.total_tool_calls,
            "total_errors": self.total_errors,
            "status": self.status
        }


class TaskLogger:
    """
    Logger для задач агента.

    Логирует все действия агента в структурированном формате.
    Поддерживает фазы, tool calls, ошибки.
    """

    LOG_FILE = "task_log.json"
    ENTRIES_FILE = "task_entries.jsonl"

    def __init__(
        self,
        agent_id: str,
        task_name: str,
        log_dir: Optional[Path] = None,
        emit_to_console: bool = True
    ):
        self.agent_id = agent_id
        self.task_name = task_name
        self.emit_to_console = emit_to_console

        # Директория для логов
        if log_dir is None:
            log_dir = Path.home() / ".claude-agent-manager" / "logs" / agent_id / task_name
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / self.LOG_FILE
        self.entries_file = self.log_dir / self.ENTRIES_FILE

        # Загружаем или создаём лог
        self.data = self._load_or_create()
        self._tool_start_times: Dict[str, datetime] = {}

    def _timestamp(self) -> str:
        """Текущий timestamp в ISO формате."""
        return datetime.now(timezone.utc).isoformat()

    def _load_or_create(self) -> TaskLog:
        """Загрузить существующий лог или создать новый."""
        if self.log_file.exists():
            try:
                with open(self.log_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Восстанавливаем PhaseStats
                phases = {}
                for phase_name, phase_data in data.get("phases", {}).items():
                    phases[phase_name] = PhaseStats(
                        phase=phase_data["phase"],
                        status=phase_data.get("status", "pending"),
                        started_at=phase_data.get("started_at"),
                        completed_at=phase_data.get("completed_at"),
                        tool_calls=phase_data.get("tool_calls", 0),
                        errors=phase_data.get("errors", 0),
                        warnings=phase_data.get("warnings", 0),
                        entries=[]
                    )

                return TaskLog(
                    agent_id=data["agent_id"],
                    task_name=data["task_name"],
                    created_at=data["created_at"],
                    updated_at=data["updated_at"],
                    current_phase=data.get("current_phase"),
                    phases=phases,
                    total_tool_calls=data.get("total_tool_calls", 0),
                    total_errors=data.get("total_errors", 0),
                    status=data.get("status", "running")
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Создаём новый лог
        now = self._timestamp()
        phases = {phase.value: PhaseStats(phase=phase.value) for phase in LogPhase}

        return TaskLog(
            agent_id=self.agent_id,
            task_name=self.task_name,
            created_at=now,
            updated_at=now,
            phases=phases
        )

    def _save(self) -> None:
        """Сохранить лог."""
        self.data.updated_at = self._timestamp()
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.data.to_dict(), f, indent=2, ensure_ascii=False)

    def _add_entry(self, entry: LogEntry) -> None:
        """Добавить запись в лог."""
        # Добавляем в фазу
        phase_key = entry.phase
        if phase_key in self.data.phases:
            self.data.phases[phase_key].entries.append(entry.to_dict())

        # Записываем в JSONL файл (append)
        with open(self.entries_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        self._save()

    def start_phase(self, phase: LogPhase, message: Optional[str] = None) -> None:
        """
        Начать фазу.

        Args:
            phase: Фаза для начала
            message: Опциональное сообщение
        """
        phase_key = phase.value
        self.data.current_phase = phase_key

        # Обновляем статус фазы
        if phase_key in self.data.phases:
            self.data.phases[phase_key].status = "active"
            self.data.phases[phase_key].started_at = self._timestamp()

        # Добавляем запись
        msg = message or f"Starting {phase_key} phase"
        entry = LogEntry(
            timestamp=self._timestamp(),
            type=LogEntryType.PHASE_START.value,
            content=msg,
            phase=phase_key
        )
        self._add_entry(entry)

        if self.emit_to_console:
            console.print(f"\n[bold cyan]>>> {msg}[/bold cyan]")

    def end_phase(self, phase: LogPhase, success: bool = True, message: Optional[str] = None) -> None:
        """
        Завершить фазу.

        Args:
            phase: Фаза для завершения
            success: Успешно ли завершилась
            message: Опциональное сообщение
        """
        phase_key = phase.value

        # Обновляем статус
        if phase_key in self.data.phases:
            self.data.phases[phase_key].status = "completed" if success else "failed"
            self.data.phases[phase_key].completed_at = self._timestamp()

        # Добавляем запись
        status_text = "Completed" if success else "Failed"
        msg = message or f"{status_text} {phase_key} phase"
        entry = LogEntry(
            timestamp=self._timestamp(),
            type=LogEntryType.PHASE_END.value,
            content=msg,
            phase=phase_key
        )
        self._add_entry(entry)

        if phase == self.data.current_phase:
            self.data.current_phase = None

        if self.emit_to_console:
            color = "green" if success else "red"
            console.print(f"[bold {color}]<<< {msg}[/bold {color}]")

    def log(
        self,
        content: str,
        entry_type: LogEntryType = LogEntryType.TEXT,
        phase: Optional[LogPhase] = None
    ) -> None:
        """
        Логировать сообщение.

        Args:
            content: Текст сообщения
            entry_type: Тип записи
            phase: Фаза (используется текущая если не указана)
        """
        phase_key = (phase.value if phase else self.data.current_phase) or LogPhase.CODING.value

        entry = LogEntry(
            timestamp=self._timestamp(),
            type=entry_type.value,
            content=content,
            phase=phase_key
        )
        self._add_entry(entry)

        # Обновляем счётчики
        if entry_type == LogEntryType.ERROR:
            self.data.total_errors += 1
            if phase_key in self.data.phases:
                self.data.phases[phase_key].errors += 1

        if self.emit_to_console:
            style = {
                LogEntryType.ERROR: "red",
                LogEntryType.SUCCESS: "green",
                LogEntryType.WARNING: "yellow",
                LogEntryType.INFO: "cyan"
            }.get(entry_type, "white")
            console.print(f"[{style}]{content}[/{style}]")

    def log_error(self, content: str) -> None:
        """Логировать ошибку."""
        self.log(content, LogEntryType.ERROR)

    def log_success(self, content: str) -> None:
        """Логировать успех."""
        self.log(content, LogEntryType.SUCCESS)

    def log_info(self, content: str) -> None:
        """Логировать информацию."""
        self.log(content, LogEntryType.INFO)

    def log_warning(self, content: str) -> None:
        """Логировать предупреждение."""
        self.log(content, LogEntryType.WARNING)

    def tool_start(self, tool_name: str, tool_input: Optional[str] = None) -> None:
        """
        Логировать начало tool call.

        Args:
            tool_name: Название инструмента
            tool_input: Входные данные
        """
        phase_key = self.data.current_phase or LogPhase.CODING.value

        # Сохраняем время начала
        self._tool_start_times[tool_name] = datetime.now(timezone.utc)

        # Truncate long inputs
        display_input = tool_input
        if display_input and len(display_input) > 100:
            display_input = display_input[:97] + "..."

        entry = LogEntry(
            timestamp=self._timestamp(),
            type=LogEntryType.TOOL_START.value,
            content=f"[{tool_name}] {display_input or 'started'}",
            phase=phase_key,
            tool_name=tool_name,
            tool_input=display_input
        )
        self._add_entry(entry)

        if self.emit_to_console:
            console.print(f"[dim][Tool: {tool_name}][/dim]")

    def tool_end(
        self,
        tool_name: str,
        success: bool = True,
        result: Optional[str] = None,
        detail: Optional[str] = None
    ) -> None:
        """
        Логировать завершение tool call.

        Args:
            tool_name: Название инструмента
            success: Успешно ли выполнился
            result: Краткий результат
            detail: Полный результат
        """
        phase_key = self.data.current_phase or LogPhase.CODING.value

        # Вычисляем duration
        duration_ms = None
        if tool_name in self._tool_start_times:
            start = self._tool_start_times.pop(tool_name)
            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        # Обновляем счётчики
        self.data.total_tool_calls += 1
        if phase_key in self.data.phases:
            self.data.phases[phase_key].tool_calls += 1

        # Truncate result
        display_result = result
        if display_result and len(display_result) > 100:
            display_result = display_result[:97] + "..."

        status = "Done" if success else "Error"
        content = f"[{tool_name}] {status}"
        if display_result:
            content += f": {display_result}"

        entry = LogEntry(
            timestamp=self._timestamp(),
            type=LogEntryType.TOOL_END.value,
            content=content,
            phase=phase_key,
            tool_name=tool_name,
            detail=detail[:5000] if detail and len(detail) > 5000 else detail,
            duration_ms=duration_ms
        )
        self._add_entry(entry)

    def complete(self, success: bool = True) -> None:
        """
        Отметить задачу как завершённую.

        Args:
            success: Успешно ли завершилась
        """
        self.data.status = "completed" if success else "failed"
        self._save()

        if self.emit_to_console:
            color = "green" if success else "red"
            status = "COMPLETED" if success else "FAILED"
            console.print(Panel(
                f"Task {status}\n\n"
                f"Total tool calls: {self.data.total_tool_calls}\n"
                f"Total errors: {self.data.total_errors}",
                title=f"Task: {self.task_name}",
                border_style=color
            ))

    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку по задаче."""
        phases_summary = []
        for phase in LogPhase:
            phase_data = self.data.phases.get(phase.value)
            if phase_data:
                phases_summary.append({
                    "phase": phase.value,
                    "status": phase_data.status,
                    "tool_calls": phase_data.tool_calls,
                    "errors": phase_data.errors
                })

        return {
            "agent_id": self.data.agent_id,
            "task_name": self.data.task_name,
            "status": self.data.status,
            "current_phase": self.data.current_phase,
            "total_tool_calls": self.data.total_tool_calls,
            "total_errors": self.data.total_errors,
            "phases": phases_summary,
            "created_at": self.data.created_at,
            "updated_at": self.data.updated_at
        }


def print_task_summary(logger: TaskLogger) -> None:
    """Красиво вывести сводку по задаче."""
    summary = logger.get_summary()

    table = Table(title=f"Task: {summary['task_name']}")
    table.add_column("Phase", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Tool Calls", justify="right")
    table.add_column("Errors", justify="right")

    for phase in summary["phases"]:
        status_color = {
            "completed": "green",
            "active": "blue",
            "failed": "red",
            "pending": "dim"
        }.get(phase["status"], "white")

        table.add_row(
            phase["phase"],
            f"[{status_color}]{phase['status']}[/{status_color}]",
            str(phase["tool_calls"]),
            str(phase["errors"]) if phase["errors"] > 0 else "-"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {summary['total_tool_calls']} tool calls, {summary['total_errors']} errors[/dim]")
