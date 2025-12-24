"""
Git Worktrees Manager - Per-Agent Architecture
===============================================

Based on Auto-Claude worktree implementation with enhancements.

Each agent task gets its own worktree:
- Worktree path: .worktrees/{agent_id}-{task_name}/
- Branch name: agent/{agent_id}/{task_name}

This allows:
1. Multiple agents to work on tasks simultaneously
2. Each task's changes are isolated
3. Branches persist until explicitly merged
4. Clear mapping: agent + task -> worktree -> branch
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

console = Console()


class WorktreeError(Exception):
    """Error during worktree operations."""
    pass


# Constants for merge operations
MAX_FILE_LINES_FOR_AI = 5000
LOCK_FILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "Pipfile.lock", "poetry.lock", "uv.lock", "Cargo.lock",
    "Gemfile.lock", "composer.lock", "go.sum",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dll", ".so",
    ".dylib", ".bin", ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pyc", ".pyo",
    ".class", ".o", ".obj",
}


@dataclass
class Worktree:
    """Information about an agent's worktree."""
    path: Path
    branch_name: str
    commit_hash: str
    created_at: datetime
    agent_id: str
    task_name: str
    base_branch: str = "main"
    is_active: bool = True
    # Statistics
    commit_count: int = 0
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    uncommitted_files: int = 0
    last_commit: str = ""
    # Change details
    changed_files: List[Tuple[str, str]] = field(default_factory=list)  # (status, path)


