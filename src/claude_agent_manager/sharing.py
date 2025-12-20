"""
Система импорта/экспорта агентов и пресетов.

Концепции:
- Preset: легковесный шаблон (permissions, config, system_prompt) — .campreset.json
- Agent Bundle: полный агент с данными — .camagent.zip

Форматы:
- Preset: JSON файл с метаданными
- Bundle: ZIP архив со структурой агента
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any
from dataclasses import dataclass, field, asdict

from pydantic import BaseModel, Field
from rich.console import Console

from .registry import (
    AgentRecord,
    PermissionConfig,
    AgentConfigOptions,
    ProxyConfig,
    load_agent,
    save_agent,
    agent_dir,
    PERMISSION_PRESETS,
)

console = Console()

# Версия формата для совместимости
FORMAT_VERSION = "1.0"

# Расширения файлов
PRESET_EXT = ".campreset.json"
BUNDLE_EXT = ".camagent.zip"


# ============================================================================
# PRESET - легковесный шаблон
# ============================================================================

class PresetMetadata(BaseModel):
    """Метаданные пресета."""
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    format_version: str = FORMAT_VERSION


class AgentPreset(BaseModel):
    """
    Пресет агента — шаблон без runtime данных.

    Включает:
    - Метаданные (имя, описание, автор)
    - Permissions (preset + custom rules)
    - Config (system_prompt, mcp_servers, settings)
    - Опционально: project_path template
    """
    metadata: PresetMetadata
    permissions: PermissionConfig = Field(default_factory=PermissionConfig)
    config: AgentConfigOptions = Field(default_factory=AgentConfigOptions)

    # Опциональные поля
    purpose_template: str = ""  # Шаблон purpose для нового агента
    project_path_hint: str = ""  # Подсказка для project path (e.g. "~/projects/web-apps")
    readme: str = ""  # Документация / инструкции

    # MCP серверы детально (для удобного редактирования)
    mcp_servers_config: dict = Field(default_factory=dict)


def export_preset(
    agent: AgentRecord,
    name: str,
    description: str = "",
    author: str = "",
    tags: Optional[List[str]] = None,
    include_system_prompt: bool = True,
    include_mcp: bool = True,
) -> AgentPreset:
    """
    Создать пресет из существующего агента.

    Args:
        agent: Исходный агент
        name: Имя пресета
        description: Описание
        author: Автор
        tags: Теги для поиска
        include_system_prompt: Включить system prompt
        include_mcp: Включить MCP серверы

    Returns:
        AgentPreset объект
    """
    metadata = PresetMetadata(
        name=name,
        description=description or agent.purpose,
        author=author,
        tags=tags or [],
    )

    # Копируем config, опционально убирая некоторые поля
    config_dict = agent.config.model_dump()
    if not include_system_prompt:
        config_dict["system_prompt"] = None
    if not include_mcp:
        config_dict["mcp_servers"] = None

    config = AgentConfigOptions(**config_dict)

    return AgentPreset(
        metadata=metadata,
        permissions=agent.permissions.model_copy(),
        config=config,
        purpose_template=agent.purpose,
        mcp_servers_config=agent.config.mcp_servers or {},
    )


def save_preset(preset: AgentPreset, path: Path) -> Path:
    """
    Сохранить пресет в файл.

    Args:
        preset: Пресет для сохранения
        path: Путь к файлу (добавит расширение если нет)

    Returns:
        Путь к сохранённому файлу
    """
    if not str(path).endswith(PRESET_EXT):
        path = Path(str(path) + PRESET_EXT)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        preset.model_dump_json(indent=2),
        encoding="utf-8"
    )

    return path


def load_preset(path: Path) -> AgentPreset:
    """
    Загрузить пресет из файла.

    Args:
        path: Путь к файлу пресета

    Returns:
        AgentPreset объект
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return AgentPreset(**data)


