"""
Tests for worktree_manager.py - Git Worktrees functionality.

Phase 1: Git Worktrees
"""

import pytest
import subprocess
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.worktree_manager import WorktreeManager, Worktree


class TestWorktreeManager:
    """Tests for WorktreeManager class."""

    def test_init_with_git_repo(self, git_repo):
        """Test initialization with valid git repository."""
        wm = WorktreeManager(git_repo)
        assert wm.project_path == git_repo.resolve()
        assert wm.worktrees_base_dir.exists()

    def test_init_with_non_git_repo(self, temp_dir):
        """Test initialization with non-git directory raises error."""
        non_git_dir = temp_dir / "not_a_repo"
        non_git_dir.mkdir()

        with pytest.raises(ValueError, match="not a git repository"):
            WorktreeManager(non_git_dir)

    def test_is_git_repo(self, git_repo):
        """Test _is_git_repo detection."""
        wm = WorktreeManager(git_repo)
        assert wm._is_git_repo() is True

    def test_create_task_worktree(self, git_repo):
        """Test creating a new worktree for a task."""
        wm = WorktreeManager(git_repo)

        worktree = wm.create_task_worktree("agent-123", "add-feature")

        assert worktree.agent_id == "agent-123"
        assert worktree.task_name == "add-feature"
        assert worktree.branch_name == "agent/agent-123/add-feature"
        assert worktree.path.exists()
        assert isinstance(worktree.created_at, datetime)

    def test_create_worktree_sanitizes_task_name(self, git_repo):
        """Test that task names are sanitized for branch names."""
        wm = WorktreeManager(git_repo)

        worktree = wm.create_task_worktree("agent-1", "Add User Auth")

        assert worktree.branch_name == "agent/agent-1/add-user-auth"

    def test_list_worktrees_empty(self, git_repo):
        """Test listing worktrees when none exist."""
        wm = WorktreeManager(git_repo)

        worktrees = wm.list_worktrees()

        assert worktrees == []

    def test_list_worktrees_with_worktrees(self, git_repo):
        """Test listing worktrees after creating some."""
        wm = WorktreeManager(git_repo)

        wm.create_task_worktree("agent-1", "task-1")
        wm.create_task_worktree("agent-2", "task-2")

        worktrees = wm.list_worktrees()

        assert len(worktrees) == 2
        agent_ids = {wt.agent_id for wt in worktrees}
        assert agent_ids == {"agent-1", "agent-2"}

    def test_get_worktree_status(self, git_repo):
        """Test getting worktree status."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        status = wm.get_worktree_status(worktree)

        assert "uncommitted_files" in status
        assert "commits_ahead" in status
        assert "last_commit" in status
        assert "has_changes" in status

    def test_worktree_status_detects_changes(self, git_repo):
        """Test that status detects uncommitted changes."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        # Add a new file in worktree
        new_file = worktree.path / "new_file.txt"
        new_file.write_text("Hello")

        status = wm.get_worktree_status(worktree)

        assert status["uncommitted_files"] > 0
        assert status["has_changes"] is True

    def test_discard_worktree(self, git_repo):
        """Test discarding a worktree."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        wm.discard_worktree(worktree)

        assert not worktree.path.exists()
        assert len(wm.list_worktrees()) == 0

    def test_discard_worktree_force(self, git_repo):
        """Test force discarding worktree with uncommitted changes."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        # Add uncommitted changes
        (worktree.path / "new.txt").write_text("test")

        wm.discard_worktree(worktree, force=True)

        assert not worktree.path.exists()

    def test_merge_worktree(self, git_repo):
        """Test merging worktree back to main."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        # Make changes in worktree
        new_file = worktree.path / "feature.py"
        new_file.write_text("# New feature\n")
        subprocess.run(["git", "add", "."], cwd=worktree.path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add feature"], cwd=worktree.path, capture_output=True)

        # Merge
        success = wm.merge_worktree(worktree, "main", delete_after=True)

        assert success is True
        assert not worktree.path.exists()

        # Verify file exists in main
        assert (git_repo / "feature.py").exists()

    def test_merge_worktree_squash(self, git_repo):
        """Test squash merge."""
        wm = WorktreeManager(git_repo)
        worktree = wm.create_task_worktree("agent-1", "feature")

        # Make multiple commits
        for i in range(3):
            (worktree.path / f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=worktree.path, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Commit {i}"], cwd=worktree.path, capture_output=True)

        success = wm.merge_worktree(worktree, "main", squash=True, delete_after=True)

        assert success is True

    def test_create_worktree_custom_base_branch(self, git_repo):
        """Test creating worktree from custom base branch."""
        wm = WorktreeManager(git_repo)

        # Create develop branch
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=git_repo, capture_output=True)
        (git_repo / "develop.txt").write_text("develop")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Develop commit"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_repo, capture_output=True)

        worktree = wm.create_task_worktree("agent-1", "feature", base_branch="develop")

        # Worktree should have develop.txt
        assert (worktree.path / "develop.txt").exists()


class TestWorktreeDataclass:
    """Tests for Worktree dataclass."""

    def test_worktree_creation(self, temp_dir):
        """Test Worktree dataclass creation."""
        worktree = Worktree(
            path=temp_dir,
            branch_name="agent/test/feature",
            commit_hash="abc123",
            created_at=datetime.now(),
            agent_id="test",
            task_name="feature"
        )

        assert worktree.agent_id == "test"
        assert worktree.task_name == "feature"
        assert worktree.branch_name == "agent/test/feature"


# Integration tests (require git)
class TestWorktreeIntegration:
    """Integration tests for worktree workflows."""

    def test_full_workflow(self, git_repo):
        """Test complete workflow: create -> work -> merge."""
        wm = WorktreeManager(git_repo)

        # 1. Create worktree
        worktree = wm.create_task_worktree("agent-dev", "implement-api")
        assert worktree.path.exists()

        # 2. Make changes
        api_file = worktree.path / "api.py"
        api_file.write_text('''
def get_users():
    return []
''')
        subprocess.run(["git", "add", "."], cwd=worktree.path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feat: add users API"], cwd=worktree.path, capture_output=True)

        # 3. Check status
        status = wm.get_worktree_status(worktree)
        assert status["commits_ahead"] > 0

        # 4. Merge
        success = wm.merge_worktree(worktree, delete_after=True)
        assert success is True

        # 5. Verify
        assert (git_repo / "api.py").exists()
        assert len(wm.list_worktrees()) == 0
