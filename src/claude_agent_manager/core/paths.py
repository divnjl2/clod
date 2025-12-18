from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    root: Path

    @property
    def manager_dir(self) -> Path:
        return self.root / "manager"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    def agent_dir(self, agent_id: str) -> Path:
        return self.agents_dir / agent_id

    def agent_runs_dir(self, agent_id: str) -> Path:
        return self.agent_dir(agent_id) / "runs"

    def run_dir(self, agent_id: str, run_id: str) -> Path:
        return self.agent_runs_dir(agent_id) / run_id

    def run_worktree_dir(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "worktree"

    def run_state_dir(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "state"

    def run_logs_dir(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "logs"

    def run_artifacts_dir(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "artifacts"

    def run_mcp_dir(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "mcp"

    def agent_locks_dir(self, agent_id: str) -> Path:
        return self.agent_dir(agent_id) / "locks"

    def run_lock_path(self, agent_id: str, run_id: str) -> Path:
        return self.run_dir(agent_id, run_id) / "run.lock"

    def agent_lock_path(self, agent_id: str) -> Path:
        return self.agent_locks_dir(agent_id) / "agent.lock"

    @property
    def manager_locks_dir(self) -> Path:
        return self.manager_dir / "locks"

    @property
    def manager_app_lock(self) -> Path:
        return self.manager_locks_dir / "app.lock"

    @property
    def registry_path(self) -> Path:
        return self.manager_dir / "registry.sqlite"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    tmp_dir = str(path.parent)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=tmp_dir, delete=False) as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
        tmp_name = f.name
    os.replace(tmp_name, path)


def create_workspace_paths(root: Path | str) -> WorkspacePaths:
    """
    Build WorkspacePaths and ensure top-level directories exist.
    """
    root_path = Path(root).expanduser().resolve()
    paths = WorkspacePaths(root=root_path)
    ensure_dir(paths.manager_dir)
    ensure_dir(paths.manager_locks_dir)
    ensure_dir(paths.agents_dir)
    return paths
