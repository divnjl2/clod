"""
Application settings management.

Handles user preferences for theme, tiling, monitors, etc.
Settings are persisted to JSON in platform-specific config directory.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional


@dataclass
class AppSettings:
    """Application settings."""

    # Appearance
    theme: Literal["dark", "light"] = "dark"

    # Tiling engine
    tiler_engine: Literal["builtin", "komorebi"] = "builtin"
    tile_layout: Literal["grid", "grid_split", "viewer_only"] = "grid_split"
    tile_split_ratio: float = 0.55

    # Auto-tiling behavior
    auto_tile_on_start: bool = True
    auto_tile_on_change: bool = True

    # Monitor settings
    monitor_mode: Literal["primary", "ui_monitor", "fixed_index"] = "primary"
    fixed_monitor_index: int = 0

    # Polling
    poll_interval_ms: int = 1500

    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create settings from dictionary, ignoring unknown keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


def get_config_dir() -> Path:
    """
    Get platform-specific config directory.

    Returns:
        - Windows: %LOCALAPPDATA%/ClaudeAgentManager
        - macOS: ~/Library/Application Support/ClaudeAgentManager
        - Linux: ~/.config/claude-agent-manager
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ClaudeAgentManager"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClaudeAgentManager"
    else:
        # Linux / other Unix
        xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return Path(xdg_config) / "claude-agent-manager"


def get_settings_path() -> Path:
    """Get path to settings JSON file."""
    return get_config_dir() / "settings.json"


def load_settings() -> AppSettings:
    """
    Load settings from disk.

    Returns default settings if file doesn't exist or is invalid.
    """
    settings_path = get_settings_path()

    if not settings_path.exists():
        return AppSettings()

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """
    Save settings to disk.

    Creates config directory if it doesn't exist.
    """
    settings_path = get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings_path.write_text(
        json.dumps(settings.to_dict(), indent=2),
        encoding="utf-8"
    )


def update_setting(key: str, value) -> AppSettings:
    """
    Update a single setting and save.

    Args:
        key: Setting name (must be valid AppSettings field)
        value: New value

    Returns:
        Updated settings

    Raises:
        KeyError: If key is not a valid setting
    """
    if key not in AppSettings.__dataclass_fields__:
        raise KeyError(f"Unknown setting: {key}")

    settings = load_settings()
    setattr(settings, key, value)
    save_settings(settings)
    return settings


# Global cached settings instance
_cached_settings: Optional[AppSettings] = None


def get_settings(reload: bool = False) -> AppSettings:
    """
    Get settings with caching.

    Args:
        reload: Force reload from disk

    Returns:
        Current settings
    """
    global _cached_settings

    if _cached_settings is None or reload:
        _cached_settings = load_settings()

    return _cached_settings


def invalidate_cache() -> None:
    """Clear cached settings, forcing reload on next access."""
    global _cached_settings
    _cached_settings = None
