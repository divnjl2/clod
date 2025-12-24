"""
Security Scanner Module
=======================

Consolidates security scanning including secrets detection and SAST tools.
Provides a unified interface for all security scanning operations.

Integrated from Auto-Claude project.
"""

import json
import subprocess
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# SECRET PATTERNS
# =============================================================================

SECRET_PATTERNS = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret_key": r"(?i)aws[_\-]?secret[_\-]?(?:access[_\-]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})",
    "github_token": r"ghp_[A-Za-z0-9_]{36}",
    "github_oauth": r"gho_[A-Za-z0-9_]{36}",
    "github_pat": r"github_pat_[A-Za-z0-9_]{22}_[A-Za-z0-9_]{59}",
    "gitlab_token": r"glpat-[A-Za-z0-9\-_]{20}",
    "slack_token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*",
    "slack_webhook": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+",
    "telegram_bot_token": r"\d{9,10}:[A-Za-z0-9_-]{35}",
    "stripe_secret": r"sk_(?:live|test)_[A-Za-z0-9]{24,}",
    "stripe_publishable": r"pk_(?:live|test)_[A-Za-z0-9]{24,}",
    "google_api_key": r"AIza[0-9A-Za-z\-_]{35}",
    "google_oauth": r"ya29\.[0-9A-Za-z\-_]+",
    "firebase_key": r"AAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}",
    "twilio_sid": r"AC[a-z0-9]{32}",
    "twilio_auth": r"SK[a-z0-9]{32}",
    "sendgrid_api": r"SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}",
    "mailgun_api": r"key-[0-9a-f]{32}",
    "heroku_api": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "jwt_token": r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
    "private_key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "npm_token": r"npm_[A-Za-z0-9]{36}",
    "pypi_token": r"pypi-[A-Za-z0-9_]{32,}",
    "docker_auth": r"(?i)docker[_\-]?(?:hub[_\-]?)?(?:password|token|auth)['\"]?\s*[:=]\s*['\"]?([^'\"\s]{8,})",
    "generic_secret": r"(?i)(?:password|secret|token|api[_\-]?key|auth[_\-]?token)['\"]?\s*[:=]\s*['\"]?([^'\"\s]{8,64})['\"]?",
    "basic_auth": r"(?i)basic\s+[A-Za-z0-9+/=]{20,}",
    "bearer_token": r"(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}",
}

# Files to skip during scanning
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".sqlite", ".db", ".sqlite3",
}

SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".pytest_cache",
    "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "coverage", ".coverage", "htmlcov",
    ".idea", ".vscode",
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class SecretMatch:
    """Represents a detected secret in code."""

    file_path: str
    line_number: int
    pattern_name: str
    matched_text: str
    context: str = ""


@dataclass
class SecurityVulnerability:
    """
    Represents a security vulnerability found during scanning.

    Attributes:
        severity: Severity level (critical, high, medium, low, info)
        source: Which scanner found this (secrets, bandit, npm_audit, etc.)
        title: Short title of the vulnerability
        description: Detailed description
        file: File where vulnerability was found (if applicable)
        line: Line number (if applicable)
        cwe: CWE identifier if available
    """

    severity: str  # critical, high, medium, low, info
    source: str  # secrets, bandit, npm_audit, semgrep, etc.
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    cwe: Optional[str] = None


@dataclass
class SecurityScanResult:
    """
    Result of a security scan.

    Attributes:
        secrets: List of detected secrets
        vulnerabilities: List of security vulnerabilities
        scan_errors: List of errors during scanning
        has_critical_issues: Whether any critical issues were found
        should_block_qa: Whether these results should block QA approval
    """

    secrets: List[dict] = field(default_factory=list)
    vulnerabilities: List[SecurityVulnerability] = field(default_factory=list)
    scan_errors: List[str] = field(default_factory=list)
    has_critical_issues: bool = False
    should_block_qa: bool = False
    files_scanned: int = 0
    scan_duration_seconds: float = 0.0


# =============================================================================
# SECRETS SCANNER
# =============================================================================


