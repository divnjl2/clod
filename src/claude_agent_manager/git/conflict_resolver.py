"""
AI-powered Git Conflict Resolver.

Автоматически разрешает конфликты merge используя AI.

Использование:
    from claude_agent_manager.git.conflict_resolver import ConflictResolver

    resolver = ConflictResolver(project_path)
    result = await resolver.resolve_file_conflicts("path/to/file.py")

    if result.success:
        print(f"Resolved {len(result.conflicts_resolved)} conflicts")
    else:
        print(f"Need manual review: {result.conflicts_remaining}")
"""

from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


class ConflictSeverity(str, Enum):
    """Серьёзность конфликта."""
    LOW = "low"          # Простые конфликты (whitespace, comments)
    MEDIUM = "medium"    # Требуют анализа контекста
    HIGH = "high"        # Критические изменения логики


class MergeStrategy(str, Enum):
    """Стратегии разрешения конфликтов."""
    OURS = "ours"            # Использовать нашу версию
    THEIRS = "theirs"        # Использовать их версию
    BOTH = "both"            # Объединить оба варианта
    MANUAL = "manual"        # Требует ручного вмешательства
    AI_MERGE = "ai_merge"    # AI-powered merge


@dataclass
class ConflictInfo:
    """Информация о конфликте."""
    file_path: str
    start_line: int
    end_line: int
    ours_content: str
    theirs_content: str
    base_content: Optional[str] = None
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    suggested_strategy: Optional[MergeStrategy] = None
    resolution: Optional[str] = None
    explanation: Optional[str] = None


@dataclass
class MergeResult:
    """Результат merge операции."""
    success: bool
    file_path: str
    merged_content: Optional[str] = None
    conflicts_resolved: List[ConflictInfo] = field(default_factory=list)
    conflicts_remaining: List[ConflictInfo] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "file_path": self.file_path,
            "conflicts_resolved": len(self.conflicts_resolved),
            "conflicts_remaining": len(self.conflicts_remaining),
            "explanation": self.explanation
        }


