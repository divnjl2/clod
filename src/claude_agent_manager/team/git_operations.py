"""
Git Operations - Git операции на основе Aider
=============================================

Источник: Aider (repo.py, coders/base_coder.py)
- Incremental commits
- Repository context gathering
- Conflict resolution
- Worktree management

Дополнения:
- Multi-worktree support
- Smart merge с AI
- Branch management для агентов
"""

from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class MergeResult(Enum):
    """Результат мержа."""
    SUCCESS = "success"
    CONFLICT = "conflict"
    FAILED = "failed"
    NO_CHANGES = "no_changes"


@dataclass
class FileChange:
    """Изменение файла."""
    path: str
    status: str  # A (added), M (modified), D (deleted), R (renamed)
    additions: int = 0
    deletions: int = 0


@dataclass
class CommitInfo:
    """Информация о коммите."""
    hash: str
    message: str
    author: str
    date: str
    files_changed: List[FileChange] = field(default_factory=list)


@dataclass
class ConflictInfo:
    """Информация о конфликте."""
    file: str
    ours: str      # Наши изменения
    theirs: str    # Их изменения
    base: str      # Общий предок


class GitOperations:
    """
    Git операции для multi-agent системы.

    Источник: Aider repo.py

    Основные паттерны:
    - Incremental commits (частые маленькие коммиты)
    - Context gathering (сбор информации о репозитории)
    - Conflict resolution (разрешение конфликтов)
    """

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._validate_repo()

    def _validate_repo(self):
        """Проверка что это git репозиторий."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists() and not (self.repo_path / ".git").is_file():
            raise ValueError(f"{self.repo_path} is not a git repository")

    def _run_git(
        self,
        *args: str,
        cwd: Optional[Path] = None,
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """Выполнить git команду."""
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=check
        )

    # =========================================================================
    # REPOSITORY INFO (из Aider repo.py)
    # =========================================================================

    def get_tracked_files(self) -> List[str]:
        """
        Получить список отслеживаемых файлов.

        Источник: Aider repo.py - get_tracked_files()
        """
        result = self._run_git("ls-files")
        return [f for f in result.stdout.strip().split("\n") if f]

    def get_current_branch(self) -> str:
        """Получить текущую ветку."""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def get_base_branch(self) -> str:
        """Определить базовую ветку (main/master)."""
        for branch in ["main", "master"]:
            result = self._run_git(
                "rev-parse", "--verify", branch,
                check=False
            )
            if result.returncode == 0:
                return branch
        return "main"

    def get_status(self) -> Dict[str, List[str]]:
        """
        Получить статус репозитория.

        Returns:
            Dict с ключами: staged, unstaged, untracked
        """
        result = self._run_git("status", "--porcelain")

        status = {
            "staged": [],
            "unstaged": [],
            "untracked": []
        }

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            index_status = line[0]
            work_status = line[1]
            file_path = line[3:]

            if index_status in "MADRCU":
                status["staged"].append(file_path)
            if work_status in "MADRCU":
                status["unstaged"].append(file_path)
            if index_status == "?" and work_status == "?":
                status["untracked"].append(file_path)

        return status

    def get_diff(self, staged: bool = False, file: Optional[str] = None) -> str:
        """
        Получить diff.

        Источник: Aider repo.py - get_diffs()
        """
        args = ["diff"]
        if staged:
            args.append("--cached")
        if file:
            args.extend(["--", file])

        result = self._run_git(*args)
        return result.stdout

    def get_recent_commits(self, count: int = 10) -> List[CommitInfo]:
        """Получить последние коммиты."""
        result = self._run_git(
            "log",
            f"-{count}",
            "--pretty=format:%H|%s|%an|%ai"
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append(CommitInfo(
                    hash=parts[0],
                    message=parts[1],
                    author=parts[2],
                    date=parts[3]
                ))

        return commits

    # =========================================================================
    # INCREMENTAL COMMITS (из Aider - ключевой паттерн)
    # =========================================================================

    def add_files(self, files: Optional[List[str]] = None):
        """Добавить файлы в staging."""
        if files:
            self._run_git("add", *files)
        else:
            self._run_git("add", ".")

    def commit(
        self,
        message: str,
        prefix: str = "[agent]",
        agent_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Создать коммит.

        Источник: Aider base_coder.py - commit pattern

        Паттерн Aider: частые инкрементальные коммиты с понятными сообщениями.
        """
        # Проверяем есть ли что коммитить
        status = self.get_status()
        if not status["staged"] and not status["unstaged"]:
            return None

        # Добавляем все изменения
        self.add_files()

        # Формируем сообщение
        if agent_name:
            full_message = f"{prefix} [{agent_name}] {message}"
        else:
            full_message = f"{prefix} {message}"

        # Коммитим
        result = self._run_git("commit", "-m", full_message)

        if result.returncode == 0:
            # Получаем hash
            hash_result = self._run_git("rev-parse", "HEAD")
            return hash_result.stdout.strip()

        return None

    def incremental_commit(
        self,
        description: str,
        agent_name: str,
        files: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Инкрементальный коммит (Aider pattern).

        Делает маленький коммит с конкретным описанием.
        """
        if files:
            self.add_files(files)
        else:
            self.add_files()

        return self.commit(description, agent_name=agent_name)

    # =========================================================================
    # WORKTREE OPERATIONS
    # =========================================================================

    def create_worktree(
        self,
        path: Path,
        branch: str,
        base_branch: Optional[str] = None
    ) -> Path:
        """
        Создать git worktree.

        Worktree = изолированная копия репозитория с отдельной веткой.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        base = base_branch or self.get_base_branch()

        # Создаём новую ветку и worktree
        self._run_git(
            "worktree", "add",
            "-b", branch,
            str(path),
            base
        )

        return path

    def remove_worktree(self, path: Path):
        """Удалить worktree."""
        self._run_git("worktree", "remove", str(path), "--force", check=False)

    def list_worktrees(self) -> List[Dict[str, str]]:
        """Список всех worktrees."""
        result = self._run_git("worktree", "list", "--porcelain")

        worktrees = []
        current = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]

        if current:
            worktrees.append(current)

        return worktrees

    def worktree_status(self, worktree_path: Path) -> Dict[str, Any]:
        """Статус конкретного worktree."""
        ops = GitOperations(worktree_path)
        return {
            "path": str(worktree_path),
            "branch": ops.get_current_branch(),
            "status": ops.get_status(),
            "recent_commits": ops.get_recent_commits(5)
        }

    # =========================================================================
    # BRANCH OPERATIONS
    # =========================================================================

    def create_branch(self, branch: str, base: Optional[str] = None):
        """Создать ветку."""
        base = base or self.get_base_branch()
        self._run_git("branch", branch, base)

    def checkout(self, branch: str):
        """Переключиться на ветку."""
        self._run_git("checkout", branch)

    def delete_branch(self, branch: str, force: bool = False):
        """Удалить ветку."""
        flag = "-D" if force else "-d"
        self._run_git("branch", flag, branch, check=False)

    def list_branches(self) -> List[str]:
        """Список веток."""
        result = self._run_git("branch", "--format=%(refname:short)")
        return [b for b in result.stdout.strip().split("\n") if b]

    def branch_exists(self, branch: str) -> bool:
        """Проверить существование ветки."""
        result = self._run_git(
            "rev-parse", "--verify", branch,
            check=False
        )
        return result.returncode == 0

    # =========================================================================
    # MERGE OPERATIONS
    # =========================================================================

    def merge(
        self,
        branch: str,
        message: Optional[str] = None,
        no_ff: bool = True
    ) -> MergeResult:
        """
        Мерж ветки.

        Args:
            branch: Ветка для мержа
            message: Сообщение коммита
            no_ff: Создавать merge commit даже для fast-forward
        """
        args = ["merge", branch]

        if no_ff:
            args.append("--no-ff")

        if message:
            args.extend(["-m", message])

        result = self._run_git(*args, check=False)

        if result.returncode == 0:
            if "Already up to date" in result.stdout:
                return MergeResult.NO_CHANGES
            return MergeResult.SUCCESS

        if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
            return MergeResult.CONFLICT

        return MergeResult.FAILED

    def abort_merge(self):
        """Отменить мерж."""
        self._run_git("merge", "--abort", check=False)

    def get_conflicts(self) -> List[str]:
        """Получить список файлов с конфликтами."""
        result = self._run_git("diff", "--name-only", "--diff-filter=U")
        return [f for f in result.stdout.strip().split("\n") if f]

    def get_conflict_content(self, file: str) -> Optional[ConflictInfo]:
        """Получить содержимое конфликта."""
        file_path = self.repo_path / file

        if not file_path.exists():
            return None

        content = file_path.read_text()

        # Парсим маркеры конфликта
        ours_match = re.search(
            r"<<<<<<< HEAD\n(.*?)\n=======",
            content,
            re.DOTALL
        )
        theirs_match = re.search(
            r"=======\n(.*?)\n>>>>>>>",
            content,
            re.DOTALL
        )

        if ours_match and theirs_match:
            return ConflictInfo(
                file=file,
                ours=ours_match.group(1),
                theirs=theirs_match.group(1),
                base=""  # Можно получить через git show :1:file
            )

        return None

    def resolve_conflict(self, file: str, content: str):
        """Разрешить конфликт записав содержимое."""
        file_path = self.repo_path / file
        file_path.write_text(content)
        self.add_files([file])

    # =========================================================================
    # SMART MERGE (наше дополнение для multi-agent)
    # =========================================================================

    def smart_merge_branches(
        self,
        branches: List[str],
        order: Optional[List[str]] = None
    ) -> Dict[str, MergeResult]:
        """
        Умный мерж нескольких веток.

        Мержит ветки в правильном порядке (учитывая зависимости).
        """
        results = {}
        merge_order = order or branches

        for branch in merge_order:
            if branch not in branches:
                continue

            result = self.merge(
                branch,
                message=f"Merge agent branch: {branch}"
            )

            results[branch] = result

            if result == MergeResult.CONFLICT:
                # Можно попытаться разрешить через AI
                # или прервать
                break

        return results

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def stash(self, message: Optional[str] = None):
        """Сохранить изменения в stash."""
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        self._run_git(*args)

    def stash_pop(self):
        """Восстановить изменения из stash."""
        self._run_git("stash", "pop", check=False)

    def reset_hard(self, ref: str = "HEAD"):
        """Hard reset к указанному ref."""
        self._run_git("reset", "--hard", ref)

    def clean(self, directories: bool = True, force: bool = True):
        """Очистить untracked файлы."""
        args = ["clean"]
        if directories:
            args.append("-d")
        if force:
            args.append("-f")
        self._run_git(*args)

    def get_file_content_at_ref(self, file: str, ref: str = "HEAD") -> Optional[str]:
        """Получить содержимое файла на определённом ref."""
        result = self._run_git("show", f"{ref}:{file}", check=False)
        if result.returncode == 0:
            return result.stdout
        return None


