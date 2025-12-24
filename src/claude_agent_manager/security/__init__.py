"""
Security Module for Claude Agent Manager
=========================================

Provides security scanning capabilities including:
- Secrets detection in code
- SAST (Static Application Security Testing)
- Dependency vulnerability audits

Integrated from Auto-Claude security scanner.
"""

from .scanner import (
    SecurityScanner,
    SecurityScanResult,
    SecurityVulnerability,
    scan_for_security_issues,
    has_security_issues,
    scan_secrets_only,
)

__all__ = [
    "SecurityScanner",
    "SecurityScanResult",
    "SecurityVulnerability",
    "scan_for_security_issues",
    "has_security_issues",
    "scan_secrets_only",
]
