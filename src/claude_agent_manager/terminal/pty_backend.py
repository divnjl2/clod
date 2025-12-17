"""
Cross-platform PTY backend.

Uses pywinpty on Windows, built-in pty on Unix.
"""
from __future__ import annotations

import os
import sys
import signal
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Callable

logger = logging.getLogger(__name__)


class PTYBackend(ABC):
    """Abstract PTY backend."""

    @abstractmethod
    def spawn(self, cmd: list[str], cwd: str, size: Tuple[int, int] = (24, 80)) -> None:
        """Spawn a process in PTY."""
        pass

    @abstractmethod
    def read(self, size: int = 4096) -> str:
        """Read from PTY (non-blocking if possible)."""
        pass

    @abstractmethod
    def write(self, data: str) -> None:
        """Write to PTY."""
        pass

    @abstractmethod
    def resize(self, rows: int, cols: int) -> None:
        """Resize PTY."""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if process is still running."""
        pass

    @abstractmethod
    def terminate(self) -> None:
        """Terminate the process."""
        pass

    @abstractmethod
    def send_signal(self, sig: int) -> None:
        """Send signal to process (e.g., SIGINT for Ctrl+C)."""
        pass


class WindowsPTY(PTYBackend):
    """Windows PTY using pywinpty/ConPTY."""

    def __init__(self):
        self.process = None

    def spawn(self, cmd: list[str], cwd: str, size: Tuple[int, int] = (24, 80)) -> None:
        try:
            from winpty import PtyProcess
        except ImportError:
            raise ImportError("pywinpty is required on Windows. Install with: pip install pywinpty")

        # Join command for Windows
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd

        self.process = PtyProcess.spawn(
            cmd_str,
            cwd=cwd,
            dimensions=(size[0], size[1])
        )
        logger.info(f"[TERMINAL] WindowsPTY spawned: {cmd_str}")

    def read(self, size: int = 4096) -> str:
        if not self.process:
            return ""
        try:
            return self.process.read(size)
        except Exception:
            return ""

    def write(self, data: str) -> None:
        if self.process:
            self.process.write(data)

    def resize(self, rows: int, cols: int) -> None:
        if self.process:
            try:
                self.process.setwinsize(rows, cols)
            except Exception as e:
                logger.warning(f"[TERMINAL] resize failed: {e}")

    def is_alive(self) -> bool:
        return self.process is not None and self.process.isalive()

    def terminate(self) -> None:
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None

    def send_signal(self, sig: int) -> None:
        # Windows doesn't support Unix signals, send Ctrl+C
        if self.process and sig == signal.SIGINT:
            self.write("\x03")  # Ctrl+C


class UnixPTY(PTYBackend):
    """Unix PTY using built-in pty module."""

    def __init__(self):
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.pid: Optional[int] = None

    def spawn(self, cmd: list[str], cwd: str, size: Tuple[int, int] = (24, 80)) -> None:
        import pty
        import fcntl
        import struct
        import termios

        # Create PTY pair
        self.master_fd, self.slave_fd = pty.openpty()

        # Set terminal size
        winsize = struct.pack('HHHH', size[0], size[1], 0, 0)
        fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)

        # Fork process
        self.pid = os.fork()

        if self.pid == 0:
            # Child process
            os.close(self.master_fd)
            os.setsid()

            # Set controlling terminal
            fcntl.ioctl(self.slave_fd, termios.TIOCSCTTY, 0)

            # Redirect stdio
            os.dup2(self.slave_fd, 0)
            os.dup2(self.slave_fd, 1)
            os.dup2(self.slave_fd, 2)

            if self.slave_fd > 2:
                os.close(self.slave_fd)

            # Change directory and exec
            os.chdir(cwd)
            os.execvp(cmd[0], cmd)
        else:
            # Parent process
            os.close(self.slave_fd)
            self.slave_fd = None

            # Set non-blocking
            import fcntl
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            logger.info(f"[TERMINAL] UnixPTY spawned PID {self.pid}: {cmd}")

    def read(self, size: int = 4096) -> str:
        if self.master_fd is None:
            return ""
        try:
            data = os.read(self.master_fd, size)
            return data.decode('utf-8', errors='replace')
        except BlockingIOError:
            return ""
        except OSError:
            return ""

    def write(self, data: str) -> None:
        if self.master_fd is not None:
            os.write(self.master_fd, data.encode('utf-8'))

    def resize(self, rows: int, cols: int) -> None:
        if self.master_fd is not None:
            import fcntl
            import struct
            import termios
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def is_alive(self) -> bool:
        if self.pid is None:
            return False
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            return False

    def terminate(self) -> None:
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.pid = None

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

    def send_signal(self, sig: int) -> None:
        if self.pid:
            try:
                os.kill(self.pid, sig)
            except ProcessLookupError:
                pass


def create_pty_backend() -> PTYBackend:
    """Create appropriate PTY backend for current platform."""
    if sys.platform == "win32":
        return WindowsPTY()
    else:
        return UnixPTY()