class WorktreeGitOps:
    """
    Git операции для конкретного worktree.

    Обёртка над GitOperations для удобной работы с worktree.
    """

    def __init__(self, worktree_path: Path, main_repo_path: Path):
        self.worktree_path = worktree_path
        self.main_repo_path = main_repo_path
        self.git = GitOperations(worktree_path)
        self.main_git = GitOperations(main_repo_path)

    def commit_and_push(
        self,
        message: str,
        agent_name: str
    ) -> Optional[str]:
        """Коммит и push в worktree."""
        commit_hash = self.git.incremental_commit(message, agent_name)

        if commit_hash:
            # Push ветки
            branch = self.git.get_current_branch()
            subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=self.worktree_path,
                capture_output=True,
                check=False
            )

        return commit_hash

    def sync_with_base(self) -> bool:
        """Синхронизация с базовой веткой."""
        base = self.main_git.get_base_branch()
        branch = self.git.get_current_branch()

        # Fetch updates
        subprocess.run(
            ["git", "fetch", "origin", base],
            cwd=self.worktree_path,
            capture_output=True
        )

        # Rebase на base
        result = subprocess.run(
            ["git", "rebase", f"origin/{base}"],
            cwd=self.worktree_path,
            capture_output=True
        )

        return result.returncode == 0

    def get_changes_from_base(self) -> str:
        """Получить все изменения относительно базовой ветки."""
        base = self.main_git.get_base_branch()
        result = subprocess.run(
            ["git", "diff", f"{base}...HEAD"],
            cwd=self.worktree_path,
            capture_output=True,
            text=True
        )
        return result.stdout
