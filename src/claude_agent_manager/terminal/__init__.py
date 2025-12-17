"""
Cross-platform terminal emulator for Claude Agent Manager.

Supports Windows (ConPTY via pywinpty) and Unix (pty module).
"""

from .widget import TerminalWidget

__all__ = ["TerminalWidget"]
