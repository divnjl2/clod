from __future__ import annotations

import json
import os
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import atomic_write_json, ensure_dir


def utc_ts() -> float:
    return time.time()


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    OpenProcess = kernel32.OpenProcess
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    OpenProcess.restype = wintypes.HANDLE

    GetExitCodeProcess = kernel32.GetExitCodeProcess
    GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    GetExitCodeProcess.restype = wintypes.BOOL

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not GetExitCodeProcess(h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        CloseHandle(h)


@dataclass(frozen=True, slots=True)
class LockMeta:
    owner_pid: int
    owner_started_at: str
    last_heartbeat_ts: float | None = None
    extra: dict[str, Any] | None = None


class FileLock(AbstractContextManager["FileLock"]):
    """
    Кроссплатформенный advisory file lock с stale-recovery.
    """

    def __init__(
        self,
        lock_path: Path,
        *,
        stale_ttl_sec: int | None = 60,
        poll_interval_sec: float = 0.2,
        timeout_sec: float = 10.0,
    ) -> None:
        self.lock_path = lock_path
        self.meta_path = lock_path.with_suffix(lock_path.suffix + ".meta.json")
        self.stale_ttl_sec = stale_ttl_sec
        self.poll_interval_sec = poll_interval_sec
        self.timeout_sec = timeout_sec
        self._fh = None

    def __enter__(self) -> "FileLock":
        ensure_dir(self.lock_path.parent)
        deadline = time.time() + self.timeout_sec

        while True:
            try:
                self._fh = open(self.lock_path, "a+b")
                self._acquire_os_lock(self._fh)
                self._write_meta(owner_pid=os.getpid())
                return self
            except BlockingIOError:
                if self._is_stale():
                    self._try_break_stale()
                else:
                    if time.time() >= deadline:
                        raise TimeoutError(f"Lock timeout: {self.lock_path}")
                    time.sleep(self.poll_interval_sec)
            finally:
                if self._fh is not None and not self._is_locked_by_me():
                    try:
                        self._fh.close()
                    except Exception:
                        pass
                    self._fh = None

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self._delete_meta()
        finally:
            if self._fh is not None:
                try:
                    self._release_os_lock(self._fh)
                finally:
                    try:
                        self._fh.close()
                    except Exception:
                        pass
                    self._fh = None

    def heartbeat(self) -> None:
        meta = self._read_meta()
        if meta is None:
            return
        data = {
            "owner_pid": meta.owner_pid,
            "owner_started_at": meta.owner_started_at,
            "last_heartbeat_ts": utc_ts(),
            "extra": meta.extra or {},
        }
        atomic_write_json(self.meta_path, data)

    def _is_locked_by_me(self) -> bool:
        meta = self._read_meta()
        return meta is not None and meta.owner_pid == os.getpid()

    def _read_meta(self) -> LockMeta | None:
        if not self.meta_path.exists():
            return None
        try:
            raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
            return LockMeta(
                owner_pid=int(raw.get("owner_pid", 0)),
                owner_started_at=str(raw.get("owner_started_at", "")),
                last_heartbeat_ts=raw.get("last_heartbeat_ts"),
                extra=raw.get("extra") or {},
            )
        except Exception:
            return None

    def _write_meta(self, owner_pid: int) -> None:
        data = {
            "owner_pid": owner_pid,
            "owner_started_at": utc_iso(),
            "last_heartbeat_ts": utc_ts(),
            "extra": {},
        }
        atomic_write_json(self.meta_path, data)

    def _delete_meta(self) -> None:
        try:
            if self.meta_path.exists():
                self.meta_path.unlink()
        except Exception:
            pass

    def _is_stale(self) -> bool:
        meta = self._read_meta()
        if meta is None:
            return False

        if meta.owner_pid and not _pid_exists(meta.owner_pid):
            return True

        if self.stale_ttl_sec is not None and meta.last_heartbeat_ts is not None:
            return (utc_ts() - float(meta.last_heartbeat_ts)) > float(self.stale_ttl_sec)

        return False

    def _try_break_stale(self) -> None:
        self._delete_meta()

    @staticmethod
    def _acquire_os_lock(fh) -> None:
        if os.name == "posix":
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    @staticmethod
    def _release_os_lock(fh) -> None:
        if os.name == "posix":
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
