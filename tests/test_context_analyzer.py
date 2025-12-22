"""
Tests for context/analyzer.py - Context Engineering system.

Phase 1: Context Engineering
"""

import pytest
import json
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.context.analyzer import (
    CodebaseAnalyzer,
    CodebaseContext,
    APIEndpoint,
    DatabaseSchema,
    CodePattern,
    print_context,
)


class TestCodePattern:
    """Tests for CodePattern dataclass."""

    def test_code_pattern_creation(self):
        """Test creating a code pattern."""
        pattern = CodePattern(
            pattern_type="naming",
            value="snake_case",
            confidence=0.95
        )

        assert pattern.pattern_type == "naming"
        assert pattern.value == "snake_case"
        assert pattern.confidence == 0.95


class TestAPIEndpoint:
    """Tests for APIEndpoint dataclass."""

    def test_api_endpoint_creation(self, temp_dir):
        """Test creating an API endpoint."""
        endpoint = APIEndpoint(
            method="GET",
            path="/api/users",
            handler="get_users",
            file=temp_dir / "api.py"
        )

        assert endpoint.method == "GET"
        assert endpoint.path == "/api/users"
        assert endpoint.handler == "get_users"


class TestDatabaseSchema:
    """Tests for DatabaseSchema dataclass."""

    def test_database_schema_creation(self, temp_dir):
        """Test creating a database schema."""
        schema = DatabaseSchema(
            table_name="users",
            columns=[
                {"name": "id", "type": "Integer"},
                {"name": "email", "type": "String"}
            ],
            file=temp_dir / "models.py"
        )

        assert schema.table_name == "users"
        assert len(schema.columns) == 2
        assert schema.columns[0]["name"] == "id"


class TestCodebaseContext:
    """Tests for CodebaseContext dataclass."""

    def test_codebase_context_creation(self, temp_dir):
        """Test creating a codebase context."""
        context = CodebaseContext(
            project_path=temp_dir,
            tech_stack={"language": "python", "framework": "fastapi"},
            structure={"important_dirs": {"src": "Source code"}},
            dependencies={"production": ["fastapi", "uvicorn"]},
            entry_points=["main.py"],
            api_endpoints=[],
            database_schemas=[],
            code_patterns={"naming_convention": "snake_case"}
        )

        assert context.project_path == temp_dir
        assert context.tech_stack["language"] == "python"
        assert "fastapi" in context.dependencies["production"]

    def test_context_save_and_load(self, temp_dir):
        """Test saving and loading context."""
        context = CodebaseContext(
            project_path=temp_dir,
            tech_stack={"language": "python"},
            structure={"important_dirs": {}},
            dependencies={"production": [], "development": [], "all": []},
            entry_points=["main.py"],
            api_endpoints=[],
            database_schemas=[],
            code_patterns={}
        )

        save_path = temp_dir / "context.json"
        context.save(save_path)

        assert save_path.exists()

        # Load back
        loaded = CodebaseContext.load(save_path)

        assert loaded.tech_stack["language"] == "python"
        assert loaded.entry_points == ["main.py"]

    def test_context_save_with_api_endpoints(self, temp_dir):
        """Test saving context with API endpoints."""
        context = CodebaseContext(
            project_path=temp_dir,
            tech_stack={},
            structure={},
            dependencies={},
            entry_points=[],
            api_endpoints=[
                APIEndpoint(
                    method="GET",
                    path="/users",
                    handler="get_users",
                    file=temp_dir / "api.py"
                )
            ],
            database_schemas=[],
            code_patterns={}
        )

        save_path = temp_dir / "context.json"
        context.save(save_path)

        # Verify JSON is valid
        with open(save_path) as f:
            data = json.load(f)

        assert len(data["api_endpoints"]) == 1
        assert data["api_endpoints"][0]["path"] == "/users"


