from __future__ import annotations

from typing import Optional

from .windows import find_main_window, move_window


def tile_two_in_cell(cmd_pid: Optional[int], viewer_pid: Optional[int], x: int, y: int, w: int, h: int) -> None:
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
