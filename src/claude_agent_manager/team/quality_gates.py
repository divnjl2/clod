"""
Quality Gates - Проверка качества кода
=====================================

Инструменты:
- Ruff (linting + formatting)
- Radon (complexity metrics)
- Bandit (security scanning)
- Coverage.py (test coverage)

Quality gates блокируют мерж если код не соответствует стандартам.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class QualityStatus(Enum):
    """Статус проверки качества."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class QualityIssue:
    """Проблема качества."""
    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str  # error, warning, info


@dataclass
class QualityCheckResult:
    """Результат проверки качества."""
    check_name: str
    status: QualityStatus
    issues: List[QualityIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    duration_ms: int = 0


@dataclass
class QualityReport:
    """Полный отчёт о качестве."""
    checks: List[QualityCheckResult]
    overall_status: QualityStatus
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация."""
        return {
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "checks": [
                {
                    "name": c.check_name,
                    "status": c.status.value,
                    "issues_count": len(c.issues),
                    "metrics": c.metrics,
                    "message": c.message
                }
                for c in self.checks
            ]
        }


class QualityGates:
    """
    Quality Gates для проверки кода.

    Thresholds (можно настроить):
    - Cyclomatic complexity: <= 10
    - Test coverage: >= 80%
    - Lint errors: 0
    - Security issues: 0
    """

    def __init__(
        self,
        path: Path,
        max_complexity: int = 10,
        min_coverage: int = 80,
        allow_warnings: bool = True
    ):
        self.path = path
        self.max_complexity = max_complexity
        self.min_coverage = min_coverage
        self.allow_warnings = allow_warnings

    def run_all_checks(self) -> QualityReport:
        """Запустить все проверки."""
        checks = [
            self.run_ruff(),
            self.run_radon(),
            self.run_bandit(),
            self.run_type_check(),
        ]

        # Определяем общий статус
        has_failures = any(c.status == QualityStatus.FAILED for c in checks)
        has_errors = any(c.status == QualityStatus.ERROR for c in checks)
        has_warnings = any(c.status == QualityStatus.WARNING for c in checks)

        if has_errors:
            overall = QualityStatus.ERROR
        elif has_failures:
            overall = QualityStatus.FAILED
        elif has_warnings and not self.allow_warnings:
            overall = QualityStatus.WARNING
        else:
            overall = QualityStatus.PASSED

        # Формируем summary
        passed = sum(1 for c in checks if c.status == QualityStatus.PASSED)
        summary = f"{passed}/{len(checks)} checks passed"

        return QualityReport(
            checks=checks,
            overall_status=overall,
            summary=summary
        )

    # =========================================================================
    # RUFF - Linting & Formatting
    # =========================================================================

    def run_ruff(self) -> QualityCheckResult:
        """
        Запустить Ruff linter.

        Ruff - быстрый Python linter написанный на Rust.
        """
        import time
        start = time.time()

        try:
            # Запускаем ruff check
            result = subprocess.run(
                ["ruff", "check", str(self.path), "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )

            duration = int((time.time() - start) * 1000)

            # Парсим результат
            issues = []
            if result.stdout:
                try:
                    ruff_output = json.loads(result.stdout)
                    for item in ruff_output:
                        issues.append(QualityIssue(
                            file=item.get("filename", ""),
                            line=item.get("location", {}).get("row", 0),
                            column=item.get("location", {}).get("column", 0),
                            code=item.get("code", ""),
                            message=item.get("message", ""),
                            severity="error" if item.get("code", "").startswith("E") else "warning"
                        ))
                except json.JSONDecodeError:
                    pass

            # Определяем статус
            errors = [i for i in issues if i.severity == "error"]

            if errors:
                status = QualityStatus.FAILED
                message = f"{len(errors)} linting errors"
            elif issues:
                status = QualityStatus.WARNING
                message = f"{len(issues)} linting warnings"
            else:
                status = QualityStatus.PASSED
                message = "No linting issues"

            return QualityCheckResult(
                check_name="ruff",
                status=status,
                issues=issues,
                metrics={"total_issues": len(issues), "errors": len(errors)},
                message=message,
                duration_ms=duration
            )

        except FileNotFoundError:
            return QualityCheckResult(
                check_name="ruff",
                status=QualityStatus.SKIPPED,
                message="Ruff not installed. Install with: pip install ruff"
            )
        except Exception as e:
            return QualityCheckResult(
                check_name="ruff",
                status=QualityStatus.ERROR,
                message=f"Error running ruff: {str(e)}"
            )

    # =========================================================================
    # RADON - Complexity Metrics
    # =========================================================================

    def run_radon(self) -> QualityCheckResult:
        """
        Запустить Radon для проверки цикломатической сложности.

        Цикломатическая сложность:
        - 1-5: A (низкая)
        - 6-10: B (средняя)
        - 11-20: C (высокая)
        - 21+: D-F (очень высокая)
        """
        import time
        start = time.time()

        try:
            # Запускаем radon cc (cyclomatic complexity)
            result = subprocess.run(
                ["radon", "cc", str(self.path), "-j", "-a"],
                capture_output=True,
                text=True,
                timeout=60
            )

            duration = int((time.time() - start) * 1000)

            issues = []
            metrics = {
                "average_complexity": 0,
                "max_complexity": 0,
                "high_complexity_functions": []
            }

            if result.stdout:
                try:
                    radon_output = json.loads(result.stdout)

                    all_complexities = []

                    for file_path, functions in radon_output.items():
                        if isinstance(functions, list):
                            for func in functions:
                                complexity = func.get("complexity", 0)
                                all_complexities.append(complexity)

                                if complexity > self.max_complexity:
                                    issues.append(QualityIssue(
                                        file=file_path,
                                        line=func.get("lineno", 0),
                                        column=0,
                                        code=f"CC{complexity}",
                                        message=f"Function '{func.get('name', '?')}' has complexity {complexity} (max: {self.max_complexity})",
                                        severity="error"
                                    ))
                                    metrics["high_complexity_functions"].append({
                                        "name": func.get("name"),
                                        "complexity": complexity,
                                        "file": file_path
                                    })

                    if all_complexities:
                        metrics["average_complexity"] = sum(all_complexities) / len(all_complexities)
                        metrics["max_complexity"] = max(all_complexities)

                except json.JSONDecodeError:
                    pass

            if issues:
                status = QualityStatus.FAILED
                message = f"{len(issues)} functions exceed complexity threshold"
            else:
                status = QualityStatus.PASSED
                message = f"All functions under complexity {self.max_complexity}"

            return QualityCheckResult(
                check_name="radon",
                status=status,
                issues=issues,
                metrics=metrics,
                message=message,
                duration_ms=duration
            )

        except FileNotFoundError:
            return QualityCheckResult(
                check_name="radon",
                status=QualityStatus.SKIPPED,
                message="Radon not installed. Install with: pip install radon"
            )
        except Exception as e:
            return QualityCheckResult(
                check_name="radon",
                status=QualityStatus.ERROR,
                message=f"Error running radon: {str(e)}"
            )

    # =========================================================================
    # BANDIT - Security Scanning
    # =========================================================================

    def run_bandit(self) -> QualityCheckResult:
        """
        Запустить Bandit для проверки безопасности.

        Bandit находит распространённые security issues в Python коде.
        """
        import time
        start = time.time()

        try:
            result = subprocess.run(
                ["bandit", "-r", str(self.path), "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=120
            )

            duration = int((time.time() - start) * 1000)

            issues = []
            metrics = {
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0
            }

            if result.stdout:
                try:
                    bandit_output = json.loads(result.stdout)
                    results = bandit_output.get("results", [])

                    for item in results:
                        severity = item.get("issue_severity", "LOW")

                        issues.append(QualityIssue(
                            file=item.get("filename", ""),
                            line=item.get("line_number", 0),
                            column=0,
                            code=item.get("test_id", ""),
                            message=item.get("issue_text", ""),
                            severity=severity.lower()
                        ))

                        if severity == "HIGH":
                            metrics["high_severity"] += 1
                        elif severity == "MEDIUM":
                            metrics["medium_severity"] += 1
                        else:
                            metrics["low_severity"] += 1

                except json.JSONDecodeError:
                    pass

            # Критичные уязвимости = fail
            if metrics["high_severity"] > 0:
                status = QualityStatus.FAILED
                message = f"{metrics['high_severity']} high severity security issues"
            elif metrics["medium_severity"] > 0:
                status = QualityStatus.WARNING
                message = f"{metrics['medium_severity']} medium severity security issues"
            elif issues:
                status = QualityStatus.WARNING
                message = f"{len(issues)} low severity security issues"
            else:
                status = QualityStatus.PASSED
                message = "No security issues found"

            return QualityCheckResult(
                check_name="bandit",
                status=status,
                issues=issues,
                metrics=metrics,
                message=message,
                duration_ms=duration
            )

        except FileNotFoundError:
            return QualityCheckResult(
                check_name="bandit",
                status=QualityStatus.SKIPPED,
                message="Bandit not installed. Install with: pip install bandit"
            )
        except Exception as e:
            return QualityCheckResult(
                check_name="bandit",
                status=QualityStatus.ERROR,
                message=f"Error running bandit: {str(e)}"
            )

    # =========================================================================
    # TYPE CHECK (mypy or pyright)
    # =========================================================================

    def run_type_check(self) -> QualityCheckResult:
        """Запустить проверку типов."""
        import time
        start = time.time()

        # Пробуем mypy
        try:
            result = subprocess.run(
                ["mypy", str(self.path), "--ignore-missing-imports", "--no-error-summary"],
                capture_output=True,
                text=True,
                timeout=120
            )

            duration = int((time.time() - start) * 1000)

            issues = []
            for line in result.stdout.strip().split("\n"):
                if not line or ":" not in line:
                    continue

                # Parse mypy output: file:line: error: message
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    issues.append(QualityIssue(
                        file=parts[0],
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        column=0,
                        code="type-error",
                        message=parts[3].strip() if len(parts) > 3 else "",
                        severity="error" if "error" in line else "warning"
                    ))

            errors = [i for i in issues if i.severity == "error"]

            if errors:
                status = QualityStatus.FAILED
                message = f"{len(errors)} type errors"
            elif issues:
                status = QualityStatus.WARNING
                message = f"{len(issues)} type warnings"
            else:
                status = QualityStatus.PASSED
                message = "No type errors"

            return QualityCheckResult(
                check_name="type_check",
                status=status,
                issues=issues,
                metrics={"errors": len(errors), "warnings": len(issues) - len(errors)},
                message=message,
                duration_ms=duration
            )

        except FileNotFoundError:
            return QualityCheckResult(
                check_name="type_check",
                status=QualityStatus.SKIPPED,
                message="mypy not installed. Install with: pip install mypy"
            )
        except Exception as e:
            return QualityCheckResult(
                check_name="type_check",
                status=QualityStatus.ERROR,
                message=f"Error running type check: {str(e)}"
            )

    # =========================================================================
    # TEST COVERAGE
    # =========================================================================

    def run_coverage(self, test_command: str = "pytest") -> QualityCheckResult:
        """Запустить тесты с coverage."""
        import time
        start = time.time()

        try:
            # Запускаем тесты с coverage
            result = subprocess.run(
                ["coverage", "run", "-m", test_command, str(self.path)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.path
            )

            # Получаем отчёт
            report_result = subprocess.run(
                ["coverage", "json", "-o", "-"],
                capture_output=True,
                text=True,
                cwd=self.path
            )

            duration = int((time.time() - start) * 1000)

            metrics = {
                "total_coverage": 0,
                "covered_lines": 0,
                "missing_lines": 0
            }

            if report_result.stdout:
                try:
                    coverage_data = json.loads(report_result.stdout)
                    totals = coverage_data.get("totals", {})
                    metrics["total_coverage"] = totals.get("percent_covered", 0)
                    metrics["covered_lines"] = totals.get("covered_lines", 0)
                    metrics["missing_lines"] = totals.get("missing_lines", 0)
                except json.JSONDecodeError:
                    pass

            if metrics["total_coverage"] >= self.min_coverage:
                status = QualityStatus.PASSED
                message = f"Coverage: {metrics['total_coverage']:.1f}%"
            else:
                status = QualityStatus.FAILED
                message = f"Coverage {metrics['total_coverage']:.1f}% < {self.min_coverage}% required"

            return QualityCheckResult(
                check_name="coverage",
                status=status,
                metrics=metrics,
                message=message,
                duration_ms=duration
            )

        except FileNotFoundError:
            return QualityCheckResult(
                check_name="coverage",
                status=QualityStatus.SKIPPED,
                message="coverage not installed. Install with: pip install coverage pytest-cov"
            )
        except Exception as e:
            return QualityCheckResult(
                check_name="coverage",
                status=QualityStatus.ERROR,
                message=f"Error running coverage: {str(e)}"
            )


# =============================================================================
# GATE ENFORCEMENT
# =============================================================================

class QualityGateEnforcer:
    """
    Enforcer для quality gates.

    Блокирует операции (мерж, коммит) если качество не соответствует.
    """

    def __init__(self, gates: QualityGates):
        self.gates = gates

    def check_before_commit(self) -> Tuple[bool, str]:
        """Проверка перед коммитом."""
        # Быстрые проверки
        ruff_result = self.gates.run_ruff()

        if ruff_result.status == QualityStatus.FAILED:
            return False, f"Commit blocked: {ruff_result.message}"

        return True, "Pre-commit checks passed"

    def check_before_merge(self) -> Tuple[bool, str]:
        """Полная проверка перед мержом."""
        report = self.gates.run_all_checks()

        if report.overall_status == QualityStatus.FAILED:
            failed_checks = [
                c.check_name for c in report.checks
                if c.status == QualityStatus.FAILED
            ]
            return False, f"Merge blocked. Failed checks: {', '.join(failed_checks)}"

        if report.overall_status == QualityStatus.ERROR:
            return False, "Merge blocked due to check errors"

        return True, report.summary

    def generate_report(self) -> str:
        """Генерация отчёта о качестве."""
        report = self.gates.run_all_checks()

        lines = [
            "# Quality Gate Report",
            f"\nOverall: **{report.overall_status.value.upper()}**",
            f"\n{report.summary}",
            "\n## Checks\n"
        ]

        for check in report.checks:
            icon = "?" if check.status == QualityStatus.PASSED else "?"
            lines.append(f"- {icon} **{check.check_name}**: {check.message}")

            if check.issues:
                lines.append(f"  - Issues: {len(check.issues)}")

            if check.metrics:
                for key, value in check.metrics.items():
                    if not isinstance(value, list):
                        lines.append(f"  - {key}: {value}")

        return "\n".join(lines)


# =============================================================================
# QUICK FUNCTIONS
# =============================================================================

def quick_lint(path: Path) -> bool:
    """Быстрая проверка линтером."""
    gates = QualityGates(path)
    result = gates.run_ruff()
    return result.status != QualityStatus.FAILED


def quick_security_scan(path: Path) -> bool:
    """Быстрая проверка безопасности."""
    gates = QualityGates(path)
    result = gates.run_bandit()
    return result.status != QualityStatus.FAILED


def full_quality_check(path: Path) -> QualityReport:
    """Полная проверка качества."""
    gates = QualityGates(path)
    return gates.run_all_checks()
