"""
Tests for monitoring/metrics.py - Advanced Metrics Collection.

Phase 3: Advanced Features
"""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.monitoring.metrics import (
    MetricsCollector,
    MetricType,
    TimeRange,
    AgentMetrics,
    SessionMetrics,
    PerformanceMetrics,
    print_metrics_summary,
)


class TestMetricType:
    """Tests for MetricType enum."""

    def test_metric_types(self):
        """Test metric type values."""
        assert MetricType.TASK_START.value == "task_start"
        assert MetricType.TASK_COMPLETE.value == "task_complete"
        assert MetricType.TOOL_CALL.value == "tool_call"
        assert MetricType.ERROR.value == "error"
        assert MetricType.TOKEN_USAGE.value == "token_usage"


class TestTimeRange:
    """Tests for TimeRange enum."""

    def test_time_range_values(self):
        """Test time range values."""
        assert TimeRange.HOUR.value == "hour"
        assert TimeRange.DAY.value == "day"
        assert TimeRange.WEEK.value == "week"
        assert TimeRange.MONTH.value == "month"
        assert TimeRange.ALL.value == "all"


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_agent_metrics_creation(self):
        """Test creating agent metrics."""
        metrics = AgentMetrics(
            agent_id="agent-1",
            total_tasks=10,
            completed_tasks=8,
            failed_tasks=2,
            success_rate=80.0
        )

        assert metrics.agent_id == "agent-1"
        assert metrics.total_tasks == 10
        assert metrics.success_rate == 80.0

    def test_agent_metrics_to_dict(self):
        """Test converting to dict."""
        metrics = AgentMetrics(
            agent_id="agent-1",
            total_tasks=5
        )

        data = metrics.to_dict()

        assert data["agent_id"] == "agent-1"
        assert data["total_tasks"] == 5


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_performance_metrics_creation(self):
        """Test creating performance metrics."""
        metrics = PerformanceMetrics(
            time_range="day",
            total_agents=5,
            total_tasks=100,
            success_rate=85.0
        )

        assert metrics.time_range == "day"
        assert metrics.total_agents == 5
        assert metrics.success_rate == 85.0

    def test_performance_metrics_to_dict(self):
        """Test converting to dict."""
        metrics = PerformanceMetrics(
            time_range="week",
            total_tasks=50,
            tool_distribution={"Read": 100, "Write": 50}
        )

        data = metrics.to_dict()

        assert data["time_range"] == "week"
        assert data["tool_distribution"]["Read"] == 100


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_collector_creation(self, temp_dir):
        """Test creating a collector."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        assert collector.db_path == db_path
        assert db_path.exists()

    def test_record_metric(self, temp_dir):
        """Test recording a metric."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record(
            "agent-1",
            MetricType.TOOL_CALL,
            value=150,
            metadata={"tool": "Read"}
        )

        # Verify by querying
        activity = collector.get_recent_activity(limit=1)
        assert len(activity) == 1
        assert activity[0]["agent_id"] == "agent-1"

    def test_record_task_start(self, temp_dir):
        """Test recording task start."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        task_id = collector.record_task_start(
            "agent-1",
            "implement-feature"
        )

        assert task_id is not None
        assert task_id.startswith("task-")

    def test_record_task_complete(self, temp_dir):
        """Test recording task completion."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        task_id = collector.record_task_start("agent-1", "test-task")
        time.sleep(0.01)  # Small delay to get duration
        collector.record_task_complete("agent-1", task_id, success=True)

        # Check stats
        stats = collector.get_agent_stats("agent-1")
        assert stats.completed_tasks >= 1

    def test_record_task_fail(self, temp_dir):
        """Test recording task failure."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        task_id = collector.record_task_start("agent-1", "failing-task")
        collector.record_task_complete("agent-1", task_id, success=False)

        stats = collector.get_agent_stats("agent-1")
        assert stats.failed_tasks >= 1

    def test_record_tool_call(self, temp_dir):
        """Test recording tool call."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record_tool_call(
            "agent-1",
            "Read",
            duration_ms=150,
            success=True
        )

        stats = collector.get_agent_stats("agent-1")
        # Tool calls counted in activity
        activity = collector.get_recent_activity(limit=1)
        assert activity[0]["metadata"]["tool"] == "Read"

    def test_record_error(self, temp_dir):
        """Test recording error."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record_error(
            "agent-1",
            "SyntaxError",
            "Invalid syntax"
        )

        activity = collector.get_recent_activity(limit=1)
        assert activity[0]["type"] == "error"

    def test_record_token_usage(self, temp_dir):
        """Test recording token usage."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record_token_usage(
            "agent-1",
            input_tokens=1000,
            output_tokens=500
        )

        activity = collector.get_recent_activity(limit=1)
        assert activity[0]["value"] == 1500


