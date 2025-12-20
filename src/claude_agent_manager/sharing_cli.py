"""
CLI команды для импорта/экспорта агентов и пресетов.

Команды:
- cam preset list          - список пресетов
- cam preset show <name>   - детали пресета
- cam preset use <name>    - создать агента из пресета
- cam preset save          - сохранить агента как пресет
- cam preset import        - импорт из файла/URL
- cam preset remove        - удалить пресет

- cam export <agent_id>    - экспорт агента в бандл
- cam import <file>        - импорт агента из бандла
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

from .sharing import (
    # Preset
    AgentPreset,
    PresetMetadata,
    PresetRegistry,
    export_preset,
    load_preset,
    save_preset,
    apply_preset,
    get_builtin_preset,
    list_builtin_presets,
    PRESET_EXT,
    # Bundle
    export_bundle,
    import_bundle,
    peek_bundle,
    BUNDLE_EXT,
)
from .registry import load_agent, save_agent, iter_agents
from .config import load_config

console = Console()

# Создаём подприложения
preset_app = typer.Typer(name="preset", help="Управление пресетами агентов")
export_app = typer.Typer(name="export", help="Экспорт агентов")
import_app = typer.Typer(name="import", help="Импорт агентов")


def _agent_root():
    cfg = load_config()
    p = Path(cfg.agent_root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _preset_registry():
    return PresetRegistry()


# ============================================================================
# PRESET COMMANDS
# ============================================================================

@preset_app.command("list")
def preset_list(
    show_builtin: bool = typer.Option(True, "--builtin/--no-builtin", help="Показать встроенные пресеты"),
):
    """Список доступных пресетов."""
    registry = _preset_registry()

    table = Table(title="Пресеты агентов")
    table.add_column("Имя", style="cyan")
    table.add_column("Описание")
    table.add_column("Теги", style="dim")
    table.add_column("Источник", style="yellow")

    # Встроенные пресеты
    if show_builtin:
        for name in list_builtin_presets():
            preset = get_builtin_preset(name)
            if preset:
                table.add_row(
                    preset.metadata.name,
                    preset.metadata.description[:50] + "..." if len(preset.metadata.description) > 50 else preset.metadata.description,
                    ", ".join(preset.metadata.tags[:3]),
                    "builtin"
                )

    # Пользовательские пресеты
    for preset in registry.list_presets():
        table.add_row(
            preset.metadata.name,
            preset.metadata.description[:50] + "..." if len(preset.metadata.description) > 50 else preset.metadata.description,
            ", ".join(preset.metadata.tags[:3]),
            "user"
        )

    console.print(table)


@preset_app.command("show")
def preset_show(
    name: str = typer.Argument(..., help="Имя пресета"),
):
    """Показать детали пресета."""
    # Сначала ищем в builtin
    preset = get_builtin_preset(name.lower().replace(" ", "-"))

    # Затем в registry
    if not preset:
        registry = _preset_registry()
        preset = registry.get_preset(name)

    if not preset:
        console.print(f"[red]Пресет '{name}' не найден[/red]")
        raise typer.Exit(1)

    # Выводим информацию
    console.print(Panel(
        f"[bold]{preset.metadata.name}[/bold]\n\n"
        f"{preset.metadata.description}\n\n"
        f"[dim]Автор: {preset.metadata.author or 'N/A'}[/dim]\n"
        f"[dim]Версия: {preset.metadata.version}[/dim]\n"
        f"[dim]Теги: {', '.join(preset.metadata.tags) or 'N/A'}[/dim]",
        title="Пресет"
    ))

    # Permissions
    console.print("\n[bold]Permissions:[/bold]")
    console.print(f"  Preset: {preset.permissions.preset}")
    if preset.permissions.allow:
        console.print(f"  Allow: {', '.join(preset.permissions.allow[:5])}" +
                     ("..." if len(preset.permissions.allow) > 5 else ""))
    if preset.permissions.deny:
        console.print(f"  Deny: {', '.join(preset.permissions.deny[:5])}" +
                     ("..." if len(preset.permissions.deny) > 5 else ""))

    # System prompt
    if preset.config.system_prompt:
        console.print("\n[bold]System Prompt:[/bold]")
        console.print(Panel(preset.config.system_prompt, border_style="dim"))

    # README
    if preset.readme:
        console.print("\n[bold]README:[/bold]")
        console.print(Markdown(preset.readme))


@preset_app.command("use")
def preset_use(
    name: str = typer.Argument(..., help="Имя пресета"),
    project: str = typer.Option(..., "--project", "-p", help="Путь к проекту"),
    agent_id: Optional[str] = typer.Option(None, "--id", help="ID агента (auto-generated if not set)"),
    port: Optional[int] = typer.Option(None, "--port", help="Порт (auto-assigned if not set)"),
    purpose: Optional[str] = typer.Option(None, "--purpose", help="Purpose агента"),
    start: bool = typer.Option(False, "--start", "-s", help="Сразу запустить агента"),
):
    """Создать нового агента из пресета."""
    from . import manager

    # Находим пресет
    preset = get_builtin_preset(name.lower().replace(" ", "-"))
    if not preset:
        registry = _preset_registry()
        preset = registry.get_preset(name)

    if not preset:
        console.print(f"[red]Пресет '{name}' не найден[/red]")
        console.print("[dim]Доступные: " + ", ".join(list_builtin_presets()) + "[/dim]")
        raise typer.Exit(1)

    cfg = load_config()
    agent_root = _agent_root()

    # Генерируем ID если не указан
    if not agent_id:
        import uuid
        agent_id = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"

    # Находим свободный порт если не указан
    if not port:
        from .worker import pick_port
        used_ports = {a.port for a in iter_agents(agent_root)}
        port = pick_port(cfg, used_ports)

    # Создаём агента из пресета
    agent = apply_preset(
        preset=preset,
        agent_id=agent_id,
        project_path=project,
        port=port,
        purpose=purpose,
    )

    # Сохраняем
    save_agent(agent_root, agent)

    console.print(f"[green]✓[/green] Создан агент: {agent.id}")
    console.print(f"  Project: {agent.project_path}")
    console.print(f"  Port: {agent.port}")
    console.print(f"  Permissions: {agent.permissions.preset}")

    if start:
        console.print("\n[cyan]Запускаю агента...[/cyan]")
        manager.start_agent(agent_id, cfg=cfg)
        console.print(f"[green]✓[/green] Агент запущен")
    else:
        console.print(f"\n[dim]Запустить: cam open {agent_id}[/dim]")


@preset_app.command("save")
def preset_save(
    agent_id: str = typer.Argument(..., help="ID агента"),
    name: str = typer.Option(..., "--name", "-n", help="Имя пресета"),
    description: str = typer.Option("", "--desc", "-d", help="Описание"),
    author: str = typer.Option("", "--author", "-a", help="Автор"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Теги через запятую"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Путь для сохранения (по умолчанию в реестр)"),
    include_prompt: bool = typer.Option(True, "--prompt/--no-prompt", help="Включить system prompt"),
    include_mcp: bool = typer.Option(True, "--mcp/--no-mcp", help="Включить MCP конфиг"),
):
    """Сохранить агента как пресет."""
    agent_root = _agent_root()
    agent = load_agent(agent_root, agent_id)

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    preset = export_preset(
        agent=agent,
        name=name,
        description=description,
        author=author,
        tags=tag_list,
        include_system_prompt=include_prompt,
        include_mcp=include_mcp,
    )

    if output:
        path = save_preset(preset, Path(output))
        console.print(f"[green]✓[/green] Пресет сохранён: {path}")
    else:
        registry = _preset_registry()
        path = registry.add_preset(preset)
        console.print(f"[green]✓[/green] Пресет добавлен в реестр: {preset.metadata.name}")

    console.print(f"\n[dim]Использовать: cam preset use \"{name}\" --project /path/to/project[/dim]")


@preset_app.command("import")
def preset_import(
    source: str = typer.Argument(..., help="Путь к файлу или URL"),
):
    """Импортировать пресет из файла или URL."""
    registry = _preset_registry()

    if source.startswith("http://") or source.startswith("https://"):
        console.print(f"[cyan]Загружаю пресет из {source}...[/cyan]")
        preset = registry.import_from_url(source)
    else:
        path = Path(source)
        if not path.exists():
            console.print(f"[red]Файл не найден: {source}[/red]")
            raise typer.Exit(1)
        preset = registry.import_from_file(path)

    console.print(f"[green]✓[/green] Импортирован пресет: {preset.metadata.name}")


@preset_app.command("remove")
def preset_remove(
    name: str = typer.Argument(..., help="Имя пресета"),
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
):
    """Удалить пресет из реестра."""
    registry = _preset_registry()

    if not force:
        confirm = typer.confirm(f"Удалить пресет '{name}'?")
        if not confirm:
            raise typer.Abort()

    if registry.remove_preset(name):
        console.print(f"[green]✓[/green] Пресет удалён: {name}")
    else:
        console.print(f"[yellow]Пресет не найден: {name}[/yellow]")


# ============================================================================
# EXPORT COMMAND
# ============================================================================

@export_app.callback(invoke_without_command=True)
def export_agent(
    ctx: typer.Context,
    agent_id: str = typer.Argument(..., help="ID агента"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Путь для сохранения"),
    include_memory: bool = typer.Option(True, "--memory/--no-memory", help="Включить память"),
    include_history: bool = typer.Option(True, "--history/--no-history", help="Включить историю"),
    include_browser: bool = typer.Option(False, "--browser", help="Включить профили браузера"),
    preset_only: bool = typer.Option(False, "--preset-only", "-p", help="Экспортировать только как пресет"),
    notes: str = typer.Option("", "--notes", "-n", help="Заметки для получателя"),
):
    """Экспортировать агента в файл."""
    agent_root = _agent_root()
    agent = load_agent(agent_root, agent_id)

    if preset_only:
        # Экспорт как пресет
        preset = export_preset(
            agent=agent,
            name=agent.get_display_name(),
            description=agent.purpose,
        )

        output_path = Path(output) if output else Path(f"./{agent_id}{PRESET_EXT}")
        save_preset(preset, output_path)
        console.print(f"[green]✓[/green] Пресет экспортирован: {output_path}")
    else:
        # Полный экспорт
        output_path = Path(output) if output else Path(f"./{agent_id}{BUNDLE_EXT}")

        console.print(f"[cyan]Экспортирую агента {agent_id}...[/cyan]")

        result = export_bundle(
            agent_root=agent_root,
            agent_id=agent_id,
            output_path=output_path,
            include_memory=include_memory,
            include_history=include_history,
            include_browser_profiles=include_browser,
            notes=notes,
        )

        # Размер файла
        size_mb = result.stat().st_size / (1024 * 1024)

        console.print(f"[green]✓[/green] Агент экспортирован: {result}")
        console.print(f"  Размер: {size_mb:.2f} MB")
        console.print(f"  Память: {'да' if include_memory else 'нет'}")
        console.print(f"  История: {'да' if include_history else 'нет'}")

        console.print(f"\n[dim]Импортировать: cam import {result}[/dim]")


# ============================================================================
# IMPORT COMMAND
# ============================================================================

@import_app.callback(invoke_without_command=True)
def import_agent(
    ctx: typer.Context,
    file: str = typer.Argument(..., help="Путь к файлу .camagent.zip или .campreset.json"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Путь к проекту"),
    agent_id: Optional[str] = typer.Option(None, "--id", help="Новый ID агента"),
    port: Optional[int] = typer.Option(None, "--port", help="Новый порт"),
    restore_memory: bool = typer.Option(True, "--memory/--no-memory", help="Восстановить память"),
    restore_history: bool = typer.Option(True, "--history/--no-history", help="Восстановить историю"),
    peek: bool = typer.Option(False, "--peek", help="Только показать содержимое, не импортировать"),
):
    """Импортировать агента из файла."""
    path = Path(file)

    if not path.exists():
        console.print(f"[red]Файл не найден: {file}[/red]")
        raise typer.Exit(1)

    agent_root = _agent_root()

    # Определяем тип файла
    if str(path).endswith(BUNDLE_EXT) or path.suffix == ".zip":
        # Bundle
        if peek:
            manifest = peek_bundle(path)
            console.print(Panel(
                f"[bold]Agent ID:[/bold] {manifest.agent_id}\n"
                f"[bold]Purpose:[/bold] {manifest.agent_purpose}\n"
                f"[bold]Original Path:[/bold] {manifest.original_project_path}\n"
                f"[bold]Created:[/bold] {manifest.created_at}\n\n"
                f"[bold]Includes:[/bold]\n"
                f"  Memory: {'да' if manifest.includes_memory else 'нет'}\n"
                f"  History: {'да' if manifest.includes_history else 'нет'}\n"
                f"  Browser: {'да' if manifest.includes_browser_profiles else 'нет'}\n\n"
                f"[bold]Files:[/bold] {len(manifest.file_list)}\n"
                f"[dim]{', '.join(manifest.file_list[:10])}{'...' if len(manifest.file_list) > 10 else ''}[/dim]",
                title=f"Bundle: {path.name}"
            ))

            if manifest.notes:
                console.print(f"\n[bold]Notes:[/bold]\n{manifest.notes}")

            return

        if not project:
            # Пытаемся использовать оригинальный путь
            manifest = peek_bundle(path)
            project = manifest.original_project_path
            console.print(f"[yellow]Используется оригинальный путь: {project}[/yellow]")
            console.print(f"[dim]Укажите --project для другого пути[/dim]\n")

        console.print(f"[cyan]Импортирую агента из {path}...[/cyan]")

        agent = import_bundle(
            bundle_path=path,
            agent_root=agent_root,
            new_agent_id=agent_id,
            new_project_path=project,
            new_port=port,
            restore_memory=restore_memory,
            restore_history=restore_history,
        )

        console.print(f"[green]✓[/green] Агент импортирован: {agent.id}")
        console.print(f"  Project: {agent.project_path}")
        console.print(f"  Port: {agent.port}")
        console.print(f"\n[dim]Запустить: cam open {agent.id}[/dim]")

    elif str(path).endswith(PRESET_EXT) or path.suffix == ".json":
        # Preset
        preset = load_preset(path)

        if peek:
            preset_show(preset.metadata.name)
            return

        if not project:
            console.print("[red]Для пресета требуется указать --project[/red]")
            raise typer.Exit(1)

        # Используем preset use логику
        preset_use(
            name=preset.metadata.name,
            project=project,
            agent_id=agent_id,
            port=port,
            purpose=None,
            start=False,
        )
    else:
        console.print(f"[red]Неизвестный формат файла. Ожидается {BUNDLE_EXT} или {PRESET_EXT}[/red]")
        raise typer.Exit(1)


# ============================================================================
# SHARE COMMAND (быстрый шаринг)
# ============================================================================

def share_command(
    agent_id: str = typer.Argument(..., help="ID агента"),
    gist: bool = typer.Option(False, "--gist", "-g", help="Создать GitHub Gist"),
    clipboard: bool = typer.Option(True, "--clipboard/--no-clipboard", help="Копировать в буфер"),
):
    """Быстрый шаринг пресета агента."""
    agent_root = _agent_root()
    agent = load_agent(agent_root, agent_id)

    preset = export_preset(
        agent=agent,
        name=agent.get_display_name(),
        description=agent.purpose,
    )

    json_str = preset.model_dump_json(indent=2)

    if gist:
        # TODO: интеграция с GitHub API
        console.print("[yellow]GitHub Gist интеграция в разработке[/yellow]")
        console.print("[dim]Пока можете скопировать JSON вручную[/dim]")

    if clipboard:
        try:
            import subprocess
            # Windows
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # macOS/Linux
                try:
                    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                except FileNotFoundError:
                    process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)

            process.communicate(json_str.encode())
            console.print("[green]✓[/green] Пресет скопирован в буфер обмена")
        except Exception as e:
            console.print(f"[yellow]Не удалось скопировать: {e}[/yellow]")

    console.print("\n[bold]Пресет:[/bold]")
    console.print(Syntax(json_str, "json", theme="monokai"))
