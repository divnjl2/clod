"""
Context Engineering - автоматический анализ проекта перед началом работы.

Собирает информацию о:
- Tech stack
- Структура директорий
- Dependencies
- API endpoints
- Database schemas
- Code patterns

Использование:
    from claude_agent_manager.context.analyzer import CodebaseAnalyzer

    analyzer = CodebaseAnalyzer(project_path)
    context = await analyzer.analyze()

    # Контекст автоматически добавляется в CLAUDE.md агента
"""

from __future__ import annotations

import json
import re
import ast
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict, Counter

from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel

console = Console()


@dataclass
class APIEndpoint:
    """API endpoint информация."""
    method: str  # GET, POST, etc.
    path: str
    handler: str  # function/class name
    file: Path


@dataclass
class DatabaseSchema:
    """Database schema информация."""
    table_name: str
    columns: List[Dict[str, str]]
    file: Path


@dataclass
class CodePattern:
    """Code pattern/convention."""
    pattern_type: str
    value: str
    confidence: float  # 0.0-1.0


@dataclass
class CodebaseContext:
    """Полный контекст кодовой базы."""
    project_path: Path
    tech_stack: Dict[str, str] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    api_endpoints: List[APIEndpoint] = field(default_factory=list)
    database_schemas: List[DatabaseSchema] = field(default_factory=list)
    code_patterns: Dict[str, str] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)

    def save(self, path: Path):
        """Сохранить контекст в JSON."""
        data = asdict(self)

        # Convert Paths to strings
        data['project_path'] = str(data['project_path'])
        for ep in data['api_endpoints']:
            ep['file'] = str(ep['file'])
        for schema in data['database_schemas']:
            schema['file'] = str(schema['file'])

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> CodebaseContext:
        """Загрузить контекст из JSON."""
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        # Convert strings back to Paths
        data['project_path'] = Path(data['project_path'])
        for ep in data['api_endpoints']:
            ep['file'] = Path(ep['file'])
        for schema in data['database_schemas']:
            schema['file'] = Path(schema['file'])

        return cls(**data)