def apply_preset(
    preset: AgentPreset,
    agent_id: str,
    project_path: str,
    port: int,
    purpose: Optional[str] = None,
) -> AgentRecord:
    """
    Создать AgentRecord из пресета.

    Args:
        preset: Пресет для применения
        agent_id: ID нового агента
        project_path: Путь к проекту
        port: Порт агента
        purpose: Purpose (по умолчанию из пресета)

    Returns:
        Новый AgentRecord
    """
    return AgentRecord(
        id=agent_id,
        purpose=purpose or preset.purpose_template or preset.metadata.name,
        display_name=preset.metadata.name,
        project_path=project_path,
        port=port,
        pm2_name=f"agent-{agent_id}",
        permissions=preset.permissions.model_copy(),
        config=preset.config.model_copy(),
    )


# ============================================================================
# BUNDLE - полный экспорт агента
# ============================================================================

class BundleManifest(BaseModel):
    """Манифест бандла агента."""
    format_version: str = FORMAT_VERSION
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str
    agent_purpose: str
    includes_memory: bool = False
    includes_history: bool = False
    includes_browser_profiles: bool = False
    original_project_path: str = ""
    file_list: List[str] = Field(default_factory=list)
    notes: str = ""


def export_bundle(
    agent_root: Path,
    agent_id: str,
    output_path: Path,
    include_memory: bool = True,
    include_history: bool = True,
    include_browser_profiles: bool = False,
    notes: str = "",
) -> Path:
    """
    Экспортировать агента в ZIP бандл.

    Args:
        agent_root: Корневая директория агентов
        agent_id: ID агента
        output_path: Путь для сохранения (добавит расширение)
        include_memory: Включить данные памяти
        include_history: Включить историю чатов
        include_browser_profiles: Включить профили браузера
        notes: Заметки для получателя

    Returns:
        Путь к созданному архиву
    """
    agent = load_agent(agent_root, agent_id)
    agent_path = agent_dir(agent_root, agent_id)

    if not str(output_path).endswith(BUNDLE_EXT):
        output_path = Path(str(output_path) + BUNDLE_EXT)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    file_list = []

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. agent.json (основной конфиг)
        agent_json = agent_path / "agent.json"
        if agent_json.exists():
            # Очищаем runtime поля перед экспортом
            export_agent = agent.model_copy()
            export_agent.cmd_pid = None
            export_agent.viewer_pid = None
            # Сохраняем очищенную версию
            zf.writestr("agent.json", export_agent.model_dump_json(indent=2))
            file_list.append("agent.json")

        # 2. Данные памяти (claude-mem data)
        if include_memory:
            memory_dir = agent_path / "memory"
            if memory_dir.exists():
                for f in memory_dir.rglob("*"):
                    if f.is_file():
                        arc_name = f"memory/{f.relative_to(memory_dir)}"
                        zf.write(f, arc_name)
                        file_list.append(arc_name)

        # 3. История чатов / логи
        if include_history:
            for hist_dir in ["history", "logs", "conversations"]:
                hist_path = agent_path / hist_dir
                if hist_path.exists():
                    for f in hist_path.rglob("*"):
                        if f.is_file():
                            arc_name = f"{hist_dir}/{f.relative_to(hist_path)}"
                            zf.write(f, arc_name)
                            file_list.append(arc_name)

        # 4. Профили браузера (осторожно - могут содержать чувствительные данные)
        if include_browser_profiles:
            browser_dir = agent_path / "browser-profiles"
            if browser_dir.exists():
                for f in browser_dir.rglob("*"):
                    if f.is_file():
                        # Пропускаем куки и credentials
                        if any(x in f.name.lower() for x in ["cookie", "credential", "password", "login"]):
                            continue
                        arc_name = f"browser-profiles/{f.relative_to(browser_dir)}"
                        zf.write(f, arc_name)
                        file_list.append(arc_name)

        # 5. CLAUDE.md из проекта (если есть)
        project_path = Path(agent.project_path)
        claude_md = project_path / "CLAUDE.md"
        if claude_md.exists():
            zf.write(claude_md, "project/CLAUDE.md")
            file_list.append("project/CLAUDE.md")

        # 6. .claude/settings.json из проекта
        claude_settings = project_path / ".claude" / "settings.json"
        if claude_settings.exists():
            zf.write(claude_settings, "project/.claude/settings.json")
            file_list.append("project/.claude/settings.json")

        # 7. Манифест
        manifest = BundleManifest(
            agent_id=agent_id,
            agent_purpose=agent.purpose,
            includes_memory=include_memory,
            includes_history=include_history,
            includes_browser_profiles=include_browser_profiles,
            original_project_path=agent.project_path,
            file_list=file_list,
            notes=notes,
        )
        zf.writestr("manifest.json", manifest.model_dump_json(indent=2))

    return output_path