class TestCodebaseAnalyzer:
    """Tests for CodebaseAnalyzer."""

    def test_analyzer_creation(self, temp_dir):
        """Test creating an analyzer."""
        analyzer = CodebaseAnalyzer(temp_dir)

        assert analyzer.project_path == temp_dir.resolve()

    def test_detect_tech_stack_python(self, temp_dir):
        """Test detecting Python tech stack."""
        (temp_dir / "requirements.txt").write_text("""
fastapi>=0.100.0
sqlalchemy>=2.0.0
pytest>=7.4.0
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        stack = analyzer._detect_tech_stack()

        assert stack["language"] == "python"
        assert stack.get("framework") == "fastapi"
        assert stack.get("orm") == "sqlalchemy"
        assert stack.get("testing") == "pytest"

    def test_detect_tech_stack_aiogram(self, temp_dir):
        """Test detecting aiogram framework."""
        (temp_dir / "requirements.txt").write_text("""
aiogram>=3.0.0
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        stack = analyzer._detect_tech_stack()

        assert stack["language"] == "python"
        assert stack.get("framework") == "aiogram"

    def test_detect_tech_stack_nodejs(self, temp_dir):
        """Test detecting Node.js tech stack."""
        (temp_dir / "package.json").write_text(json.dumps({
            "dependencies": {
                "react": "^18.0.0",
                "express": "^4.18.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0"
            }
        }))

        analyzer = CodebaseAnalyzer(temp_dir)
        stack = analyzer._detect_tech_stack()

        assert stack["language"] == "typescript"
        assert stack.get("frontend") == "react"
        assert stack.get("backend") == "express"

    def test_detect_tech_stack_pyproject(self, temp_dir):
        """Test detecting from pyproject.toml."""
        (temp_dir / "pyproject.toml").write_text("""
[project]
dependencies = ["fastapi>=0.100.0"]
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        stack = analyzer._detect_tech_stack()

        assert stack["language"] == "python"

    def test_analyze_structure(self, temp_dir):
        """Test analyzing project structure."""
        # Create structure
        (temp_dir / "src").mkdir()
        (temp_dir / "tests").mkdir()
        (temp_dir / "docs").mkdir()
        (temp_dir / "src" / "main.py").write_text("print('hello')")
        (temp_dir / "src" / "utils.py").write_text("pass")
        (temp_dir / "tests" / "test_main.py").write_text("pass")

        analyzer = CodebaseAnalyzer(temp_dir)
        structure = analyzer._analyze_structure()

        assert "important_dirs" in structure
        assert "file_counts" in structure
        assert "architecture" in structure
        assert structure["file_counts"][".py"] == 3

    def test_analyze_structure_mvc(self, temp_dir):
        """Test detecting MVC architecture."""
        (temp_dir / "models").mkdir()
        (temp_dir / "views").mkdir()
        (temp_dir / "controllers").mkdir()

        analyzer = CodebaseAnalyzer(temp_dir)
        structure = analyzer._analyze_structure()

        assert structure["architecture"] == "MVC"

    def test_analyze_structure_telegram_bot(self, temp_dir):
        """Test detecting Telegram Bot architecture."""
        (temp_dir / "handlers").mkdir()
        (temp_dir / "routers").mkdir()

        analyzer = CodebaseAnalyzer(temp_dir)
        structure = analyzer._analyze_structure()

        assert structure["architecture"] == "Telegram Bot"

    def test_parse_dependencies_requirements(self, temp_dir):
        """Test parsing requirements.txt."""
        (temp_dir / "requirements.txt").write_text("fastapi>=0.100.0\nsqlalchemy==2.0.0\npytest~=7.4.0\nrequests\n# comment\n")

        analyzer = CodebaseAnalyzer(temp_dir)
        deps = analyzer._parse_dependencies()

        assert "fastapi" in deps["production"]
        assert "sqlalchemy" in deps["production"]
        assert "pytest" in deps["production"]
        assert "requests" in deps["production"]

    def test_parse_dependencies_package_json(self, temp_dir):
        """Test parsing package.json."""
        (temp_dir / "package.json").write_text(json.dumps({
            "dependencies": {
                "express": "^4.18.0",
                "mongoose": "^7.0.0"
            },
            "devDependencies": {
                "jest": "^29.0.0"
            }
        }))

        analyzer = CodebaseAnalyzer(temp_dir)
        deps = analyzer._parse_dependencies()

        assert "express" in deps["production"]
        assert "mongoose" in deps["production"]
        assert "jest" in deps["development"]

    def test_find_entry_points(self, temp_dir):
        """Test finding entry points."""
        (temp_dir / "main.py").write_text("if __name__ == '__main__': pass")
        (temp_dir / "app.py").write_text("app = FastAPI()")
        (temp_dir / "bot.py").write_text("# bot")

        analyzer = CodebaseAnalyzer(temp_dir)
        entry_points = analyzer._find_entry_points()

        assert "main.py" in entry_points
        assert "app.py" in entry_points
        assert "bot.py" in entry_points

    def test_find_entry_points_in_src(self, temp_dir):
        """Test finding entry points in src directory."""
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text("pass")

        analyzer = CodebaseAnalyzer(temp_dir)
        entry_points = analyzer._find_entry_points()

        assert "src/main.py" in entry_points

    def test_find_fastapi_endpoints(self, temp_dir):
        """Test finding FastAPI endpoints."""
        (temp_dir / "api.py").write_text("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def get_users():
    return []

@app.post("/users")
def create_user():
    return {}
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        endpoints = analyzer._find_fastapi_endpoints()

        paths = [ep.path for ep in endpoints]
        assert "/users" in paths

    def test_find_flask_endpoints(self, temp_dir):
        """Test finding Flask endpoints."""
        (temp_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)

@app.route("/api/items", methods=["GET", "POST"])
def items():
    return []

@app.route("/api/status")
def status():
    return "ok"
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        endpoints = analyzer._find_flask_endpoints()

        paths = [ep.path for ep in endpoints]
        assert "/api/items" in paths
        assert "/api/status" in paths

    def test_find_db_schemas_sqlalchemy(self, temp_dir):
        """Test finding SQLAlchemy database schemas."""
        (temp_dir / "models.py").write_text("""
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        schemas = analyzer._find_db_schemas()

        # Should find the User model
        table_names = [s.table_name for s in schemas]
        assert "User" in table_names

    def test_detect_code_patterns_snake_case(self, temp_dir):
        """Test detecting snake_case naming convention."""
        (temp_dir / "module.py").write_text("""
def get_user_by_id(user_id):
    pass

def create_new_order(order_data):
    pass

def validate_email_address(email):
    pass
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        patterns = analyzer._detect_code_patterns()

        assert patterns.get("naming_convention") == "snake_case"

    def test_detect_code_patterns_type_hints(self, temp_dir):
        """Test detecting type hints usage."""
        (temp_dir / "typed.py").write_text("""
from typing import List, Dict

def get_users() -> List[Dict[str, str]]:
    return []

def create_user(name: str, email: str) -> Dict:
    return {"name": name, "email": email}

def process_data(data: List[int]) -> int:
    return sum(data)
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        patterns = analyzer._detect_code_patterns()

        assert patterns.get("type_hints") == "yes"

    def test_detect_code_patterns_async(self, temp_dir):
        """Test detecting async patterns."""
        (temp_dir / "async_module.py").write_text("""
async def fetch_data():
    pass

async def process_request(request):
    data = await fetch_data()
    return data
""")

        analyzer = CodebaseAnalyzer(temp_dir)
        patterns = analyzer._detect_code_patterns()

        assert patterns.get("async_pattern") == "async/await"

    @pytest.mark.asyncio
    async def test_full_analyze(self, python_project):
        """Test full project analysis."""
        analyzer = CodebaseAnalyzer(python_project)

        context = await analyzer.analyze(force_refresh=True)

        assert isinstance(context, CodebaseContext)
        assert context.project_path == python_project.resolve()
        assert context.tech_stack.get("language") == "python"

    @pytest.mark.asyncio
    async def test_analyze_caches_result(self, python_project):
        """Test that analysis is cached."""
        analyzer = CodebaseAnalyzer(python_project)

        # First analysis
        context1 = await analyzer.analyze(force_refresh=True)

        # Second analysis should use cache
        context2 = await analyzer.analyze(force_refresh=False)

        assert context1.tech_stack == context2.tech_stack

    @pytest.mark.asyncio
    async def test_analyze_force_refresh(self, python_project):
        """Test forcing refresh of analysis."""
        analyzer = CodebaseAnalyzer(python_project)

        # First analysis
        await analyzer.analyze(force_refresh=True)

        # Force refresh
        context = await analyzer.analyze(force_refresh=True)

        assert isinstance(context, CodebaseContext)


class TestCodebaseAnalyzerEdgeCases:
    """Edge case tests for CodebaseAnalyzer."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, temp_dir):
        """Test analyzing empty directory."""
        analyzer = CodebaseAnalyzer(temp_dir)

        context = await analyzer.analyze(force_refresh=True)

        assert context.project_path == temp_dir.resolve()
        assert context.tech_stack == {}

    @pytest.mark.asyncio
    async def test_directory_with_only_ignored_dirs(self, temp_dir):
        """Test directory with only dirs that should be ignored."""
        # Create only directories that typically would be ignored
        (temp_dir / ".git").mkdir()
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "node_modules").mkdir()

        analyzer = CodebaseAnalyzer(temp_dir)
        context = await analyzer.analyze(force_refresh=True)

        # Structure should recognize these directories
        structure = context.structure
        assert "file_counts" in structure

    def test_binary_file_handling(self, temp_dir):
        """Test that binary files don't cause errors."""
        # Create binary file
        (temp_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (temp_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03")
        (temp_dir / "script.py").write_text("print('hello')")

        analyzer = CodebaseAnalyzer(temp_dir)

        # Should not raise
        structure = analyzer._analyze_structure()

        assert structure["file_counts"][".py"] == 1

    def test_unicode_in_files(self, temp_dir):
        """Test handling of unicode content."""
        (temp_dir / "unicode.py").write_text("""
# -*- coding: utf-8 -*-
message = "Привет мир! 你好世界! 🌍"

def greet():
    return message
""", encoding="utf-8")

        analyzer = CodebaseAnalyzer(temp_dir)
        patterns = analyzer._detect_code_patterns()

        # Should not raise and should detect patterns
        assert isinstance(patterns, dict)


class TestPrintContext:
    """Tests for print_context function."""

    def test_print_context_basic(self, temp_dir, capsys):
        """Test printing basic context."""
        context = CodebaseContext(
            project_path=temp_dir,
            tech_stack={"language": "python", "framework": "fastapi"},
            structure={
                "important_dirs": {"src": "Source code"},
                "file_counts": {".py": 10},
                "architecture": "Service-oriented"
            },
            dependencies={"production": ["fastapi", "uvicorn"]},
            entry_points=["main.py"],
            api_endpoints=[],
            database_schemas=[],
            code_patterns={"naming_convention": "snake_case"}
        )

        print_context(context)

        captured = capsys.readouterr()
        # Should print something about tech stack
        assert "python" in captured.out.lower() or "Tech Stack" in captured.out

    def test_print_context_with_endpoints(self, temp_dir, capsys):
        """Test printing context with API endpoints."""
        context = CodebaseContext(
            project_path=temp_dir,
            tech_stack={},
            structure={"important_dirs": {}, "file_counts": {}, "architecture": "unknown"},
            dependencies={"production": []},
            entry_points=[],
            api_endpoints=[
                APIEndpoint("GET", "/users", "get_users", temp_dir / "api.py"),
                APIEndpoint("POST", "/users", "create_user", temp_dir / "api.py")
            ],
            database_schemas=[],
            code_patterns={}
        )

        print_context(context)

        captured = capsys.readouterr()
        assert "GET" in captured.out or "/users" in captured.out or "API" in captured.out


class TestCodebaseAnalyzerIntegration:
    """Integration tests for CodebaseAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyze_real_project_structure(self, python_project):
        """Test analyzing a realistic project structure."""
        analyzer = CodebaseAnalyzer(python_project)

        context = await analyzer.analyze(force_refresh=True)

        # Verify comprehensive analysis
        assert context.project_path
        assert context.tech_stack
        assert context.structure

    @pytest.mark.asyncio
    async def test_context_can_be_serialized(self, python_project):
        """Test that context can be fully serialized to JSON."""
        analyzer = CodebaseAnalyzer(python_project)
        context = await analyzer.analyze(force_refresh=True)

        # Save should work
        save_path = python_project / "test_context.json"
        context.save(save_path)

        # Load back should work
        loaded = CodebaseContext.load(save_path)

        assert loaded.project_path == context.project_path

    @pytest.mark.asyncio
    async def test_cache_file_created(self, python_project):
        """Test that cache file is created after analysis."""
        analyzer = CodebaseAnalyzer(python_project)

        await analyzer.analyze(force_refresh=True)

        cache_path = python_project / ".clod" / "context.json"
        assert cache_path.exists()
