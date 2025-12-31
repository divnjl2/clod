from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Глобальный конфиг менеджера."""

    claude_mem_root: str = Field(default_factory=lambda: str(Path.home() / ".claude-mem"))
    worker_script: Optional[str] = Field(default=None)

    agent_root: str = Field(default_factory=lambda: str(Path.home() / ".claude-agents"))

    # edge-app | default | path:C:\...\chrome.exe
    browser: str = Field(default="edge-app")

    port_min: int = 37700
    port_max: int = 37799

    def validate_ready(self) -> None:
        """Validate that essential config is set. worker_script is optional."""
        if not self.claude_mem_root:
            raise ValueError("Config 'claude_mem_root' is not set. Run: cam config --claude-mem-root ...")


def config_dir() -> Path:
    return Path.home() / ".cam"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(**data)


def save_config(cfg: AppConfig) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_path().write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
