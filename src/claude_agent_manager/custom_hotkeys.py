"""
Система настраиваемых хоткеев.

Позволяет пользователям:
- Настраивать глобальные хоткеи
- Сохранять конфигурацию
- Добавлять кастомные действия
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Callable, Optional, Any
from enum import Enum

from .hotkeys import (
    GlobalHotkeyManager,
    get_hotkey_manager,
    parse_hotkey_string,
    format_hotkey,
)


class HotkeyAction(str, Enum):
    """Предопределённые действия для хоткеев."""
    TOGGLE_DASHBOARD = "toggle_dashboard"
    SHOW_DASHBOARD = "show_dashboard"
    HIDE_DASHBOARD = "hide_dashboard"

    TOGGLE_OVERLAY = "toggle_overlay"
    SHOW_OVERLAY = "show_overlay"
    HIDE_OVERLAY = "hide_overlay"

    TILE_WINDOWS = "tile_windows"
    FOCUS_AGENT = "focus_agent"

    NEW_AGENT = "new_agent"
    STOP_ALL = "stop_all"

    QUICK_SWITCH_1 = "quick_switch_1"
    QUICK_SWITCH_2 = "quick_switch_2"
    QUICK_SWITCH_3 = "quick_switch_3"
    QUICK_SWITCH_4 = "quick_switch_4"

    COPY_LAST_OUTPUT = "copy_last_output"
    SCREENSHOT_AGENT = "screenshot_agent"

    CUSTOM = "custom"


@dataclass
class HotkeyConfig:
    """Конфигурация одного хоткея."""
    action: str
    hotkey: str  # e.g. "ctrl+alt+d"
    enabled: bool = True
    description: str = ""
    custom_command: str = ""  # Для CUSTOM action

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "HotkeyConfig":
        return cls(**data)


@dataclass
class HotkeySettings:
    """Полные настройки хоткеев."""
    version: str = "1.0"
    hotkeys: Dict[str, HotkeyConfig] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "hotkeys": {k: v.to_dict() for k, v in self.hotkeys.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "HotkeySettings":
        settings = cls(version=data.get("version", "1.0"))
        for action, config in data.get("hotkeys", {}).items():
            settings.hotkeys[action] = HotkeyConfig.from_dict(config)
        return settings


# Дефолтные хоткеи
DEFAULT_HOTKEYS: Dict[str, HotkeyConfig] = {
    HotkeyAction.TOGGLE_DASHBOARD.value: HotkeyConfig(
        action=HotkeyAction.TOGGLE_DASHBOARD.value,
        hotkey="ctrl+alt+d",
        description="Показать/скрыть главное меню агентов"
    ),
    HotkeyAction.TOGGLE_OVERLAY.value: HotkeyConfig(
        action=HotkeyAction.TOGGLE_OVERLAY.value,
        hotkey="ctrl+alt+o",
        description="Показать/скрыть overlay с метриками"
    ),
    HotkeyAction.TILE_WINDOWS.value: HotkeyConfig(
        action=HotkeyAction.TILE_WINDOWS.value,
        hotkey="ctrl+alt+t",
        description="Расположить окна агентов плиткой"
    ),
    HotkeyAction.QUICK_SWITCH_1.value: HotkeyConfig(
        action=HotkeyAction.QUICK_SWITCH_1.value,
        hotkey="ctrl+alt+1",
        description="Переключиться на агента #1"
    ),
    HotkeyAction.QUICK_SWITCH_2.value: HotkeyConfig(
        action=HotkeyAction.QUICK_SWITCH_2.value,
        hotkey="ctrl+alt+2",
        description="Переключиться на агента #2"
    ),
    HotkeyAction.QUICK_SWITCH_3.value: HotkeyConfig(
        action=HotkeyAction.QUICK_SWITCH_3.value,
        hotkey="ctrl+alt+3",
        description="Переключиться на агента #3"
    ),
    HotkeyAction.QUICK_SWITCH_4.value: HotkeyConfig(
        action=HotkeyAction.QUICK_SWITCH_4.value,
        hotkey="ctrl+alt+4",
        description="Переключиться на агента #4"
    ),
    HotkeyAction.NEW_AGENT.value: HotkeyConfig(
        action=HotkeyAction.NEW_AGENT.value,
        hotkey="ctrl+alt+n",
        description="Создать нового агента",
        enabled=False  # Отключено по умолчанию
    ),
    HotkeyAction.STOP_ALL.value: HotkeyConfig(
        action=HotkeyAction.STOP_ALL.value,
        hotkey="ctrl+alt+escape",
        description="Остановить всех агентов",
        enabled=False  # Отключено по умолчанию (опасно)
    ),
}


class CustomHotkeyManager:
    """
    Менеджер кастомных хоткеев с персистентностью.

    Использование:
        manager = CustomHotkeyManager()
        manager.load()
        manager.register_action(HotkeyAction.TOGGLE_DASHBOARD, show_hide_dashboard)
        manager.start()
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or (
            Path.home() / ".claude-agent-manager" / "hotkeys.json"
        )
        self._settings = HotkeySettings(hotkeys=dict(DEFAULT_HOTKEYS))
        self._action_handlers: Dict[str, Callable[[], None]] = {}
        self._hotkey_manager = get_hotkey_manager()
        self._registered_ids: List[int] = []

    @property
    def settings(self) -> HotkeySettings:
        return self._settings

    def load(self) -> None:
        """Загрузить настройки из файла."""
        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                loaded = HotkeySettings.from_dict(data)

                # Мержим с дефолтами (добавляем новые, сохраняем пользовательские)
                for action, default_config in DEFAULT_HOTKEYS.items():
                    if action not in loaded.hotkeys:
                        loaded.hotkeys[action] = default_config

                self._settings = loaded
            except Exception:
                pass  # Используем дефолты

    def save(self) -> None:
        """Сохранить настройки в файл."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps(self._settings.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def register_action(self, action: HotkeyAction | str, handler: Callable[[], None]) -> None:
        """Зарегистрировать обработчик для действия."""
        action_str = action.value if isinstance(action, HotkeyAction) else action
        self._action_handlers[action_str] = handler

    def set_hotkey(self, action: str, hotkey: str) -> bool:
        """Изменить хоткей для действия."""
        if action not in self._settings.hotkeys:
            return False

        # Проверяем валидность
        mods, vk = parse_hotkey_string(hotkey)
        if vk == 0 and hotkey.lower() != "none":
            return False

        self._settings.hotkeys[action].hotkey = hotkey
        self.save()

        # Перерегистрируем если запущено
        self._reregister_hotkeys()

        return True

    def set_enabled(self, action: str, enabled: bool) -> None:
        """Включить/выключить хоткей."""
        if action in self._settings.hotkeys:
            self._settings.hotkeys[action].enabled = enabled
            self.save()
            self._reregister_hotkeys()

    def add_custom_hotkey(
        self,
        name: str,
        hotkey: str,
        handler: Callable[[], None],
        description: str = ""
    ) -> bool:
        """Добавить полностью кастомный хоткей."""
        # Проверяем валидность
        mods, vk = parse_hotkey_string(hotkey)
        if vk == 0:
            return False

        action_id = f"custom_{name}"

        self._settings.hotkeys[action_id] = HotkeyConfig(
            action=HotkeyAction.CUSTOM.value,
            hotkey=hotkey,
            description=description,
            custom_command=name
        )

        self._action_handlers[action_id] = handler
        self.save()
        self._reregister_hotkeys()

        return True

    def remove_custom_hotkey(self, name: str) -> bool:
        """Удалить кастомный хоткей."""
        action_id = f"custom_{name}"
        if action_id in self._settings.hotkeys:
            del self._settings.hotkeys[action_id]
            self._action_handlers.pop(action_id, None)
            self.save()
            self._reregister_hotkeys()
            return True
        return False

    def get_hotkey_for_action(self, action: HotkeyAction | str) -> str:
        """Получить текущий хоткей для действия."""
        action_str = action.value if isinstance(action, HotkeyAction) else action
        config = self._settings.hotkeys.get(action_str)
        return config.hotkey if config else ""

    def list_hotkeys(self) -> List[Dict[str, Any]]:
        """Получить список всех хоткеев."""
        result = []
        for action, config in self._settings.hotkeys.items():
            result.append({
                "action": action,
                "hotkey": config.hotkey,
                "hotkey_formatted": format_hotkey(*parse_hotkey_string(config.hotkey)) if config.hotkey else "None",
                "enabled": config.enabled,
                "description": config.description,
                "has_handler": action in self._action_handlers,
            })
        return result

    def start(self) -> None:
        """Запустить обработку хоткеев."""
        self._register_all_hotkeys()
        self._hotkey_manager.start()

    def stop(self) -> None:
        """Остановить обработку хоткеев."""
        self._hotkey_manager.stop()

    def process_callbacks(self) -> None:
        """Обработать ожидающие callbacks (вызывать из main thread)."""
        self._hotkey_manager.process_callbacks()

    def _register_all_hotkeys(self) -> None:
        """Зарегистрировать все хоткеи."""
        for action, config in self._settings.hotkeys.items():
            if not config.enabled:
                continue

            if action not in self._action_handlers:
                continue

            mods, vk = parse_hotkey_string(config.hotkey)
            if vk == 0:
                continue

            self._hotkey_manager.register(
                config.hotkey,
                self._action_handlers[action],
                config.description
            )

    def _reregister_hotkeys(self) -> None:
        """Перерегистрировать хоткеи после изменения настроек."""
        if self._hotkey_manager._running:
            self._hotkey_manager.unregister_all()
            self._register_all_hotkeys()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_custom_manager: Optional[CustomHotkeyManager] = None


def get_custom_hotkey_manager() -> CustomHotkeyManager:
    """Получить singleton менеджера кастомных хоткеев."""
    global _custom_manager
    if _custom_manager is None:
        _custom_manager = CustomHotkeyManager()
        _custom_manager.load()
    return _custom_manager


def setup_default_hotkeys(
    toggle_dashboard: Callable[[], None],
    toggle_overlay: Optional[Callable[[], None]] = None,
    tile_windows: Optional[Callable[[], None]] = None,
    quick_switch: Optional[Callable[[int], None]] = None,
) -> CustomHotkeyManager:
    """
    Быстрая настройка стандартных хоткеев.

    Args:
        toggle_dashboard: Показать/скрыть dashboard
        toggle_overlay: Показать/скрыть overlay
        tile_windows: Расположить окна плиткой
        quick_switch: Переключение на агента по номеру (1-4)

    Returns:
        Настроенный менеджер
    """
    manager = get_custom_hotkey_manager()

    manager.register_action(HotkeyAction.TOGGLE_DASHBOARD, toggle_dashboard)

    if toggle_overlay:
        manager.register_action(HotkeyAction.TOGGLE_OVERLAY, toggle_overlay)

    if tile_windows:
        manager.register_action(HotkeyAction.TILE_WINDOWS, tile_windows)

    if quick_switch:
        manager.register_action(HotkeyAction.QUICK_SWITCH_1, lambda: quick_switch(1))
        manager.register_action(HotkeyAction.QUICK_SWITCH_2, lambda: quick_switch(2))
        manager.register_action(HotkeyAction.QUICK_SWITCH_3, lambda: quick_switch(3))
        manager.register_action(HotkeyAction.QUICK_SWITCH_4, lambda: quick_switch(4))

    return manager
