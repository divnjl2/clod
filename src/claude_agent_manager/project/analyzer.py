"""
Project Analyzer
================

Analyzes a project's structure to determine:
- Technology stack (languages, frameworks, databases)
- Package managers
- Infrastructure (Docker, K8s)
- Custom scripts (npm, Makefile, etc.)
- Safe commands for the project

Integrated from Auto-Claude project.
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import CustomScripts, SecurityProfile, TechnologyStack

logger = logging.getLogger(__name__)

# =============================================================================
# COMMAND REGISTRIES
# =============================================================================

# Base commands always allowed
BASE_COMMANDS = {
    # File operations (safe)
    "ls", "dir", "cat", "head", "tail", "less", "more", "file", "stat",
    "wc", "sort", "uniq", "diff", "grep", "find", "tree",
    # Git operations
    "git", "gh",
    # Basic utilities
    "echo", "printf", "date", "whoami", "pwd", "which", "where", "env",
    "true", "false", "test", "[",
}

# Language-specific commands
LANGUAGE_COMMANDS = {
    "python": {"python", "python3", "pip", "pip3", "poetry", "uv", "pytest", "mypy", "black", "ruff", "isort"},
    "javascript": {"node", "npm", "npx", "yarn", "pnpm", "bun"},
    "typescript": {"tsc", "ts-node", "tsx"},
    "rust": {"cargo", "rustc", "rustup", "rustfmt", "clippy"},
    "go": {"go", "gofmt", "golint"},
    "java": {"java", "javac", "mvn", "gradle", "ant"},
    "ruby": {"ruby", "gem", "bundle", "bundler", "rake", "rails"},
    "php": {"php", "composer", "artisan"},
    "csharp": {"dotnet", "nuget", "msbuild"},
    "elixir": {"elixir", "mix", "iex"},
    "swift": {"swift", "swiftc", "xcodebuild"},
    "kotlin": {"kotlin", "kotlinc"},
}

# Framework-specific commands
FRAMEWORK_COMMANDS = {
    "react": {"create-react-app", "react-scripts"},
    "nextjs": {"next"},
    "vue": {"vue-cli-service", "vite"},
    "nuxt": {"nuxt"},
    "angular": {"ng"},
    "svelte": {"svelte-kit"},
    "django": {"django-admin", "manage.py"},
    "flask": {"flask"},
    "fastapi": {"uvicorn"},
    "rails": {"rails", "rake"},
    "laravel": {"artisan", "php"},
    "express": {},
    "nestjs": {"nest"},
}

# Database commands
DATABASE_COMMANDS = {
    "postgresql": {"psql", "pg_dump", "pg_restore", "createdb", "dropdb"},
    "mysql": {"mysql", "mysqldump", "mysqlimport"},
    "mongodb": {"mongo", "mongod", "mongodump", "mongorestore"},
    "redis": {"redis-cli", "redis-server"},
    "sqlite": {"sqlite3"},
    "elasticsearch": {"elasticsearch"},
}

# Infrastructure commands
INFRASTRUCTURE_COMMANDS = {
    "docker": {"docker", "docker-compose"},
    "kubernetes": {"kubectl", "minikube", "kind", "helm"},
    "terraform": {"terraform"},
    "ansible": {"ansible", "ansible-playbook"},
    "pulumi": {"pulumi"},
}

# Cloud provider commands
CLOUD_COMMANDS = {
    "aws": {"aws", "sam", "cdk"},
    "gcp": {"gcloud", "gsutil"},
    "azure": {"az"},
    "vercel": {"vercel"},
    "netlify": {"netlify"},
    "heroku": {"heroku"},
    "fly": {"flyctl", "fly"},
}

# Code quality commands
CODE_QUALITY_COMMANDS = {
    "eslint": {"eslint"},
    "prettier": {"prettier"},
    "jest": {"jest"},
    "vitest": {"vitest"},
    "mocha": {"mocha"},
    "pytest": {"pytest"},
    "ruff": {"ruff"},
    "black": {"black"},
    "mypy": {"mypy"},
    "pylint": {"pylint"},
    "flake8": {"flake8"},
    "rubocop": {"rubocop"},
    "phpstan": {"phpstan"},
    "phpcs": {"phpcs"},
}


# =============================================================================
# DETECTION PATTERNS
# =============================================================================

# Language detection by file extension
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".ex": "elixir",
    ".exs": "elixir",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

# Package manager detection by file
PACKAGE_MANAGER_FILES = {
    "package.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
    "requirements.txt": "pip",
    "pyproject.toml": "poetry",  # Could also be pip
    "Pipfile": "pipenv",
    "uv.lock": "uv",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "Gemfile": "bundler",
    "composer.json": "composer",
}

# Framework detection patterns in dependencies
FRAMEWORK_PATTERNS = {
    "react": ["react", "react-dom"],
    "nextjs": ["next"],
    "vue": ["vue"],
    "nuxt": ["nuxt"],
    "angular": ["@angular/core"],
    "svelte": ["svelte"],
    "django": ["django", "Django"],
    "flask": ["flask", "Flask"],
    "fastapi": ["fastapi", "FastAPI"],
    "express": ["express"],
    "nestjs": ["@nestjs/core"],
    "rails": ["rails"],
    "laravel": ["laravel/framework"],
}

# Database detection patterns
DATABASE_PATTERNS = {
    "postgresql": ["psycopg2", "pg", "postgres", "asyncpg", "postgresql"],
    "mysql": ["mysql", "mysql2", "pymysql"],
    "mongodb": ["mongodb", "mongoose", "pymongo", "motor"],
    "redis": ["redis", "ioredis", "aioredis"],
    "sqlite": ["sqlite3", "better-sqlite3", "sqlite"],
    "elasticsearch": ["elasticsearch", "@elastic/elasticsearch"],
}


class ProjectAnalyzer:
    """
    Analyzes a project's structure to determine safe commands.

    Detection methods:
    1. File extensions and patterns
    2. Config file presence (package.json, pyproject.toml, etc.)
    3. Dependency parsing (frameworks, libraries)
    4. Script detection (npm scripts, Makefile targets)
    5. Infrastructure files (Dockerfile, k8s manifests)
    """

    PROFILE_FILENAME = ".claude-agent-security.json"

    def __init__(self, project_dir: Path):
        """
        Initialize analyzer.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.profile = SecurityProfile()

    def get_profile_path(self) -> Path:
        """Get the path where profile should be stored."""
        return self.project_dir / self.PROFILE_FILENAME

    def load_profile(self) -> Optional[SecurityProfile]:
        """Load existing profile if it exists."""
        profile_path = self.get_profile_path()
        if not profile_path.exists():
            return None

        try:
            with open(profile_path) as f:
                data = json.load(f)
            return SecurityProfile.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load profile: {e}")
            return None

    def save_profile(self, profile: SecurityProfile) -> None:
        """Save profile to disk."""
        profile_path = self.get_profile_path()
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        with open(profile_path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def compute_project_hash(self) -> str:
        """
        Compute a hash of key project files to detect changes.

        This allows us to know when to re-analyze.
        """
        hash_files = [
            "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock",
            "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
            "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
            "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ]

        hasher = hashlib.md5()
        files_found = 0

        for filename in hash_files:
            filepath = self.project_dir / filename
            if filepath.exists():
                try:
                    stat = filepath.stat()
                    hasher.update(f"{filename}:{stat.st_mtime}:{stat.st_size}".encode())
                    files_found += 1
                except OSError:
                    pass

        # If no config files found, hash the project directory structure
        if files_found == 0:
            for ext in ["*.py", "*.js", "*.ts", "*.go", "*.rs"]:
                count = len(list(self.project_dir.glob(f"**/{ext}")))
                hasher.update(f"{ext}:{count}".encode())
            hasher.update(self.project_dir.name.encode())

        return hasher.hexdigest()

    def should_reanalyze(self, profile: SecurityProfile) -> bool:
        """Check if project has changed since last analysis."""
        current_hash = self.compute_project_hash()
        return current_hash != profile.project_hash

    def analyze(self, force: bool = False) -> SecurityProfile:
        """
        Perform full project analysis.

        Args:
            force: Force re-analysis even if profile exists

        Returns:
            SecurityProfile with all detected commands
        """
        # Check for existing profile
        existing = self.load_profile()
        if existing and not force and not self.should_reanalyze(existing):
            logger.info(f"Using cached security profile (hash: {existing.project_hash[:8]})")
            return existing

        logger.info("Analyzing project structure for security profile...")

        # Start fresh
        self.profile = SecurityProfile()
        self.profile.base_commands = BASE_COMMANDS.copy()
        self.profile.project_dir = str(self.project_dir)

        # Run detection
        self._detect_languages()
        self._detect_package_managers()
        self._detect_frameworks()
        self._detect_databases()
        self._detect_infrastructure()
        self._detect_cloud_providers()
        self._detect_code_quality_tools()
        self._detect_custom_scripts()

        # Build stack commands from detected technologies
        self._build_stack_commands()

        # Finalize
        self.profile.created_at = datetime.now().isoformat()
        self.profile.project_hash = self.compute_project_hash()

        # Save
        self.save_profile(self.profile)

        return self.profile

    def _detect_languages(self) -> None:
        """Detect programming languages by file extensions."""
        languages = set()

        for ext, lang in LANGUAGE_EXTENSIONS.items():
            # Check if any files with this extension exist
            try:
                next(self.project_dir.rglob(f"*{ext}"))
                languages.add(lang)
            except StopIteration:
                pass

        self.profile.detected_stack.languages = sorted(languages)

    def _detect_package_managers(self) -> None:
        """Detect package managers by config files."""
        managers = set()

        for filename, manager in PACKAGE_MANAGER_FILES.items():
            if (self.project_dir / filename).exists():
                managers.add(manager)

        self.profile.detected_stack.package_managers = sorted(managers)

    def _detect_frameworks(self) -> None:
        """Detect frameworks from dependencies."""
        frameworks = set()

        # Check package.json for JavaScript frameworks
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                deps = list(data.get("dependencies", {}).keys())
                deps.extend(data.get("devDependencies", {}).keys())

                for fw, patterns in FRAMEWORK_PATTERNS.items():
                    if any(p in deps for p in patterns):
                        frameworks.add(fw)
            except (OSError, json.JSONDecodeError):
                pass

        # Check pyproject.toml for Python frameworks
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                for fw, patterns in FRAMEWORK_PATTERNS.items():
                    if any(p.lower() in content.lower() for p in patterns):
                        frameworks.add(fw)
            except OSError:
                pass

        # Check requirements.txt
        requirements = self.project_dir / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text().lower()
                for fw, patterns in FRAMEWORK_PATTERNS.items():
                    if any(p.lower() in content for p in patterns):
                        frameworks.add(fw)
            except OSError:
                pass

        self.profile.detected_stack.frameworks = sorted(frameworks)

    def _detect_databases(self) -> None:
        """Detect databases from dependencies."""
        databases = set()

        # Check all dependency files
        for dep_file in ["package.json", "pyproject.toml", "requirements.txt"]:
            filepath = self.project_dir / dep_file
            if filepath.exists():
                try:
                    content = filepath.read_text().lower()
                    for db, patterns in DATABASE_PATTERNS.items():
                        if any(p.lower() in content for p in patterns):
                            databases.add(db)
                except OSError:
                    pass

        # Check for docker-compose with database services
        for compose_file in ["docker-compose.yml", "docker-compose.yaml"]:
            filepath = self.project_dir / compose_file
            if filepath.exists():
                try:
                    content = filepath.read_text().lower()
                    if "postgres" in content:
                        databases.add("postgresql")
                    if "mysql" in content or "mariadb" in content:
                        databases.add("mysql")
                    if "mongo" in content:
                        databases.add("mongodb")
                    if "redis" in content:
                        databases.add("redis")
                except OSError:
                    pass

        self.profile.detected_stack.databases = sorted(databases)

    def _has_files(self, pattern: str) -> bool:
        """Check if any files match the glob pattern."""
        try:
            next(self.project_dir.rglob(pattern))
            return True
        except StopIteration:
            return False

    def _detect_infrastructure(self) -> None:
        """Detect infrastructure tools."""
        infrastructure = set()

        # Docker
        if (self.project_dir / "Dockerfile").exists() or self._has_files("Dockerfile*"):
            infrastructure.add("docker")

        if (self.project_dir / "docker-compose.yml").exists() or (self.project_dir / "docker-compose.yaml").exists():
            infrastructure.add("docker")

        # Kubernetes
        if self._has_files("*.yaml") or self._has_files("*.yml"):
            for yaml_file in self.project_dir.rglob("*.yaml"):
                try:
                    content = yaml_file.read_text()
                    if "apiVersion:" in content and "kind:" in content:
                        infrastructure.add("kubernetes")
                        break
                except OSError:
                    pass

        # Terraform
        if self._has_files("*.tf"):
            infrastructure.add("terraform")

        # Ansible
        if (self.project_dir / "playbook.yml").exists() or self._has_files("playbook*.yml"):
            infrastructure.add("ansible")

        self.profile.detected_stack.infrastructure = sorted(infrastructure)

    def _detect_cloud_providers(self) -> None:
        """Detect cloud provider usage."""
        providers = set()

        # Check for cloud-specific files
        if (self.project_dir / "vercel.json").exists():
            providers.add("vercel")

        if (self.project_dir / "netlify.toml").exists():
            providers.add("netlify")

        if (self.project_dir / "fly.toml").exists():
            providers.add("fly")

        if (self.project_dir / "Procfile").exists():
            providers.add("heroku")

        # Check for AWS
        if (self.project_dir / "samconfig.toml").exists() or self._has_files("**/cdk.json"):
            providers.add("aws")

        self.profile.detected_stack.cloud_providers = sorted(providers)

    def _detect_code_quality_tools(self) -> None:
        """Detect code quality tools."""
        tools = set()

        # Check for config files
        tool_files = {
            ".eslintrc": "eslint",
            ".eslintrc.js": "eslint",
            ".eslintrc.json": "eslint",
            "eslint.config.js": "eslint",
            ".prettierrc": "prettier",
            "prettier.config.js": "prettier",
            "jest.config.js": "jest",
            "jest.config.ts": "jest",
            "vitest.config.js": "vitest",
            "vitest.config.ts": "vitest",
            "pytest.ini": "pytest",
            "pyproject.toml": "pytest",  # If [tool.pytest] exists
            "setup.cfg": "pytest",
            ".ruff.toml": "ruff",
            "ruff.toml": "ruff",
            "mypy.ini": "mypy",
            ".mypy.ini": "mypy",
            ".rubocop.yml": "rubocop",
        }

        for filename, tool in tool_files.items():
            if (self.project_dir / filename).exists():
                tools.add(tool)

        self.profile.detected_stack.code_quality_tools = sorted(tools)

    def _detect_custom_scripts(self) -> None:
        """Detect custom scripts (npm scripts, Makefile targets, etc.)."""
        scripts = CustomScripts()

        # npm scripts
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                scripts.npm_scripts = list(data.get("scripts", {}).keys())
            except (OSError, json.JSONDecodeError):
                pass

        # Makefile targets
        makefile = self.project_dir / "Makefile"
        if makefile.exists():
            try:
                content = makefile.read_text()
                # Match target definitions like "target:" or "target: deps"
                targets = re.findall(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", content, re.MULTILINE)
                scripts.make_targets = [t for t in targets if not t.startswith(".")]
            except OSError:
                pass

        # Shell scripts
        for sh_file in self.project_dir.rglob("*.sh"):
            if sh_file.is_file():
                scripts.shell_scripts.append(str(sh_file.relative_to(self.project_dir)))

        self.profile.custom_scripts = scripts

        # Build script commands
        for script in scripts.npm_scripts:
            self.profile.script_commands.add(f"npm run {script}")
            self.profile.script_commands.add(f"yarn {script}")
            self.profile.script_commands.add(f"pnpm {script}")

        for target in scripts.make_targets:
            self.profile.script_commands.add(f"make {target}")

    def _build_stack_commands(self) -> None:
        """Build the set of allowed commands from detected stack."""
        stack = self.profile.detected_stack
        commands = self.profile.stack_commands

        # Add language commands
        for lang in stack.languages:
            if lang in LANGUAGE_COMMANDS:
                commands.update(LANGUAGE_COMMANDS[lang])

        # Add framework commands
        for fw in stack.frameworks:
            if fw in FRAMEWORK_COMMANDS:
                commands.update(FRAMEWORK_COMMANDS[fw])

        # Add database commands
        for db in stack.databases:
            if db in DATABASE_COMMANDS:
                commands.update(DATABASE_COMMANDS[db])

        # Add infrastructure commands
        for infra in stack.infrastructure:
            if infra in INFRASTRUCTURE_COMMANDS:
                commands.update(INFRASTRUCTURE_COMMANDS[infra])

        # Add cloud commands
        for cloud in stack.cloud_providers:
            if cloud in CLOUD_COMMANDS:
                commands.update(CLOUD_COMMANDS[cloud])

        # Add code quality commands
        for tool in stack.code_quality_tools:
            if tool in CODE_QUALITY_COMMANDS:
                commands.update(CODE_QUALITY_COMMANDS[tool])

    def get_summary(self) -> Dict:
        """Get a summary of the analysis."""
        stack = self.profile.detected_stack
        scripts = self.profile.custom_scripts

        return {
            "languages": stack.languages,
            "package_managers": stack.package_managers,
            "frameworks": stack.frameworks,
            "databases": stack.databases,
            "infrastructure": stack.infrastructure,
            "cloud_providers": stack.cloud_providers,
            "code_quality_tools": stack.code_quality_tools,
            "npm_scripts": len(scripts.npm_scripts),
            "make_targets": len(scripts.make_targets),
            "shell_scripts": len(scripts.shell_scripts),
            "total_allowed_commands": len(self.profile.get_all_allowed_commands()),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_or_create_profile(project_dir: Path, force_reanalyze: bool = False) -> SecurityProfile:
    """
    Get or create a security profile for a project.

    Args:
        project_dir: Path to project root
        force_reanalyze: Force re-analysis even if profile exists

    Returns:
        SecurityProfile for the project
    """
    analyzer = ProjectAnalyzer(project_dir)
    return analyzer.analyze(force=force_reanalyze)


def is_command_allowed(project_dir: Path, command: str) -> bool:
    """
    Check if a command is allowed for the project.

    Args:
        project_dir: Path to project root
        command: Command to check (just the first word/binary name)

    Returns:
        True if command is allowed
    """
    profile = get_or_create_profile(project_dir)
    allowed = profile.get_all_allowed_commands()

    # Extract the base command (first word)
    base_cmd = command.split()[0] if command else ""

    return base_cmd in allowed