def import_bundle(
    bundle_path: Path,
    agent_root: Path,
    new_agent_id: Optional[str] = None,
    new_project_path: Optional[str] = None,
    new_port: Optional[int] = None,
    restore_memory: bool = True,
    restore_history: bool = True,
) -> AgentRecord:
    """
    Импортировать агента из ZIP бандла.

    Args:
        bundle_path: Путь к архиву
        agent_root: Корневая директория агентов
        new_agent_id: Новый ID (по умолчанию из бандла)
        new_project_path: Новый путь проекта
        new_port: Новый порт
        restore_memory: Восстановить данные памяти
        restore_history: Восстановить историю

    Returns:
        Созданный AgentRecord
    """
    with zipfile.ZipFile(bundle_path, "r") as zf:
        # Читаем манифест
        manifest_data = json.loads(zf.read("manifest.json"))
        manifest = BundleManifest(**manifest_data)

        # Читаем agent.json
        agent_data = json.loads(zf.read("agent.json"))
        agent = AgentRecord(**agent_data)

        # Переопределяем поля
        if new_agent_id:
            agent.id = new_agent_id
            agent.pm2_name = f"agent-{new_agent_id}"

        if new_project_path:
            agent.project_path = new_project_path

        if new_port:
            agent.port = new_port

        # Создаём директорию агента
        new_agent_path = agent_dir(agent_root, agent.id)
        new_agent_path.mkdir(parents=True, exist_ok=True)

        # Сохраняем agent.json
        save_agent(agent_root, agent)

        # Распаковываем данные
        for name in zf.namelist():
            if name == "manifest.json" or name == "agent.json":
                continue

            # Memory
            if name.startswith("memory/") and restore_memory:
                target = new_agent_path / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())

            # History
            elif any(name.startswith(p) for p in ["history/", "logs/", "conversations/"]) and restore_history:
                target = new_agent_path / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())

            # Project files (CLAUDE.md, settings)
            elif name.startswith("project/") and new_project_path:
                rel_path = name[len("project/"):]
                target = Path(new_project_path) / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())

    return agent


def peek_bundle(bundle_path: Path) -> BundleManifest:
    """
    Посмотреть содержимое бандла без распаковки.

    Args:
        bundle_path: Путь к архиву

    Returns:
        BundleManifest с информацией
    """
    with zipfile.ZipFile(bundle_path, "r") as zf:
        manifest_data = json.loads(zf.read("manifest.json"))
        return BundleManifest(**manifest_data)


# ============================================================================
# PRESET REGISTRY - локальный реестр пресетов
# ============================================================================

class PresetRegistry:
    """
    Локальный реестр пресетов.

    Хранит пресеты в ~/.claude-agent-manager/presets/
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or (Path.home() / ".claude-agent-manager" / "presets")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def list_presets(self) -> List[AgentPreset]:
        """Список всех пресетов."""
        presets = []
        for f in self.base_path.glob(f"*{PRESET_EXT}"):
            try:
                presets.append(load_preset(f))
            except Exception:
                continue
        return presets

    def get_preset(self, name: str) -> Optional[AgentPreset]:
        """Получить пресет по имени."""
        # Нормализуем имя
        safe_name = self._safe_filename(name)
        path = self.base_path / f"{safe_name}{PRESET_EXT}"
        if path.exists():
            return load_preset(path)

        # Поиск по metadata.name
        for preset in self.list_presets():
            if preset.metadata.name.lower() == name.lower():
                return preset

        return None

    def add_preset(self, preset: AgentPreset) -> Path:
        """Добавить пресет в реестр."""
        safe_name = self._safe_filename(preset.metadata.name)
        path = self.base_path / f"{safe_name}{PRESET_EXT}"
        return save_preset(preset, path)

    def remove_preset(self, name: str) -> bool:
        """Удалить пресет."""
        safe_name = self._safe_filename(name)
        path = self.base_path / f"{safe_name}{PRESET_EXT}"
        if path.exists():
            path.unlink()
            return True
        return False

    def import_from_file(self, path: Path) -> AgentPreset:
        """Импортировать пресет из файла в реестр."""
        preset = load_preset(path)
        self.add_preset(preset)
        return preset

    def import_from_url(self, url: str) -> AgentPreset:
        """Импортировать пресет по URL."""
        import urllib.request

        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        preset = AgentPreset(**data)
        self.add_preset(preset)
        return preset

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Преобразовать имя в безопасное для файловой системы."""
        # Убираем спец символы, оставляем буквы, цифры, дефисы
        safe = re.sub(r"[^\w\-]", "-", name.lower())
        # Убираем множественные дефисы
        safe = re.sub(r"-+", "-", safe).strip("-")
        return safe or "unnamed"


