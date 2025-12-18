from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import ensure_dir


@dataclass(frozen=True, slots=True)
class RunnerEnv:
    env: dict[str, str]
    home_dir: Path
    cache_dir: Path
    config_dir: Path
    data_dir: Path


def build_run_sandbox_env(run_dir: Path, base_env: dict[str, str] | None = None) -> RunnerEnv:
    """
    Ensure caches/configs/data are scoped to the run_dir for isolation.
    """
    base = dict(base_env or os.environ)

    home_dir = ensure_dir(run_dir / ".home")
    cache_dir = ensure_dir(run_dir / ".cache")
    config_dir = ensure_dir(run_dir / ".config")
    data_dir = ensure_dir(run_dir / ".local" / "share")

    env = dict(base)

    env["HOME"] = str(home_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["XDG_CONFIG_HOME"] = str(config_dir)
    env["XDG_DATA_HOME"] = str(data_dir)

    env["USERPROFILE"] = str(home_dir)
    env["APPDATA"] = str(config_dir)
    env["LOCALAPPDATA"] = str(cache_dir)

    env["AGENT_RUN_DIR"] = str(run_dir)
    env["AGENT_HOME"] = str(home_dir)

    return RunnerEnv(env=env, home_dir=home_dir, cache_dir=cache_dir, config_dir=config_dir, data_dir=data_dir)
