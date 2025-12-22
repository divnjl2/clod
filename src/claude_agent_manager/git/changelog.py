"""
Changelog Generator - автоматическая генерация changelog из git history.

Анализирует коммиты и генерирует структурированный changelog
в формате Keep a Changelog (https://keepachangelog.com/).

Использование:
    from claude_agent_manager.git.changelog import ChangelogGenerator

    generator = ChangelogGenerator(project_path)
    changelog = generator.generate(from_tag="v1.0.0", to_tag="HEAD")

    # Сохранить в CHANGELOG.md
    generator.save_changelog(changelog, "CHANGELOG.md")

    # Создать GitHub Release
    generator.create_github_release(changelog, "v1.1.0")
"""

from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from enum import Enum

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


class ChangeType(str, Enum):
    """Типы изменений (Keep a Changelog)."""
    ADDED = "Added"
    CHANGED = "Changed"
    DEPRECATED = "Deprecated"
    REMOVED = "Removed"
    FIXED = "Fixed"
    SECURITY = "Security"
    BREAKING = "Breaking"
    OTHER = "Other"


@dataclass
class ChangelogEntry:
    """Запись в changelog."""
    type: ChangeType
    description: str
    commit_hash: str
    author: str
    date: datetime
    scope: Optional[str] = None  # e.g., "api", "cli", "core"
    breaking: bool = False
    related_issues: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Конвертировать в markdown."""
        prefix = "**BREAKING:** " if self.breaking else ""
        scope = f"**{self.scope}:** " if self.scope else ""
        issues = ""
        if self.related_issues:
            issues = " (" + ", ".join(f"#{i}" for i in self.related_issues) + ")"

        return f"- {prefix}{scope}{self.description}{issues}"


@dataclass
class ChangelogVersion:
    """Версия changelog."""
    version: str
    date: datetime
    entries: Dict[ChangeType, List[ChangelogEntry]] = field(default_factory=dict)

    def add_entry(self, entry: ChangelogEntry) -> None:
        """Добавить запись."""
        if entry.type not in self.entries:
            self.entries[entry.type] = []
        self.entries[entry.type].append(entry)

    def to_markdown(self) -> str:
        """Конвертировать в markdown."""
        lines = [
            f"## [{self.version}] - {self.date.strftime('%Y-%m-%d')}",
            ""
        ]

        # Порядок секций согласно Keep a Changelog
        order = [
            ChangeType.BREAKING,
            ChangeType.ADDED,
            ChangeType.CHANGED,
            ChangeType.DEPRECATED,
            ChangeType.REMOVED,
            ChangeType.FIXED,
            ChangeType.SECURITY,
            ChangeType.OTHER
        ]

        for change_type in order:
            entries = self.entries.get(change_type, [])
            if entries:
                lines.append(f"### {change_type.value}")
                lines.append("")
                for entry in entries:
                    lines.append(entry.to_markdown())
                lines.append("")

        return '\n'.join(lines)


class ChangelogGenerator:
    """
    Генератор changelog из git history.

    Анализирует conventional commits и создаёт структурированный changelog.
    """

    # Conventional Commits pattern
    COMMIT_PATTERN = re.compile(
        r'^(?P<type>\w+)'
        r'(?:\((?P<scope>[^)]+)\))?'
        r'(?P<breaking>!)?'
        r':\s*'
        r'(?P<description>.+)$'
    )

    # Маппинг типов коммитов в ChangeType
    TYPE_MAPPING = {
        'feat': ChangeType.ADDED,
        'feature': ChangeType.ADDED,
        'add': ChangeType.ADDED,
        'fix': ChangeType.FIXED,
        'bugfix': ChangeType.FIXED,
        'hotfix': ChangeType.FIXED,
        'change': ChangeType.CHANGED,
        'refactor': ChangeType.CHANGED,
        'perf': ChangeType.CHANGED,
        'docs': ChangeType.CHANGED,
        'style': ChangeType.CHANGED,
        'deprecate': ChangeType.DEPRECATED,
        'remove': ChangeType.REMOVED,
        'security': ChangeType.SECURITY,
        'breaking': ChangeType.BREAKING,
        'chore': ChangeType.OTHER,
        'ci': ChangeType.OTHER,
        'build': ChangeType.OTHER,
        'test': ChangeType.OTHER,
    }

    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()

    def _run_git(self, *args) -> str:
        """Выполнить git команду."""
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def get_commits(
        self,
        from_ref: str = "",
        to_ref: str = "HEAD"
    ) -> List[Dict]:
        """
        Получить список коммитов между refs.

        Args:
            from_ref: Начальный ref (пустой = с начала)
            to_ref: Конечный ref

        Returns:
            Список коммитов
        """
        # Format: hash|author|date|subject|body
        format_str = "%H|%an|%aI|%s|%b"

        if from_ref:
            range_spec = f"{from_ref}..{to_ref}"
        else:
            range_spec = to_ref

        output = self._run_git(
            "log",
            f"--pretty=format:{format_str}",
            "--no-merges",
            range_spec
        )

        commits = []
        for line in output.split('\n'):
            if not line.strip():
                continue

            parts = line.split('|', 4)
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'author': parts[1],
                    'date': parts[2],
                    'subject': parts[3],
                    'body': parts[4] if len(parts) > 4 else ''
                })

        return commits

    def parse_commit(self, commit: Dict) -> Optional[ChangelogEntry]:
        """
        Парсить коммит в ChangelogEntry.

        Args:
            commit: Данные коммита

        Returns:
            ChangelogEntry или None если не парсится
        """
        subject = commit['subject']

        # Пробуем Conventional Commits
        match = self.COMMIT_PATTERN.match(subject)

        if match:
            commit_type = match.group('type').lower()
            scope = match.group('scope')
            breaking = bool(match.group('breaking'))
            description = match.group('description')

            change_type = self.TYPE_MAPPING.get(commit_type, ChangeType.OTHER)

            # BREAKING override
            if breaking:
                change_type = ChangeType.BREAKING

        else:
            # Пробуем определить тип из ключевых слов
            lower_subject = subject.lower()

            if any(kw in lower_subject for kw in ['add', 'new', 'feat', 'implement']):
                change_type = ChangeType.ADDED
            elif any(kw in lower_subject for kw in ['fix', 'bug', 'repair', 'resolve']):
                change_type = ChangeType.FIXED
            elif any(kw in lower_subject for kw in ['remove', 'delete', 'drop']):
                change_type = ChangeType.REMOVED
            elif any(kw in lower_subject for kw in ['security', 'vuln', 'cve']):
                change_type = ChangeType.SECURITY
            elif any(kw in lower_subject for kw in ['deprecat']):
                change_type = ChangeType.DEPRECATED
            elif any(kw in lower_subject for kw in ['break', 'incompatible']):
                change_type = ChangeType.BREAKING
            else:
                change_type = ChangeType.CHANGED

            scope = None
            breaking = 'breaking' in lower_subject.lower()
            description = subject

        # Ищем связанные issues
        issues = re.findall(r'#(\d+)', commit['body'] + ' ' + subject)

        # Парсим дату
        try:
            date = datetime.fromisoformat(commit['date'].replace('Z', '+00:00'))
        except:
            date = datetime.now()

        return ChangelogEntry(
            type=change_type,
            description=description,
            commit_hash=commit['hash'][:8],
            author=commit['author'],
            date=date,
            scope=scope,
            breaking=breaking,
            related_issues=issues
        )

    def generate(
        self,
        version: str = "Unreleased",
        from_tag: str = "",
        to_tag: str = "HEAD",
        include_types: Optional[List[ChangeType]] = None,
        exclude_scopes: Optional[List[str]] = None
    ) -> ChangelogVersion:
        """
        Сгенерировать changelog.

        Args:
            version: Название версии
            from_tag: Начальный тег/ref
            to_tag: Конечный тег/ref
            include_types: Какие типы включать (None = все)
            exclude_scopes: Какие scope исключить

        Returns:
            ChangelogVersion
        """
        commits = self.get_commits(from_tag, to_tag)

        changelog = ChangelogVersion(
            version=version,
            date=datetime.now()
        )

        for commit in commits:
            entry = self.parse_commit(commit)

            if entry is None:
                continue

            # Фильтрация по типам
            if include_types and entry.type not in include_types:
                continue

            # Фильтрация по scope
            if exclude_scopes and entry.scope in exclude_scopes:
                continue

            changelog.add_entry(entry)

        return changelog

    def generate_full_changelog(
        self,
        versions: Optional[List[Dict]] = None
    ) -> str:
        """
        Сгенерировать полный changelog по версиям.

        Args:
            versions: Список версий с тегами
                [{"version": "1.0.0", "from": "v0.9.0", "to": "v1.0.0"}, ...]

        Returns:
            Полный markdown changelog
        """
        lines = [
            "# Changelog",
            "",
            "All notable changes to this project will be documented in this file.",
            "",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
            "",
        ]

        if versions is None:
            # Автоматически определяем версии из тегов
            versions = self._get_versions_from_tags()

        for ver in versions:
            changelog = self.generate(
                version=ver['version'],
                from_tag=ver.get('from', ''),
                to_tag=ver.get('to', 'HEAD')
            )
            lines.append(changelog.to_markdown())

        return '\n'.join(lines)

    def _get_versions_from_tags(self) -> List[Dict]:
        """Получить версии из git тегов."""
        output = self._run_git("tag", "-l", "--sort=-version:refname", "v*")

        tags = [t.strip() for t in output.split('\n') if t.strip()]

        if not tags:
            return [{"version": "Unreleased", "from": "", "to": "HEAD"}]

        versions = [{"version": "Unreleased", "from": tags[0], "to": "HEAD"}]

        for i, tag in enumerate(tags):
            from_tag = tags[i + 1] if i + 1 < len(tags) else ""
            versions.append({
                "version": tag.lstrip('v'),
                "from": from_tag,
                "to": tag
            })

        return versions

    def save_changelog(
        self,
        changelog: ChangelogVersion,
        output_path: str = "CHANGELOG.md",
        prepend: bool = True
    ) -> Path:
        """
        Сохранить changelog.

        Args:
            changelog: Changelog для сохранения
            output_path: Путь к файлу
            prepend: Добавить в начало существующего файла

        Returns:
            Путь к файлу
        """
        output_file = self.project_path / output_path

        new_content = changelog.to_markdown()

        if prepend and output_file.exists():
            existing = output_file.read_text(encoding='utf-8')

            # Находим место для вставки (после заголовка)
            header_end = existing.find('\n## ')
            if header_end > 0:
                # Вставляем после заголовка
                content = existing[:header_end] + '\n' + new_content + existing[header_end:]
            else:
                # Добавляем в конец
                content = existing + '\n' + new_content
        else:
            content = new_content

        output_file.write_text(content, encoding='utf-8')

        console.print(f"[green]Changelog saved to {output_file}[/green]")
        return output_file

    def create_github_release(
        self,
        changelog: ChangelogVersion,
        tag_name: str,
        draft: bool = True
    ) -> bool:
        """
        Создать GitHub Release.

        Args:
            changelog: Changelog для release notes
            tag_name: Название тега
            draft: Создать как draft

        Returns:
            True если успешно
        """
        try:
            notes = changelog.to_markdown()

            # Удаляем заголовок версии для release notes
            lines = notes.split('\n')
            if lines and lines[0].startswith('## '):
                notes = '\n'.join(lines[2:])

            draft_flag = "--draft" if draft else ""

            subprocess.run(
                ["gh", "release", "create", tag_name,
                 "--title", f"Release {tag_name}",
                 "--notes", notes,
                 draft_flag],
                cwd=self.project_path,
                check=True
            )

            console.print(f"[green]GitHub Release created: {tag_name}[/green]")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to create release: {e}[/red]")
            return False
        except FileNotFoundError:
            console.print("[yellow]gh CLI not found. Install: https://cli.github.com/[/yellow]")
            return False


def print_changelog(changelog: ChangelogVersion) -> None:
    """Красиво вывести changelog."""
    md = Markdown(changelog.to_markdown())
    console.print(Panel(md, title=f"Changelog v{changelog.version}", border_style="blue"))
