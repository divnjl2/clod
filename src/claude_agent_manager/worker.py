from __future__ import annotations

import random
import socket
from pathlib import Path

from .config import AppConfig
from .processes import pm2_start_worker


def is_port_free(port: int) -> bool:
    """Проверяет, свободен ли порт в системе."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def pick_port(cfg: AppConfig, used: set[int]) -> int:
    """
    Выбирает свободный порт для нового агента.

    Проверяет:
    1. Порт не используется другими агентами (used set)
    2. Порт свободен в системе (socket bind test)
    """
    for _ in range(200):
        p = random.randint(cfg.port_min, cfg.port_max)
        if p not in used and is_port_free(p):
            return p
    raise RuntimeError("Unable to pick a free port from the configured range.")


def find_available_port(
    preferred: int | None,
    port_min: int,
    port_max: int,
    exclude: set[int],
) -> int:
    """
    Адаптивный выбор порта для агента при запуске.

    Логика:
    1. Если preferred задан и свободен → вернуть его (sticky port)
    2. Иначе найти первый свободный в диапазоне [port_min, port_max]
    3. Исключить порты других агентов (exclude)

    Args:
        preferred: Предпочтительный порт (last_port агента)
        port_min: Минимум диапазона
        port_max: Максимум диапазона
        exclude: Порты других запущенных агентов

    Returns:
        Свободный порт

    Raises:
        RuntimeError: Если нет свободных портов в диапазоне
    """
    # 1. Пробуем preferred порт
    if preferred is not None and preferred not in exclude:
        if is_port_free(preferred):
            return preferred

    # 2. Последовательный поиск свободного порта в диапазоне
    for port in range(port_min, port_max + 1):
        if port not in exclude and is_port_free(port):
            return port

    # 3. Fallback: рандомный поиск (на случай если последовательный пропустил)
    for _ in range(100):
        port = random.randint(port_min, port_max)
        if port not in exclude and is_port_free(port):
            return port

    raise RuntimeError(
        f"Не найден свободный порт в диапазоне [{port_min}-{port_max}]. "
        f"Исключено портов: {len(exclude)}"
    )


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