class CodebaseAnalyzer:
    """
    Анализирует структуру проекта и собирает контекст.

    Результат используется для создания более умных агентов,
    которые понимают проект перед началом работы.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()
        self.cache_path = project_path / ".clod" / "context.json"

    async def analyze(self, force_refresh: bool = False) -> CodebaseContext:
        """
        Анализировать проект и создать контекст.

        Args:
            force_refresh: игнорировать кеш и пересканировать

        Returns:
            CodebaseContext с полной информацией о проекте
        """
        # Проверяем кеш
        if not force_refresh and self.cache_path.exists():
            console.print("[cyan]Loading cached context...[/cyan]")
            return CodebaseContext.load(self.cache_path)

        console.print("[cyan]Analyzing codebase...[/cyan]")

        context = CodebaseContext(project_path=self.project_path)

        # 1. Определяем tech stack
        console.print("  [dim]- Detecting tech stack...[/dim]")
        context.tech_stack = self._detect_tech_stack()

        # 2. Анализируем структуру
        console.print("  [dim]- Analyzing structure...[/dim]")
        context.structure = self._analyze_structure()

        # 3. Парсим dependencies
        console.print("  [dim]- Parsing dependencies...[/dim]")
        context.dependencies = self._parse_dependencies()

        # 4. Находим entry points
        console.print("  [dim]- Finding entry points...[/dim]")
        context.entry_points = self._find_entry_points()

        # 5. Ищем API endpoints (если REST API)
        if any(fw in context.tech_stack.values() for fw in ["fastapi", "flask", "django"]):
            console.print("  [dim]- Finding API endpoints...[/dim]")
            context.api_endpoints = self._find_api_endpoints(context.tech_stack)

        # 6. Ищем database schemas
        console.print("  [dim]- Finding database schemas...[/dim]")
        context.database_schemas = self._find_db_schemas()

        # 7. Определяем code patterns
        console.print("  [dim]- Detecting code patterns...[/dim]")
        context.code_patterns = self._detect_code_patterns()

        # Сохраняем в кеш
        context.save(self.cache_path)

        console.print("[green]Codebase analysis complete![/green]")

        return context

    def _detect_tech_stack(self) -> Dict[str, str]:
        """
        Определить tech stack проекта.

        Returns:
            dict с информацией: language, framework, frontend, database, etc.
        """
        stack = {}

        # Python
        if (self.project_path / "requirements.txt").exists():
            stack["language"] = "python"

            reqs = (self.project_path / "requirements.txt").read_text(encoding='utf-8')

            if "fastapi" in reqs.lower():
                stack["framework"] = "fastapi"
            elif "flask" in reqs.lower():
                stack["framework"] = "flask"
            elif "django" in reqs.lower():
                stack["framework"] = "django"
            elif "aiogram" in reqs.lower():
                stack["framework"] = "aiogram"

            if "sqlalchemy" in reqs.lower():
                stack["orm"] = "sqlalchemy"
            elif "tortoise" in reqs.lower():
                stack["orm"] = "tortoise"

            if "pytest" in reqs.lower():
                stack["testing"] = "pytest"

        elif (self.project_path / "pyproject.toml").exists():
            stack["language"] = "python"

            with open(self.project_path / "pyproject.toml", encoding='utf-8') as f:
                content = f.read()

                if "fastapi" in content:
                    stack["framework"] = "fastapi"
                elif "aiogram" in content:
                    stack["framework"] = "aiogram"

        # Node.js
        if (self.project_path / "package.json").exists():
            with open(self.project_path / "package.json", encoding='utf-8') as f:
                pkg = json.load(f)

            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "react" in deps:
                stack["frontend"] = "react"
                if "next" in deps:
                    stack["framework"] = "nextjs"
            elif "vue" in deps:
                stack["frontend"] = "vue"
            elif "angular" in deps:
                stack["frontend"] = "angular"
            elif "svelte" in deps:
                stack["frontend"] = "svelte"

            if "express" in deps:
                stack["backend"] = "express"
            elif "fastify" in deps:
                stack["backend"] = "fastify"

            if "typescript" in deps:
                stack["language"] = "typescript"
            else:
                stack["language"] = "javascript"

        # Go
        if (self.project_path / "go.mod").exists():
            stack["language"] = "go"

        # Rust
        if (self.project_path / "Cargo.toml").exists():
            stack["language"] = "rust"

        return stack

    def _analyze_structure(self) -> Dict[str, Any]:
        """
        Анализ структуры директорий.

        Returns:
            dict с:
            - important_dirs: ключевые директории и их назначение
            - file_counts: количество файлов по типам
            - architecture: MVC, microservices, monolith, etc.
        """
        structure = {
            "important_dirs": {},
            "file_counts": {},  # Use regular dict instead of defaultdict for serialization
            "architecture": "unknown"
        }

        # Паттерны для определения назначения директорий
        dir_patterns = {
            "src": "Source code",
            "lib": "Libraries",
            "tests": "Tests",
            "test": "Tests",
            "docs": "Documentation",
            "static": "Static assets",
            "templates": "Templates",
            "migrations": "Database migrations",
            "models": "Data models",
            "controllers": "Controllers",
            "views": "Views",
            "api": "API endpoints",
            "services": "Business logic",
            "utils": "Utilities",
            "config": "Configuration",
            "handlers": "Message handlers",
            "routers": "API routers",
            "managers": "Business managers"
        }

        # Сканируем директории
        for item in self.project_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Проверяем паттерны
                for pattern, description in dir_patterns.items():
                    if pattern in item.name.lower():
                        structure["important_dirs"][str(item.relative_to(self.project_path))] = description
                        break

        # Считаем файлы по типам
        for file_path in self.project_path.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext:
                    structure["file_counts"][ext] = structure["file_counts"].get(ext, 0) + 1

        # Определяем архитектуру
        dirs = set(structure["important_dirs"].keys())

        if "models" in dirs and "views" in dirs and "controllers" in dirs:
            structure["architecture"] = "MVC"
        elif "services" in dirs and "api" in dirs:
            structure["architecture"] = "Service-oriented"
        elif len(list(self.project_path.glob("docker-compose*.yml"))) > 0:
            structure["architecture"] = "Microservices"
        elif "handlers" in dirs or "routers" in dirs:
            structure["architecture"] = "Telegram Bot"
        else:
            structure["architecture"] = "Monolith"

        return dict(structure)

    def _parse_dependencies(self) -> Dict[str, List[str]]:
        """
        Парсить dependencies из package managers.

        Returns:
            dict с категориями dependencies
        """
        deps = {
            "production": [],
            "development": [],
            "all": []
        }

        # Python requirements.txt
        if (self.project_path / "requirements.txt").exists():
            with open(self.project_path / "requirements.txt", encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        # Извлекаем package name (до version specifier)
                        # Handle all version specifiers: >=, <=, ==, ~=, !=, <, >, ~
                        pkg = re.split(r'[<>=!~\[]', line)[0].strip()
                        if pkg:
                            deps["production"].append(pkg)
                            deps["all"].append(pkg)

        # Python pyproject.toml
        if (self.project_path / "pyproject.toml").exists():
            try:
                import tomllib
                with open(self.project_path / "pyproject.toml", 'rb') as f:
                    data = tomllib.load(f)

                # Dependencies
                if "project" in data and "dependencies" in data["project"]:
                    for dep in data["project"]["dependencies"]:
                        pkg = re.split(r'[<>=!~\[]', dep)[0].strip()
                        if pkg:
                            deps["production"].append(pkg)
                            deps["all"].append(pkg)

                # Dev dependencies
                if "project" in data and "optional-dependencies" in data["project"]:
                    for group_deps in data["project"]["optional-dependencies"].values():
                        for dep in group_deps:
                            pkg = re.split(r'[<>=!~\[]', dep)[0].strip()
                            if pkg:
                                deps["development"].append(pkg)
                                deps["all"].append(pkg)
            except ImportError:
                pass  # tomllib not available in Python < 3.11

        # Node.js package.json
        if (self.project_path / "package.json").exists():
            with open(self.project_path / "package.json", encoding='utf-8') as f:
                pkg = json.load(f)

            # Production deps
            for dep_name in pkg.get("dependencies", {}).keys():
                deps["production"].append(dep_name)
                deps["all"].append(dep_name)

            # Dev deps
            for dep_name in pkg.get("devDependencies", {}).keys():
                deps["development"].append(dep_name)
                deps["all"].append(dep_name)

        return deps

    def _find_entry_points(self) -> List[str]:
        """
        Найти entry points проекта (main files).

        Returns:
            список путей к entry point файлам
        """
        entry_points = []

        common_entry_points = [
            "main.py",
            "app.py",
            "__main__.py",
            "run.py",
            "bot.py",
            "run_bot.py",
            "index.js",
            "index.ts",
            "server.js",
            "server.ts",
            "main.go"
        ]

        for ep in common_entry_points:
            if (self.project_path / ep).exists():
                entry_points.append(ep)

        # Ищем в src/
        src_dir = self.project_path / "src"
        if src_dir.exists():
            for ep in common_entry_points:
                if (src_dir / ep).exists():
                    entry_points.append(f"src/{ep}")

        return entry_points

    def _find_api_endpoints(self, tech_stack: Dict[str, str]) -> List[APIEndpoint]:
        """
        Найти API endpoints в проекте.

        Поддержка:
        - FastAPI
        - Flask
        - Django
        """
        endpoints = []
        framework = tech_stack.get("framework")

        if framework == "fastapi":
            endpoints.extend(self._find_fastapi_endpoints())
        elif framework == "flask":
            endpoints.extend(self._find_flask_endpoints())
        # Django требует более сложного парсинга urls.py

        return endpoints

    def _find_fastapi_endpoints(self) -> List[APIEndpoint]:
        """Найти FastAPI endpoints."""
        endpoints = []

        for py_file in self.project_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Ищем вызовы app.get(), app.post(), etc.
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            method_name = node.func.attr

                            if method_name in ['get', 'post', 'put', 'delete', 'patch']:
                                # Первый аргумент - path
                                if node.args:
                                    if isinstance(node.args[0], ast.Constant):
                                        path = node.args[0].value

                                        endpoints.append(APIEndpoint(
                                            method=method_name.upper(),
                                            path=path,
                                            handler=f"line {node.lineno}",
                                            file=py_file.relative_to(self.project_path)
                                        ))

            except:
                continue

        return endpoints

    def _find_flask_endpoints(self) -> List[APIEndpoint]:
        """Найти Flask endpoints."""
        endpoints = []

        for py_file in self.project_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Regex для @app.route("/path", methods=["GET", "POST"])
                pattern = r'@\w+\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)'

                for match in re.finditer(pattern, content):
                    path = match.group(1)
                    methods_str = match.group(2)

                    if methods_str:
                        methods = [m.strip('\'" ') for m in methods_str.split(',')]
                    else:
                        methods = ["GET"]

                    for method in methods:
                        endpoints.append(APIEndpoint(
                            method=method,
                            path=path,
                            handler="flask_route",
                            file=py_file.relative_to(self.project_path)
                        ))

            except:
                continue

        return endpoints

    def _find_db_schemas(self) -> List[DatabaseSchema]:
        """Найти database schemas (SQLAlchemy models, Django models, etc.)."""
        schemas = []

        # Ищем SQLAlchemy models
        for py_file in self.project_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Простой поиск по ключевым словам
                if "Base = declarative_base()" in content or "from sqlalchemy" in content:
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Извлекаем columns
                            columns = []
                            for item in node.body:
                                if isinstance(item, ast.Assign):
                                    for target in item.targets:
                                        if isinstance(target, ast.Name):
                                            col_name = target.id
                                            # Пытаемся определить тип
                                            col_type = "unknown"

                                            if isinstance(item.value, ast.Call):
                                                if isinstance(item.value.func, ast.Name):
                                                    col_type = item.value.func.id

                                            columns.append({
                                                "name": col_name,
                                                "type": col_type
                                            })

                            if columns:
                                schemas.append(DatabaseSchema(
                                    table_name=node.name,
                                    columns=columns,
                                    file=py_file.relative_to(self.project_path)
                                ))

            except:
                continue

        return schemas

    def _detect_code_patterns(self) -> Dict[str, str]:
        """
        Определить code patterns и conventions.

        Returns:
            dict с patterns: naming, imports, async, etc.
        """
        patterns = {}

        # Анализируем Python файлы
        py_files = list(self.project_path.rglob("*.py"))

        if not py_files:
            return patterns

        # Sample some files
        sample_files = py_files[:min(20, len(py_files))]

        naming_styles = Counter()
        import_styles = Counter()
        uses_type_hints = 0
        uses_async = 0

        for py_file in sample_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                # Naming convention
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        name = node.name
                        if '_' in name and name.islower():
                            naming_styles['snake_case'] += 1
                        elif name[0].islower() and any(c.isupper() for c in name[1:]):
                            naming_styles['camelCase'] += 1

                    # Type hints
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.returns is not None or any(arg.annotation for arg in node.args.args):
                            uses_type_hints += 1

                    # Async usage
                    if isinstance(node, (ast.AsyncFunctionDef, ast.AsyncFor, ast.AsyncWith)):
                        uses_async += 1

                # Import style
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        import_styles['absolute'] += 1
                    elif isinstance(node, ast.ImportFrom):
                        if node.level > 0:
                            import_styles['relative'] += 1
                        else:
                            import_styles['absolute'] += 1

            except:
                continue

        # Определяем доминирующие patterns
        if naming_styles:
            patterns["naming_convention"] = naming_styles.most_common(1)[0][0]

        if import_styles:
            patterns["import_style"] = import_styles.most_common(1)[0][0]

        patterns["type_hints"] = "yes" if uses_type_hints > len(sample_files) * 0.5 else "no"
        patterns["async_pattern"] = "async/await" if uses_async > 0 else "sync"

        return patterns


def print_context(context: CodebaseContext):
    """Pretty print codebase context."""

    # Tech Stack
    console.print(Panel(
        "\n".join(f"{k.title()}: {v}" for k, v in context.tech_stack.items()),
        title="Tech Stack",
        border_style="cyan"
    ))

    # Structure
    tree = Tree("[bold]Project Structure[/bold]")
    tree.add(f"Architecture: {context.structure.get('architecture', 'unknown')}")

    dirs_node = tree.add("Important Directories")
    for dir_path, desc in context.structure.get("important_dirs", {}).items():
        dirs_node.add(f"[cyan]{dir_path}[/cyan]: {desc}")

    files_node = tree.add("File Counts")
    for ext, count in sorted(context.structure.get("file_counts", {}).items(), key=lambda x: -x[1])[:10]:
        files_node.add(f"{ext}: {count}")

    console.print(tree)

    # Dependencies
    if context.dependencies.get("production"):
        console.print(f"\n[green]Production Dependencies:[/green] {len(context.dependencies['production'])}")
        console.print("  " + ", ".join(context.dependencies["production"][:10]))
        if len(context.dependencies["production"]) > 10:
            console.print(f"  ... and {len(context.dependencies['production']) - 10} more")

    # API Endpoints
    if context.api_endpoints:
        console.print(f"\n[green]API Endpoints:[/green] {len(context.api_endpoints)} found")
        for ep in context.api_endpoints[:10]:
            console.print(f"  [{ep.method}] {ep.path}")
        if len(context.api_endpoints) > 10:
            console.print(f"  ... and {len(context.api_endpoints) - 10} more")

    # Code Patterns
    if context.code_patterns:
        console.print("\n[green]Code Patterns:[/green]")
        for pattern, value in context.code_patterns.items():
            console.print(f"  {pattern}: {value}")