class WorktreeManager:
    """
    Manages per-agent Git worktrees.

    Each agent task gets its own worktree in .worktrees/{agent_id}-{task_name}/
    with a corresponding branch agent/{agent_id}/{task_name}.
    """

    def __init__(self, project_path: Path, worktrees_base_dir: Optional[Path] = None):
        self.project_path = project_path.resolve()

        if not self._is_git_repo():
            raise ValueError(f"{project_path} is not a git repository")

        self.base_branch = self._detect_base_branch()

        # Base directory for worktrees
        if worktrees_base_dir is None:
            self.worktrees_base_dir = self.project_path / ".worktrees"
        else:
            self.worktrees_base_dir = worktrees_base_dir

        self.worktrees_base_dir.mkdir(exist_ok=True)
        self._merge_lock = asyncio.Lock()

    def _is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        return (self.project_path / ".git").exists()

    def _detect_base_branch(self) -> str:
        """
        Detect the base branch for worktree creation.

        Priority order:
        1. DEFAULT_BRANCH environment variable
        2. Auto-detect main/master (if they exist)
        3. Fall back to current branch (with warning)
        """
        # 1. Check for DEFAULT_BRANCH env var
        env_branch = os.getenv("DEFAULT_BRANCH")
        if env_branch:
            result = self._run_git("rev-parse", "--verify", env_branch)
            if result.returncode == 0:
                return env_branch
            console.print(f"[yellow]Warning: DEFAULT_BRANCH '{env_branch}' not found, auto-detecting...[/yellow]")

        # 2. Auto-detect main/master
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return branch

        # 3. Fall back to current branch with warning
        current = self._get_current_branch()
        console.print(f"[yellow]Warning: Could not find 'main' or 'master' branch.[/yellow]")
        console.print(f"[yellow]Using current branch '{current}' as base for worktree.[/yellow]")
        return current

    def _get_current_branch(self) -> str:
        """Get the current git branch."""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.project_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise WorktreeError(f"Failed to get current branch: {result.stderr}")
        return result.stdout.strip()

    def _run_git(self, *args, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run a git command and return the result."""
        if cwd is None:
            cwd = self.project_path

        return subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _run_git_checked(self, *args, cwd: Optional[Path] = None) -> str:
        """Run git command and raise on error."""
        result = self._run_git(*args, cwd=cwd)
        if result.returncode != 0:
            raise WorktreeError(f"Git command failed: {result.stderr}")
        return result.stdout.strip()

    # ==================== Worktree Path/Branch Methods ====================

    def get_worktree_path(self, agent_id: str, task_name: str) -> Path:
        """Get the worktree path for an agent task."""
        safe_task = task_name.lower().replace(" ", "-").replace("_", "-")
        return self.worktrees_base_dir / f"{agent_id}-{safe_task}"

    def get_branch_name(self, agent_id: str, task_name: str) -> str:
        """Get the branch name for an agent task."""
        safe_task = task_name.lower().replace(" ", "-").replace("_", "-")
        return f"agent/{agent_id}/{safe_task}"

    def worktree_exists(self, agent_id: str, task_name: str) -> bool:
        """Check if a worktree exists for an agent task."""
        return self.get_worktree_path(agent_id, task_name).exists()

    # ==================== Statistics ====================

    def _get_worktree_stats(self, worktree_path: Path) -> Dict:
        """Get diff statistics for a worktree."""
        stats = {
            "commit_count": 0,
            "files_changed": 0,
            "additions": 0,
            "deletions": 0,
            "uncommitted_files": 0,
            "last_commit": "",
            "changed_files": [],
        }

        if not worktree_path.exists():
            return stats

        # Commit count ahead of base
        result = self._run_git(
            "rev-list", "--count", f"{self.base_branch}..HEAD",
            cwd=worktree_path
        )
        if result.returncode == 0:
            stats["commit_count"] = int(result.stdout.strip() or "0")

        # Diff stats (additions/deletions)
        result = self._run_git(
            "diff", "--shortstat", f"{self.base_branch}...HEAD",
            cwd=worktree_path
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse: "3 files changed, 50 insertions(+), 10 deletions(-)"
            match = re.search(r"(\d+) files? changed", result.stdout)
            if match:
                stats["files_changed"] = int(match.group(1))
            match = re.search(r"(\d+) insertions?", result.stdout)
            if match:
                stats["additions"] = int(match.group(1))
            match = re.search(r"(\d+) deletions?", result.stdout)
            if match:
                stats["deletions"] = int(match.group(1))

        # Uncommitted files count
        result = self._run_git("status", "--porcelain", cwd=worktree_path)
        if result.returncode == 0:
            stats["uncommitted_files"] = len([l for l in result.stdout.split('\n') if l.strip()])

        # Last commit message
        result = self._run_git("log", "-1", "--pretty=%s", cwd=worktree_path)
        if result.returncode == 0:
            stats["last_commit"] = result.stdout.strip()[:80]

        # Changed files list
        result = self._run_git(
            "diff", "--name-status", f"{self.base_branch}...HEAD",
            cwd=worktree_path
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        stats["changed_files"].append((parts[0], parts[1]))

        return stats

    # ==================== Branch Namespace Check ====================

    def _check_branch_namespace_conflict(self, agent_id: str) -> Optional[str]:
        """
        Check if a branch named 'agent' or 'agent/{agent_id}' exists,
        which would block creating branches in the namespace.
        """
        # Check for 'agent' branch blocking 'agent/*'
        result = self._run_git("rev-parse", "--verify", "agent")
        if result.returncode == 0:
            return "agent"

        # Check for 'agent/{agent_id}' blocking 'agent/{agent_id}/*'
        result = self._run_git("rev-parse", "--verify", f"agent/{agent_id}")
        if result.returncode == 0:
            return f"agent/{agent_id}"

        return None

    # ==================== Create Worktree ====================

    def create_task_worktree(
        self,
        agent_id: str,
        task_name: str,
        base_branch: Optional[str] = None
    ) -> Worktree:
        """
        Create an isolated worktree for an agent task.

        Args:
            agent_id: ID of the agent
            task_name: Name of the task (used in branch name)
            base_branch: Base branch to create from (default: auto-detected)

        Returns:
            Worktree object with information about the created worktree
        """
        if base_branch:
            self.base_branch = base_branch

        worktree_path = self.get_worktree_path(agent_id, task_name)
        branch_name = self.get_branch_name(agent_id, task_name)

        # Check for branch namespace conflict
        conflicting_branch = self._check_branch_namespace_conflict(agent_id)
        if conflicting_branch:
            raise WorktreeError(
                f"Branch '{conflicting_branch}' exists and blocks creating '{branch_name}'.\n"
                f"Fix: Rename the conflicting branch:\n"
                f"  git branch -m {conflicting_branch} {conflicting_branch}-backup"
            )

        # Remove existing worktree if present (from crashed previous run)
        if worktree_path.exists():
            console.print(f"[yellow]Warning: Worktree {worktree_path} exists, removing...[/yellow]")
            self._run_git("worktree", "remove", "--force", str(worktree_path))
            if worktree_path.exists():
                shutil.rmtree(worktree_path, ignore_errors=True)

        # Delete branch if it exists (from previous attempt)
        self._run_git("branch", "-D", branch_name)

        # Update base branch if remote exists
        has_remote = "origin" in self._run_git("remote").stdout
        if has_remote:
            try:
                self._run_git("fetch", "origin", self.base_branch)
                self._run_git("checkout", self.base_branch)
                self._run_git("pull", "origin", self.base_branch)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update {self.base_branch}: {e}[/yellow]")

        # Create worktree with new branch from base
        result = self._run_git(
            "worktree", "add", "-b", branch_name,
            str(worktree_path), self.base_branch
        )

        if result.returncode != 0:
            raise WorktreeError(f"Failed to create worktree: {result.stderr}")

        # Get commit hash
        commit_hash = self._run_git("rev-parse", "HEAD", cwd=worktree_path).stdout.strip()

        worktree = Worktree(
            path=worktree_path,
            branch_name=branch_name,
            commit_hash=commit_hash,
            created_at=datetime.now(),
            agent_id=agent_id,
            task_name=task_name,
            base_branch=self.base_branch,
            is_active=True,
        )

        console.print(Panel(
            f"Created worktree for agent {agent_id}\n"
            f"Path: {worktree_path}\n"
            f"Branch: {branch_name}\n"
            f"Base: {self.base_branch}\n"
            f"Commit: {commit_hash[:8]}",
            title="Worktree Created",
            border_style="green"
        ))

        return worktree

    def get_or_create_worktree(self, agent_id: str, task_name: str) -> Worktree:
        """Get existing worktree or create a new one."""
        worktrees = self.list_worktrees()
        for wt in worktrees:
            if wt.agent_id == agent_id and wt.task_name == task_name:
                console.print(f"[cyan]Using existing worktree: {wt.path}[/cyan]")
                return wt
        return self.create_task_worktree(agent_id, task_name)

    # ==================== List Worktrees ====================

    def list_worktrees(self) -> List[Worktree]:
        """List all active worktrees with full statistics."""
        output = self._run_git("worktree", "list", "--porcelain")

        worktrees = []
        lines = output.stdout.split('\n')

        i = 0
        while i < len(lines):
            if lines[i].startswith('worktree '):
                path_str = lines[i].split(' ', 1)[1]
                path = Path(path_str)

                # Skip main worktree
                if path == self.project_path:
                    i += 1
                    while i < len(lines) and not lines[i].startswith('worktree '):
                        i += 1
                    continue

                # Parse fields
                branch_name = None
                commit_hash = None

                i += 1
                while i < len(lines) and not lines[i].startswith('worktree '):
                    if lines[i].startswith('HEAD '):
                        commit_hash = lines[i].split(' ')[1]
                    elif lines[i].startswith('branch '):
                        branch_name = lines[i].split(' ', 1)[1].replace('refs/heads/', '')
                    i += 1

                # Extract agent_id and task_name from branch name
                agent_id = "unknown"
                task_name = "unknown"

                if branch_name and branch_name.startswith('agent/'):
                    parts = branch_name.split('/')
                    if len(parts) >= 3:
                        agent_id = parts[1]
                        task_name = '/'.join(parts[2:])

                # Get statistics
                stats = self._get_worktree_stats(path)

                try:
                    created_at = datetime.fromtimestamp(path.stat().st_ctime)
                except:
                    created_at = datetime.now()

                worktrees.append(Worktree(
                    path=path,
                    branch_name=branch_name or "unknown",
                    commit_hash=commit_hash or "unknown",
                    created_at=created_at,
                    agent_id=agent_id,
                    task_name=task_name,
                    base_branch=self.base_branch,
                    is_active=True,
                    commit_count=stats["commit_count"],
                    files_changed=stats["files_changed"],
                    additions=stats["additions"],
                    deletions=stats["deletions"],
                    uncommitted_files=stats["uncommitted_files"],
                    last_commit=stats["last_commit"],
                    changed_files=stats["changed_files"],
                ))
            else:
                i += 1

        return worktrees

    def get_worktree_for_agent(self, agent_id: str) -> Optional[Worktree]:
        """Get worktree for a specific agent."""
        for wt in self.list_worktrees():
            if wt.agent_id == agent_id:
                return wt
        return None

    # ==================== Merge Worktree ====================

    def _unstage_ignored_files(self) -> None:
        """Unstage any staged files that are gitignored."""
        result = self._run_git("diff", "--cached", "--name-only")
        if result.returncode != 0 or not result.stdout.strip():
            return

        staged_files = result.stdout.strip().split("\n")

        # Check which are gitignored
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=self.project_path,
            input="\n".join(staged_files),
            capture_output=True,
            text=True,
        )

        files_to_unstage = set()
        if result.stdout.strip():
            for file in result.stdout.strip().split("\n"):
                if file.strip():
                    files_to_unstage.add(file.strip())

        if files_to_unstage:
            console.print(f"[yellow]Unstaging {len(files_to_unstage)} gitignored file(s)...[/yellow]")
            for file in files_to_unstage:
                self._run_git("reset", "HEAD", "--", file)

    def merge_worktree(
        self,
        worktree: Worktree | Path,
        target_branch: Optional[str] = None,
        delete_after: bool = True,
        squash: bool = False,
        no_commit: bool = False
    ) -> bool:
        """
        Merge changes from worktree into target branch.

        Args:
            worktree: Worktree object or Path to worktree
            target_branch: Target branch for merge (default: base_branch)
            delete_after: Delete worktree after successful merge
            squash: Use squash merge
            no_commit: Merge but don't commit (for review)

        Returns:
            True if merge succeeded
        """
        if target_branch is None:
            target_branch = self.base_branch

        # Find worktree if Path provided
        if isinstance(worktree, Path):
            for wt in self.list_worktrees():
                if wt.path == worktree:
                    worktree = wt
                    break
            else:
                raise ValueError(f"Worktree not found: {worktree}")

        # Check for uncommitted changes
        if worktree.uncommitted_files > 0:
            console.print(f"[yellow]Warning: {worktree.uncommitted_files} uncommitted files in worktree[/yellow]")

        # Check remote
        has_remote = "origin" in self._run_git("remote").stdout

        # Switch to target branch
        result = self._run_git("checkout", target_branch)
        if result.returncode != 0:
            console.print(f"[red]Error: Could not checkout {target_branch}: {result.stderr}[/red]")
            return False

        if has_remote:
            self._run_git("pull", "origin", target_branch)

        # Perform merge
        if no_commit:
            console.print(f"[cyan]Merging {worktree.branch_name} into {target_branch} (staged, not committed)...[/cyan]")
            merge_args = ["merge", "--no-ff", "--no-commit", worktree.branch_name]
        elif squash:
            console.print(f"[cyan]Squash merging {worktree.branch_name} into {target_branch}...[/cyan]")
            merge_args = ["merge", "--squash", worktree.branch_name]
        else:
            console.print(f"[cyan]Merging {worktree.branch_name} into {target_branch}...[/cyan]")
            merge_args = ["merge", "--no-ff", "-m", f"Merge branch '{worktree.branch_name}'", worktree.branch_name]

        result = self._run_git(*merge_args)

        if result.returncode != 0:
            console.print(f"[red]Merge conflict! Aborting merge...[/red]")
            self._run_git("merge", "--abort")
            console.print("[yellow]You may need to resolve conflicts manually[/yellow]")
            return False

        # Handle post-merge actions
        if squash:
            # Squash requires manual commit
            commit_msg = f"Merge branch '{worktree.branch_name}' (squashed)"
            result = self._run_git("commit", "-m", commit_msg)
            if result.returncode != 0 and "nothing to commit" not in result.stdout + result.stderr:
                console.print(f"[red]Commit failed: {result.stderr}[/red]")
                return False

        if no_commit:
            self._unstage_ignored_files()
            console.print(f"[green]Changes from {worktree.branch_name} are staged for review.[/green]")
            console.print("[cyan]Review changes, then commit: git commit -m 'your message'[/cyan]")
        else:
            console.print(Panel(
                f"Successfully merged {worktree.branch_name} into {target_branch}",
                title="Merge Complete",
                border_style="green"
            ))

            # Push if remote exists
            if has_remote:
                try:
                    self._run_git("push", "origin", target_branch)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not push to origin: {e}[/yellow]")

        # Cleanup
        if delete_after and not no_commit:
            self.discard_worktree(worktree.path, force=True)

        return True

    # ==================== Discard Worktree ====================

    def discard_worktree(self, worktree: Worktree | Path, force: bool = False) -> None:
        """
        Remove worktree and its branch.

        Args:
            worktree: Worktree object or Path to worktree
            force: Force removal even with uncommitted changes
        """
        if isinstance(worktree, Worktree):
            path = worktree.path
            branch_name = worktree.branch_name
        else:
            path = worktree
            branch_name = None
            for wt in self.list_worktrees():
                if wt.path == path:
                    branch_name = wt.branch_name
                    break

        # Remove worktree
        if path.exists():
            if force:
                result = self._run_git("worktree", "remove", "--force", str(path))
            else:
                result = self._run_git("worktree", "remove", str(path))

            if result.returncode != 0:
                console.print(f"[yellow]Warning: Could not remove worktree via git: {result.stderr}[/yellow]")
                shutil.rmtree(path, ignore_errors=True)

        # Delete branch
        if branch_name:
            self._run_git("branch", "-D", branch_name)
            console.print(f"[green]Deleted branch {branch_name}[/green]")

        # Prune worktrees
        self._run_git("worktree", "prune")
        console.print(f"[green]Discarded worktree: {path}[/green]")

    # ==================== Commit in Worktree ====================

    def commit_in_worktree(self, worktree: Worktree | Path, message: str) -> bool:
        """Commit all changes in a worktree."""
        if isinstance(worktree, Worktree):
            path = worktree.path
        else:
            path = worktree

        if not path.exists():
            return False

        self._run_git("add", ".", cwd=path)
        result = self._run_git("commit", "-m", message, cwd=path)

        if result.returncode == 0:
            console.print(f"[green]Committed: {message}[/green]")
            return True
        elif "nothing to commit" in result.stdout + result.stderr:
            console.print("[yellow]Nothing to commit[/yellow]")
            return True
        else:
            console.print(f"[red]Commit failed: {result.stderr}[/red]")
            return False

    # ==================== Cleanup ====================

    def cleanup_stale_worktrees(self) -> int:
        """
        Remove worktrees that aren't registered with git.

        Returns:
            Number of stale worktrees removed
        """
        if not self.worktrees_base_dir.exists():
            return 0

        # Get list of registered worktrees
        result = self._run_git("worktree", "list", "--porcelain")
        registered_paths = set()
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                registered_paths.add(Path(line.split(" ", 1)[1]))

        # Remove unregistered directories
        removed = 0
        for item in self.worktrees_base_dir.iterdir():
            if item.is_dir() and item not in registered_paths:
                console.print(f"[yellow]Removing stale worktree: {item.name}[/yellow]")
                shutil.rmtree(item, ignore_errors=True)
                removed += 1

        self._run_git("worktree", "prune")

        if removed:
            console.print(f"[green]Removed {removed} stale worktree(s)[/green]")

        return removed

    def cleanup_all(self) -> None:
        """Remove all worktrees and their branches."""
        for worktree in self.list_worktrees():
            self.discard_worktree(worktree, force=True)
        console.print("[green]All worktrees cleaned up[/green]")

    # ==================== Status ====================

    def get_worktree_status(self, worktree: Worktree | Path) -> Dict:
        """Get full status for a worktree."""
        if isinstance(worktree, Worktree):
            path = worktree.path
        else:
            path = worktree

        return self._get_worktree_stats(path)

    def has_uncommitted_changes(self, worktree: Optional[Worktree | Path] = None) -> bool:
        """Check if there are uncommitted changes."""
        if worktree is None:
            cwd = self.project_path
        elif isinstance(worktree, Worktree):
            cwd = worktree.path
        else:
            cwd = worktree

        result = self._run_git("status", "--porcelain", cwd=cwd)
        return bool(result.stdout.strip())

    # ==================== Utility Functions ====================

    def list_all_agent_branches(self) -> List[str]:
        """List all agent branches (even if worktree removed)."""
        result = self._run_git("branch", "--list", "agent/*")
        if result.returncode != 0:
            return []

        branches = []
        for line in result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("* ")
            if branch:
                branches.append(branch)

        return branches

    def get_changed_files(self, worktree: Worktree | Path) -> List[Tuple[str, str]]:
        """Get list of changed files in worktree as (status, path) tuples."""
        if isinstance(worktree, Worktree):
            path = worktree.path
        else:
            path = worktree

        if not path.exists():
            return []

        result = self._run_git(
            "diff", "--name-status", f"{self.base_branch}...HEAD",
            cwd=path
        )

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    files.append((parts[0], parts[1]))  # (status, path)

        return files

    def get_change_summary(self, worktree: Worktree | Path) -> Dict[str, int]:
        """Get summary of changes in worktree."""
        files = self.get_changed_files(worktree)

        return {
            "added": sum(1 for s, _ in files if s == "A"),
            "modified": sum(1 for s, _ in files if s == "M"),
            "deleted": sum(1 for s, _ in files if s == "D"),
            "renamed": sum(1 for s, _ in files if s.startswith("R")),
            "total": len(files),
        }


# ==================== Validation Utilities ====================

def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary based on extension."""
    return Path(file_path).suffix.lower() in BINARY_EXTENSIONS


def is_lock_file(file_path: str) -> bool:
    """Check if a file is a package manager lock file."""
    return Path(file_path).name in LOCK_FILES


def validate_python_syntax(content: str, file_path: str) -> Tuple[bool, str]:
    """Validate Python syntax."""
    try:
        compile(content, file_path, "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"Python syntax error: {e.msg} at line {e.lineno}"


def validate_json_syntax(content: str) -> Tuple[bool, str]:
    """Validate JSON syntax."""
    try:
        json.loads(content)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"JSON error: {e.msg} at line {e.lineno}"


def validate_merged_syntax(file_path: str, content: str) -> Tuple[bool, str]:
    """
    Validate syntax of merged code.

    Returns (is_valid, error_message).
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".py":
        return validate_python_syntax(content, file_path)
    elif ext == ".json":
        return validate_json_syntax(content)

    # Other file types - skip validation
    return True, ""
