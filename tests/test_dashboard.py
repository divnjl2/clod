"""
Tests for monitoring/dashboard.py - Metrics Dashboard.

Phase 3: Advanced Features
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.monitoring.metrics import MetricsCollector, MetricType, TimeRange
from claude_agent_manager.monitoring.dashboard import (
    MetricsDashboard,
    DashboardConfig,
    ChartType,
    AsciiChart,
    render_dashboard,
)


class TestChartType:
    """Tests for ChartType enum."""

    def test_chart_types(self):
        """Test chart type values."""
        assert ChartType.BAR.value == "bar"
        assert ChartType.LINE.value == "line"
        assert ChartType.SPARKLINE.value == "sparkline"
        assert ChartType.HEATMAP.value == "heatmap"
        assert ChartType.PIE.value == "pie"


class TestDashboardConfig:
    """Tests for DashboardConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = DashboardConfig()

        assert config.title == "Claude Agent Manager - Metrics Dashboard"
        assert config.refresh_interval == 5
        assert config.time_range == TimeRange.DAY
        assert config.show_agents is True
        assert config.chart_width == 50

    def test_custom_config(self):
        """Test custom configuration."""
        config = DashboardConfig(
            title="Custom Dashboard",
            refresh_interval=10,
            time_range=TimeRange.WEEK,
            max_agents=5
        )

        assert config.title == "Custom Dashboard"
        assert config.time_range == TimeRange.WEEK
        assert config.max_agents == 5


class TestAsciiChart:
    """Tests for AsciiChart class."""

    def test_sparkline_empty(self):
        """Test sparkline with empty data."""
        result = AsciiChart.sparkline([])
        assert result == "No data"

    def test_sparkline_single_value(self):
        """Test sparkline with single value."""
        result = AsciiChart.sparkline([5])
        assert len(result) > 0

    def test_sparkline_multiple_values(self):
        """Test sparkline with multiple values."""
        result = AsciiChart.sparkline([1, 2, 3, 4, 5, 4, 3, 2, 1])
        assert len(result) > 0
        # Should contain block characters
        assert any(c in result for c in " ▁▂▃▄▅▆▇█")

    def test_sparkline_width(self):
        """Test sparkline respects width."""
        result = AsciiChart.sparkline([1, 2, 3, 4, 5], width=10)
        assert len(result) == 10

    def test_sparkline_uniform_values(self):
        """Test sparkline with uniform values."""
        result = AsciiChart.sparkline([5, 5, 5, 5, 5])
        # All should be same character
        assert len(set(result.replace(" ", ""))) <= 1 or result.count(result[0]) == len(result)

    def test_bar_chart_empty(self):
        """Test bar chart with empty data."""
        result = AsciiChart.bar_chart({})
        assert result == ["No data"]

    def test_bar_chart_single(self):
        """Test bar chart with single item."""
        result = AsciiChart.bar_chart({"Test": 100})

        assert len(result) == 1
        assert "Test" in result[0]
        assert "100" in result[0]

    def test_bar_chart_multiple(self):
        """Test bar chart with multiple items."""
        data = {"Read": 100, "Write": 50, "Edit": 75}
        result = AsciiChart.bar_chart(data)

        assert len(result) == 3
        # Bars should be proportional
        assert "█" in "".join(result)

    def test_bar_chart_label_width(self):
        """Test bar chart label truncation."""
        data = {"VeryLongLabelName": 100}
        result = AsciiChart.bar_chart(data, max_label_width=10)

        # Label should be truncated
        assert len(result[0].split("│")[0].strip()) <= 10

    def test_vertical_bar_chart_empty(self):
        """Test vertical bar chart with empty data."""
        result = AsciiChart.vertical_bar_chart({})
        assert result == ["No data"]

    def test_vertical_bar_chart(self):
        """Test vertical bar chart."""
        data = {"A": 10, "B": 5, "C": 8}
        result = AsciiChart.vertical_bar_chart(data, height=5, width=15)

        assert len(result) > 0
        # Should have rows
        assert any("█" in line for line in result)

    def test_pie_chart_empty(self):
        """Test pie chart with empty data."""
        result = AsciiChart.pie_chart({})
        assert result == ["No data"]

    def test_pie_chart_zero_total(self):
        """Test pie chart with zero total."""
        result = AsciiChart.pie_chart({"A": 0, "B": 0})
        assert result == ["No data"]

    def test_pie_chart(self):
        """Test pie chart."""
        data = {"Success": 80, "Failed": 20}
        result = AsciiChart.pie_chart(data)

        assert len(result) == 2
        assert "Success" in result[0]
        assert "80.0%" in result[0]
        assert "Failed" in result[1]
        assert "20.0%" in result[1]

    def test_heatmap_empty(self):
        """Test heatmap with empty data."""
        result = AsciiChart.heatmap([], [], [])
        assert result == ["No data"]

    def test_heatmap(self):
        """Test heatmap."""
        data = [[1, 2, 3], [4, 5, 6]]
        rows = ["Row1", "Row2"]
        cols = ["A", "B", "C"]

        result = AsciiChart.heatmap(data, rows, cols)

        assert len(result) > 0
        # Should have intensity characters
        assert any(c in "".join(result) for c in " ░▒▓█")


