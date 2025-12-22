"""
Tests for validation.py - Self-Validation system.

Phase 1: Self-Validation
"""

import pytest
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.validation import (
    ValidationAgent,
    ValidationReport,
    ValidationIssue,
    PytestRunResult,
    Severity,
    print_validation_report,
)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_issue_creation(self, temp_dir):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            severity=Severity.ERROR,
            tool="mypy",
            file=temp_dir / "test.py",
            line=10,
            column=5,
            code="E501",
            message="Line too long"
        )

        assert issue.severity == Severity.ERROR
        assert issue.tool == "mypy"
        assert issue.line == 10
        assert "Line too long" in str(issue)

    def test_issue_str_format(self, temp_dir):
        """Test issue string representation."""
        issue = ValidationIssue(
            severity=Severity.WARNING,
            tool="ruff",
            file=temp_dir / "main.py",
            line=25,
            column=1,
            code="W503",
            message="Line break before operator"
        )

        str_repr = str(issue)
        assert "main.py:25" in str_repr
        assert "W503" in str_repr


class TestValidationReport:
    """Tests for ValidationReport."""

    def test_empty_report(self):
        """Test empty validation report."""
        report = ValidationReport()

        assert report.issues == []
        assert report.test_result is None
        assert not report.has_errors()
        assert not report.has_critical_errors()

    def test_add_issue(self, temp_dir):
        """Test adding issues to report."""
        report = ValidationReport()

        issue = ValidationIssue(
            severity=Severity.ERROR,
            tool="mypy",
            file=temp_dir / "test.py",
            line=1,
            column=1,
            code="E001",
            message="Error"
        )
        report.add_issue(issue)

        assert len(report.issues) == 1
        assert report.has_errors()

    def test_has_critical_errors(self, temp_dir):
        """Test detection of critical errors."""
        report = ValidationReport()

        # Add non-critical issue
        report.add_issue(ValidationIssue(
            severity=Severity.WARNING,
            tool="ruff",
            file=temp_dir / "a.py",
            line=1,
            column=1,
            code="W001",
            message="Warning"
        ))
        assert not report.has_critical_errors()

        # Add critical issue
        report.add_issue(ValidationIssue(
            severity=Severity.CRITICAL,
            tool="python",
            file=temp_dir / "b.py",
            line=1,
            column=1,
            code="SyntaxError",
            message="Invalid syntax"
        ))
        assert report.has_critical_errors()

    def test_get_issues_by_severity(self, temp_dir):
        """Test grouping issues by severity."""
        report = ValidationReport()

        # Add various severity issues
        for sev, count in [(Severity.ERROR, 3), (Severity.WARNING, 2), (Severity.INFO, 1)]:
            for i in range(count):
                report.add_issue(ValidationIssue(
                    severity=sev,
                    tool="test",
                    file=temp_dir / f"{sev.value}_{i}.py",
                    line=i,
                    column=1,
                    code=f"{sev.value[0]}{i}",
                    message=f"{sev.value} message"
                ))

        grouped = report.get_issues_by_severity()

        assert len(grouped[Severity.ERROR]) == 3
        assert len(grouped[Severity.WARNING]) == 2
        assert len(grouped[Severity.INFO]) == 1

    def test_summary(self, temp_dir):
        """Test summary generation."""
        report = ValidationReport()

        report.add_issue(ValidationIssue(
            severity=Severity.ERROR,
            tool="mypy",
            file=temp_dir / "t.py",
            line=1,
            column=1,
            code="E1",
            message="Error"
        ))

        summary = report.summary()

        assert "1 error" in summary.lower()

    def test_summary_with_tests(self, temp_dir):
        """Test summary includes test results."""
        report = ValidationReport()
        report.test_result = PytestRunResult(
            passed=True,
            total_tests=10,
            passed_tests=10,
            failed_tests=0,
            coverage=85.0,
            duration=1.5
        )

        summary = report.summary()

        assert "10/10" in summary or "10" in summary


class TestPytestRunResult:
    """Tests for PytestRunResult dataclass."""

    def test_passed_result(self):
        """Test successful test result."""
        result = PytestRunResult(
            passed=True,
            total_tests=50,
            passed_tests=50,
            failed_tests=0,
            coverage=92.5,
            duration=5.3
        )

        assert result.passed
        assert result.total_tests == 50
        assert result.coverage == 92.5

    def test_failed_result(self):
        """Test failed test result."""
        result = PytestRunResult(
            passed=False,
            total_tests=50,
            passed_tests=45,
            failed_tests=5,
            coverage=80.0,
            duration=6.1,
            failures=["test_a", "test_b", "test_c", "test_d", "test_e"]
        )

        assert not result.passed
        assert result.failed_tests == 5
        assert len(result.failures) == 5


