"""
Модуль мониторинга Claude Code агентов.

Собирает и предоставляет полезную информацию:
- Статус агента (running, idle, working)
- Использование токенов
- Текущий контекст (файлы, размер)
- Последние действия
- Системные метрики (CPU, RAM)
- MCP статус
- Ошибки и warnings
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from threading import Thread, Lock
import queue

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TokenUsage:
    """Использование токенов."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ContextInfo:
    """Информация о текущем контексте."""
    files_count: int = 0
    files_list: List[str] = field(default_factory=list)
    estimated_tokens: int = 0
    working_directory: str = ""
    git_branch: str = ""
    git_dirty: bool = False


@dataclass
class AgentAction:
    """Последнее действие агента."""
    timestamp: datetime = field(default_factory=datetime.now)
    action_type: str = ""  # bash, edit, read, write, mcp, think
    description: str = ""
    status: str = "running"  # running, success, error
    duration_ms: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """Системные метрики процесса."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    threads_count: int = 0
    open_files: int = 0
    uptime_seconds: float = 0.0


@dataclass
class MCPStatus:
    """Статус MCP серверов."""
    servers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # server_name -> {status: "connected"|"disconnected"|"error", tools: [...]}


@dataclass
class AgentMetrics:
    """Полные метрики агента."""
    agent_id: str
    status: str = "unknown"  # running, idle, working, stopped, error
    status_detail: str = ""

    # Токены
    tokens: TokenUsage = field(default_factory=TokenUsage)
    session_tokens: TokenUsage = field(default_factory=TokenUsage)

    # Контекст
    context: ContextInfo = field(default_factory=ContextInfo)

    # Действия
    current_action: Optional[AgentAction] = None
    recent_actions: List[AgentAction] = field(default_factory=list)

    # Система
    system: SystemMetrics = field(default_factory=SystemMetrics)

    # MCP
    mcp: MCPStatus = field(default_factory=MCPStatus)

    # Ошибки
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timestamps
    last_update: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None
    started_at: Optional[datetime] = None


# ============================================================================
# METRICS COLLECTOR
# ============================================================================

class AgentMonitor:
    """
    Мониторинг отдельного агента.

    Собирает метрики из различных источников:
    - PM2 logs
    - Process metrics
    - Git status
    - Claude Code API (если доступно)
    """

    def __init__(self, agent_id: str, pm2_name: str, project_path: str, port: int):
        self.agent_id = agent_id
        self.pm2_name = pm2_name
        self.project_path = Path(project_path)
        self.port = port

        self._metrics = AgentMetrics(agent_id=agent_id)
        self._lock = Lock()
        self._callbacks: List[Callable[[AgentMetrics], None]] = []

        # Log parsing state
        self._last_log_position = 0
        self._action_history: List[AgentAction] = []

    @property
    def metrics(self) -> AgentMetrics:
        with self._lock:
            return self._metrics

    def add_callback(self, callback: Callable[[AgentMetrics], None]) -> None:
        """Добавить callback для уведомлений об изменениях."""
        self._callbacks.append(callback)

    def update(self) -> AgentMetrics:
        """Обновить все метрики."""
        with self._lock:
            self._update_status()
            self._update_system_metrics()
            self._update_context()
            self._parse_logs()
            self._metrics.last_update = datetime.now()

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(self._metrics)
            except Exception:
                pass

        return self._metrics

    def _update_status(self) -> None:
        """Обновить статус агента через PM2."""
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
                    if proc.get("name") == self.pm2_name:
                        pm2_status = proc.get("pm2_env", {}).get("status", "unknown")

                        if pm2_status == "online":
                            # Проверяем активность
                            if self._metrics.current_action:
                                self._metrics.status = "working"
                                self._metrics.status_detail = self._metrics.current_action.description[:50]
                            else:
                                idle_time = datetime.now() - (self._metrics.last_activity or datetime.now())
                                if idle_time > timedelta(minutes=5):
                                    self._metrics.status = "idle"
                                    self._metrics.status_detail = f"Idle for {int(idle_time.total_seconds() // 60)}m"
                                else:
                                    self._metrics.status = "running"
                                    self._metrics.status_detail = "Ready"
                        else:
                            self._metrics.status = pm2_status
                            self._metrics.status_detail = pm2_status.capitalize()

                        # Uptime
                        pm_uptime = proc.get("pm2_env", {}).get("pm_uptime", 0)
                        if pm_uptime:
                            self._metrics.started_at = datetime.fromtimestamp(pm_uptime / 1000)

                        return

                self._metrics.status = "stopped"
                self._metrics.status_detail = "Not found in PM2"

        except Exception as e:
            self._metrics.status = "error"
            self._metrics.status_detail = str(e)[:50]

    def _update_system_metrics(self) -> None:
        """Обновить системные метрики процесса."""
        if not HAS_PSUTIL:
            return

        try:
            # Ищем процесс по имени или порту
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    cmdline_str = ' '.join(cmdline)

                    # Ищем claude процесс для нашего агента
                    if 'claude' in cmdline_str.lower() and str(self.port) in cmdline_str:
                        with proc.oneshot():
                            self._metrics.system.cpu_percent = proc.cpu_percent()
                            mem_info = proc.memory_info()
                            self._metrics.system.memory_mb = mem_info.rss / (1024 * 1024)
                            self._metrics.system.memory_percent = proc.memory_percent()
                            self._metrics.system.threads_count = proc.num_threads()

                            try:
                                self._metrics.system.open_files = len(proc.open_files())
                            except (psutil.AccessDenied, psutil.NoSuchProcess):
                                pass

                            create_time = proc.create_time()
                            self._metrics.system.uptime_seconds = time.time() - create_time

                        return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception:
            pass

    def _update_context(self) -> None:
        """Обновить информацию о контексте."""
        self._metrics.context.working_directory = str(self.project_path)

        # Git info
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self._metrics.context.git_branch = result.stdout.strip()

            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=2
            )
            self._metrics.context.git_dirty = bool(result.stdout.strip())

        except Exception:
            pass

    def _parse_logs(self) -> None:
        """Парсить PM2 логи для извлечения действий."""
        try:
            # Получаем последние логи
            result = subprocess.run(
                ["pm2", "logs", self.pm2_name, "--lines", "50", "--nostream", "--raw"],
                capture_output=True,
                text=True,
                shell=True,
                timeout=5
            )

            if result.returncode != 0:
                return

            lines = result.stdout.split('\n')

            for line in lines:
                action = self._parse_log_line(line)
                if action:
                    self._metrics.recent_actions.append(action)
                    self._metrics.last_activity = action.timestamp

                    if action.status == "running":
                        self._metrics.current_action = action
                    elif self._metrics.current_action and action.action_type == self._metrics.current_action.action_type:
                        self._metrics.current_action = None

            # Ограничиваем историю
            self._metrics.recent_actions = self._metrics.recent_actions[-20:]

            # Парсим токены
            self._parse_token_usage(result.stdout)

        except Exception:
            pass

    def _parse_log_line(self, line: str) -> Optional[AgentAction]:
        """Парсить строку лога в действие."""
        if not line.strip():
            return None

        action = AgentAction()

        # Паттерны для разных действий Claude Code
        patterns = [
            (r"Running command: (.+)", "bash", "running"),
            (r"Command completed", "bash", "success"),
            (r"Command failed", "bash", "error"),
            (r"Reading file: (.+)", "read", "success"),
            (r"Writing file: (.+)", "write", "success"),
            (r"Editing file: (.+)", "edit", "running"),
            (r"Edit complete", "edit", "success"),
            (r"Calling MCP tool: (.+)", "mcp", "running"),
            (r"MCP tool result", "mcp", "success"),
            (r"Thinking\.\.\.", "think", "running"),
            (r"tokens? used", "token_update", "success"),
            (r"Error:", "error", "error"),
            (r"Warning:", "warning", "warning"),
        ]

        for pattern, action_type, status in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                action.action_type = action_type
                action.status = status
                action.description = match.group(1) if match.lastindex else action_type

                # Добавляем в ошибки/warnings
                if action_type == "error":
                    self._metrics.errors.append(line[:200])
                    self._metrics.errors = self._metrics.errors[-10:]
                elif action_type == "warning":
                    self._metrics.warnings.append(line[:200])
                    self._metrics.warnings = self._metrics.warnings[-10:]

                return action

        return None

    def _parse_token_usage(self, log_text: str) -> None:
        """Парсить использование токенов из логов."""
        # Паттерны для токенов
        patterns = {
            "input": r"input[_\s]?tokens?:\s*(\d+)",
            "output": r"output[_\s]?tokens?:\s*(\d+)",
            "cache_read": r"cache[_\s]?read[_\s]?tokens?:\s*(\d+)",
            "cache_write": r"cache[_\s]?write[_\s]?tokens?:\s*(\d+)",
        }

        for key, pattern in patterns.items():
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            if matches:
                total = sum(int(m) for m in matches)
                if key == "input":
                    self._metrics.session_tokens.input_tokens = total
                elif key == "output":
                    self._metrics.session_tokens.output_tokens = total
                elif key == "cache_read":
                    self._metrics.session_tokens.cache_read_tokens = total
                elif key == "cache_write":
                    self._metrics.session_tokens.cache_write_tokens = total


# ============================================================================
# MULTI-AGENT MONITOR
# ============================================================================

class MonitoringService:
    """
    Сервис мониторинга всех агентов.

    Запускает фоновый поток для периодического обновления метрик.
    """

    def __init__(self, update_interval: float = 2.0):
        self._monitors: Dict[str, AgentMonitor] = {}
        self._lock = Lock()
        self._running = False
        self._thread: Optional[Thread] = None
        self._update_interval = update_interval
        self._callbacks: List[Callable[[Dict[str, AgentMetrics]], None]] = []

    def add_agent(self, agent_id: str, pm2_name: str, project_path: str, port: int) -> AgentMonitor:
        """Добавить агента для мониторинга."""
        with self._lock:
            if agent_id not in self._monitors:
                monitor = AgentMonitor(agent_id, pm2_name, project_path, port)
                self._monitors[agent_id] = monitor
            return self._monitors[agent_id]

    def remove_agent(self, agent_id: str) -> None:
        """Удалить агента из мониторинга."""
        with self._lock:
            self._monitors.pop(agent_id, None)

    def get_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """Получить метрики агента."""
        with self._lock:
            monitor = self._monitors.get(agent_id)
            return monitor.metrics if monitor else None

    def get_all_metrics(self) -> Dict[str, AgentMetrics]:
        """Получить метрики всех агентов."""
        with self._lock:
            return {aid: m.metrics for aid, m in self._monitors.items()}

    def add_callback(self, callback: Callable[[Dict[str, AgentMetrics]], None]) -> None:
        """Добавить callback для уведомлений."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Запустить фоновый мониторинг."""
        if self._running:
            return

        self._running = True
        self._thread = Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Остановить мониторинг."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Основной цикл мониторинга."""
        while self._running:
            try:
                with self._lock:
                    monitors = list(self._monitors.values())

                for monitor in monitors:
                    try:
                        monitor.update()
                    except Exception:
                        pass

                # Notify callbacks
                all_metrics = self.get_all_metrics()
                for cb in self._callbacks:
                    try:
                        cb(all_metrics)
                    except Exception:
                        pass

            except Exception:
                pass

            time.sleep(self._update_interval)


# ============================================================================
# SINGLETON
# ============================================================================

_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Получить singleton сервиса мониторинга."""
    global _service
    if _service is None:
        _service = MonitoringService()
    return _service
