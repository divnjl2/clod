"""
Window tiling utilities for Claude Agent Manager.

Supports smart tiling of agent windows based on count:
- 1 agent: maximize or centered large
- 2 agents: side by side (horizontal) or stacked (vertical)
- 3 agents: 2+1 layout
- 4+ agents: grid layout
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

from .windows import find_main_window, move_window

# Windows API for monitor info
user32 = ctypes.WinDLL("user32", use_last_error=True)

# Monitor enumeration
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
GetMonitorInfoW.restype = wintypes.BOOL

EnumDisplayMonitors = user32.EnumDisplayMonitors
EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), MONITORENUMPROC, wintypes.LPARAM]
EnumDisplayMonitors.restype = wintypes.BOOL

MonitorFromWindow = user32.MonitorFromWindow
MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
MonitorFromWindow.restype = wintypes.HMONITOR

MONITOR_DEFAULTTOPRIMARY = 1
MONITOR_DEFAULTTONEAREST = 2


@dataclass
class MonitorRect:
    """Monitor work area rectangle."""
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


def get_primary_monitor_work_area() -> MonitorRect:
    """Get work area of primary monitor (excludes taskbar)."""
    monitors: List[MonitorRect] = []

    @MONITORENUMPROC
    def enum_proc(hmon, hdc, rect, lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if GetMonitorInfoW(hmon, ctypes.byref(info)):
            # Check if primary (dwFlags & 1)
            if info.dwFlags & 1:
                rc = info.rcWork
                monitors.append(MonitorRect(rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top))
        return True

    EnumDisplayMonitors(None, None, enum_proc, 0)

    if monitors:
        return monitors[0]

    # Fallback to screen metrics
    return MonitorRect(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def get_all_monitors() -> List[MonitorRect]:
    """Get work areas of all monitors."""
    monitors: List[MonitorRect] = []

    @MONITORENUMPROC
    def enum_proc(hmon, hdc, rect, lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if GetMonitorInfoW(hmon, ctypes.byref(info)):
            rc = info.rcWork
            monitors.append(MonitorRect(rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top))
        return True

    EnumDisplayMonitors(None, None, enum_proc, 0)
    return monitors


def get_monitor_from_hwnd(hwnd: int) -> MonitorRect:
    """Get monitor work area containing the given window."""
    hmon = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if GetMonitorInfoW(hmon, ctypes.byref(info)):
        rc = info.rcWork
        return MonitorRect(rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)
    return get_primary_monitor_work_area()


# Layout types
TileLayout = Literal["horizontal", "vertical", "grid", "smart"]


def tile_two_in_cell(cmd_pid: Optional[int], viewer_pid: Optional[int], x: int, y: int, w: int, h: int) -> None:
    """Legacy function: tile cmd and viewer in a cell (55/45 split)."""
    cmd_w = int(w * 0.55)
    view_w = w - cmd_w

    if cmd_pid:
        hwnd = find_main_window(cmd_pid)
        if hwnd:
            move_window(hwnd, x, y, cmd_w, h)

    if viewer_pid:
        hwnd = find_main_window(viewer_pid)
        if hwnd:
            move_window(hwnd, x + cmd_w, y, view_w, h)


def tile_windows(
    hwnds: List[int],
    layout: TileLayout = "smart",
    monitor: Optional[MonitorRect] = None,
    gap: int = 8,
) -> None:
    """
    Tile windows according to layout.

    Args:
        hwnds: List of window handles to tile
        layout: Layout type - "horizontal", "vertical", "grid", or "smart"
        monitor: Monitor to tile on (defaults to primary)
        gap: Gap between windows in pixels
    """
    if not hwnds:
        return

    if monitor is None:
        monitor = get_primary_monitor_work_area()

    count = len(hwnds)

    if layout == "smart":
        # Smart layout based on window count
        if count == 1:
            _tile_single(hwnds[0], monitor, gap)
        elif count == 2:
            _tile_two(hwnds, monitor, gap)
        elif count == 3:
            _tile_three(hwnds, monitor, gap)
        else:
            _tile_grid(hwnds, monitor, gap)
    elif layout == "horizontal":
        _tile_horizontal(hwnds, monitor, gap)
    elif layout == "vertical":
        _tile_vertical(hwnds, monitor, gap)
    elif layout == "grid":
        _tile_grid(hwnds, monitor, gap)


def _tile_single(hwnd: int, mon: MonitorRect, gap: int) -> None:
    """Tile single window - maximize with margins."""
    margin = gap * 2
    move_window(
        hwnd,
        mon.x + margin,
        mon.y + margin,
        mon.width - margin * 2,
        mon.height - margin * 2,
    )


def _tile_two(hwnds: List[int], mon: MonitorRect, gap: int) -> None:
    """Tile two windows side by side."""
    half_w = (mon.width - gap * 3) // 2
    h = mon.height - gap * 2

    # Left window
    move_window(hwnds[0], mon.x + gap, mon.y + gap, half_w, h)
    # Right window
    move_window(hwnds[1], mon.x + gap * 2 + half_w, mon.y + gap, half_w, h)


def _tile_three(hwnds: List[int], mon: MonitorRect, gap: int) -> None:
    """Tile three windows - 2 on left, 1 on right (or 2 top, 1 bottom)."""
    # Horizontal layout: [1][2] on left half, [3] on right half
    if mon.width >= mon.height:
        # Landscape: 2 stacked on left, 1 large on right
        left_w = (mon.width - gap * 3) // 2
        right_w = mon.width - left_w - gap * 3
        half_h = (mon.height - gap * 3) // 2

        # Top-left
        move_window(hwnds[0], mon.x + gap, mon.y + gap, left_w, half_h)
        # Bottom-left
        move_window(hwnds[1], mon.x + gap, mon.y + gap * 2 + half_h, left_w, half_h)
        # Right (full height)
        move_window(hwnds[2], mon.x + gap * 2 + left_w, mon.y + gap, right_w, mon.height - gap * 2)
    else:
        # Portrait: 2 on top row, 1 on bottom
        half_w = (mon.width - gap * 3) // 2
        top_h = (mon.height - gap * 3) // 2
        bottom_h = mon.height - top_h - gap * 3

        # Top-left
        move_window(hwnds[0], mon.x + gap, mon.y + gap, half_w, top_h)
        # Top-right
        move_window(hwnds[1], mon.x + gap * 2 + half_w, mon.y + gap, half_w, top_h)
        # Bottom (full width)
        move_window(hwnds[2], mon.x + gap, mon.y + gap * 2 + top_h, mon.width - gap * 2, bottom_h)


def _tile_grid(hwnds: List[int], mon: MonitorRect, gap: int) -> None:
    """Tile windows in a grid pattern."""
    count = len(hwnds)
    if count == 0:
        return

    # Calculate grid dimensions
    if count <= 2:
        cols = count
        rows = 1
    elif count <= 4:
        cols = 2
        rows = 2
    elif count <= 6:
        cols = 3
        rows = 2
    elif count <= 9:
        cols = 3
        rows = 3
    else:
        cols = 4
        rows = (count + 3) // 4

    cell_w = (mon.width - gap * (cols + 1)) // cols
    cell_h = (mon.height - gap * (rows + 1)) // rows

    for i, hwnd in enumerate(hwnds):
        row = i // cols
        col = i % cols
        x = mon.x + gap + col * (cell_w + gap)
        y = mon.y + gap + row * (cell_h + gap)
        move_window(hwnd, x, y, cell_w, cell_h)


def _tile_horizontal(hwnds: List[int], mon: MonitorRect, gap: int) -> None:
    """Tile windows horizontally (side by side)."""
    count = len(hwnds)
    cell_w = (mon.width - gap * (count + 1)) // count
    h = mon.height - gap * 2

    for i, hwnd in enumerate(hwnds):
        x = mon.x + gap + i * (cell_w + gap)
        move_window(hwnd, x, mon.y + gap, cell_w, h)


def _tile_vertical(hwnds: List[int], mon: MonitorRect, gap: int) -> None:
    """Tile windows vertically (stacked)."""
    count = len(hwnds)
    cell_h = (mon.height - gap * (count + 1)) // count
    w = mon.width - gap * 2

    for i, hwnd in enumerate(hwnds):
        y = mon.y + gap + i * (cell_h + gap)
        move_window(hwnd, mon.x + gap, y, w, cell_h)


def tile_agent_windows(
    windows: List[Tuple[str, int]],  # [(agent_id, hwnd), ...]
    layout: TileLayout = "smart",
    monitor: Optional[MonitorRect] = None,
    gap: int = 8,
) -> int:
    """
    Tile agent windows.

    Args:
        windows: List of (agent_id, hwnd) tuples
        layout: Layout type
        monitor: Target monitor (defaults to primary)
        gap: Gap between windows

    Returns:
        Number of windows tiled
    """
    # Filter valid handles
    valid_hwnds = [hwnd for _, hwnd in windows if hwnd]
    if not valid_hwnds:
        return 0

    tile_windows(valid_hwnds, layout=layout, monitor=monitor, gap=gap)
    return len(valid_hwnds)