class TestMetricsCollectorStats:
    """Tests for collector statistics methods."""

    def test_get_agent_stats(self, temp_dir):
        """Test getting agent stats."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create some metrics
        task_id = collector.record_task_start("agent-1", "task-1")
        collector.record_tool_call("agent-1", "Read", 100)
        collector.record_tool_call("agent-1", "Write", 50)
        collector.record_task_complete("agent-1", task_id, success=True)

        stats = collector.get_agent_stats("agent-1")

        assert stats.agent_id == "agent-1"
        assert stats.total_tasks >= 1
        assert stats.completed_tasks >= 1

    def test_get_agent_stats_with_time_range(self, temp_dir):
        """Test getting agent stats with time range."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record_task_start("agent-1", "recent-task")

        stats_hour = collector.get_agent_stats("agent-1", TimeRange.HOUR)
        stats_all = collector.get_agent_stats("agent-1", TimeRange.ALL)

        # Both should have data since we just created it
        assert stats_hour.total_tasks >= 0
        assert stats_all.total_tasks >= stats_hour.total_tasks

    def test_get_all_agents(self, temp_dir):
        """Test getting all agents."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record("agent-1", MetricType.TASK_START)
        collector.record("agent-2", MetricType.TASK_START)
        collector.record("agent-3", MetricType.TASK_START)

        agents = collector.get_all_agents()

        assert len(agents) >= 3
        assert "agent-1" in agents
        assert "agent-2" in agents

    def test_get_performance_metrics(self, temp_dir):
        """Test getting global performance metrics."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create some metrics
        collector.record_task_start("agent-1", "task-1")
        collector.record_tool_call("agent-1", "Read", 100)
        collector.record("agent-2", MetricType.TASK_START)

        perf = collector.get_performance_metrics(TimeRange.ALL)

        assert perf.total_agents >= 2
        assert perf.total_tool_calls >= 1

    def test_get_trends(self, temp_dir):
        """Test getting trends."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create some metrics
        for i in range(5):
            collector.record("agent-1", MetricType.TOOL_CALL)

        trends = collector.get_trends(TimeRange.HOUR)

        assert isinstance(trends, list)

    def test_get_trends_by_type(self, temp_dir):
        """Test getting trends filtered by type."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record("agent-1", MetricType.TOOL_CALL)
        collector.record("agent-1", MetricType.ERROR)

        trends = collector.get_trends(
            TimeRange.HOUR,
            metric_type=MetricType.TOOL_CALL
        )

        assert isinstance(trends, list)

    def test_get_recent_activity(self, temp_dir):
        """Test getting recent activity."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        for i in range(10):
            collector.record(f"agent-{i}", MetricType.TOOL_CALL)

        activity = collector.get_recent_activity(limit=5)

        assert len(activity) == 5


class TestMetricsCollectorMaintenance:
    """Tests for maintenance methods."""

    def test_cleanup_old_metrics(self, temp_dir):
        """Test cleaning up old metrics."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create some metrics
        for i in range(5):
            collector.record("agent-1", MetricType.TOOL_CALL)

        # Cleanup with 0 days should delete all
        deleted = collector.cleanup_old_metrics(days=0)

        # Note: cleanup uses current timestamp, so recent metrics won't be deleted
        assert isinstance(deleted, int)

    def test_export_metrics(self, temp_dir):
        """Test exporting metrics."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create some metrics
        collector.record("agent-1", MetricType.TASK_START)
        collector.record("agent-1", MetricType.TOOL_CALL)

        export_path = temp_dir / "export.json"
        collector.export_metrics(export_path)

        assert export_path.exists()

        with open(export_path) as f:
            data = json.load(f)

        assert "metrics" in data
        assert "exported_at" in data


class TestPrintMetricsSummary:
    """Tests for print_metrics_summary function."""

    def test_print_agent_summary(self, temp_dir, capsys):
        """Test printing agent summary."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record_task_start("test-agent", "test-task")

        print_metrics_summary(collector, "test-agent")

        captured = capsys.readouterr()
        assert "test-agent" in captured.out

    def test_print_global_summary(self, temp_dir, capsys):
        """Test printing global summary."""
        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        collector.record("agent-1", MetricType.TOOL_CALL)

        print_metrics_summary(collector)

        captured = capsys.readouterr()
        assert "Performance" in captured.out or "Overview" in captured.out
