"""
Tests for tasks/kanban.py and tasks/models.py - Kanban Board system.

Phase 2: Task Management
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.tasks.models import (
    Task,
    TaskStatus,
    TaskPriority,
    TaskType,
)
from claude_agent_manager.tasks.kanban import (
    KanbanBoard,
    print_board,
    print_task_detail,
)


class TestTaskModel:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task.create(
            title="Add authentication",
            description="Implement OAuth2",
            priority=TaskPriority.HIGH,
            task_type=TaskType.FEATURE
        )

        assert task.title == "Add authentication"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.BACKLOG
        assert task.id.startswith("FEA-")

    def test_task_id_generation(self):
        """Test task ID generation by type."""
        feature = Task.create("Feature", task_type=TaskType.FEATURE)
        bug = Task.create("Bug", task_type=TaskType.BUG)
        refactor = Task.create("Refactor", task_type=TaskType.REFACTOR)

        assert feature.id.startswith("FEA-")
        assert bug.id.startswith("BUG-")
        assert refactor.id.startswith("REF-")

    def test_task_to_dict(self):
        """Test converting task to dictionary."""
        task = Task.create("Test task")
        data = task.to_dict()

        assert data["title"] == "Test task"
        assert data["status"] == "backlog"
        assert data["priority"] == "medium"

    def test_task_from_dict(self):
        """Test creating task from dictionary."""
        data = {
            "id": "FEA-123ABC",
            "title": "Test task",
            "status": "in_progress",
            "priority": "high",
            "task_type": "feature"
        }

        task = Task.from_dict(data)

        assert task.id == "FEA-123ABC"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.HIGH

    def test_task_start(self):
        """Test starting a task."""
        task = Task.create("Test")

        task.start(agent_id="agent-1")

        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        assert task.assigned_agent == "agent-1"

    def test_task_complete(self):
        """Test completing a task."""
        task = Task.create("Test")
        task.start()

        task.complete()

        assert task.status == TaskStatus.DONE
        assert task.completed_at is not None
        assert task.actual_hours is not None

    def test_task_move_to(self):
        """Test moving task to different status."""
        task = Task.create("Test")

        task.move_to(TaskStatus.TODO)
        assert task.status == TaskStatus.TODO

        task.move_to(TaskStatus.IN_PROGRESS)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_task_assign(self):
        """Test assigning task to agent."""
        task = Task.create("Test")

        task.assign("agent-123")

        assert task.assigned_agent == "agent-123"

    def test_task_add_subtask(self):
        """Test adding subtask."""
        task = Task.create("Parent task")

        task.add_subtask("SUB-001")
        task.add_subtask("SUB-002")
        task.add_subtask("SUB-001")  # Duplicate

        assert len(task.subtasks) == 2

    def test_task_add_label(self):
        """Test adding label."""
        task = Task.create("Test")

        task.add_label("urgent")
        task.add_label("frontend")
        task.add_label("urgent")  # Duplicate

        assert len(task.labels) == 2

    def test_task_is_blocked(self):
        """Test blocked task detection."""
        task = Task.create("Test")
        assert not task.is_blocked

        task.add_label("blocked")
        assert task.is_blocked

    def test_task_str(self):
        """Test task string representation."""
        task = Task.create("Test task")
        str_repr = str(task)

        assert task.id in str_repr
        assert "Test task" in str_repr


class TestKanbanBoard:
    """Tests for KanbanBoard class."""

    def test_board_creation(self, temp_dir):
        """Test creating a kanban board."""
        board = KanbanBoard(temp_dir)

        assert board.project_path == temp_dir.resolve()
        assert len(board.tasks) == 0

    def test_create_task(self, temp_dir):
        """Test creating a task on the board."""
        board = KanbanBoard(temp_dir)

        task = board.create_task("Test task")

        assert task.id in board.tasks
        assert board.tasks[task.id].title == "Test task"

    def test_create_task_with_options(self, temp_dir):
        """Test creating task with all options."""
        board = KanbanBoard(temp_dir)

        task = board.create_task(
            title="Complex task",
            description="Detailed description",
            priority=TaskPriority.URGENT,
            task_type=TaskType.BUG,
            labels=["critical", "production"]
        )

        assert task.priority == TaskPriority.URGENT
        assert task.task_type == TaskType.BUG
        assert "critical" in task.labels

    def test_get_task(self, temp_dir):
        """Test getting task by ID."""
        board = KanbanBoard(temp_dir)
        created = board.create_task("Test")

        retrieved = board.get_task(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_task(self, temp_dir):
        """Test getting nonexistent task."""
        board = KanbanBoard(temp_dir)

        result = board.get_task("NONEXISTENT")

        assert result is None

    def test_delete_task(self, temp_dir):
        """Test deleting a task."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("To delete")

        result = board.delete_task(task.id)

        assert result is True
        assert task.id not in board.tasks

    def test_move_task(self, temp_dir):
        """Test moving task to different status."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("Test")

        board.move_task(task.id, TaskStatus.TODO)

        assert board.tasks[task.id].status == TaskStatus.TODO

    def test_start_task(self, temp_dir):
        """Test starting a task."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("Test")

        board.start_task(task.id, agent_id="agent-1")

        assert board.tasks[task.id].status == TaskStatus.IN_PROGRESS
        assert board.tasks[task.id].assigned_agent == "agent-1"

    def test_complete_task(self, temp_dir):
        """Test completing a task."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("Test")
        board.start_task(task.id)

        board.complete_task(task.id)

        assert board.tasks[task.id].status == TaskStatus.DONE

    def test_assign_task(self, temp_dir):
        """Test assigning task to agent."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("Test")

        board.assign_task(task.id, "agent-123")

        assert board.tasks[task.id].assigned_agent == "agent-123"

    def test_get_tasks_by_status(self, temp_dir):
        """Test filtering tasks by status."""
        board = KanbanBoard(temp_dir)
        board.create_task("Task 1")
        task2 = board.create_task("Task 2")
        board.start_task(task2.id)

        backlog = board.get_tasks_by_status(TaskStatus.BACKLOG)
        in_progress = board.get_tasks_by_status(TaskStatus.IN_PROGRESS)

        assert len(backlog) == 1
        assert len(in_progress) == 1

    def test_get_tasks_by_agent(self, temp_dir):
        """Test filtering tasks by agent."""
        board = KanbanBoard(temp_dir)
        task1 = board.create_task("Task 1")
        task2 = board.create_task("Task 2")
        board.assign_task(task1.id, "agent-1")
        board.assign_task(task2.id, "agent-2")

        agent1_tasks = board.get_tasks_by_agent("agent-1")

        assert len(agent1_tasks) == 1
        assert agent1_tasks[0].id == task1.id

    def test_get_tasks_by_priority(self, temp_dir):
        """Test filtering tasks by priority."""
        board = KanbanBoard(temp_dir)
        board.create_task("Low", priority=TaskPriority.LOW)
        board.create_task("High 1", priority=TaskPriority.HIGH)
        board.create_task("High 2", priority=TaskPriority.HIGH)

        high_priority = board.get_tasks_by_priority(TaskPriority.HIGH)

        assert len(high_priority) == 2

    def test_search_tasks(self, temp_dir):
        """Test searching tasks by text."""
        board = KanbanBoard(temp_dir)
        board.create_task("Add authentication", description="OAuth implementation")
        board.create_task("Fix bug in login")
        board.create_task("Update docs")

        results = board.search_tasks("auth")

        assert len(results) == 1
        assert "authentication" in results[0].title

    def test_get_column_counts(self, temp_dir):
        """Test getting column counts."""
        board = KanbanBoard(temp_dir)
        board.create_task("Task 1")
        board.create_task("Task 2")
        task3 = board.create_task("Task 3")
        board.start_task(task3.id)

        counts = board.get_column_counts()

        assert counts[TaskStatus.BACKLOG] == 2
        assert counts[TaskStatus.IN_PROGRESS] == 1

    def test_get_summary(self, temp_dir):
        """Test getting board summary."""
        board = KanbanBoard(temp_dir)
        board.create_task("Task 1")
        task2 = board.create_task("Task 2")
        board.start_task(task2.id)
        board.complete_task(task2.id)

        summary = board.get_summary()

        assert summary["total_tasks"] == 2
        assert summary["done"] == 1
        assert summary["done_percent"] == 50.0

    def test_persistence(self, temp_dir):
        """Test board persistence."""
        # Create board and add task
        board1 = KanbanBoard(temp_dir)
        board1.create_task("Persistent task")

        # Create new board instance - should load existing data
        board2 = KanbanBoard(temp_dir)

        assert len(board2.tasks) == 1
        assert list(board2.tasks.values())[0].title == "Persistent task"


class TestKanbanBoardPrinting:
    """Tests for board printing functions."""

    def test_print_board(self, temp_dir, capsys):
        """Test printing board."""
        board = KanbanBoard(temp_dir)
        board.create_task("Test task")

        print_board(board)

        captured = capsys.readouterr()
        assert "Backlog" in captured.out or "backlog" in captured.out.lower()

    def test_print_task_detail(self, temp_dir, capsys):
        """Test printing task detail."""
        board = KanbanBoard(temp_dir)
        task = board.create_task("Detailed task", description="Full description")

        print_task_detail(task)

        captured = capsys.readouterr()
        assert "Detailed task" in captured.out
