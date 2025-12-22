"""
Web Dashboard module - FastAPI-based web interface.

Phase 3: Advanced Features
"""

from .app import (
    create_app,
    WebDashboard,
    run_server,
)

__all__ = [
    "create_app",
    "WebDashboard",
    "run_server",
]