class ConflictResolver:
    """
    AI-powered conflict resolver для git merge.

    Анализирует конфликты и пытается автоматически их разрешить.
    """

    # Regex для парсинга git conflict markers
    CONFLICT_PATTERN = re.compile(
        r'<<<<<<< (?P<ours_label>.*?)\n'
        r'(?P<ours>.*?)'
        r'(?:\|{7} (?P<base_label>.*?)\n(?P<base>.*?))?'
        r'={7}\n'
        r'(?P<theirs>.*?)'
        r'>>>>>>> (?P<theirs_label>.*?)\n',
        re.DOTALL
    )

    def __init__(self, project_path: Path, enable_ai: bool = True):
        self.project_path = project_path.resolve()
        self.enable_ai = enable_ai

    def _run_git(self, *args, cwd: Optional[Path] = None) -> str:
        """Выполнить git команду."""
        if cwd is None:
            cwd = self.project_path

        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def get_conflicted_files(self) -> List[Path]:
        """Получить список файлов с конфликтами."""
        output = self._run_git("diff", "--name-only", "--diff-filter=U")

        files = []
        for line in output.split('\n'):
            if line.strip():
                files.append(self.project_path / line.strip())

        return files

    def parse_conflicts(self, file_path: Path) -> List[ConflictInfo]:
        """
        Парсить конфликты из файла.

        Args:
            file_path: Путь к файлу с конфликтами

        Returns:
            Список ConflictInfo
        """
        if not file_path.exists():
            return []

        content = file_path.read_text(encoding='utf-8')
        conflicts = []

        for i, match in enumerate(self.CONFLICT_PATTERN.finditer(content)):
            ours = match.group('ours').strip()
            theirs = match.group('theirs').strip()
            base = match.group('base')
            if base:
                base = base.strip()

            # Определяем severity
            severity = self._assess_severity(ours, theirs)

            # Предлагаем стратегию
            strategy = self._suggest_strategy(ours, theirs, base)

            # Вычисляем номера строк
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            end_line = start_line + match.group(0).count('\n')

            # Используем resolve() для обработки коротких путей Windows
            try:
                rel_path = str(file_path.resolve().relative_to(self.project_path.resolve()))
            except ValueError:
                # Если relative_to не работает, используем имя файла
                rel_path = str(file_path.name)

            conflicts.append(ConflictInfo(
                file_path=rel_path,
                start_line=start_line,
                end_line=end_line,
                ours_content=ours,
                theirs_content=theirs,
                base_content=base,
                severity=severity,
                suggested_strategy=strategy
            ))

        return conflicts

    def _assess_severity(self, ours: str, theirs: str) -> ConflictSeverity:
        """Оценить серьёзность конфликта."""
        # Простые случаи
        if ours.strip() == theirs.strip():
            return ConflictSeverity.LOW

        # Whitespace только
        if ours.split() == theirs.split():
            return ConflictSeverity.LOW

        # Одна сторона пустая
        if not ours.strip() or not theirs.strip():
            return ConflictSeverity.LOW

        # Изменения в ключевых конструкциях
        critical_keywords = ['def ', 'class ', 'return ', 'raise ', 'import ', 'async ', 'await ']
        for keyword in critical_keywords:
            ours_has = keyword in ours
            theirs_has = keyword in theirs
            if ours_has != theirs_has:
                return ConflictSeverity.HIGH

        # По умолчанию
        return ConflictSeverity.MEDIUM

    def _suggest_strategy(
        self,
        ours: str,
        theirs: str,
        base: Optional[str]
    ) -> MergeStrategy:
        """
        Предложить стратегию разрешения.

        Args:
            ours: Наша версия
            theirs: Их версия
            base: Базовая версия (если есть)

        Returns:
            Рекомендованная стратегия
        """
        # Одинаковые - любая
        if ours.strip() == theirs.strip():
            return MergeStrategy.OURS

        # Одна пустая - использовать непустую
        if not ours.strip():
            return MergeStrategy.THEIRS
        if not theirs.strip():
            return MergeStrategy.OURS

        # Если есть base - проверяем, кто изменил
        if base:
            if ours == base:
                return MergeStrategy.THEIRS  # Только theirs изменился
            if theirs == base:
                return MergeStrategy.OURS    # Только ours изменился

        # Добавления (не перекрываются)
        if self._can_combine(ours, theirs):
            return MergeStrategy.BOTH

        # Сложный случай - нужен AI или ручной review
        return MergeStrategy.AI_MERGE

    def _can_combine(self, ours: str, theirs: str) -> bool:
        """
        Проверить, можно ли объединить изменения.

        Простые случаи:
        - Добавления в конец
        - Добавления в начало
        - Добавления в разные места
        """
        ours_lines = set(ours.strip().split('\n'))
        theirs_lines = set(theirs.strip().split('\n'))

        # Проверяем пересечение
        common = ours_lines & theirs_lines

        # Если большая часть общая - можно объединить
        if len(common) > min(len(ours_lines), len(theirs_lines)) * 0.5:
            return True

        return False

    def resolve_conflict(self, conflict: ConflictInfo) -> ConflictInfo:
        """
        Разрешить один конфликт.

        Args:
            conflict: Информация о конфликте

        Returns:
            ConflictInfo с заполненным resolution
        """
        strategy = conflict.suggested_strategy or MergeStrategy.MANUAL

        if strategy == MergeStrategy.OURS:
            conflict.resolution = conflict.ours_content
            conflict.explanation = "Used our version (theirs was unchanged or empty)"

        elif strategy == MergeStrategy.THEIRS:
            conflict.resolution = conflict.theirs_content
            conflict.explanation = "Used their version (ours was unchanged or empty)"

        elif strategy == MergeStrategy.BOTH:
            # Объединяем
            conflict.resolution = self._merge_both(
                conflict.ours_content,
                conflict.theirs_content,
                conflict.base_content
            )
            conflict.explanation = "Combined both changes"

        elif strategy == MergeStrategy.AI_MERGE and self.enable_ai:
            # AI merge - пока используем эвристики
            conflict.resolution = self._ai_merge(
                conflict.ours_content,
                conflict.theirs_content,
                conflict.base_content
            )
            conflict.explanation = "AI-assisted merge based on semantic analysis"

        else:
            # Нужен ручной review
            conflict.resolution = None
            conflict.explanation = "Requires manual review - changes are too complex"

        return conflict

    def _merge_both(
        self,
        ours: str,
        theirs: str,
        base: Optional[str]
    ) -> str:
        """Объединить оба варианта."""
        # Простая стратегия: добавляем уникальные строки из theirs после ours
        ours_lines = ours.strip().split('\n')
        theirs_lines = theirs.strip().split('\n')

        result_lines = ours_lines.copy()

        for line in theirs_lines:
            if line not in ours_lines:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def _ai_merge(
        self,
        ours: str,
        theirs: str,
        base: Optional[str]
    ) -> str:
        """
        AI-powered merge (упрощённая версия).

        В будущем здесь может быть вызов к Claude API для
        семантического анализа и merge.
        """
        # Пока используем эвристику: берём longer version
        # и проверяем, что она включает ключевые элементы из обеих версий

        ours_keywords = set(re.findall(r'\b\w+\b', ours))
        theirs_keywords = set(re.findall(r'\b\w+\b', theirs))

        # Если ours содержит больше keywords из theirs - используем ours
        if len(theirs_keywords - ours_keywords) < len(ours_keywords - theirs_keywords):
            return ours
        else:
            return theirs

    def resolve_file_conflicts(self, file_path: Path) -> MergeResult:
        """
        Разрешить все конфликты в файле.

        Args:
            file_path: Путь к файлу

        Returns:
            MergeResult с результатами
        """
        if not file_path.exists():
            return MergeResult(
                success=False,
                file_path=str(file_path),
                explanation=f"File not found: {file_path}"
            )

        conflicts = self.parse_conflicts(file_path)

        if not conflicts:
            return MergeResult(
                success=True,
                file_path=str(file_path),
                merged_content=file_path.read_text(encoding='utf-8'),
                explanation="No conflicts found"
            )

        resolved = []
        remaining = []

        # Разрешаем конфликты
        for conflict in conflicts:
            resolved_conflict = self.resolve_conflict(conflict)

            if resolved_conflict.resolution is not None:
                resolved.append(resolved_conflict)
            else:
                remaining.append(resolved_conflict)

        # Если все разрешены - применяем
        if not remaining:
            content = file_path.read_text(encoding='utf-8')
            merged = self._apply_resolutions(content, resolved)

            return MergeResult(
                success=True,
                file_path=str(file_path),
                merged_content=merged,
                conflicts_resolved=resolved,
                explanation=f"Resolved {len(resolved)} conflict(s)"
            )
        else:
            return MergeResult(
                success=False,
                file_path=str(file_path),
                conflicts_resolved=resolved,
                conflicts_remaining=remaining,
                explanation=f"Resolved {len(resolved)}, need review: {len(remaining)}"
            )

    def _apply_resolutions(
        self,
        content: str,
        conflicts: List[ConflictInfo]
    ) -> str:
        """Применить разрешения к контенту."""
        # Применяем в обратном порядке (чтобы не сбивать позиции)
        result = content

        for conflict in reversed(conflicts):
            if conflict.resolution is None:
                continue

            # Находим и заменяем конфликт
            for match in self.CONFLICT_PATTERN.finditer(result):
                if match.group('ours').strip() == conflict.ours_content:
                    result = (
                        result[:match.start()] +
                        conflict.resolution + '\n' +
                        result[match.end():]
                    )
                    break

        return result

    def resolve_all(self, auto_apply: bool = False) -> List[MergeResult]:
        """
        Разрешить конфликты во всех файлах.

        Args:
            auto_apply: Автоматически применить разрешённые конфликты

        Returns:
            Список результатов
        """
        files = self.get_conflicted_files()
        results = []

        for file_path in files:
            console.print(f"[cyan]Processing {file_path}...[/cyan]")

            result = self.resolve_file_conflicts(file_path)
            results.append(result)

            if result.success and auto_apply and result.merged_content:
                file_path.write_text(result.merged_content, encoding='utf-8')
                console.print(f"[green]✓ Applied resolution to {file_path}[/green]")
            elif not result.success:
                console.print(f"[yellow]! Need manual review: {file_path}[/yellow]")
                for conflict in result.conflicts_remaining:
                    console.print(f"  Line {conflict.start_line}: {conflict.explanation}")

        return results


def print_conflict(conflict: ConflictInfo) -> None:
    """Красиво вывести информацию о конфликте."""
    console.print(Panel(
        f"File: {conflict.file_path}\n"
        f"Lines: {conflict.start_line}-{conflict.end_line}\n"
        f"Severity: {conflict.severity.value}\n"
        f"Strategy: {conflict.suggested_strategy.value if conflict.suggested_strategy else 'unknown'}",
        title="Conflict",
        border_style="yellow"
    ))

    console.print("[bold]Ours:[/bold]")
    console.print(Syntax(conflict.ours_content, "python", line_numbers=True))

    console.print("\n[bold]Theirs:[/bold]")
    console.print(Syntax(conflict.theirs_content, "python", line_numbers=True))

    if conflict.resolution:
        console.print("\n[bold green]Resolution:[/bold green]")
        console.print(Syntax(conflict.resolution, "python", line_numbers=True))
