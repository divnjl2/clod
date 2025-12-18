from __future__ import annotations

import random
from pathlib import Path

from .config import AppConfig
from .processes import pm2_start_worker


def pick_port(cfg: AppConfig, used: set[int]) -> int:
    for _ in range(200):
        p = random.randint(cfg.port_min, cfg.port_max)
        if p not in used:
            return p
    raise RuntimeError("Unable to pick a free port from the configured range.")


def start_worker(cfg: AppConfig, pm2_name: str, port: int, data_dir: Path, base_env: dict[str, str] | None = None) -> None:
    env = {
        **(base_env or {}),
        "CLAUDE_MEM_WORKER_PORT": str(port),
        "CLAUDE_MEM_DATA_DIR": str(data_dir),
    }
    pm2_start_worker(
        name=pm2_name,
        worker_script=cfg.worker_script,  # type: ignore[arg-type]
        cwd=cfg.claude_mem_root,          # type: ignore[arg-type]
        env=env,
    )
