from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

# Define WNDENUMPROC callback type
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32 = ctypes.WinDLL("user32", use_last_error=True)

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
EnumWindows.restype = wintypes.BOOL

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = [wintypes.HWND]
GetWindowTextLengthW.restype = ctypes.c_int

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

MoveWindow = user32.MoveWindow
MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
MoveWindow.restype = wintypes.BOOL

SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = [wintypes.HWND]
SetForegroundWindow.restype = wintypes.BOOL

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
ShowWindow.restype = wintypes.BOOL

# ShowWindow commands
SW_HIDE = 0
SW_MINIMIZE = 6
SW_RESTORE = 9
SW_SHOW = 5


def _get_window_text(hwnd: int) -> str:
    length = GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_main_window(pid: int) -> Optional[int]:
    found: dict[str, Optional[int]] = {"hwnd": None}

    @WNDENUMPROC
    def enum_proc(hwnd, lparam):
        if not IsWindowVisible(hwnd):
            return True
        proc_id = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value != pid:
            return True
        title = _get_window_text(hwnd)
        if not title.strip():
            return True
        found["hwnd"] = int(hwnd)
        return False

    EnumWindows(enum_proc, 0)
    return found["hwnd"]


def move_window(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    MoveWindow(hwnd, x, y, w, h, True)


def bring_to_front(hwnd: int) -> None:
    """Bring window to foreground."""
    ShowWindow(hwnd, SW_RESTORE)
    SetForegroundWindow(hwnd)


def minimize_window(hwnd: int) -> None:
    """Minimize window."""
    ShowWindow(hwnd, SW_MINIMIZE)


def restore_window(hwnd: int) -> None:
    """Restore minimized window."""
    ShowWindow(hwnd, SW_RESTORE)
