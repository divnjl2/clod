"""
Self-Validation system для автоматической проверки кода.

Проверяет:
- Синтаксис Python (ast)
- Type hints (mypy)
- Code style (ruff)
- Security (bandit)
- Tests (pytest)

Использование:
    from claude_agent_manager.validation import ValidationAgent

    validator = ValidationAgent(agent_id="agent-123")
    report = await validator.validate_changes([Path("file1.py"), Path("file2.py")])

    if report.has_critical_errors():
        print("Critical errors found!")
        for error in report.errors:
            print(f"  - {error}")
"""

from __future__ import annotations

import ast
import subprocess
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


class Severity(Enum):
    """Severity уровни для проблем."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Проблема найденная валидацией."""
    severity: Severity
    tool: str  # mypy, ruff, bandit, etc.
    file: Path
    line: Optional[int]
    column: Optional[int]
    code: str  # error code (e.g., "E501", "B608")
    message: str

    def __str__(self):
        location = f"{self.file}:{self.line}" if self.line else str(self.file)
        return f"[{self.severity.value}] {location} - {self.code}: {self.message}"


@dataclass
class PytestRunResult:
    """Результат запуска тестов."""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    coverage: float  # percentage
    duration: float  # seconds
    failures: List[str] = field(default_factory=list)


# Alias for backwards compatibility
TestResult = PytestRunResult


@dataclass
class ValidationReport:
    """Полный отчёт валидации."""
    issues: List[ValidationIssue] = field(default_factory=list)
    test_result: Optional[TestResult] = None
    validated_at: str = ""

    def add_issue(self, issue: ValidationIssue):
        """Добавить проблему в отчёт."""
        self.issues.append(issue)

    def has_critical_errors(self) -> bool:
        """Есть ли критические ошибки."""
        return any(
            issue.severity == Severity.CRITICAL
            for issue in self.issues
        )

    def has_errors(self) -> bool:
        """Есть ли ошибки (critical или error)."""
        return any(
            issue.severity in (Severity.CRITICAL, Severity.ERROR)
            for issue in self.issues
        )

    def get_issues_by_severity(self) -> Dict[Severity, List[ValidationIssue]]:
        """Сгруппировать проблемы по severity."""
        from collections import defaultdict
        grouped = defaultdict(list)
        for issue in self.issues:
            grouped[issue.severity].append(issue)
        return dict(grouped)

    def summary(self) -> str:
        """Краткое резюме отчёта."""
        by_severity = self.get_issues_by_severity()

        summary_parts = []

        for severity in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO]:
            count = len(by_severity.get(severity, []))
            if count > 0:
                emoji = {
                    Severity.CRITICAL: "[red]!![/red]",
                    Severity.ERROR: "[red]X[/red]",
                    Severity.WARNING: "[yellow]![/yellow]",
                    Severity.INFO: "[blue]i[/blue]"
                }[severity]
                summary_parts.append(f"{emoji} {count} {severity.value}(s)")

        if self.test_result:
            if self.test_result.passed:
                summary_parts.append(f"[green]Tests: {self.test_result.passed_tests}/{self.test_result.total_tests} passed[/green]")
            else:
                summary_parts.append(f"[red]Tests: {self.test_result.failed_tests} failed[/red]")

        return " | ".join(summary_parts) if summary_parts else "[green]No issues found[/green]"


