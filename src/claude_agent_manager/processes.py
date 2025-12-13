from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import psutil

CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000


def which(cmd: str) -> Optional[str]:
    from shutil import which as _which
    return _which(cmd)


def is_pid_running(pid: Optional[int]) -> bool:
    return bool(pid) and psutil.pid_exists(pid)


def kill_tree(pid: int) -> None:
    """Жёстко убивает процесс и всех детей."""
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for child in parent.children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def run_pm2(args: list[str], cwd: Optional[str] = None, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess:
    pm2 = which("pm2")
    if not pm2:
        raise RuntimeError("pm2 not found in PATH. Install: npm install -g pm2")
    return subprocess.run(
        [pm2, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=CREATE_NO_WINDOW,
    )


def pm2_exists(name: str) -> bool:
    res = run_pm2(["describe", name])
    return res.returncode == 0


def pm2_start_worker(name: str, worker_script: str, cwd: str, env: dict[str, str]) -> None:
    res = run_pm2(
        ["start", worker_script, "--name", name, "--cwd", cwd],
        cwd=cwd,
        env={**os.environ, **env},
    )
    if res.returncode != 0:
        raise RuntimeError(f"pm2 start failed: {res.stderr.strip() or res.stdout.strip()}")


def pm2_delete(name: str) -> None:
    run_pm2(["delete", name])


def pm2_stop(name: str) -> None:
    """Stop a pm2 process by name."""
    run_pm2(["stop", name])


def pm2_restart(name: str) -> None:
    """Restart a pm2 process by name."""
    run_pm2(["restart", name])


def pm2_status(name: str) -> Optional[dict]:
    """Get status of a pm2 process by name. Returns dict with status info or None."""
    import json
    res = run_pm2(["jlist"])
    if res.returncode != 0:
        return None
    try:
        # PM2 may output warnings before JSON, find the JSON array
        stdout = res.stdout
        json_start = stdout.find('[')
        if json_start == -1:
            return None
        stdout = stdout[json_start:]

        processes = json.loads(stdout)
        for proc in processes:
            if proc.get("name") == name:
                return {
                    "status": proc.get("pm2_env", {}).get("status", "unknown"),
                    "pid": proc.get("pid"),
                    "pm_id": proc.get("pm_id"),
                }
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def spawn_cmd(project_path: str, port: int) -> Optional[int]:
    """Spawn a command window with claude for the project."""
    claude = which("claude")
    if not claude:
        return None

    # Create a batch script that runs claude in the project directory
    cmd = f'cd /d "{project_path}" && claude'
    p = subprocess.Popen(
        ["cmd.exe", "/k", cmd],
        cwd=project_path,
        creationflags=CREATE_NEW_CONSOLE,
        env={**os.environ, "CLAUDE_MEM_WORKER_PORT": str(port)},
    )
    return p.pid


def spawn_cmd_window(cmd_script: Path, workdir: Optional[str] = None) -> int:
    p = subprocess.Popen(
        ["cmd.exe", "/k", str(cmd_script)],
        cwd=workdir,
        creationflags=CREATE_NEW_CONSOLE,
    )
    return p.pid


def spawn_browser(url: str, browser: str, agent_id: Optional[str] = None, *, headless: bool = False) -> Optional[int]:
    """
    Spawn browser window for viewer.
    Each agent gets its own isolated browser profile via --user-data-dir.
    """
    b = browser.strip().lower()

    # Unique profile dir per agent for true isolation
    profile_name = agent_id or f"viewer-{os.getpid()}"
    profile_dir = Path.home() / ".claude-agents" / "browser-profiles" / profile_name

    if b == "default":
        subprocess.Popen(["cmd.exe", "/c", "start", "", url], creationflags=CREATE_NEW_CONSOLE)
        return None

    if b == "edge-app":
        edge = which("msedge") or which("msedge.exe")
        if not edge:
            subprocess.Popen(["cmd.exe", "/c", "start", "", url], creationflags=CREATE_NEW_CONSOLE)
            return None
        # Fully isolated instance with dark mode
        p = subprocess.Popen([
            edge,
            f"--app={url}",
            "--new-window",
            "--force-dark-mode",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--enable-features=msEdgeHeadless",
            *(["--headless=new"] if headless else []),
            f"--user-data-dir={profile_dir}",
        ])
        return p.pid

    if b.startswith("path:"):
        exe = browser.split(":", 1)[1].strip().strip('"')
        p = subprocess.Popen([
            exe,
            f"--app={url}",
            "--new-window",
            "--force-dark-mode",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            *(["--headless=new"] if headless else []),
            f"--user-data-dir={profile_dir}",
        ])
        return p.pid

    subprocess.Popen(["cmd.exe", "/c", "start", "", url], creationflags=CREATE_NEW_CONSOLE)
    return None