class TestMetricsDashboard:
    """Tests for MetricsDashboard class."""

    def test_dashboard_creation(self, temp_dir):
        """Test creating a dashboard."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        dashboard = MetricsDashboard(collector)

        assert dashboard.collector == collector
        assert dashboard.config is not None

    def test_dashboard_with_config(self, temp_dir):
        """Test creating dashboard with custom config."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        config = DashboardConfig(
            title="Custom Title",
            time_range=TimeRange.WEEK
        )

        dashboard = MetricsDashboard(collector, config)

        assert dashboard.config.title == "Custom Title"
        assert dashboard.config.time_range == TimeRange.WEEK

    def test_render_chart_bar(self, temp_dir, capsys):
        """Test rendering bar chart."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)
        dashboard = MetricsDashboard(collector)

        data = {"Read": 100, "Write": 50}
        dashboard.render_chart(ChartType.BAR, data, "Tool Usage")

        captured = capsys.readouterr()
        assert "Tool Usage" in captured.out

    def test_render_chart_sparkline(self, temp_dir, capsys):
        """Test rendering sparkline chart."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)
        dashboard = MetricsDashboard(collector)

        data = {"1": 10, "2": 20, "3": 15, "4": 25}
        dashboard.render_chart(ChartType.SPARKLINE, data, "Trend")

        captured = capsys.readouterr()
        assert "Trend" in captured.out

    def test_render_chart_pie(self, temp_dir, capsys):
        """Test rendering pie chart."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)
        dashboard = MetricsDashboard(collector)

        data = {"Success": 80, "Failed": 20}
        dashboard.render_chart(ChartType.PIE, data, "Status")

        captured = capsys.readouterr()
        assert "Status" in captured.out


class TestRenderDashboard:
    """Tests for render_dashboard function."""

    def test_render_dashboard_basic(self, temp_dir, capsys):
        """Test basic dashboard render."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Add some data
        collector.record("agent-1", MetricType.TASK_START)
        collector.record("agent-1", MetricType.TOOL_CALL)

        render_dashboard(collector, TimeRange.DAY)

        captured = capsys.readouterr()
        # Should have some output
        assert len(captured.out) > 0

    def test_render_dashboard_empty(self, temp_dir, capsys):
        """Test dashboard render with no data."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        render_dashboard(collector, TimeRange.DAY)

        captured = capsys.readouterr()
        # Should still render something
        assert "Dashboard" in captured.out or "Overview" in captured.out or len(captured.out) > 0


class TestDashboardIntegration:
    """Integration tests for dashboard."""

    def test_full_dashboard_workflow(self, temp_dir, capsys):
        """Test complete dashboard workflow."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create varied metrics
        for agent in ["agent-1", "agent-2", "agent-3"]:
            task_id = collector.record_task_start(agent, "test-task")
            collector.record_tool_call(agent, "Read", 100)
            collector.record_tool_call(agent, "Write", 50)
            collector.record_task_complete(agent, task_id, success=True)

        collector.record_error("agent-1", "TestError", "Test message")

        # Create dashboard
        config = DashboardConfig(
            title="Test Dashboard",
            show_agents=True,
            show_tools=True,
            show_errors=True
        )

        dashboard = MetricsDashboard(collector, config)
        dashboard.render()

        captured = capsys.readouterr()

        # Verify output contains expected sections
        assert len(captured.out) > 100  # Should have substantial output
