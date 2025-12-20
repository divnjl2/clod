"""
Auto-updater для claude-agent-manager.

Стратегия:
- При запуске CLI проверяет версию в фоне (не блокирует)
- Кэширует результат на 24 часа
- Показывает уведомление если есть апдейт
- Команда `cam update` для ручного обновления
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

from . import __version__

# Конфигурация - можно переопределить через env vars
GITHUB_REPO = os.environ.get("CAM_GITHUB_REPO", "YOUR_USERNAME/clod")  # TODO: заменить
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
PYPI_PACKAGE = os.environ.get("CAM_PYPI_PACKAGE", "")  # Пусто = не проверять PyPI

# Кэш файл
CACHE_DIR = Path.home() / ".claude-agent-manager"
UPDATE_CACHE = CACHE_DIR / "update_cache.json"
CHECK_INTERVAL = timedelta(hours=int(os.environ.get("CAM_UPDATE_CHECK_HOURS", "24")))

# Можно отключить через env var
UPDATES_DISABLED = os.environ.get("CAM_DISABLE_UPDATES", "").lower() in ("1", "true", "yes")

console = Console()


def get_current_version() -> str:
    """Получить текущую установленную версию."""
    return __version__


def _load_cache() -> dict:
    """Загрузить кэш проверки обновлений."""
    try:
        if UPDATE_CACHE.exists():
            return json.loads(UPDATE_CACHE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(data: dict) -> None:
    """Сохранить кэш."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        UPDATE_CACHE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _should_check() -> bool:
    """Проверить, нужно ли делать запрос (кэш истёк?)."""
    cache = _load_cache()
    last_check = cache.get("last_check")
    if not last_check:
        return True

    try:
        last_dt = datetime.fromisoformat(last_check)
        return datetime.now() - last_dt > CHECK_INTERVAL
    except Exception:
        return True


def _fetch_latest_version_github() -> Optional[str]:
    """Получить последнюю версию с GitHub Releases."""
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json"}
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            # Убираем 'v' prefix если есть
            return tag.lstrip("v") if tag else None
    except Exception:
        return None


def _fetch_latest_version_pypi() -> Optional[str]:
    """Получить последнюю версию с PyPI."""
    try:
        import urllib.request

        url = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("info", {}).get("version")
    except Exception:
        return None


def _compare_versions(current: str, latest: str) -> bool:
    """Сравнить версии. Возвращает True если latest > current."""
    def parse(v: str) -> Tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except Exception:
            return (0,)

    return parse(latest) > parse(current)


def check_for_updates(silent: bool = True) -> Optional[str]:
    """
    Проверить наличие обновлений.

    Args:
        silent: Если True, не выводить сообщения (для фоновой проверки)

    Returns:
        Новая версия если доступна, иначе None
    """
    # Проверяем кэш
    if not _should_check():
        cache = _load_cache()
        latest = cache.get("latest_version")
        current = get_current_version()
        if latest and _compare_versions(current, latest):
            return latest
        return None

    # Делаем запрос
    latest = _fetch_latest_version_github()

    # Fallback на PyPI если GitHub не ответил
    if not latest and PYPI_PACKAGE:
        latest = _fetch_latest_version_pypi()

    # Сохраняем в кэш
    _save_cache({
        "last_check": datetime.now().isoformat(),
        "latest_version": latest,
        "current_version": get_current_version()
    })

    if latest and _compare_versions(get_current_version(), latest):
        return latest

    return None


def check_updates_background(callback=None) -> None:
    """
    Запустить проверку обновлений в фоновом потоке.

    Args:
        callback: Функция для вызова если найдено обновление (принимает версию)
    """
    if UPDATES_DISABLED:
        return

    def _check():
        try:
            new_version = check_for_updates(silent=True)
            if new_version and callback:
                callback(new_version)
        except Exception:
            pass  # Тихо игнорируем ошибки в фоне

    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


def print_update_notification(new_version: str) -> None:
    """Вывести уведомление об обновлении."""
    console.print(
        f"\n[yellow]⬆ Доступна новая версия: {new_version}[/yellow] "
        f"[dim](текущая: {get_current_version()})[/dim]"
    )
    console.print("[dim]  Обновить: cam update[/dim]\n")


def do_update(force: bool = False) -> bool:
    """
    Выполнить обновление.

    Args:
        force: Принудительное обновление даже если версия та же

    Returns:
        True если обновление успешно
    """
    console.print("[cyan]Проверяю обновления...[/cyan]")

    new_version = check_for_updates(silent=False)
    current = get_current_version()

    if not new_version and not force:
        console.print(f"[green]✓[/green] Уже установлена последняя версия ({current})")
        return True

    if new_version:
        console.print(f"[yellow]Найдена новая версия: {new_version}[/yellow]")

    console.print("[cyan]Обновляю...[/cyan]")

    try:
        # Вариант 1: pip install с GitHub
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install", "--upgrade",
                f"git+https://github.com/{GITHUB_REPO}.git"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print(f"[green]✓[/green] Обновлено до версии {new_version or 'latest'}")

            # Очищаем кэш
            _save_cache({})

            console.print("[dim]Перезапустите cam для применения изменений[/dim]")
            return True
        else:
            console.print(f"[red]✗[/red] Ошибка обновления: {result.stderr}")
            return False

    except Exception as e:
        console.print(f"[red]✗[/red] Ошибка: {e}")
        return False


def do_update_from_local(path: str) -> bool:
    """
    Обновить из локальной директории (для разработки).

    Args:
        path: Путь к локальной копии репозитория
    """
    console.print(f"[cyan]Устанавливаю из {path}...[/cyan]")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Установлено в режиме разработки")
            return True
        else:
            console.print(f"[red]✗[/red] Ошибка: {result.stderr}")
            return False

    except Exception as e:
        console.print(f"[red]✗[/red] Ошибка: {e}")
        return False