# ============================================================================
# BUILT-IN PRESETS - встроенные пресеты
# ============================================================================

BUILTIN_PRESETS = {
    "web-developer": AgentPreset(
        metadata=PresetMetadata(
            name="Web Developer",
            description="Полнофункциональный веб-разработчик с доступом к npm, git, docker",
            author="claude-agent-manager",
            tags=["web", "frontend", "backend", "fullstack"],
        ),
        permissions=PermissionConfig(
            preset="permissive",
            allow=["Bash(docker-compose:*)"],
        ),
        config=AgentConfigOptions(
            system_prompt="You are a senior full-stack web developer. Focus on clean, maintainable code with proper error handling.",
        ),
        purpose_template="Web Development Assistant",
    ),

    "code-reviewer": AgentPreset(
        metadata=PresetMetadata(
            name="Code Reviewer",
            description="Безопасный ревьювер кода - только чтение, без модификаций",
            author="claude-agent-manager",
            tags=["review", "security", "readonly"],
        ),
        permissions=PermissionConfig(
            preset="strict",
        ),
        config=AgentConfigOptions(
            system_prompt="You are a code reviewer. Analyze code for bugs, security issues, and improvements. Never modify files directly.",
        ),
        purpose_template="Code Review Assistant",
    ),

    "data-analyst": AgentPreset(
        metadata=PresetMetadata(
            name="Data Analyst",
            description="Анализ данных с Python, pandas, jupyter",
            author="claude-agent-manager",
            tags=["data", "python", "analytics", "ml"],
        ),
        permissions=PermissionConfig(
            preset="default",
            allow=[
                "Bash(jupyter:*)",
                "Bash(pandas:*)",
                "Bash(conda:*)",
            ],
        ),
        config=AgentConfigOptions(
            system_prompt="You are a data analyst expert. Use Python, pandas, and visualization libraries to analyze data and provide insights.",
        ),
        purpose_template="Data Analysis Assistant",
    ),

    "devops": AgentPreset(
        metadata=PresetMetadata(
            name="DevOps Engineer",
            description="DevOps с доступом к Docker, k8s, terraform",
            author="claude-agent-manager",
            tags=["devops", "docker", "kubernetes", "infrastructure"],
        ),
        permissions=PermissionConfig(
            preset="permissive",
            allow=[
                "Bash(kubectl:*)",
                "Bash(terraform:*)",
                "Bash(helm:*)",
                "Bash(aws:*)",
                "Bash(gcloud:*)",
                "Bash(az:*)",
            ],
        ),
        config=AgentConfigOptions(
            system_prompt="You are a DevOps engineer. Help with infrastructure, CI/CD, containerization, and cloud deployments.",
        ),
        purpose_template="DevOps Assistant",
    ),

    "researcher": AgentPreset(
        metadata=PresetMetadata(
            name="Research Assistant",
            description="Исследователь с веб-поиском и анализом документов",
            author="claude-agent-manager",
            tags=["research", "web", "analysis"],
        ),
        permissions=PermissionConfig(
            preset="default",
        ),
        config=AgentConfigOptions(
            system_prompt="You are a research assistant. Search the web, analyze documents, and synthesize information into clear reports.",
        ),
        purpose_template="Research Assistant",
    ),
}


def get_builtin_preset(name: str) -> Optional[AgentPreset]:
    """Получить встроенный пресет."""
    return BUILTIN_PRESETS.get(name)


def list_builtin_presets() -> List[str]:
    """Список имён встроенных пресетов."""
    return list(BUILTIN_PRESETS.keys())