def get_all_tracked_files(project_dir: Path) -> List[str]:
    """Get all files tracked by git, or all source files if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: walk directory
    files = []
    for ext in ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.json", "*.yaml", "*.yml", "*.env*", "*.cfg", "*.ini", "*.toml"]:
        for f in project_dir.rglob(ext):
            if not any(skip in str(f) for skip in SKIP_DIRECTORIES):
                files.append(str(f.relative_to(project_dir)))
    return files


def scan_file_for_secrets(file_path: Path, project_dir: Path) -> List[SecretMatch]:
    """Scan a single file for secrets."""
    matches = []

    # Skip binary files
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        return matches

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments that look like examples
            if "example" in line.lower() or "sample" in line.lower() or "xxx" in line.lower():
                continue

            for pattern_name, pattern in SECRET_PATTERNS.items():
                try:
                    for match in re.finditer(pattern, line):
                        matched_text = match.group(0)

                        # Skip if it looks like a placeholder
                        if any(p in matched_text.lower() for p in ["xxx", "your_", "example", "sample", "placeholder"]):
                            continue

                        matches.append(SecretMatch(
                            file_path=str(file_path.relative_to(project_dir)),
                            line_number=line_num,
                            pattern_name=pattern_name,
                            matched_text=matched_text,
                            context=line.strip()[:100],
                        ))
                except re.error:
                    continue
    except (OSError, UnicodeDecodeError):
        pass

    return matches


def scan_files(file_list: List[str], project_dir: Path) -> List[SecretMatch]:
    """Scan multiple files for secrets."""
    all_matches = []

    for file_path_str in file_list:
        file_path = project_dir / file_path_str
        if file_path.exists() and file_path.is_file():
            matches = scan_file_for_secrets(file_path, project_dir)
            all_matches.extend(matches)

    return all_matches


# =============================================================================
# SECURITY SCANNER
# =============================================================================


class SecurityScanner:
    """
    Consolidates all security scanning operations.

    Integrates:
    - Custom secrets detection (pattern-based)
    - Bandit for Python SAST (if available)
    - npm audit for JavaScript vulnerabilities (if applicable)
    - pip-audit for Python dependencies (if available)
    """

    def __init__(self) -> None:
        """Initialize the security scanner."""
        self._bandit_available: Optional[bool] = None
        self._npm_available: Optional[bool] = None

    def scan(
        self,
        project_dir: Path,
        spec_dir: Optional[Path] = None,
        changed_files: Optional[List[str]] = None,
        run_secrets: bool = True,
        run_sast: bool = True,
        run_dependency_audit: bool = True,
    ) -> SecurityScanResult:
        """
        Run all applicable security scans.

        Args:
            project_dir: Path to the project root
            spec_dir: Path to the spec directory (for storing results)
            changed_files: Optional list of files to scan (if None, scans all)
            run_secrets: Whether to run secrets scanning
            run_sast: Whether to run SAST tools
            run_dependency_audit: Whether to run dependency audits

        Returns:
            SecurityScanResult with all findings
        """
        import time
        start_time = time.time()

        project_dir = Path(project_dir)
        result = SecurityScanResult()

        # Run secrets scan
        if run_secrets:
            self._run_secrets_scan(project_dir, changed_files, result)

        # Run SAST based on project type
        if run_sast:
            self._run_sast_scans(project_dir, result)

        # Run dependency audits
        if run_dependency_audit:
            self._run_dependency_audits(project_dir, result)

        # Determine if should block QA
        result.has_critical_issues = (
            any(v.severity in ["critical", "high"] for v in result.vulnerabilities)
            or len(result.secrets) > 0
        )

        # Any secrets always block, critical vulnerabilities block
        result.should_block_qa = len(result.secrets) > 0 or any(
            v.severity == "critical" for v in result.vulnerabilities
        )

        result.scan_duration_seconds = time.time() - start_time

        # Save results if spec_dir provided
        if spec_dir:
            self._save_results(spec_dir, result)

        return result

    def _run_secrets_scan(
        self,
        project_dir: Path,
        changed_files: Optional[List[str]],
        result: SecurityScanResult,
    ) -> None:
        """Run secrets scanning using custom pattern matching."""
        try:
            # Get files to scan
            if changed_files:
                files_to_scan = changed_files
            else:
                files_to_scan = get_all_tracked_files(project_dir)

            result.files_scanned = len(files_to_scan)

            # Run scan
            matches = scan_files(files_to_scan, project_dir)

            # Convert matches to result format
            for match in matches:
                result.secrets.append({
                    "file": match.file_path,
                    "line": match.line_number,
                    "pattern": match.pattern_name,
                    "matched_text": self._redact_secret(match.matched_text),
                    "context": match.context,
                })

                # Also add as vulnerability
                result.vulnerabilities.append(
                    SecurityVulnerability(
                        severity="critical",
                        source="secrets",
                        title=f"Potential secret: {match.pattern_name}",
                        description=f"Found potential {match.pattern_name} in file",
                        file=match.file_path,
                        line=match.line_number,
                    )
                )

        except Exception as e:
            result.scan_errors.append(f"Secrets scan error: {str(e)}")
            logger.exception("Secrets scan failed")

    def _run_sast_scans(self, project_dir: Path, result: SecurityScanResult) -> None:
        """Run SAST tools based on project type."""
        # Python SAST with Bandit
        if self._is_python_project(project_dir):
            self._run_bandit(project_dir, result)

    def _run_bandit(self, project_dir: Path, result: SecurityScanResult) -> None:
        """Run Bandit security scanner for Python projects."""
        if not self._check_bandit_available():
            return

        try:
            # Find Python source directories
            src_dirs = []
            for candidate in ["src", "app", project_dir.name, "."]:
                candidate_path = project_dir / candidate
                if candidate_path.exists():
                    if (candidate_path / "__init__.py").exists() or list(candidate_path.glob("*.py")):
                        src_dirs.append(str(candidate_path))

            if not src_dirs:
                # Try to find any Python files
                py_files = list(project_dir.glob("**/*.py"))
                if not py_files:
                    return
                src_dirs = ["."]

            # Run bandit
            cmd = [
                "bandit",
                "-r",
                *src_dirs,
                "-f",
                "json",
                "--exit-zero",  # Don't fail on findings
            ]

            proc = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.stdout:
                try:
                    bandit_output = json.loads(proc.stdout)
                    for finding in bandit_output.get("results", []):
                        severity = finding.get("issue_severity", "MEDIUM").lower()
                        if severity == "high":
                            severity = "high"
                        elif severity == "medium":
                            severity = "medium"
                        else:
                            severity = "low"

                        result.vulnerabilities.append(
                            SecurityVulnerability(
                                severity=severity,
                                source="bandit",
                                title=finding.get("issue_text", "Unknown issue"),
                                description=finding.get("issue_text", ""),
                                file=finding.get("filename"),
                                line=finding.get("line_number"),
                                cwe=str(finding.get("issue_cwe", {}).get("id")) if finding.get("issue_cwe") else None,
                            )
                        )
                except json.JSONDecodeError:
                    result.scan_errors.append("Failed to parse Bandit output")

        except subprocess.TimeoutExpired:
            result.scan_errors.append("Bandit scan timed out")
        except FileNotFoundError:
            pass  # Bandit not found
        except Exception as e:
            result.scan_errors.append(f"Bandit error: {str(e)}")

    def _run_dependency_audits(
        self, project_dir: Path, result: SecurityScanResult
    ) -> None:
        """Run dependency vulnerability audits."""
        # npm audit for JavaScript projects
        if (project_dir / "package.json").exists():
            self._run_npm_audit(project_dir, result)

        # pip-audit for Python projects (if available)
        if self._is_python_project(project_dir):
            self._run_pip_audit(project_dir, result)

    def _run_npm_audit(self, project_dir: Path, result: SecurityScanResult) -> None:
        """Run npm audit for JavaScript projects."""
        try:
            cmd = ["npm", "audit", "--json"]

            proc = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.stdout:
                try:
                    audit_output = json.loads(proc.stdout)

                    # npm audit v2+ format
                    vulnerabilities = audit_output.get("vulnerabilities", {})
                    for pkg_name, vuln_info in vulnerabilities.items():
                        severity = vuln_info.get("severity", "moderate")
                        if severity == "critical":
                            severity = "critical"
                        elif severity == "high":
                            severity = "high"
                        elif severity == "moderate":
                            severity = "medium"
                        else:
                            severity = "low"

                        via = vuln_info.get("via", [])
                        desc = ""
                        if isinstance(via, list) and via:
                            first = via[0]
                            if isinstance(first, dict):
                                desc = first.get("title", "")
                            else:
                                desc = str(first)
                        elif via:
                            desc = str(via)

                        result.vulnerabilities.append(
                            SecurityVulnerability(
                                severity=severity,
                                source="npm_audit",
                                title=f"Vulnerable dependency: {pkg_name}",
                                description=desc,
                                file="package.json",
                            )
                        )
                except json.JSONDecodeError:
                    pass  # npm audit may return invalid JSON on no findings

        except subprocess.TimeoutExpired:
            result.scan_errors.append("npm audit timed out")
        except FileNotFoundError:
            pass  # npm not available
        except Exception as e:
            result.scan_errors.append(f"npm audit error: {str(e)}")

    def _run_pip_audit(self, project_dir: Path, result: SecurityScanResult) -> None:
        """Run pip-audit for Python projects (if available)."""
        try:
            cmd = ["pip-audit", "--format", "json"]

            proc = subprocess.run(
                cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.stdout:
                try:
                    audit_output = json.loads(proc.stdout)
                    for vuln in audit_output:
                        severity = "high" if vuln.get("fix_versions") else "medium"

                        result.vulnerabilities.append(
                            SecurityVulnerability(
                                severity=severity,
                                source="pip_audit",
                                title=f"Vulnerable package: {vuln.get('name')}",
                                description=vuln.get("description", ""),
                                cwe=vuln.get("aliases", [""])[0] if vuln.get("aliases") else None,
                            )
                        )
                except json.JSONDecodeError:
                    pass

        except FileNotFoundError:
            pass  # pip-audit not available
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    def _is_python_project(self, project_dir: Path) -> bool:
        """Check if this is a Python project."""
        indicators = [
            project_dir / "pyproject.toml",
            project_dir / "requirements.txt",
            project_dir / "setup.py",
            project_dir / "setup.cfg",
        ]
        return any(p.exists() for p in indicators)

    def _check_bandit_available(self) -> bool:
        """Check if Bandit is available."""
        if self._bandit_available is None:
            try:
                subprocess.run(
                    ["bandit", "--version"],
                    capture_output=True,
                    timeout=5,
                )
                self._bandit_available = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._bandit_available = False
        return self._bandit_available

    def _redact_secret(self, text: str) -> str:
        """Redact a secret for safe logging."""
        if len(text) <= 8:
            return "*" * len(text)
        return text[:4] + "*" * (len(text) - 8) + text[-4:]

    def _save_results(self, spec_dir: Path, result: SecurityScanResult) -> None:
        """Save scan results to spec directory."""
        spec_dir = Path(spec_dir)
        spec_dir.mkdir(parents=True, exist_ok=True)

        output_file = spec_dir / "security_scan_results.json"
        output_data = self.to_dict(result)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

    def to_dict(self, result: SecurityScanResult) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "secrets": result.secrets,
            "vulnerabilities": [
                {
                    "severity": v.severity,
                    "source": v.source,
                    "title": v.title,
                    "description": v.description,
                    "file": v.file,
                    "line": v.line,
                    "cwe": v.cwe,
                }
                for v in result.vulnerabilities
            ],
            "scan_errors": result.scan_errors,
            "has_critical_issues": result.has_critical_issues,
            "should_block_qa": result.should_block_qa,
            "files_scanned": result.files_scanned,
            "scan_duration_seconds": result.scan_duration_seconds,
            "summary": {
                "total_secrets": len(result.secrets),
                "total_vulnerabilities": len(result.vulnerabilities),
                "critical_count": sum(1 for v in result.vulnerabilities if v.severity == "critical"),
                "high_count": sum(1 for v in result.vulnerabilities if v.severity == "high"),
                "medium_count": sum(1 for v in result.vulnerabilities if v.severity == "medium"),
                "low_count": sum(1 for v in result.vulnerabilities if v.severity == "low"),
            },
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def scan_for_security_issues(
    project_dir: Path,
    spec_dir: Optional[Path] = None,
    changed_files: Optional[List[str]] = None,
) -> SecurityScanResult:
    """
    Convenience function to run security scan.

    Args:
        project_dir: Path to project root
        spec_dir: Optional spec directory to save results
        changed_files: Optional list of files to scan

    Returns:
        SecurityScanResult with all findings
    """
    scanner = SecurityScanner()
    return scanner.scan(project_dir, spec_dir, changed_files)


def has_security_issues(project_dir: Path) -> bool:
    """
    Quick check if project has security issues.

    Args:
        project_dir: Path to project root

    Returns:
        True if any critical/high issues found
    """
    scanner = SecurityScanner()
    result = scanner.scan(project_dir, run_sast=False, run_dependency_audit=False)
    return result.has_critical_issues


def scan_secrets_only(
    project_dir: Path,
    changed_files: Optional[List[str]] = None,
) -> List[dict]:
    """
    Scan only for secrets (quick scan).

    Args:
        project_dir: Path to project root
        changed_files: Optional list of files to scan

    Returns:
        List of detected secrets
    """
    scanner = SecurityScanner()
    result = scanner.scan(
        project_dir,
        changed_files=changed_files,
        run_sast=False,
        run_dependency_audit=False,
    )
    return result.secrets
