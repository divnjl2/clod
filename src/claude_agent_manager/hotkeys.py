"""
Global hotkey support using Windows API.

Registers system-wide hotkeys that work even when app is not focused.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from threading import Thread
from typing import Callable, Dict, Optional
import queue

user32 = ctypes.WinDLL("user32", use_last_error=True)

# Windows API functions
RegisterHotKey = user32.RegisterHotKey
RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
RegisterHotKey.restype = wintypes.BOOL

UnregisterHotKey = user32.UnregisterHotKey
UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
UnregisterHotKey.restype = wintypes.BOOL

GetMessageW = user32.GetMessageW
GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
GetMessageW.restype = wintypes.BOOL

PostThreadMessageW = user32.PostThreadMessageW
PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
PostThreadMessageW.restype = wintypes.BOOL

# Modifier keys
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Virtual key codes
VK_CODES = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE,
    "/": 0xBF,
}

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


@dataclass
class HotkeyBinding:
    """Represents a hotkey binding."""
    id: int
    modifiers: int
    vk: int
    callback: Callable[[], None]
    description: str


def parse_hotkey_string(hotkey_str: str) -> tuple[int, int]:
    """
    Parse hotkey string like "ctrl+alt+t" into (modifiers, vk).

    Returns (0, 0) if invalid or "none".
    """
    if not hotkey_str or hotkey_str.lower() == "none":
        return (0, 0)

    parts = hotkey_str.lower().replace(" ", "").split("+")
    modifiers = 0
    vk = 0

    for part in parts:
        if part == "ctrl" or part == "control":
            modifiers |= MOD_CONTROL
        elif part == "alt":
            modifiers |= MOD_ALT
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part == "win" or part == "super":
            modifiers |= MOD_WIN
        elif part in VK_CODES:
            vk = VK_CODES[part]

    return (modifiers | MOD_NOREPEAT, vk)


def format_hotkey(modifiers: int, vk: int) -> str:
    """Format modifiers and vk back to string."""
    parts = []
    if modifiers & MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & MOD_ALT:
        parts.append("Alt")
    if modifiers & MOD_SHIFT:
        parts.append("Shift")
    if modifiers & MOD_WIN:
        parts.append("Win")

    for key, code in VK_CODES.items():
        if code == vk:
            parts.append(key.upper() if len(key) == 1 else key.capitalize())
            break

    return "+".join(parts)


class GlobalHotkeyManager:
    """
    Manages global hotkeys using Windows RegisterHotKey API.

    Usage:
        manager = GlobalHotkeyManager()
        manager.register("ctrl+alt+t", callback, "Tile windows")
        manager.start()
        # ... app runs ...
        manager.stop()
    """

    def __init__(self):
        self._bindings: Dict[int, HotkeyBinding] = {}
        self._next_id = 1
        self._thread: Optional[Thread] = None
        self._thread_id: Optional[int] = None
        self._running = False
        self._callback_queue: queue.Queue = queue.Queue()

    def register(self, hotkey_str: str, callback: Callable[[], None], description: str = "") -> bool:
        """
        Register a global hotkey.

        Args:
            hotkey_str: Hotkey string like "ctrl+alt+t"
            callback: Function to call when hotkey pressed
            description: Human-readable description

        Returns:
            True if registered successfully
        """
        modifiers, vk = parse_hotkey_string(hotkey_str)
        if vk == 0:
            return False

        binding = HotkeyBinding(
            id=self._next_id,
            modifiers=modifiers,
            vk=vk,
            callback=callback,
            description=description,
        )
        self._bindings[self._next_id] = binding
        self._next_id += 1

        # If already running, register immediately
        if self._running:
            result = RegisterHotKey(None, binding.id, binding.modifiers, binding.vk)
            if not result:
                del self._bindings[binding.id]
                return False

        return True

    def unregister(self, hotkey_id: int) -> bool:
        """Unregister a hotkey by ID."""
        if hotkey_id not in self._bindings:
            return False

        if self._running:
            UnregisterHotKey(None, hotkey_id)

        del self._bindings[hotkey_id]
        return True

    def unregister_all(self) -> None:
        """Unregister all hotkeys."""
        for hk_id in list(self._bindings.keys()):
            self.unregister(hk_id)

    def start(self) -> bool:
        """Start the hotkey listener thread."""
        if self._running:
            return True

        self._running = True
        self._thread = Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the hotkey listener thread."""
        if not self._running:
            return

        self._running = False

        # Post quit message to thread
        if self._thread_id:
            PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def process_callbacks(self) -> None:
        """
        Process pending callbacks in the main thread.

        Call this periodically from your main thread (e.g., via Tkinter after()).
        """
        while True:
            try:
                callback = self._callback_queue.get_nowait()
                callback()
            except queue.Empty:
                break

    def _message_loop(self) -> None:
        """Message loop running in background thread."""
        import ctypes
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # Register all hotkeys
        for binding in self._bindings.values():
            result = RegisterHotKey(None, binding.id, binding.modifiers, binding.vk)
            if not result:
                print(f"Failed to register hotkey: {format_hotkey(binding.modifiers, binding.vk)}")

        msg = wintypes.MSG()
        while self._running:
            result = GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break

            if msg.message == WM_HOTKEY:
                hk_id = msg.wParam
                if hk_id in self._bindings:
                    # Queue callback to be processed in main thread
                    self._callback_queue.put(self._bindings[hk_id].callback)

        # Unregister all hotkeys
        for binding in self._bindings.values():
            UnregisterHotKey(None, binding.id)

        self._thread_id = None


# Singleton instance
_manager: Optional[GlobalHotkeyManager] = None


def get_hotkey_manager() -> GlobalHotkeyManager:
    """Get or create the global hotkey manager singleton."""
    global _manager
    if _manager is None:
        _manager = GlobalHotkeyManager()
    return _manager
