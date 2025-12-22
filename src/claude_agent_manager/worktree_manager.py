"""
Git Worktrees Manager для безопасной изоляции задач.

Использование:
    from claude_agent_manager.worktree_manager import WorktreeManager

    wm = WorktreeManager(project_path)
    worktree = wm.create_task_worktree("agent-123", "add-oauth")

    # Работа в worktree...

    # Merge или discard
    wm.merge_worktree(worktree)
    # или
    wm.discard_worktree(worktree)
"""

from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

console = Console()


@dataclass
class Worktree:
    """Представление git worktree."""
    path: Path
    branch_name: str
    commit_hash: str
    created_at: datetime
    agent_id: str
    task_name: str


class WorktreeManager:
    """Управление git worktrees для изоляции агентских задач."""

    def __init__(self, project_path: Path, worktrees_base_dir: Optional[Path] = None):
        self.project_path = project_path.resolve()

        if not self._is_git_repo():
            raise ValueError(f"{project_path} is not a git repository")

        # Базовая директория для worktrees
        if worktrees_base_dir is None:
            self.worktrees_base_dir = self.project_path / ".worktrees"
        else:
            self.worktrees_base_dir = worktrees_base_dir

        self.worktrees_base_dir.mkdir(exist_ok=True)

    def _is_git_repo(self) -> bool:
        """Проверить, является ли директория git репозиторием."""
        return (self.project_path / ".git").exists()

    def _run_git(self, *args, cwd: Optional[Path] = None) -> str:
        """Выполнить git команду."""
        if cwd is None:
            cwd = self.project_path

        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()

    def create_task_worktree(
        self,
        agent_id: str,
        task_name: str,
        base_branch: str = "main"
    ) -> Worktree:
        """
        Создать изолированный worktree для задачи агента.

        Args:
            agent_id: ID агента
            task_name: название задачи (используется в branch name)
            base_branch: базовая ветка для создания worktree

        Returns:
            Worktree объект с информацией о созданном worktree

        Example:
            wm = WorktreeManager(Path("/project"))
            worktree = wm.create_task_worktree("agent-123", "add-oauth")
            # Теперь агент может работать в worktree.path
        """
        # Санитизируем task_name для использования в branch
        safe_task_name = task_name.lower().replace(" ", "-").replace("_", "-")
        branch_name = f"agent/{agent_id}/{safe_task_name}"

        # Путь к worktree
        worktree_path = self.worktrees_base_dir / f"{agent_id}-{safe_task_name}"

        # Проверяем, не существует ли уже
        if worktree_path.exists():
            console.print(f"[yellow]Warning: Worktree {worktree_path} already exists, removing...[/yellow]")
            self.discard_worktree(worktree_path)

        # Обновляем базовую ветку (если есть remote)
        has_remote = False
        try:
            remotes = self._run_git("remote")
            has_remote = "origin" in remotes
        except subprocess.CalledProcessError:
            pass

        if has_remote:
            try:
                self._run_git("fetch", "origin", base_branch)
                self._run_git("checkout", base_branch)
                self._run_git("pull", "origin", base_branch)
            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]Warning: Could not update {base_branch}: {e}[/yellow]")
        else:
            # Для локальных репозиториев просто переключаемся на base_branch
            try:
                self._run_git("checkout", base_branch)
            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]Warning: Could not checkout {base_branch}: {e}[/yellow]")

        # Проверяем, существует ли уже ветка
        branch_exists = False
        try:
            self._run_git("rev-parse", "--verify", branch_name)
            branch_exists = True
        except subprocess.CalledProcessError:
            pass

        # Создаём worktree
        try:
            if branch_exists:
                # Ветка уже существует - используем её
                console.print(f"[yellow]Branch {branch_name} exists, creating worktree from existing branch[/yellow]")
                self._run_git(
                    "worktree", "add",
                    str(worktree_path),
                    branch_name
                )
            else:
                # Создаём новую ветку
                self._run_git(
                    "worktree", "add",
                    "-b", branch_name,
                    str(worktree_path),
                    base_branch
                )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create worktree: {e.stderr or e}")

        # Получаем commit hash
        commit_hash = self._run_git("rev-parse", "HEAD", cwd=worktree_path)

        worktree = Worktree(
            path=worktree_path,
            branch_name=branch_name,
            commit_hash=commit_hash,
            created_at=datetime.now(),
            agent_id=agent_id,
            task_name=task_name
        )

        console.print(Panel(
            f"Created worktree for agent {agent_id}\n"
            f"Path: {worktree_path}\n"
            f"Branch: {branch_name}\n"
            f"Commit: {commit_hash[:8]}",
            title="Worktree Created",
            border_style="green"
        ))

        return worktree

    def list_worktrees(self) -> List[Worktree]:
        """
        Список всех активных worktrees.

        Returns:
            Список Worktree объектов
        """
        output = self._run_git("worktree", "list", "--porcelain")

        worktrees = []
        lines = output.split('\n')

        i = 0
        while i < len(lines):
            if lines[i].startswith('worktree '):
                path_str = lines[i].split(' ', 1)[1]
                path = Path(path_str)

                # Пропускаем main worktree
                if path == self.project_path:
                    i += 1
                    while i < len(lines) and not lines[i].startswith('worktree '):
                        i += 1
                    continue

                # Парсим остальные поля
                branch_name = None
                commit_hash = None

                i += 1
                while i < len(lines) and not lines[i].startswith('worktree '):
                    if lines[i].startswith('HEAD '):
                        commit_hash = lines[i].split(' ')[1]
                    elif lines[i].startswith('branch '):
                        branch_name = lines[i].split(' ', 1)[1].replace('refs/heads/', '')
                    i += 1

                # Пытаемся извлечь agent_id и task_name из branch name
                agent_id = "unknown"
                task_name = "unknown"

                if branch_name and branch_name.startswith('agent/'):
                    parts = branch_name.split('/')
                    if len(parts) >= 3:
                        agent_id = parts[1]
                        task_name = '/'.join(parts[2:])

                worktrees.append(Worktree(
                    path=path,
                    branch_name=branch_name or "unknown",
                    commit_hash=commit_hash or "unknown",
                    created_at=datetime.fromtimestamp(path.stat().st_ctime),
                    agent_id=agent_id,
                    task_name=task_name
                ))
            else:
                i += 1

        return worktrees

    def merge_worktree(
        self,
        worktree: Worktree | Path,
        target_branch: str = "main",
        delete_after: bool = True,
        squash: bool = False
    ) -> bool:
        """
        Смёржить изменения из worktree в целевую ветку.

        Args:
            worktree: Worktree объект или Path к worktree
            target_branch: целевая ветка для merge
            delete_after: удалить worktree после успешного merge
            squash: использовать squash merge

        Returns:
            True если merge успешен, False иначе
        """
        if isinstance(worktree, Path):
            # Найти worktree по пути
            for wt in self.list_worktrees():
                if wt.path == worktree:
                    worktree = wt
                    break
            else:
                raise ValueError(f"Worktree not found: {worktree}")

        # Проверяем наличие remote
        has_remote = False
        try:
            remotes = self._run_git("remote")
            has_remote = "origin" in remotes
        except subprocess.CalledProcessError:
            pass

        # Переключаемся на target branch
        try:
            self._run_git("checkout", target_branch)
            if has_remote:
                self._run_git("pull", "origin", target_branch)
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error updating {target_branch}: {e}[/red]")
            return False

        # Выполняем merge
        try:
            if squash:
                self._run_git("merge", "--squash", worktree.branch_name)
                # После squash нужно сделать commit вручную
                commit_msg = f"Merge branch '{worktree.branch_name}' (squashed)"
                self._run_git("commit", "-m", commit_msg)
            else:
                self._run_git("merge", worktree.branch_name, "--no-ff")

            console.print(Panel(
                f"Successfully merged {worktree.branch_name} into {target_branch}",
                title="Merge Complete",
                border_style="green"
            ))

            # Push изменения (только если есть remote)
            if has_remote:
                try:
                    self._run_git("push", "origin", target_branch)
                except subprocess.CalledProcessError as e:
                    console.print(f"[yellow]Warning: Could not push to origin: {e}[/yellow]")

            # Удаляем worktree если требуется
            if delete_after:
                self.discard_worktree(worktree.path)

            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Merge failed: {e}[/red]")
            console.print("[yellow]You may need to resolve conflicts manually[/yellow]")
            return False

    def discard_worktree(self, worktree: Worktree | Path, force: bool = False):
        """
        Удалить worktree и опционально ветку.

        Args:
            worktree: Worktree объект или Path к worktree
            force: принудительное удаление даже с uncommitted changes
        """
        if isinstance(worktree, Worktree):
            path = worktree.path
            branch_name = worktree.branch_name
        else:
            path = worktree
            # Пытаемся найти branch name
            for wt in self.list_worktrees():
                if wt.path == path:
                    branch_name = wt.branch_name
                    break
            else:
                branch_name = None

        # Удаляем worktree
        try:
            if force:
                self._run_git("worktree", "remove", "--force", str(path))
            else:
                self._run_git("worktree", "remove", str(path))
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error removing worktree: {e}[/red]")
            # Если worktree не существует в git, но директория есть - удаляем вручную
            if path.exists():
                shutil.rmtree(path)

        # Удаляем ветку
        if branch_name:
            try:
                self._run_git("branch", "-D", branch_name)
                console.print(f"[green]Deleted branch {branch_name}[/green]")
            except subprocess.CalledProcessError:
                pass  # Branch уже удалён или не существует

        console.print(f"[green]Discarded worktree: {path}[/green]")

    def get_worktree_status(self, worktree: Worktree | Path) -> dict:
        """
        Получить статус worktree (изменённые файлы, commits ahead и т.д.)

        Returns:
            dict с информацией о статусе
        """
        if isinstance(worktree, Worktree):
            path = worktree.path
        else:
            path = worktree

        # Количество uncommitted changes
        status_output = self._run_git("status", "--porcelain", cwd=path)
        uncommitted_files = len([line for line in status_output.split('\n') if line])

        # Количество commits ahead of main
        try:
            ahead_output = self._run_git(
                "rev-list", "--count", "main..HEAD",
                cwd=path
            )
            commits_ahead = int(ahead_output)
        except:
            commits_ahead = 0

        # Последний commit message
        try:
            last_commit = self._run_git(
                "log", "-1", "--pretty=%B",
                cwd=path
            )
        except:
            last_commit = "No commits"

        return {
            "uncommitted_files": uncommitted_files,
            "commits_ahead": commits_ahead,
            "last_commit": last_commit,
            "has_changes": uncommitted_files > 0 or commits_ahead > 0
        }
