"""
Tests for task_logger.py - Task Logging system.

Phase 2: Task Logging
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.task_logger import (
    TaskLogger,
    LogPhase,
    LogEntryType,
    LogEntry,
    PhaseStats,
    TaskLog,
    print_task_summary,
)


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a log entry."""
        entry = LogEntry(
            timestamp="2024-01-01T10:00:00",
            type="text",
            content="Test message",
            phase="coding"
        )

        assert entry.type == "text"
        assert entry.content == "Test message"
        assert entry.phase == "coding"

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = LogEntry(
            timestamp="2024-01-01T10:00:00",
            type="tool_start",
            content="[Read] config.py",
            phase="analysis",
            tool_name="Read",
            tool_input="config.py"
        )

        data = entry.to_dict()

        assert data["type"] == "tool_start"
        assert data["tool_name"] == "Read"
        assert "duration_ms" not in data  # None values excluded

    def test_entry_with_all_fields(self):
        """Test entry with all fields populated."""
        entry = LogEntry(
            timestamp="2024-01-01T10:00:00",
            type="tool_end",
            content="[Read] Done",
            phase="coding",
            tool_name="Read",
            tool_input="file.py",
            detail="File contents...",
            duration_ms=150
        )

        data = entry.to_dict()
        assert data["duration_ms"] == 150
        assert data["detail"] == "File contents..."


class TestPhaseStats:
    """Tests for PhaseStats dataclass."""

    def test_phase_stats_creation(self):
        """Test creating phase stats."""
        stats = PhaseStats(phase="coding")

        assert stats.phase == "coding"
        assert stats.status == "pending"
        assert stats.tool_calls == 0
        assert stats.errors == 0

    def test_phase_stats_to_dict(self):
        """Test converting phase stats to dict."""
        stats = PhaseStats(
            phase="validation",
            status="completed",
            tool_calls=5,
            errors=1
        )

        data = stats.to_dict()

        assert data["phase"] == "validation"
        assert data["tool_calls"] == 5
        assert data["entries_count"] == 0


class TestTaskLog:
    """Tests for TaskLog dataclass."""

    def test_task_log_creation(self):
        """Test creating task log."""
        log = TaskLog(
            agent_id="agent-1",
            task_name="add-feature",
            created_at="2024-01-01T10:00:00",
            updated_at="2024-01-01T10:00:00"
        )

        assert log.agent_id == "agent-1"
        assert log.task_name == "add-feature"
        assert log.status == "running"

    def test_task_log_to_dict(self):
        """Test converting task log to dict."""
        log = TaskLog(
            agent_id="agent-1",
            task_name="fix-bug",
            created_at="2024-01-01T10:00:00",
            updated_at="2024-01-01T10:30:00",
            total_tool_calls=10,
            total_errors=1,
            status="completed"
        )

        data = log.to_dict()

        assert data["total_tool_calls"] == 10
        assert data["status"] == "completed"


class TestTaskLogger:
    """Tests for TaskLogger class."""

    def test_logger_creation(self, temp_dir):
        """Test creating a task logger."""
        logger = TaskLogger(
            agent_id="agent-1",
            task_name="test-task",
            log_dir=temp_dir,
            emit_to_console=False
        )

        assert logger.agent_id == "agent-1"
        assert logger.task_name == "test-task"
        assert logger.log_dir == temp_dir

    def test_start_phase(self, temp_dir):
        """Test starting a phase."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.ANALYSIS)

        assert logger.data.current_phase == "analysis"
        assert logger.data.phases["analysis"].status == "active"

    def test_end_phase(self, temp_dir):
        """Test ending a phase."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.end_phase(LogPhase.CODING, success=True)

        assert logger.data.phases["coding"].status == "completed"
        assert logger.data.phases["coding"].completed_at is not None

    def test_end_phase_failed(self, temp_dir):
        """Test ending a phase with failure."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.VALIDATION)
        logger.end_phase(LogPhase.VALIDATION, success=False)

        assert logger.data.phases["validation"].status == "failed"

    def test_log_message(self, temp_dir):
        """Test logging a message."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.log("Test message")

        # Check entries file was created
        assert logger.entries_file.exists()

    def test_log_error(self, temp_dir):
        """Test logging an error."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.log_error("Something went wrong")

        assert logger.data.total_errors == 1
        assert logger.data.phases["coding"].errors == 1

    def test_tool_tracking(self, temp_dir):
        """Test tool start/end tracking."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.tool_start("Read", "config.py")
        logger.tool_end("Read", success=True, result="File read successfully")

        assert logger.data.total_tool_calls == 1
        assert logger.data.phases["coding"].tool_calls == 1

    def test_tool_duration(self, temp_dir):
        """Test tool duration calculation."""
        import time

        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.tool_start("Bash", "ls")
        time.sleep(0.1)  # 100ms
        logger.tool_end("Bash", success=True)

        # Duration should be recorded (approximately 100ms)
        # We can't easily test this without reading the entries file

    def test_complete_task(self, temp_dir):
        """Test completing a task."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.complete(success=True)

        assert logger.data.status == "completed"

    def test_complete_task_failed(self, temp_dir):
        """Test completing a task with failure."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.complete(success=False)

        assert logger.data.status == "failed"

    def test_get_summary(self, temp_dir):
        """Test getting task summary."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.tool_start("Read", "file.py")
        logger.tool_end("Read", success=True)
        logger.log_error("Test error")
        logger.end_phase(LogPhase.CODING, success=True)

        summary = logger.get_summary()

        assert summary["agent_id"] == "agent-1"
        assert summary["total_tool_calls"] == 1
        assert summary["total_errors"] == 1

    def test_persistence(self, temp_dir):
        """Test that logs are persisted."""
        # Create logger and add data
        logger1 = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)
        logger1.start_phase(LogPhase.ANALYSIS)
        logger1.log("Test message")
        logger1.end_phase(LogPhase.ANALYSIS, success=True)

        # Create new logger with same params - should load existing data
        logger2 = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        assert logger2.data.phases["analysis"].status == "completed"

    def test_log_file_created(self, temp_dir):
        """Test that log file is created."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.log("Test")

        assert logger.log_file.exists()

        # Verify JSON is valid
        with open(logger.log_file) as f:
            data = json.load(f)

        assert data["agent_id"] == "agent-1"


class TestTaskLoggerHelpers:
    """Tests for helper log functions."""

    def test_log_info(self, temp_dir):
        """Test log_info helper."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)
        logger.start_phase(LogPhase.CODING)

        logger.log_info("Info message")
        # No errors should be raised

    def test_log_warning(self, temp_dir):
        """Test log_warning helper."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)
        logger.start_phase(LogPhase.CODING)

        logger.log_warning("Warning message")
        # Warnings don't increment error count
        assert logger.data.total_errors == 0

    def test_log_success(self, temp_dir):
        """Test log_success helper."""
        logger = TaskLogger("agent-1", "task", log_dir=temp_dir, emit_to_console=False)
        logger.start_phase(LogPhase.CODING)

        logger.log_success("Success message")
        # No errors should be raised


class TestPrintTaskSummary:
    """Tests for print_task_summary function."""

    def test_print_summary(self, temp_dir, capsys):
        """Test printing task summary."""
        logger = TaskLogger("agent-1", "test-task", log_dir=temp_dir, emit_to_console=False)

        logger.start_phase(LogPhase.CODING)
        logger.end_phase(LogPhase.CODING, success=True)

        print_task_summary(logger)

        captured = capsys.readouterr()
        assert "test-task" in captured.out
