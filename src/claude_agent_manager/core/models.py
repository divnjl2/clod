from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    name: str
    role: str
    created_at: datetime = field(default_factory=utc_now)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunSpec:
    run_id: str
    agent_id: str
    created_at: datetime = field(default_factory=utc_now)
    status: str = "created"  # created|starting|running|stopping|stopped|failed
    run_dir: Path | None = None
    worktree_dir: Path | None = None
    ports: dict[str, int] = field(default_factory=dict)
    pids: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
