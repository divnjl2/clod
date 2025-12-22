"""
Metrics Dashboard - Terminal-based visualization.

Визуализация метрик в терминале с ASCII графиками.

Использование:
    from claude_agent_manager.monitoring.dashboard import MetricsDashboard

    dashboard = MetricsDashboard(collector)
    dashboard.render()  # Отрисовать полный дашборд
    dashboard.render_chart(ChartType.BAR, data)  # Отдельный график
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .metrics import MetricsCollector, TimeRange, PerformanceMetrics, AgentMetrics

console = Console()


class ChartType(str, Enum):
    """Типы графиков."""
    BAR = "bar"
    LINE = "line"
    SPARKLINE = "sparkline"
    HEATMAP = "heatmap"
    PIE = "pie"


@dataclass
class DashboardConfig:
    """Конфигурация дашборда."""
    title: str = "Claude Agent Manager - Metrics Dashboard"
    refresh_interval: int = 5  # seconds
    time_range: TimeRange = TimeRange.DAY
    show_agents: bool = True
    show_tools: bool = True
    show_trends: bool = True
    show_errors: bool = True
    max_agents: int = 10
    max_tools: int = 10
    chart_width: int = 50
    chart_height: int = 10


class AsciiChart:
    """Генератор ASCII графиков."""

    BLOCKS = " ▁▂▃▄▅▆▇█"
    BAR_CHARS = "█▓▒░"

    @staticmethod
    def sparkline(values: List[float], width: int = 50) -> str:
        """
        Создать sparkline график.

        Args:
            values: Список значений
            width: Ширина графика

        Returns:
            Строка с ASCII sparkline
        """
        if not values:
            return "No data"

        # Нормализуем значения
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val if max_val != min_val else 1

        # Ресемплируем если нужно
        if len(values) > width:
            step = len(values) / width
            values = [values[int(i * step)] for i in range(width)]
        elif len(values) < width:
            # Растягиваем
            step = width / len(values)
            new_values = []
            for i in range(width):
                idx = min(int(i / step), len(values) - 1)
                new_values.append(values[idx])
            values = new_values

        # Конвертируем в блоки
        blocks = AsciiChart.BLOCKS
        result = []
        for v in values:
            normalized = (v - min_val) / range_val
            idx = int(normalized * (len(blocks) - 1))
            result.append(blocks[idx])

        return "".join(result)

    @staticmethod
    def bar_chart(
        data: Dict[str, float],
        width: int = 40,
        max_label_width: int = 15
    ) -> List[str]:
        """
        Создать горизонтальный bar chart.

        Args:
            data: Словарь {label: value}
            width: Ширина полосы
            max_label_width: Макс ширина лейбла

        Returns:
            Список строк графика
        """
        if not data:
            return ["No data"]

        max_val = max(data.values()) if data.values() else 1
        lines = []

        for label, value in data.items():
            # Обрезаем label
            short_label = label[:max_label_width].ljust(max_label_width)

            # Вычисляем ширину полосы
            bar_width = int((value / max_val) * width) if max_val > 0 else 0

            bar = "█" * bar_width
            lines.append(f"{short_label} │{bar} {value:.0f}")

        return lines

    @staticmethod
    def vertical_bar_chart(
        data: Dict[str, float],
        height: int = 10,
        width: int = 50
    ) -> List[str]:
        """
        Создать вертикальный bar chart.

        Args:
            data: Словарь {label: value}
            height: Высота графика
            width: Ширина графика

        Returns:
            Список строк графика
        """
        if not data:
            return ["No data"]

        values = list(data.values())
        labels = list(data.keys())
        max_val = max(values) if values else 1

        # Ширина одной колонки
        col_width = max(2, width // len(data))

        lines = []

        # Рисуем бары сверху вниз
        for row in range(height, 0, -1):
            line = ""
            threshold = (row / height) * max_val

            for val in values:
                if val >= threshold:
                    line += "█" * (col_width - 1) + " "
                else:
                    line += " " * col_width

            lines.append(line)

        # Добавляем ось X
        lines.append("─" * (col_width * len(data)))

        # Добавляем labels
        label_line = ""
        for label in labels:
            short = label[:col_width - 1].center(col_width)
            label_line += short

        lines.append(label_line)

        return lines

    @staticmethod
    def pie_chart(data: Dict[str, float], radius: int = 5) -> List[str]:
        """
        Создать ASCII pie chart (упрощённый).

        Args:
            data: Словарь {label: value}
            radius: Радиус

        Returns:
            Список строк с легендой
        """
        if not data:
            return ["No data"]

        total = sum(data.values())
        if total == 0:
            return ["No data"]

        lines = []
        chars = "●○◐◑◒◓"

        for i, (label, value) in enumerate(data.items()):
            pct = (value / total) * 100
            char = chars[i % len(chars)]
            lines.append(f"{char} {label}: {value:.0f} ({pct:.1f}%)")

        return lines

    @staticmethod
    def heatmap(
        data: List[List[float]],
        row_labels: List[str],
        col_labels: List[str]
    ) -> List[str]:
        """
        Создать ASCII heatmap.

        Args:
            data: 2D массив значений
            row_labels: Метки строк
            col_labels: Метки колонок

        Returns:
            Список строк heatmap
        """
        if not data or not data[0]:
            return ["No data"]

        # Символы для интенсивности
        intensity = " ░▒▓█"

        # Нормализуем
        flat = [v for row in data for v in row]
        min_val = min(flat)
        max_val = max(flat)
        range_val = max_val - min_val if max_val != min_val else 1

        lines = []

        # Заголовок колонок
        header = "      " + " ".join(c[:3].center(3) for c in col_labels)
        lines.append(header)

        for i, row in enumerate(data):
            label = row_labels[i][:5].ljust(5)
            cells = ""

            for v in row:
                normalized = (v - min_val) / range_val
                idx = int(normalized * (len(intensity) - 1))
                cells += f" {intensity[idx] * 3}"

            lines.append(f"{label}{cells}")

        return lines


class MetricsDashboard:
    """
    Дашборд метрик с Rich визуализацией.

    Отображает статистику, графики и тренды в терминале.
    """

    def __init__(
        self,
        collector: MetricsCollector,
        config: Optional[DashboardConfig] = None
    ):
        self.collector = collector
        self.config = config or DashboardConfig()

    def render(self) -> None:
        """Отрисовать полный дашборд."""
        console.clear()

        # Заголовок
        console.print(Panel(
            f"[bold cyan]{self.config.title}[/bold cyan]\n"
            f"Time Range: {self.config.time_range.value} | "
            f"Updated: {datetime.now().strftime('%H:%M:%S')}",
            border_style="cyan"
        ))

        # Общая статистика
        perf = self.collector.get_performance_metrics(self.config.time_range)
        self._render_overview(perf)

        # Графики
        if self.config.show_trends:
            self._render_trends()

        # Топ агентов
        if self.config.show_agents:
            self._render_agents()

        # Инструменты
        if self.config.show_tools:
            self._render_tools(perf)

        # Ошибки
        if self.config.show_errors and perf.error_distribution:
            self._render_errors(perf)

    def _render_overview(self, perf: PerformanceMetrics) -> None:
        """Отрисовать обзорную панель."""
        # Создаём таблицу с ключевыми метриками
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric")
        table.add_column("Value", justify="right", style="bold")
        table.add_column("Metric2")
        table.add_column("Value2", justify="right", style="bold")

        table.add_row(
            "Total Agents:", str(perf.total_agents),
            "Success Rate:", f"{perf.success_rate:.1f}%"
        )
        table.add_row(
            "Total Tasks:", str(perf.total_tasks),
            "Error Rate:", f"{perf.error_rate:.1f}%"
        )
        table.add_row(
            "Tool Calls:", str(perf.total_tool_calls),
            "Avg Duration:", f"{perf.avg_task_duration_ms:.0f}ms"
        )

        console.print(Panel(table, title="Overview", border_style="green"))

    def _render_trends(self) -> None:
        """Отрисовать тренды."""
        trends = self.collector.get_trends(self.config.time_range)

        if not trends:
            return

        values = [t["count"] for t in trends]
        sparkline = AsciiChart.sparkline(values, self.config.chart_width)

        # Подписи
        if trends:
            first = trends[0]["period"].split()[-1] if " " in trends[0]["period"] else trends[0]["period"]
            last = trends[-1]["period"].split()[-1] if " " in trends[-1]["period"] else trends[-1]["period"]
            label = f"{first} → {last}"
        else:
            label = ""

        console.print(Panel(
            f"[cyan]{sparkline}[/cyan]\n"
            f"[dim]{label}[/dim]\n"
            f"Min: {min(values) if values else 0} | "
            f"Max: {max(values) if values else 0} | "
            f"Avg: {sum(values)/len(values) if values else 0:.1f}",
            title="Activity Trend",
            border_style="blue"
        ))

    def _render_agents(self) -> None:
        """Отрисовать статистику агентов."""
        agents = self.collector.get_all_agents()[:self.config.max_agents]

        if not agents:
            return

        table = Table(title="Agent Statistics")
        table.add_column("Agent", style="cyan")
        table.add_column("Tasks", justify="right")
        table.add_column("Success", justify="right")
        table.add_column("Tools", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Rate", justify="right")

        for agent_id in agents:
            stats = self.collector.get_agent_stats(agent_id, self.config.time_range)

            # Цвет success rate
            rate_color = "green" if stats.success_rate >= 80 else "yellow" if stats.success_rate >= 50 else "red"

            table.add_row(
                agent_id[:20],
                str(stats.total_tasks),
                str(stats.completed_tasks),
                str(stats.total_tool_calls),
                str(stats.total_errors),
                f"[{rate_color}]{stats.success_rate:.0f}%[/{rate_color}]"
            )

        console.print(table)

    def _render_tools(self, perf: PerformanceMetrics) -> None:
        """Отрисовать распределение инструментов."""
        tools = dict(list(perf.tool_distribution.items())[:self.config.max_tools])

        if not tools:
            return

        chart_lines = AsciiChart.bar_chart(tools, width=30)

        console.print(Panel(
            "\n".join(chart_lines),
            title="Tool Usage",
            border_style="magenta"
        ))

    def _render_errors(self, perf: PerformanceMetrics) -> None:
        """Отрисовать распределение ошибок."""
        errors = dict(list(perf.error_distribution.items())[:5])

        if not errors:
            return

        pie_lines = AsciiChart.pie_chart(errors)

        console.print(Panel(
            "\n".join(pie_lines),
            title="Error Distribution",
            border_style="red"
        ))

    def render_live(self, duration: int = 60) -> None:
        """
        Отрисовать дашборд с live-обновлением.

        Args:
            duration: Длительность в секундах
        """
        import time

        end_time = time.time() + duration

        with Live(console=console, refresh_per_second=1) as live:
            while time.time() < end_time:
                # Генерируем контент
                output = self._generate_live_content()
                live.update(output)
                time.sleep(self.config.refresh_interval)

    def _generate_live_content(self) -> Group:
        """Сгенерировать контент для live-режима."""
        perf = self.collector.get_performance_metrics(self.config.time_range)
        trends = self.collector.get_trends(self.config.time_range)
        recent = self.collector.get_recent_activity(limit=5)

        # Заголовок
        header = Panel(
            f"[bold cyan]{self.config.title}[/bold cyan]\n"
            f"Time Range: {self.config.time_range.value} | "
            f"Updated: {datetime.now().strftime('%H:%M:%S')}",
            border_style="cyan"
        )

        # Ключевые метрики
        metrics_table = Table(show_header=False, box=None)
        metrics_table.add_column("K1")
        metrics_table.add_column("V1", justify="right", style="bold cyan")
        metrics_table.add_column("K2")
        metrics_table.add_column("V2", justify="right", style="bold green")
        metrics_table.add_column("K3")
        metrics_table.add_column("V3", justify="right", style="bold yellow")

        metrics_table.add_row(
            "Agents", str(perf.total_agents),
            "Tasks", str(perf.total_tasks),
            "Success", f"{perf.success_rate:.0f}%"
        )

        # Sparkline
        values = [t["count"] for t in trends] if trends else [0]
        sparkline = AsciiChart.sparkline(values, 60)
        trend_panel = Panel(f"[cyan]{sparkline}[/cyan]", title="Trend", border_style="blue")

        # Последняя активность
        activity_lines = []
        for act in recent:
            ts = act["timestamp"].split("T")[1][:8]
            activity_lines.append(
                f"[dim]{ts}[/dim] [{act['type']}] {act['agent_id']}"
            )

        activity_panel = Panel(
            "\n".join(activity_lines) if activity_lines else "No recent activity",
            title="Recent Activity",
            border_style="green"
        )

        return Group(header, metrics_table, trend_panel, activity_panel)

    def render_chart(
        self,
        chart_type: ChartType,
        data: Dict[str, float],
        title: str = "Chart"
    ) -> None:
        """
        Отрисовать отдельный график.

        Args:
            chart_type: Тип графика
            data: Данные
            title: Заголовок
        """
        if chart_type == ChartType.BAR:
            lines = AsciiChart.bar_chart(data, self.config.chart_width)
        elif chart_type == ChartType.SPARKLINE:
            lines = [AsciiChart.sparkline(list(data.values()), self.config.chart_width)]
        elif chart_type == ChartType.PIE:
            lines = AsciiChart.pie_chart(data)
        else:
            lines = AsciiChart.bar_chart(data)

        console.print(Panel("\n".join(lines), title=title))


def render_dashboard(
    collector: MetricsCollector,
    time_range: TimeRange = TimeRange.DAY,
    live: bool = False
) -> None:
    """
    Быстрый рендер дашборда.

    Args:
        collector: MetricsCollector
        time_range: Временной диапазон
        live: Включить live-режим
    """
    config = DashboardConfig(time_range=time_range)
    dashboard = MetricsDashboard(collector, config)

    if live:
        dashboard.render_live()
    else:
        dashboard.render()
