"""
Pytest configuration and fixtures.
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def git_repo(temp_dir):
    """Create a temporary git repository."""
    repo_path = temp_dir / "test_repo"
    repo_path.mkdir()

    # Initialize git repo with main as default branch
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

    yield repo_path


@pytest.fixture
def python_project(temp_dir):
    """Create a temporary Python project structure."""
    project_path = temp_dir / "python_project"
    project_path.mkdir()

    # Create project structure
    src_dir = project_path / "src"
    src_dir.mkdir()

    # requirements.txt with packages that will be detected
    (project_path / "requirements.txt").write_text("""fastapi>=0.100.0
sqlalchemy>=2.0.0
pytest>=7.0.0
""")

    # Main module
    (src_dir / "__init__.py").write_text("")
    (src_dir / "main.py").write_text('''
"""Main module."""

def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
''')

    # Module with issues (for validation tests)
    (src_dir / "problematic.py").write_text('''
"""Module with some issues for testing."""

import os
import sys
import json  # unused import

def very_long_function_that_does_too_many_things(
    param1, param2, param3, param4, param5, param6, param7
):
    """This function has too many parameters."""
    result = 0
    for i in range(100):
        if i % 2 == 0:
            if i % 3 == 0:
                if i % 5 == 0:
                    if i % 7 == 0:
                        result += i
    return result


# Hardcoded secret (security issue)
API_KEY = "sk-1234567890abcdef"

def unsafe_eval(user_input):
    """Unsafe use of eval."""
    return eval(user_input)
''')

    yield project_path


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file."""
    file_path = temp_dir / "sample.py"
    file_path.write_text('''
"""Sample module."""

def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


class Calculator:
    """Simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
''')
    yield file_path
