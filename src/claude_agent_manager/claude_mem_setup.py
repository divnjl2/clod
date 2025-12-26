"""
Claude-mem dependency management and testing utilities.

Handles automatic installation of Bun and worker management.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any

# Logging
import logging
logger = logging.getLogger(__name__)


def get_claude_mem_paths() -> Dict[str, Path]:
    """Get all claude-mem related paths."""
    home = Path.home()
    return {
        "data_dir": home / ".claude-mem",
        "db": home / ".claude-mem" / "claude-mem.db",
        "settings": home / ".claude-mem" / "settings.json",
        "logs": home / ".claude-mem" / "logs",
        "plugin_dir": home / ".claude" / "plugins" / "marketplaces" / "thedotmack",
        "bun_bin": home / ".bun" / "bin",
        "bun_exe": home / ".bun" / "bin" / ("bun.exe" if sys.platform == "win32" else "bun"),
    }


def is_bun_installed() -> bool:
    """Check if Bun is installed and accessible."""
    paths = get_claude_mem_paths()

    # Check in .bun/bin first
    if paths["bun_exe"].exists():
        return True

    # Check in PATH
    bun_path = shutil.which("bun")
    return bun_path is not None


def get_bun_path() -> Optional[Path]:
    """Get path to bun executable."""
    paths = get_claude_mem_paths()

    if paths["bun_exe"].exists():
        return paths["bun_exe"]

    bun_in_path = shutil.which("bun")
    if bun_in_path:
        return Path(bun_in_path)

    return None


def install_bun(silent: bool = False) -> bool:
    """
    Install Bun runtime automatically.

    Returns True if installation succeeded or Bun already installed.
    """
    if is_bun_installed():
        if not silent:
            logger.info("[CLAUDE_MEM] Bun already installed")
        return True

    if not silent:
        logger.info("[CLAUDE_MEM] Installing Bun runtime...")

    try:
        if sys.platform == "win32":
            # Windows: Use PowerShell installer
            result = subprocess.run(
                ["powershell", "-Command", "irm bun.sh/install.ps1 | iex"],
                capture_output=True,
                text=True,
                timeout=120
            )
        else:
            # Unix: Use curl installer
            result = subprocess.run(
                ["bash", "-c", "curl -fsSL https://bun.sh/install | bash"],
                capture_output=True,
                text=True,
                timeout=120
            )

        if result.returncode == 0:
            if not silent:
                logger.info("[CLAUDE_MEM] Bun installed successfully")
            return True
        else:
            logger.error(f"[CLAUDE_MEM] Bun installation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("[CLAUDE_MEM] Bun installation timed out")
        return False
    except Exception as e:
        logger.error(f"[CLAUDE_MEM] Bun installation error: {e}")
        return False


def get_worker_port() -> int:
    """Get configured worker port from settings."""
    paths = get_claude_mem_paths()

    if paths["settings"].exists():
        try:
            with open(paths["settings"], "r") as f:
                settings = json.load(f)
                return int(settings.get("CLAUDE_MEM_WORKER_PORT", 37777))
        except Exception:
            pass

    return 37777  # Default port


def is_worker_running() -> bool:
    """Check if claude-mem worker is running."""
    port = get_worker_port()

    try:
        url = f"http://127.0.0.1:{port}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            return data.get("status") == "ok"
    except Exception:
        return False


def get_worker_stats() -> Optional[Dict[str, Any]]:
    """Get worker statistics."""
    port = get_worker_port()

    try:
        url = f"http://127.0.0.1:{port}/api/stats"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def start_worker(silent: bool = False) -> bool:
    """
    Start claude-mem worker service.

    Automatically installs Bun if needed.
    """
    paths = get_claude_mem_paths()

    # Check if plugin is installed
    if not paths["plugin_dir"].exists():
        logger.error("[CLAUDE_MEM] Plugin not installed. Run: /plugin install claude-mem")
        return False

    # Ensure Bun is installed
    if not install_bun(silent=silent):
        return False

    # Check if already running
    if is_worker_running():
        if not silent:
            logger.info("[CLAUDE_MEM] Worker already running")
        return True

    bun_path = get_bun_path()
    if not bun_path:
        logger.error("[CLAUDE_MEM] Bun not found after installation")
        return False

    if not silent:
        logger.info("[CLAUDE_MEM] Starting worker...")

    try:
        # Start worker using npm script
        env = os.environ.copy()
        env["PATH"] = f"{paths['bun_bin']}{os.pathsep}{env.get('PATH', '')}"

        # Run worker:start
        result = subprocess.run(
            ["npm", "run", "worker:start"],
            cwd=str(paths["plugin_dir"]),
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"[CLAUDE_MEM] Worker start failed: {result.stderr}")
            return False

        # Wait for worker to be ready
        for _ in range(10):
            time.sleep(0.5)
            if is_worker_running():
                if not silent:
                    logger.info("[CLAUDE_MEM] Worker started successfully")
                return True

        logger.error("[CLAUDE_MEM] Worker started but not responding")
        return False

    except subprocess.TimeoutExpired:
        logger.error("[CLAUDE_MEM] Worker start timed out")
        return False
    except Exception as e:
        logger.error(f"[CLAUDE_MEM] Worker start error: {e}")
        return False


def stop_worker(silent: bool = False) -> bool:
    """Stop claude-mem worker service."""
    paths = get_claude_mem_paths()

    if not paths["plugin_dir"].exists():
        return True  # Nothing to stop

    if not is_worker_running():
        if not silent:
            logger.info("[CLAUDE_MEM] Worker not running")
        return True

    try:
        env = os.environ.copy()
        env["PATH"] = f"{paths['bun_bin']}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(
            ["npm", "run", "worker:stop"],
            cwd=str(paths["plugin_dir"]),
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        if not silent:
            logger.info("[CLAUDE_MEM] Worker stopped")
        return True

    except Exception as e:
        logger.error(f"[CLAUDE_MEM] Worker stop error: {e}")
        return False


def ensure_worker_running(silent: bool = True) -> bool:
    """
    Ensure worker is running, start if needed.

    This is the main entry point for automatic worker management.
    Call this before any operation that needs claude-mem.
    """
    if is_worker_running():
        return True

    return start_worker(silent=silent)


def get_observation_count() -> int:
    """Get current number of observations in database."""
    stats = get_worker_stats()
    if stats and "database" in stats:
        return stats["database"].get("observations", 0)
    return 0


def diagnose_claude_mem() -> Dict[str, Any]:
    """
    Run full diagnostic on claude-mem setup.

    Returns dict with status of all components.
    """
    paths = get_claude_mem_paths()

    diagnosis = {
        "bun_installed": is_bun_installed(),
        "bun_path": str(get_bun_path()) if get_bun_path() else None,
        "plugin_installed": paths["plugin_dir"].exists(),
        "data_dir_exists": paths["data_dir"].exists(),
        "db_exists": paths["db"].exists(),
        "settings_exists": paths["settings"].exists(),
        "worker_running": is_worker_running(),
        "worker_port": get_worker_port(),
        "observations": 0,
        "sessions": 0,
        "errors": [],
    }

    # Get stats if worker is running
    if diagnosis["worker_running"]:
        stats = get_worker_stats()
        if stats and "database" in stats:
            diagnosis["observations"] = stats["database"].get("observations", 0)
            diagnosis["sessions"] = stats["database"].get("sessions", 0)

    # Check for issues
    if not diagnosis["bun_installed"]:
        diagnosis["errors"].append("Bun not installed")
    if not diagnosis["plugin_installed"]:
        diagnosis["errors"].append("claude-mem plugin not installed")
    if not diagnosis["worker_running"]:
        diagnosis["errors"].append("Worker not running")

    diagnosis["healthy"] = len(diagnosis["errors"]) == 0

    return diagnosis


# CLI interface
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Claude-mem setup utility")
    parser.add_argument("command", choices=["diagnose", "install", "start", "stop", "status"])
    args = parser.parse_args()

    if args.command == "diagnose":
        diag = diagnose_claude_mem()
        print(json.dumps(diag, indent=2))
    elif args.command == "install":
        success = install_bun(silent=False)
        sys.exit(0 if success else 1)
    elif args.command == "start":
        success = start_worker(silent=False)
        sys.exit(0 if success else 1)
    elif args.command == "stop":
        success = stop_worker(silent=False)
        sys.exit(0 if success else 1)
    elif args.command == "status":
        if is_worker_running():
            stats = get_worker_stats()
            print(f"Worker: RUNNING (port {get_worker_port()})")
            if stats:
                print(f"Observations: {stats['database']['observations']}")
                print(f"Sessions: {stats['database']['sessions']}")
        else:
            print("Worker: NOT RUNNING")
            sys.exit(1)