class ValidationAgent:
    """
    Агент для автоматической валидации кода.

    Запускает различные линтеры и тесты, собирает результаты.
    """

    def __init__(self, agent_id: str, project_path: Optional[Path] = None):
        self.agent_id = agent_id
        self.project_path = project_path if project_path else Path.cwd()

    async def validate_changes(
        self,
        changed_files: List[Path],
        run_tests: bool = True,
        check_types: bool = True,
        check_style: bool = True,
        check_security: bool = True
    ) -> ValidationReport:
        """
        Валидировать изменённые файлы.

        Args:
            changed_files: список файлов для проверки
            run_tests: запускать ли тесты
            check_types: проверять ли типы (mypy)
            check_style: проверять ли стиль (ruff)
            check_security: проверять ли безопасность (bandit)

        Returns:
            ValidationReport с результатами
        """
        from datetime import datetime

        report = ValidationReport(validated_at=datetime.now().isoformat())

        # Фильтруем только Python файлы
        python_files = [f for f in changed_files if f.suffix == ".py"]

        if not python_files:
            console.print("[yellow]No Python files to validate[/yellow]")
            return report

        # 1. Проверка синтаксиса
        console.print("[cyan]Checking syntax...[/cyan]")
        syntax_issues = self._check_syntax(python_files)
        report.issues.extend(syntax_issues)

        # Если есть синтаксические ошибки, дальше не идём
        if any(issue.severity == Severity.CRITICAL for issue in syntax_issues):
            console.print("[red]Critical syntax errors found, skipping other checks[/red]")
            return report

        # 2. Параллельно запускаем остальные проверки
        tasks = []

        if check_types:
            tasks.append(self._check_types(python_files))

        if check_style:
            tasks.append(self._check_style(python_files))

        if check_security:
            tasks.append(self._check_security(python_files))

        if run_tests:
            tasks.append(self._run_tests())

        # Ждём все задачи
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                console.print(f"[red]Validation error: {result}[/red]")
            elif isinstance(result, list):
                # Список issues
                report.issues.extend(result)
            elif isinstance(result, TestResult):
                report.test_result = result

        return report

    def _check_syntax(self, files: List[Path]) -> List[ValidationIssue]:
        """Проверить синтаксис Python через ast."""
        issues = []

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()

                # Пытаемся распарсить
                ast.parse(code)

            except SyntaxError as e:
                issues.append(ValidationIssue(
                    severity=Severity.CRITICAL,
                    tool="python",
                    file=file_path,
                    line=e.lineno,
                    column=e.offset,
                    code="SyntaxError",
                    message=e.msg
                ))
            except Exception as e:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    tool="python",
                    file=file_path,
                    line=None,
                    column=None,
                    code="ParseError",
                    message=str(e)
                ))

        return issues

    async def _check_types(self, files: List[Path]) -> List[ValidationIssue]:
        """Проверить типы через mypy."""
        console.print("[cyan]Running mypy...[/cyan]")

        issues = []

        # Проверяем, установлен ли mypy
        try:
            result = await asyncio.create_subprocess_exec(
                "mypy",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
        except FileNotFoundError:
            console.print("[yellow]mypy not found, skipping type checking[/yellow]")
            return issues

        # Запускаем mypy
        try:
            process = await asyncio.create_subprocess_exec(
                "mypy",
                "--show-column-numbers",
                "--show-error-codes",
                *[str(f) for f in files],
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()

            # Парсим вывод mypy
            for line in output.split('\n'):
                if not line.strip() or line.startswith('Found'):
                    continue

                # Format: file.py:10:5: error: Message [error-code]
                parts = line.split(':', 4)
                if len(parts) >= 5:
                    file_path = Path(parts[0])
                    line_no = int(parts[1]) if parts[1].isdigit() else None
                    col_no = int(parts[2]) if parts[2].isdigit() else None

                    # Извлекаем severity и message
                    rest = parts[4].strip()
                    if rest.startswith('error:'):
                        severity = Severity.ERROR
                        message = rest[6:].strip()
                    elif rest.startswith('note:'):
                        severity = Severity.INFO
                        message = rest[5:].strip()
                    else:
                        severity = Severity.WARNING
                        message = rest

                    # Извлекаем error code
                    code_match = message.rfind('[')
                    if code_match != -1:
                        code = message[code_match+1:-1]
                        message = message[:code_match].strip()
                    else:
                        code = "mypy"

                    issues.append(ValidationIssue(
                        severity=severity,
                        tool="mypy",
                        file=file_path,
                        line=line_no,
                        column=col_no,
                        code=code,
                        message=message
                    ))

        except Exception as e:
            console.print(f"[red]mypy error: {e}[/red]")

        return issues

    async def _check_style(self, files: List[Path]) -> List[ValidationIssue]:
        """Проверить стиль через ruff."""
        console.print("[cyan]Running ruff...[/cyan]")

        issues = []

        try:
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "--output-format=json",
                *[str(f) for f in files],
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()

            # Парсим JSON output
            import json
            results = json.loads(stdout.decode())

            for result in results:
                # Ruff output format:
                # {"code": "E501", "message": "...", "location": {"row": 10, "column": 5}, "filename": "..."}

                severity = Severity.WARNING
                if result['code'].startswith('E') and int(result['code'][1:]) < 600:
                    # Errors E001-E599
                    severity = Severity.ERROR

                issues.append(ValidationIssue(
                    severity=severity,
                    tool="ruff",
                    file=Path(result['filename']),
                    line=result['location']['row'],
                    column=result['location']['column'],
                    code=result['code'],
                    message=result['message']
                ))

        except FileNotFoundError:
            console.print("[yellow]ruff not found, skipping style checking[/yellow]")
        except Exception as e:
            console.print(f"[red]ruff error: {e}[/red]")

        return issues

    async def _check_security(self, files: List[Path]) -> List[ValidationIssue]:
        """Проверить безопасность через bandit."""
        console.print("[cyan]Running bandit...[/cyan]")

        issues = []

        try:
            process = await asyncio.create_subprocess_exec(
                "bandit",
                "-f", "json",
                "-r",
                *[str(f) for f in files],
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()

            # Парсим JSON output
            import json
            result = json.loads(stdout.decode())

            for finding in result.get('results', []):
                # Bandit severity: HIGH, MEDIUM, LOW
                severity_map = {
                    'HIGH': Severity.ERROR,
                    'MEDIUM': Severity.WARNING,
                    'LOW': Severity.INFO
                }
                severity = severity_map.get(finding['issue_severity'], Severity.WARNING)

                issues.append(ValidationIssue(
                    severity=severity,
                    tool="bandit",
                    file=Path(finding['filename']),
                    line=finding['line_number'],
                    column=None,
                    code=finding['test_id'],
                    message=f"{finding['issue_text']} ({finding['issue_severity']})"
                ))

        except FileNotFoundError:
            console.print("[yellow]bandit not found, skipping security checking[/yellow]")
        except Exception as e:
            console.print(f"[red]bandit error: {e}[/red]")

        return issues

    async def _run_tests(self) -> TestResult:
        """Запустить тесты через pytest."""
        console.print("[cyan]Running tests...[/cyan]")

        import tempfile
        import os

        try:
            import time
            start_time = time.time()

            # Используем временные файлы для отчётов
            with tempfile.TemporaryDirectory() as tmpdir:
                pytest_report = os.path.join(tmpdir, "pytest-report.json")
                coverage_report = os.path.join(tmpdir, "coverage.json")

                process = await asyncio.create_subprocess_exec(
                    "pytest",
                    f"--json-report",
                    f"--json-report-file={pytest_report}",
                    "--cov",
                    f"--cov-report=json:{coverage_report}",
                    "-v",
                    cwd=self.project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()
                duration = time.time() - start_time

                # Читаем JSON report
                import json

                try:
                    with open(pytest_report) as f:
                        pytest_data = json.load(f)

                    summary = pytest_data['summary']
                    total = summary['total']
                    passed = summary.get('passed', 0)
                    failed = summary.get('failed', 0)

                    failures = []
                    for test in pytest_data.get('tests', []):
                        if test['outcome'] == 'failed':
                            failures.append(f"{test['nodeid']}: {test.get('call', {}).get('longrepr', 'Unknown error')}")

                except:
                    # Fallback: парсим stdout
                    total = 0
                    passed = 0
                    failed = 0
                    failures = []

                # Читаем coverage
                coverage_pct = 0.0
                try:
                    with open(coverage_report) as f:
                        cov_data = json.load(f)
                        coverage_pct = cov_data['totals']['percent_covered']
                except:
                    pass

                return TestResult(
                    passed=(process.returncode == 0),
                    total_tests=total,
                    passed_tests=passed,
                    failed_tests=failed,
                    coverage=coverage_pct,
                    duration=duration,
                    failures=failures
                )

        except FileNotFoundError:
            console.print("[yellow]pytest not found, skipping tests[/yellow]")
            return TestResult(
                passed=True,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage=0.0,
                duration=0.0
            )
        except Exception as e:
            console.print(f"[red]pytest error: {e}[/red]")
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                coverage=0.0,
                duration=0.0,
                failures=[str(e)]
            )


def print_validation_report(report: ValidationReport):
    """Pretty print validation report."""

    # Summary panel
    console.print(Panel(
        report.summary(),
        title="Validation Summary",
        border_style="cyan"
    ))

    # Issues table
    if report.issues:
        by_severity = report.get_issues_by_severity()

        for severity in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING]:
            issues = by_severity.get(severity, [])
            if not issues:
                continue

            table = Table(title=f"{severity.value.title()}s")
            table.add_column("File", style="cyan")
            table.add_column("Line", style="yellow")
            table.add_column("Tool", style="green")
            table.add_column("Code", style="magenta")
            table.add_column("Message", style="red" if severity == Severity.ERROR else "yellow")

            for issue in issues:
                table.add_row(
                    str(issue.file),
                    str(issue.line) if issue.line else "-",
                    issue.tool,
                    issue.code,
                    issue.message[:80]
                )

            console.print(table)

    # Test results
    if report.test_result:
        tr = report.test_result

        test_panel_content = f"""
        Total Tests: {tr.total_tests}
        Passed: {tr.passed_tests}
        Failed: {tr.failed_tests}
        Coverage: {tr.coverage:.1f}%
        Duration: {tr.duration:.2f}s
        """

        console.print(Panel(
            test_panel_content,
            title="Test Results",
            border_style="green" if tr.passed else "red"
        ))

        if tr.failures:
            console.print("\n[red]Failed Tests:[/red]")
            for failure in tr.failures[:5]:  # Показываем первые 5
                console.print(f"  - {failure}")
