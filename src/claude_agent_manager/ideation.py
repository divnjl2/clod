"""
Feature Anticipation / Ideation - генерация идей для улучшения проекта.

Анализирует проект и предлагает:
- Улучшения кода
- UI/UX улучшения
- Документацию
- Безопасность
- Производительность

Использование:
    from claude_agent_manager.ideation import IdeaGenerator

    generator = IdeaGenerator(project_path)
    ideas = await generator.generate_ideas(types=["security", "performance"])

    for idea in ideas:
        print(f"{idea.type}: {idea.title}")
"""

from __future__ import annotations

import json
import re
import ast
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class IdeaType(str, Enum):
    """Типы идей."""
    CODE_IMPROVEMENT = "code_improvement"
    UI_UX = "ui_ux"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    TESTING = "testing"
    ARCHITECTURE = "architecture"


class Priority(str, Enum):
    """Приоритет идеи."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Effort(str, Enum):
    """Оценка трудозатрат."""
    TRIVIAL = "trivial"      # < 1 час
    SMALL = "small"          # 1-4 часа
    MEDIUM = "medium"        # 1-2 дня
    LARGE = "large"          # 3-5 дней
    EPIC = "epic"            # > 1 недели


@dataclass
class Idea:
    """Идея для улучшения."""
    id: str
    type: IdeaType
    title: str
    description: str
    priority: Priority = Priority.MEDIUM
    effort: Effort = Effort.MEDIUM
    affected_files: List[str] = field(default_factory=list)
    rationale: str = ""
    implementation_hint: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        result = asdict(self)
        result['type'] = self.type.value
        result['priority'] = self.priority.value
        result['effort'] = self.effort.value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Idea:
        return cls(
            id=data['id'],
            type=IdeaType(data['type']),
            title=data['title'],
            description=data['description'],
            priority=Priority(data.get('priority', 'medium')),
            effort=Effort(data.get('effort', 'medium')),
            affected_files=data.get('affected_files', []),
            rationale=data.get('rationale', ''),
            implementation_hint=data.get('implementation_hint', ''),
            created_at=data.get('created_at', '')
        )


class IdeaGenerator:
    """
    Генератор идей для улучшения проекта.

    Анализирует код и предлагает улучшения.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()
        self.ideas_file = self.project_path / ".clod" / "ideas.json"
        self.ideas_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_ideas(self) -> List[Idea]:
        """Загрузить существующие идеи."""
        if not self.ideas_file.exists():
            return []

        try:
            with open(self.ideas_file, encoding='utf-8') as f:
                data = json.load(f)
            return [Idea.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_ideas(self, ideas: List[Idea]) -> None:
        """Сохранить идеи."""
        with open(self.ideas_file, 'w', encoding='utf-8') as f:
            json.dump([i.to_dict() for i in ideas], f, indent=2, ensure_ascii=False)

    def _generate_id(self, idea_type: IdeaType) -> str:
        """Генерировать уникальный ID."""
        existing = self._load_ideas()
        type_count = sum(1 for i in existing if i.type == idea_type) + 1
        prefix = idea_type.value[:3].upper()
        return f"{prefix}-{type_count:03d}"

    def generate_ideas(
        self,
        types: Optional[List[IdeaType]] = None,
        max_per_type: int = 5
    ) -> List[Idea]:
        """
        Сгенерировать идеи на основе анализа проекта.

        Args:
            types: Типы идей для генерации (None = все)
            max_per_type: Максимум идей каждого типа

        Returns:
            Список идей
        """
        if types is None:
            types = list(IdeaType)

        all_ideas = []

        for idea_type in types:
            console.print(f"[cyan]Analyzing for {idea_type.value}...[/cyan]")

            if idea_type == IdeaType.CODE_QUALITY:
                ideas = self._analyze_code_quality(max_per_type)
            elif idea_type == IdeaType.SECURITY:
                ideas = self._analyze_security(max_per_type)
            elif idea_type == IdeaType.PERFORMANCE:
                ideas = self._analyze_performance(max_per_type)
            elif idea_type == IdeaType.DOCUMENTATION:
                ideas = self._analyze_documentation(max_per_type)
            elif idea_type == IdeaType.TESTING:
                ideas = self._analyze_testing(max_per_type)
            elif idea_type == IdeaType.ARCHITECTURE:
                ideas = self._analyze_architecture(max_per_type)
            else:
                ideas = []

            all_ideas.extend(ideas)

        # Сохраняем
        existing = self._load_ideas()
        all_ideas.extend(existing)
        self._save_ideas(all_ideas)

        return all_ideas

    def _analyze_code_quality(self, max_ideas: int) -> List[Idea]:
        """Анализ качества кода."""
        ideas = []

        for py_file in self.project_path.rglob("*.py"):
            # Пропускаем venv, __pycache__, etc.
            if any(p in str(py_file) for p in ['venv', '__pycache__', '.git', 'node_modules']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                tree = ast.parse(content)
            except:
                continue

            # 1. Длинные функции
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 50
                    if lines > 50:
                        ideas.append(Idea(
                            id=self._generate_id(IdeaType.CODE_QUALITY),
                            type=IdeaType.CODE_QUALITY,
                            title=f"Refactor long function '{node.name}'",
                            description=f"Function '{node.name}' is {lines} lines long. Consider splitting it into smaller functions.",
                            priority=Priority.MEDIUM,
                            effort=Effort.MEDIUM,
                            affected_files=[str(py_file.relative_to(self.project_path))],
                            rationale="Long functions are hard to understand, test, and maintain.",
                            implementation_hint="Extract related logic into helper functions."
                        ))

            # 2. Много параметров
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = len(node.args.args)
                    if params > 5:
                        ideas.append(Idea(
                            id=self._generate_id(IdeaType.CODE_QUALITY),
                            type=IdeaType.CODE_QUALITY,
                            title=f"Too many parameters in '{node.name}'",
                            description=f"Function '{node.name}' has {params} parameters. Consider using a dataclass or config object.",
                            priority=Priority.LOW,
                            effort=Effort.SMALL,
                            affected_files=[str(py_file.relative_to(self.project_path))],
                            rationale="Functions with many parameters are hard to call correctly.",
                            implementation_hint="Create a dataclass for related parameters."
                        ))

            # 3. Глубокая вложенность
            # Упрощённая проверка через regex
            deep_nesting = len(re.findall(r'^(\s{16,})(if|for|while|with)', content, re.MULTILINE))
            if deep_nesting > 3:
                ideas.append(Idea(
                    id=self._generate_id(IdeaType.CODE_QUALITY),
                    type=IdeaType.CODE_QUALITY,
                    title=f"Deep nesting in {py_file.name}",
                    description="File contains deeply nested code blocks. Consider extracting functions.",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    affected_files=[str(py_file.relative_to(self.project_path))],
                    rationale="Deep nesting makes code hard to follow.",
                    implementation_hint="Use early returns, extract functions, or flatten conditionals."
                ))

            if len(ideas) >= max_ideas:
                break

        return ideas[:max_ideas]

    def _analyze_security(self, max_ideas: int) -> List[Idea]:
        """Анализ безопасности."""
        ideas = []

        security_patterns = [
            (r'eval\s*\(', "Use of eval()", "Eval can execute arbitrary code. Replace with ast.literal_eval() or safe alternatives."),
            (r'exec\s*\(', "Use of exec()", "Exec can execute arbitrary code. Consider safer alternatives."),
            (r'subprocess\..*shell\s*=\s*True', "Shell=True in subprocess", "Shell=True can lead to shell injection. Use shell=False with list arguments."),
            (r'pickle\.load', "Pickle deserialization", "Pickle can execute arbitrary code on load. Use json or safer alternatives."),
            (r'yaml\.load\s*\([^,]+\)', "Unsafe YAML load", "Use yaml.safe_load() instead of yaml.load()."),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password", "Passwords should not be hardcoded. Use environment variables or secrets management."),
            (r'(api_key|secret|token)\s*=\s*["\'][^"\']+["\']', "Hardcoded secret", "Secrets should not be hardcoded. Use environment variables."),
            (r'\.format\([^)]*\)\s*$', "Potential SQL injection", "String formatting for SQL can lead to injection. Use parameterized queries."),
        ]

        for py_file in self.project_path.rglob("*.py"):
            if any(p in str(py_file) for p in ['venv', '__pycache__', '.git', 'test']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
            except:
                continue

            for pattern, title, hint in security_patterns:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                if matches:
                    ideas.append(Idea(
                        id=self._generate_id(IdeaType.SECURITY),
                        type=IdeaType.SECURITY,
                        title=title,
                        description=f"Found {len(matches)} instance(s) in {py_file.name}",
                        priority=Priority.HIGH,
                        effort=Effort.SMALL,
                        affected_files=[str(py_file.relative_to(self.project_path))],
                        rationale="Security vulnerability pattern detected.",
                        implementation_hint=hint
                    ))

            if len(ideas) >= max_ideas:
                break

        return ideas[:max_ideas]

    def _analyze_performance(self, max_ideas: int) -> List[Idea]:
        """Анализ производительности."""
        ideas = []

        perf_patterns = [
            (r'for\s+\w+\s+in\s+range\(len\(', "range(len()) antipattern", "Use enumerate() instead of range(len())."),
            (r'\.append\([^)]+\)\s*$', "Append in loop", "Consider list comprehension instead of append in loops."),
            (r'\+\s*=\s*["\']', "String concatenation in loop", "Use ''.join() for string building in loops."),
            (r'time\.sleep\([^)]*\)', "Blocking sleep", "Consider async/await for I/O operations."),
            (r'import\s+\*', "Wildcard import", "Import only what you need for faster startup."),
        ]

        for py_file in self.project_path.rglob("*.py"):
            if any(p in str(py_file) for p in ['venv', '__pycache__', '.git']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
            except:
                continue

            for pattern, title, hint in perf_patterns:
                matches = list(re.finditer(pattern, content))
                if matches:
                    ideas.append(Idea(
                        id=self._generate_id(IdeaType.PERFORMANCE),
                        type=IdeaType.PERFORMANCE,
                        title=f"{title} in {py_file.name}",
                        description=f"Found {len(matches)} instance(s).",
                        priority=Priority.LOW,
                        effort=Effort.TRIVIAL,
                        affected_files=[str(py_file.relative_to(self.project_path))],
                        rationale="Performance optimization opportunity.",
                        implementation_hint=hint
                    ))

            if len(ideas) >= max_ideas:
                break

        return ideas[:max_ideas]

    def _analyze_documentation(self, max_ideas: int) -> List[Idea]:
        """Анализ документации."""
        ideas = []

        # Проверяем наличие README
        if not (self.project_path / "README.md").exists():
            ideas.append(Idea(
                id=self._generate_id(IdeaType.DOCUMENTATION),
                type=IdeaType.DOCUMENTATION,
                title="Add README.md",
                description="Project lacks a README file.",
                priority=Priority.HIGH,
                effort=Effort.SMALL,
                rationale="README is essential for project discoverability.",
                implementation_hint="Include: project description, installation, usage, contributing."
            ))

        # Функции без docstrings
        for py_file in self.project_path.rglob("*.py"):
            if any(p in str(py_file) for p in ['venv', '__pycache__', '.git', 'test']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                tree = ast.parse(content)
            except:
                continue

            missing_docstrings = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        missing_docstrings.append(node.name)

            if len(missing_docstrings) > 3:
                ideas.append(Idea(
                    id=self._generate_id(IdeaType.DOCUMENTATION),
                    type=IdeaType.DOCUMENTATION,
                    title=f"Add docstrings in {py_file.name}",
                    description=f"{len(missing_docstrings)} functions/classes lack docstrings.",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    affected_files=[str(py_file.relative_to(self.project_path))],
                    rationale="Docstrings improve code understanding.",
                    implementation_hint=f"Add docstrings to: {', '.join(missing_docstrings[:5])}..."
                ))

            if len(ideas) >= max_ideas:
                break

        return ideas[:max_ideas]

    def _analyze_testing(self, max_ideas: int) -> List[Idea]:
        """Анализ тестового покрытия."""
        ideas = []

        test_dir = self.project_path / "tests"
        has_tests = test_dir.exists() and list(test_dir.rglob("test_*.py"))

        if not has_tests:
            ideas.append(Idea(
                id=self._generate_id(IdeaType.TESTING),
                type=IdeaType.TESTING,
                title="Add unit tests",
                description="Project lacks test coverage.",
                priority=Priority.HIGH,
                effort=Effort.LARGE,
                rationale="Tests ensure code reliability and prevent regressions.",
                implementation_hint="Start with critical business logic. Use pytest."
            ))
        else:
            # Проверяем покрытие основных модулей
            src_files = set()
            for py_file in self.project_path.rglob("*.py"):
                if 'test' not in str(py_file) and 'venv' not in str(py_file):
                    src_files.add(py_file.stem)

            test_files = set()
            for test_file in test_dir.rglob("test_*.py"):
                # test_foo.py -> foo
                test_files.add(test_file.stem.replace('test_', ''))

            untested = src_files - test_files
            if untested and len(untested) > 2:
                ideas.append(Idea(
                    id=self._generate_id(IdeaType.TESTING),
                    type=IdeaType.TESTING,
                    title="Improve test coverage",
                    description=f"{len(untested)} modules lack dedicated tests.",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    affected_files=list(untested)[:5],
                    rationale="Higher test coverage prevents bugs.",
                    implementation_hint=f"Add tests for: {', '.join(list(untested)[:5])}"
                ))

        return ideas[:max_ideas]

    def _analyze_architecture(self, max_ideas: int) -> List[Idea]:
        """Анализ архитектуры."""
        ideas = []

        # Проверяем структуру проекта
        src_dir = self.project_path / "src"
        if not src_dir.exists():
            # Проверяем наличие множества .py файлов в корне
            root_py = list(self.project_path.glob("*.py"))
            if len(root_py) > 5:
                ideas.append(Idea(
                    id=self._generate_id(IdeaType.ARCHITECTURE),
                    type=IdeaType.ARCHITECTURE,
                    title="Organize code into packages",
                    description=f"Found {len(root_py)} Python files in project root.",
                    priority=Priority.MEDIUM,
                    effort=Effort.MEDIUM,
                    rationale="Package structure improves code organization.",
                    implementation_hint="Create src/ directory with logical packages."
                ))

        # Проверяем циклические импорты (упрощённо)
        imports = {}
        for py_file in self.project_path.rglob("*.py"):
            if any(p in str(py_file) for p in ['venv', '__pycache__', '.git']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8')
                tree = ast.parse(content)
            except:
                continue

            module = py_file.stem
            imports[module] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports[module].append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports[module].append(node.module.split('.')[0])

        # Простая проверка A imports B and B imports A
        for mod_a, imp_a in imports.items():
            for mod_b in imp_a:
                if mod_b in imports and mod_a in imports.get(mod_b, []):
                    ideas.append(Idea(
                        id=self._generate_id(IdeaType.ARCHITECTURE),
                        type=IdeaType.ARCHITECTURE,
                        title=f"Circular import: {mod_a} <-> {mod_b}",
                        description="Circular imports can cause issues.",
                        priority=Priority.MEDIUM,
                        effort=Effort.MEDIUM,
                        affected_files=[f"{mod_a}.py", f"{mod_b}.py"],
                        rationale="Circular imports make code harder to understand and can cause bugs.",
                        implementation_hint="Extract shared code to a third module."
                    ))
                    break

            if len(ideas) >= max_ideas:
                break

        return ideas[:max_ideas]


def print_ideas(ideas: List[Idea]) -> None:
    """Красиво вывести идеи."""
    table = Table(title="Feature Ideas & Improvements")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Priority", style="magenta")
    table.add_column("Title", style="white")
    table.add_column("Effort", style="green")

    priority_colors = {
        Priority.CRITICAL: "red",
        Priority.HIGH: "orange1",
        Priority.MEDIUM: "yellow",
        Priority.LOW: "dim"
    }

    for idea in ideas:
        color = priority_colors.get(idea.priority, "white")
        table.add_row(
            idea.id,
            idea.type.value,
            f"[{color}]{idea.priority.value}[/{color}]",
            idea.title,
            idea.effort.value
        )

    console.print(table)