class TestValidationAgent:
    """Tests for ValidationAgent."""

    def test_agent_creation(self, temp_dir):
        """Test creating a validation agent."""
        agent = ValidationAgent("agent-1", temp_dir)

        assert agent.agent_id == "agent-1"
        assert agent.project_path == temp_dir

    def test_check_syntax_valid(self, sample_python_file):
        """Test syntax check on valid Python file."""
        agent = ValidationAgent("test", sample_python_file.parent)

        issues = agent._check_syntax([sample_python_file])

        assert len(issues) == 0

    def test_check_syntax_invalid(self, temp_dir):
        """Test syntax check on invalid Python file."""
        bad_file = temp_dir / "bad.py"
        bad_file.write_text("def broken(\n")  # Syntax error

        agent = ValidationAgent("test", temp_dir)
        issues = agent._check_syntax([bad_file])

        assert len(issues) == 1
        assert issues[0].severity == Severity.CRITICAL
        assert issues[0].code == "SyntaxError"

    @pytest.mark.asyncio
    async def test_validate_changes_empty_list(self, temp_dir):
        """Test validation with empty file list."""
        agent = ValidationAgent("test", temp_dir)

        report = await agent.validate_changes([])

        assert len(report.issues) == 0

    @pytest.mark.asyncio
    async def test_validate_changes_non_python(self, temp_dir):
        """Test validation skips non-Python files."""
        txt_file = temp_dir / "readme.txt"
        txt_file.write_text("Hello")

        agent = ValidationAgent("test", temp_dir)
        report = await agent.validate_changes([txt_file])

        assert len(report.issues) == 0

    @pytest.mark.asyncio
    async def test_validate_changes_syntax_only(self, sample_python_file):
        """Test validation with syntax check only."""
        agent = ValidationAgent("test", sample_python_file.parent)

        report = await agent.validate_changes(
            [sample_python_file],
            run_tests=False,
            check_types=False,
            check_style=False,
            check_security=False
        )

        # Valid file should have no syntax errors
        critical = [i for i in report.issues if i.severity == Severity.CRITICAL]
        assert len(critical) == 0

    @pytest.mark.asyncio
    async def test_validate_with_syntax_error_stops_early(self, temp_dir):
        """Test that syntax errors stop further validation."""
        bad_file = temp_dir / "broken.py"
        bad_file.write_text("def x(\n")

        agent = ValidationAgent("test", temp_dir)
        report = await agent.validate_changes([bad_file])

        # Should have critical error and stop
        assert report.has_critical_errors()


class TestValidationIntegration:
    """Integration tests for validation."""

    @pytest.mark.asyncio
    async def test_validate_project_with_issues(self, python_project):
        """Test validating a project that has issues."""
        agent = ValidationAgent("test", python_project)

        problematic = python_project / "src" / "problematic.py"
        report = await agent.validate_changes(
            [problematic],
            run_tests=False,
            check_types=False,  # Skip mypy (may not be installed)
            check_style=False,  # Skip ruff (may not be installed)
            check_security=False  # Skip bandit (may not be installed)
        )

        # At minimum, syntax should pass
        critical = [i for i in report.issues if i.severity == Severity.CRITICAL]
        assert len(critical) == 0

    @pytest.mark.asyncio
    async def test_validate_clean_file(self, sample_python_file):
        """Test validating a clean Python file."""
        agent = ValidationAgent("test", sample_python_file.parent)

        report = await agent.validate_changes(
            [sample_python_file],
            run_tests=False,
            check_types=False,
            check_style=False,
            check_security=False
        )

        # Clean file should have no critical errors
        assert not report.has_critical_errors()


class TestPrintValidationReport:
    """Tests for print_validation_report function."""

    def test_print_empty_report(self, capsys):
        """Test printing empty report."""
        report = ValidationReport()

        print_validation_report(report)

        captured = capsys.readouterr()
        assert "Validation Summary" in captured.out or "No issues" in captured.out.lower()

    def test_print_report_with_issues(self, temp_dir, capsys):
        """Test printing report with issues."""
        report = ValidationReport()
        report.add_issue(ValidationIssue(
            severity=Severity.ERROR,
            tool="test",
            file=temp_dir / "x.py",
            line=1,
            column=1,
            code="E001",
            message="Test error"
        ))

        print_validation_report(report)

        captured = capsys.readouterr()
        assert "E001" in captured.out or "error" in captured.out.lower()
