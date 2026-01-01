"""Modern minimalist Tkinter dashboard for Claude agents.

Compact card-based UI with smooth animations, theme toggle and agent settings.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

# PIL for anti-aliased graphics
try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = ImageDraw = ImageTk = None

# Detect if running in PyInstaller bundle
_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_asset_path(filename: str) -> Path:
    """Get path to asset file, works both in dev and PyInstaller builds."""
    # PyInstaller stores assets in _MEIPASS temp directory
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "assets" / filename
    # Dev mode - assets are in project root
    return Path(__file__).parent.parent.parent / "assets" / filename


def get_app_data_dir() -> Path:
    """Get platform-specific app data directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ClaudeAgentManager"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClaudeAgentManager"
    else:  # Linux and others
        return Path.home() / ".local" / "share" / "claude-agent-manager"


def ensure_app_dirs() -> Path:
    """Create app directory structure if not exists."""
    app_dir = get_app_data_dir()

    # Create directory structure
    (app_dir / "config" / "templates").mkdir(parents=True, exist_ok=True)
    (app_dir / "agents").mkdir(parents=True, exist_ok=True)

    return app_dir

# Import real agent manager - use absolute imports for PyInstaller compatibility
def _import_backend():
    """Import backend modules, handling both package and frozen contexts."""
    global manager, load_config, pm2_status, pm2_restart, which, ac, AgentConfigOptions

    try:
        # Try absolute imports first (works in PyInstaller)
        import claude_agent_manager.manager as manager
        from claude_agent_manager.config import load_config
        from claude_agent_manager.processes import pm2_status, pm2_restart, which
        import claude_agent_manager.agent_config as ac
        from claude_agent_manager.registry import AgentConfigOptions
        return True
    except ImportError:
        try:
            # Fallback to relative imports (works in dev)
            from . import manager as manager
            from .config import load_config
            from .processes import pm2_status, pm2_restart, which
            from . import agent_config as ac
            from claude_agent_manager.registry import AgentConfigOptions
            return True
        except ImportError as e:
            print(f"[STARTUP] Backend import failed: {e}")
            import traceback
            traceback.print_exc()
            return False

# Initialize backend
manager = None
load_config = None
pm2_status = None
pm2_restart = None
which = None
ac = None
AgentConfigOptions = None

HAS_BACKEND = _import_backend()
if HAS_BACKEND:
    print("[STARTUP] Backend imports successful")

# Import embedded console (optional, graceful fallback)
try:
    from claude_agent_manager.terminal.embedded_console import EmbeddedConsole, create_agent_window
    HAS_EMBEDDED_CONSOLE = True
except ImportError:
    HAS_EMBEDDED_CONSOLE = False
    EmbeddedConsole = None
    create_agent_window = None

# Import tiling and hotkey support
try:
    from claude_agent_manager.tile import tile_windows, get_primary_monitor_work_area
    from claude_agent_manager.hotkeys import get_hotkey_manager, parse_hotkey_string
    HAS_TILING = True
except ImportError:
    HAS_TILING = False
    tile_windows = None
    get_hotkey_manager = None

# Terminal panel is disabled (using separate embedded windows instead)
HAS_TERMINAL = False
TerminalWidget = None

# Import worktree UI components
try:
    from claude_agent_manager.worktree_ui import (
        WorktreePanel, WorktreeInfo,
        CreateWorktreeDialog, MergeConfirmDialog, DiscardConfirmDialog
    )
    from claude_agent_manager.worktree_manager import WorktreeManager
    HAS_WORKTREE_UI = True
except ImportError:
    HAS_WORKTREE_UI = False
    WorktreePanel = None
    WorktreeManager = None

# Import memory modules for cleanup
try:
    from claude_agent_manager.memory import GraphMemory, SessionMemory
    HAS_MEMORY = True
except ImportError:
    HAS_MEMORY = False
    GraphMemory = None
    SessionMemory = None


# ═══════════════════════════════════════════════════════════════════════════════
# WINDOWS TITLE BAR COLOR
# ═══════════════════════════════════════════════════════════════════════════════

def set_title_bar_color(root: tk.Tk, is_dark: bool) -> None:
    """Set Windows title bar color to match theme."""
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1 if is_dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass  # Silently fail on non-Windows or older Windows


# ═══════════════════════════════════════════════════════════════════════════════
# THEMES
# ═══════════════════════════════════════════════════════════════════════════════

THEMES = {
    "dark": {
        "bg": "#1a1a1a",
        "card_bg": "#252525",
        "card_hover": "#2d2d2d",
        "fg": "#e8e8e8",
        "fg_dim": "#777",
        "accent": "#4a9eff",
        "border": "#333",
        "btn_bg": "#333",
        "btn_hover": "#404040",
        "online": "#4ade80",
        "offline": "#555",
        "stop_bg": "#3d2a2a",
        "stop_fg": "#f87171",
        "start_bg": "#2a3d2a",
        "start_fg": "#4ade80",
        "separator": "#333",
        "toggle_track": "#444",
        "toggle_knob": "#fff",
    },
    "light": {
        "bg": "#f0f0f0",
        "card_bg": "#fff",
        "card_hover": "#f8f8f8",
        "fg": "#1a1a1a",
        "fg_dim": "#666",
        "accent": "#2563eb",
        "border": "#ddd",
        "btn_bg": "#f0f0f0",
        "btn_hover": "#e5e5e5",
        "online": "#22c55e",
        "offline": "#bbb",
        "stop_bg": "#fef2f2",
        "stop_fg": "#dc2626",
        "start_bg": "#f0fdf4",
        "start_fg": "#16a34a",
        "separator": "#e5e5e5",
        "toggle_track": "#ccc",
        "toggle_knob": "#1a1a1a",
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# TOGGLE SWITCH (Modern, smooth, larger)
# ═══════════════════════════════════════════════════════════════════════════════

class ToggleSwitch(tk.Canvas):
    """Modern animated toggle switch with smooth transitions."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 52,
        height: int = 26,
        on_toggle: Callable[[bool], None] = None,
        initial: bool = True,
        **kwargs
    ):
        super().__init__(parent, width=width, height=height, highlightthickness=0, **kwargs)
        self.w = width
        self.h = height
        self.on_toggle = on_toggle
        self.is_on = initial  # True = dark theme
        self._knob_x = 0.0
        self._target_x = 0.0
        self._animating = False
        self._visual_state = initial
        self._knob_padding = 2
        self._knob_size = self.h - self._knob_padding * 2

        # Canvas item IDs
        self._track_ids = []
        self._knob_id = None

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))

        self._update_target()
        self._knob_x = self._target_x
        self._create_items()

    def _update_target(self):
        """Calculate target knob position based on state."""
        pad = self._knob_padding
        if self.is_on:
            self._target_x = self.w - self._knob_size - pad
        else:
            self._target_x = pad

    def _create_items(self):
        """Create canvas items once."""
        theme = THEMES["dark" if self._visual_state else "light"]
        pad = self._knob_padding
        ks = self._knob_size
        r = self.h // 2

        # Track (3 parts for pill shape)
        self._track_ids = [
            self.create_oval(0, 0, self.h, self.h, fill=theme["toggle_track"], outline=""),
            self.create_oval(self.w - self.h, 0, self.w, self.h, fill=theme["toggle_track"], outline=""),
            self.create_rectangle(r, 0, self.w - r, self.h, fill=theme["toggle_track"], outline=""),
        ]

        # Knob
        self._knob_id = self.create_oval(
            self._knob_x, pad,
            self._knob_x + ks, pad + ks,
            fill=theme["toggle_knob"], outline=""
        )

    def _update_knob_position(self):
        """Move knob without recreating."""
        pad = self._knob_padding
        ks = self._knob_size
        self.coords(self._knob_id, self._knob_x, pad, self._knob_x + ks, pad + ks)

    def _update_colors(self):
        """Update colors without recreating items."""
        theme = THEMES["dark" if self._visual_state else "light"]
        for tid in self._track_ids:
            self.itemconfig(tid, fill=theme["toggle_track"])
        self.itemconfig(self._knob_id, fill=theme["toggle_knob"])

    def _on_click(self, event=None):
        if self._animating:
            return
        self.is_on = not self.is_on
        self._update_target()
        self._animate()

    def _animate(self, step: int = 0):
        total_steps = 10

        # Fire callback at step 0 (before animation visually starts)
        # This applies theme immediately, then knob animates over already-changed UI
        if step == 0 and self.on_toggle:
            self.on_toggle(self.is_on)

        if step >= total_steps:
            self._animating = False
            self._knob_x = self._target_x
            self._visual_state = self.is_on
            self._update_knob_position()
            self._update_colors()
            return

        self._animating = True
        progress = step / total_steps
        ease = 1 - (1 - progress) ** 3

        pad = self._knob_padding
        ks = self._knob_size
        start_x = (self.w - ks - pad) if not self.is_on else pad
        end_x = self._target_x
        self._knob_x = start_x + (end_x - start_x) * ease

        # Switch toggle colors at 50%
        if step == total_steps // 2:
            self._visual_state = self.is_on
            self._update_colors()

        self._update_knob_position()
        self.after(12, lambda: self._animate(step + 1))

    def set_bg(self, color: str):
        self.configure(bg=color)


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMATED BUTTON (Simple Label - no Canvas flickering)
# ═══════════════════════════════════════════════════════════════════════════════

class AnimatedButton(tk.Label):
    """Simple button with hover effects - no Canvas to avoid flickering."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable,
        theme: Dict,
        style: str = "default",
        font_size: int = 9,
        padx: int = 10,
        pady: int = 3,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.text_str = text
        self.command = command
        self.theme = theme
        self.style = style

        self._setup_colors()

        self.configure(
            text=text,
            font=("Segoe UI", font_size),
            bg=self.default_bg,
            fg=self.fg,
            padx=padx,
            pady=pady,
            cursor="hand2"
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _setup_colors(self):
        t = self.theme
        if self.style == "stop":
            self.default_bg = t["stop_bg"]
            self.hover_bg = t["stop_fg"]
            self.fg = t["stop_fg"]
            self.hover_fg = "white"
        elif self.style == "start":
            self.default_bg = t["start_bg"]
            self.hover_bg = t["start_fg"]
            self.fg = t["start_fg"]
            self.hover_fg = "white"
        elif self.style == "primary":
            self.default_bg = t["accent"]
            self.hover_bg = t["accent"]
            self.fg = "white"
            self.hover_fg = "white"
        else:
            self.default_bg = t["btn_bg"]
            self.hover_bg = t["btn_hover"]
            self.fg = t["fg"]
            self.hover_fg = t["fg"]

    def _on_enter(self, event=None):
        self.configure(bg=self.hover_bg, fg=self.hover_fg)

    def _on_leave(self, event=None):
        self.configure(bg=self.default_bg, fg=self.fg)

    def _on_click(self, event=None):
        if self.command:
            self.command()

    def update_theme(self, theme: Dict):
        self.theme = theme
        self._setup_colors()
        self.configure(bg=self.default_bg, fg=self.fg)

    def set_bg(self, color: str):
        """Set background to match parent."""
        pass  # Label bg is set directly


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION BUTTON (for settings panel - simple Label)
# ═══════════════════════════════════════════════════════════════════════════════

class ActionButton(tk.Label):
    """Simple action button - no Canvas to avoid flickering."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable,
        theme: Dict,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.text_str = text
        self.command = command
        self.theme = theme

        self.configure(
            text=text,
            font=("Segoe UI Emoji", 9),  # Better emoji alignment
            bg=theme["btn_bg"],
            fg=theme["fg"],
            anchor="w",
            padx=10,
            pady=4,
            cursor="hand2"
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, event=None):
        self.configure(bg=self.theme["btn_hover"])

    def _on_leave(self, event=None):
        self.configure(bg=self.theme["btn_bg"])

    def _on_click(self, event=None):
        if self.command:
            self.command()

    def update_theme(self, theme: Dict):
        self.theme = theme
        self.configure(bg=theme["btn_bg"], fg=theme["fg"])


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS DOT (with pulse animation)
# ═══════════════════════════════════════════════════════════════════════════════

class StatusDot(tk.Canvas):
    """Animated pulsing status indicator."""

    def __init__(self, parent: tk.Widget, online: bool = False, theme: Dict = None, size: int = 8, **kwargs):
        super().__init__(parent, width=size + 4, height=size + 4, highlightthickness=0, **kwargs)
        self.theme = theme or THEMES["dark"]
        self.size = size
        self.online = online
        self._pulse_alpha = 0
        self._pulse_dir = 1

        self.dot = self.create_oval(2, 2, size + 2, size + 2, fill=self._color(), outline="")
        if online:
            self._pulse()

    def _color(self) -> str:
        return self.theme["online"] if self.online else self.theme["offline"]

    def _pulse(self):
        if not self.online:
            return
        self._pulse_alpha += self._pulse_dir * 15
        if self._pulse_alpha >= 60:
            self._pulse_dir = -1
        elif self._pulse_alpha <= 0:
            self._pulse_dir = 1
        self.itemconfig(self.dot, fill=self._color())
        self.after(100, self._pulse)

    def update_theme(self, theme: Dict):
        self.theme = theme
        self.itemconfig(self.dot, fill=self._color())


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT SETTINGS PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class AgentSettingsPanel(tk.Frame):
    """Slide-in settings panel for agent configuration."""

    def __init__(self, parent: tk.Widget, theme: Dict, on_close: Callable, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.on_close = on_close
        self.agent_data: Optional[Dict] = None
        self.callbacks: Dict[str, Callable] = {}
        self.action_buttons: List[tk.Widget] = []

        self.configure(bg=theme["card_bg"], width=200)
        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # Header
        self.header = tk.Frame(self, bg=t["card_bg"])
        self.header.pack(fill=tk.X, padx=12, pady=(10, 6))

        self.title_lbl = tk.Label(
            self.header, text="Settings",
            font=("Segoe UI Semibold", 11),
            bg=t["card_bg"], fg=t["fg"]
        )
        self.title_lbl.pack(side=tk.LEFT)

        self.close_btn = tk.Label(
            self.header, text="✕", font=("Segoe UI", 12),
            bg=t["card_bg"], fg=t["fg_dim"], cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT)
        self.close_btn.bind("<Button-1>", lambda e: self.on_close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg=self.theme["fg"]))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg=self.theme["fg_dim"]))

        # Separator
        self.sep = tk.Frame(self, bg=t["separator"], height=1)
        self.sep.pack(fill=tk.X, padx=12, pady=(0, 10))

        # Content
        self.content = tk.Frame(self, bg=t["card_bg"])
        self.content.pack(fill=tk.BOTH, expand=True, padx=12)

        # Info
        self.info_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.info_frame.pack(fill=tk.X, pady=(0, 10))

        self.agent_id_lbl = tk.Label(
            self.info_frame, text="", font=("Consolas", 8),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        self.agent_id_lbl.pack(anchor="w")

        self.purpose_lbl = tk.Label(
            self.info_frame, text="", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg"]
        )
        self.purpose_lbl.pack(anchor="w", pady=(2, 0))

        self.status_lbl = tk.Label(
            self.info_frame, text="", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        self.status_lbl.pack(anchor="w", pady=(2, 0))

        # Actions label
        self.actions_label = tk.Label(
            self.content, text="ACTIONS", font=("Segoe UI", 7),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        self.actions_label.pack(anchor="w", pady=(6, 4))

        self.actions_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.actions_frame.pack(fill=tk.X)

    def show(self, agent_data: Dict, callbacks: Dict[str, Callable]):
        self.agent_data = agent_data
        self.callbacks = callbacks
        t = self.theme

        self.title_lbl.configure(text=f"{agent_data['id'][:10]}")
        self.agent_id_lbl.configure(text=agent_data['id'])
        # Show display_name with fallback to purpose + pencil (editable on click)
        name = agent_data.get("display_name") or agent_data["purpose"]
        self.purpose_lbl.configure(text=f"{name} ✎", cursor="hand2")
        self.purpose_lbl.bind("<Button-1>", self._on_name_click)
        # Hover: subtle highlight
        self.purpose_lbl.bind("<Enter>", lambda e: self.purpose_lbl.configure(fg=self.theme["accent"]))
        self.purpose_lbl.bind("<Leave>", lambda e: self.purpose_lbl.configure(fg=self.theme["fg"]))

        status = agent_data["status"]
        status_color = t["online"] if status == "online" else t["offline"]
        self.status_lbl.configure(text=f"● {status}", fg=status_color)

        # Clear old buttons
        for btn in self.action_buttons:
            btn.destroy()
        self.action_buttons.clear()

        # Create action buttons with emoji
        actions = [
            ("⚙️  Configure Claude", "configure"),
            ("🧠  Memory Viewer", "memory"),
            ("🔄  Restart Memory", "restart_memory"),
            ("🔒  Proxy Settings", "proxy"),
            ("📋  View Logs", "logs"),
            ("🗑  Delete", "delete"),
        ]

        for text, key in actions:
            btn = ActionButton(
                self.actions_frame,
                text=text,
                command=lambda k=key: self._on_action(k),
                theme=t
            )
            btn.pack(fill=tk.X, pady=1)
            self.action_buttons.append(btn)

    def _on_action(self, action: str):
        if action in self.callbacks and self.agent_data:
            self.callbacks[action](self.agent_data)

    def _on_name_click(self, event=None):
        """Inline edit: replace label with entry field."""
        if not self.agent_data or getattr(self, '_editing_name', False):
            return

        self._editing_name = True
        t = self.theme

        # Get current display text
        current_name = self.agent_data.get("display_name") or self.agent_data["purpose"]

        # Hide label
        self.purpose_lbl.pack_forget()

        # Create inline entry (same position as label)
        self._name_entry = tk.Entry(
            self.info_frame,
            font=("Segoe UI", 9),
            bg=t["btn_bg"],
            fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=t["accent"],
            highlightcolor=t["accent"]
        )
        self._name_entry.insert(0, current_name)
        self._name_entry.pack(anchor="w", fill=tk.X, pady=(2, 0), ipady=2)
        self._name_entry.focus_set()
        self._name_entry.select_range(0, tk.END)

        def save_name(event=None):
            if not getattr(self, '_editing_name', False):
                return
            new_name = self._name_entry.get().strip()
            # If same as purpose, treat as empty (use purpose as display)
            if new_name == self.agent_data["purpose"]:
                new_name = None
            else:
                new_name = new_name or None

            try:
                manager.update_display_name(self.agent_data["id"], new_name)
                self.agent_data["display_name"] = new_name
            except Exception as e:
                print(f"Error updating name: {e}")

            self._finish_editing()
            # Refresh to update card list
            if "refresh" in self.callbacks:
                self.callbacks["refresh"](None)

        def cancel_edit(event=None):
            self._finish_editing()

        self._name_entry.bind("<Return>", save_name)
        self._name_entry.bind("<Escape>", cancel_edit)

        # Global click handler to save when clicking outside
        def on_global_click(event):
            if not getattr(self, '_editing_name', False):
                return
            try:
                if event.widget != self._name_entry:
                    save_name()
            except:
                pass

        self._global_click_id = self.winfo_toplevel().bind("<Button-1>", on_global_click, "+")

    def _finish_editing(self):
        """Restore label after inline edit."""
        if not getattr(self, '_editing_name', False):
            return

        self._editing_name = False  # Set first to prevent re-entry

        # Unbind global click handler
        if hasattr(self, '_global_click_id') and self._global_click_id:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._global_click_id)
            except:
                pass
            self._global_click_id = None

        if hasattr(self, '_name_entry') and self._name_entry:
            try:
                self._name_entry.destroy()
            except:
                pass
            self._name_entry = None

        # Show label again with updated text + pencil
        name = self.agent_data.get("display_name") or self.agent_data["purpose"]
        self.purpose_lbl.configure(text=f"{name} ✎", font=("Segoe UI", 9))
        self.purpose_lbl.pack(anchor="w", pady=(2, 0))

    def update_theme(self, theme: Dict):
        self.theme = theme
        t = theme
        self.configure(bg=t["card_bg"])
        self.header.configure(bg=t["card_bg"])
        self.title_lbl.configure(bg=t["card_bg"], fg=t["fg"])
        self.close_btn.configure(bg=t["card_bg"], fg=t["fg_dim"])
        # Rebind hover with new theme colors
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg=self.theme["fg"]))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg=self.theme["fg_dim"]))
        self.sep.configure(bg=t["separator"])
        self.content.configure(bg=t["card_bg"])
        self.info_frame.configure(bg=t["card_bg"])
        self.agent_id_lbl.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.purpose_lbl.configure(bg=t["card_bg"], fg=t["fg"])
        self.status_lbl.configure(bg=t["card_bg"])
        self.actions_label.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.actions_frame.configure(bg=t["card_bg"])

        # Update action buttons
        for btn in self.action_buttons:
            btn.update_theme(t)


# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL PANEL (Embedded CLI)
# ═══════════════════════════════════════════════════════════════════════════════

class TerminalPanel(tk.Frame):
    """Embedded terminal panel for running Claude CLI within the dashboard."""

    def __init__(self, parent: tk.Widget, theme: Dict, on_close: Callable, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.on_close = on_close
        self.agent_data: Optional[Dict] = None
        self.terminal: Optional[Any] = None  # TerminalWidget instance

        self.configure(bg=theme["card_bg"])
        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # Header
        self.header = tk.Frame(self, bg=t["card_bg"])
        self.header.pack(fill=tk.X, padx=8, pady=(6, 4))

        self.title_lbl = tk.Label(
            self.header, text="Terminal",
            font=("Segoe UI Semibold", 10),
            bg=t["card_bg"], fg=t["fg"]
        )
        self.title_lbl.pack(side=tk.LEFT)

        self.status_lbl = tk.Label(
            self.header, text="",
            font=("Segoe UI", 8),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        self.status_lbl.pack(side=tk.LEFT, padx=(8, 0))

        self.close_btn = tk.Label(
            self.header, text="✕", font=("Segoe UI", 11),
            bg=t["card_bg"], fg=t["fg_dim"], cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT)
        self.close_btn.bind("<Button-1>", lambda e: self._close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg=self.theme["fg"]))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg=self.theme["fg_dim"]))

        # Separator
        self.sep = tk.Frame(self, bg=t["separator"], height=1)
        self.sep.pack(fill=tk.X, padx=8, pady=(0, 4))

        # Terminal container
        self.terminal_frame = tk.Frame(self, bg=t["bg"])
        self.terminal_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # Placeholder if terminal not available
        if not HAS_TERMINAL:
            placeholder = tk.Label(
                self.terminal_frame,
                text="Terminal not available.\nInstall pywinpty: pip install pywinpty",
                font=("Consolas", 9),
                bg=t["bg"], fg=t["fg_dim"],
                justify="center"
            )
            placeholder.pack(expand=True)

    def show(self, agent_data: Dict):
        """Show terminal for the given agent."""
        self.agent_data = agent_data

        if not HAS_TERMINAL:
            self.status_lbl.configure(text="(unavailable)", fg="#f87171")
            return

        # Build terminal theme from dashboard theme
        term_theme = {
            "bg": self.theme["bg"],
            "fg": self.theme["fg"],
            "cursor": self.theme["accent"],
            "selection": self.theme.get("selection", "#264f78"),
        }

        # Create terminal widget if not exists
        if self.terminal is None:
            self.terminal = TerminalWidget(
                self.terminal_frame,
                theme=term_theme,
                font_family="Consolas",
                font_size=10,
                scrollback=10000,
                on_exit=self._on_terminal_exit
            )
            self.terminal.pack(fill=tk.BOTH, expand=True)

        # Start Claude CLI in agent's project directory
        self._start_terminal()

    def _start_terminal(self):
        """Start the terminal with Claude CLI."""
        if not self.terminal or not self.agent_data:
            return

        # Get Claude executable
        claude_cmd = which("claude") if which else None
        if not claude_cmd:
            self.status_lbl.configure(text="(claude not found)", fg="#f87171")
            return

        project_path = self.agent_data.get("project_path", ".")
        port = self.agent_data.get("port", 3100)
        agent_id = self.agent_data.get("id", "unknown")

        # Environment with memory worker port
        import os
        env = {**os.environ, "CLAUDE_MEM_WORKER_PORT": str(port)}

        # Start terminal
        self.terminal.start(
            cmd=["claude"],
            cwd=project_path,
            env=env
        )

        name = self.agent_data.get("display_name") or self.agent_data.get("purpose", agent_id)
        self.title_lbl.configure(text=f"Terminal: {name[:20]}")
        self.status_lbl.configure(text="running", fg=self.theme["online"])

    def _on_terminal_exit(self, exit_code: int):
        """Handle terminal process exit."""
        self.status_lbl.configure(
            text=f"exited ({exit_code})",
            fg=self.theme["fg_dim"]
        )

    def _close(self):
        """Close terminal and hide panel."""
        if self.terminal:
            self.terminal.stop()
        self.on_close()

    def stop(self):
        """Stop terminal without closing panel."""
        if self.terminal:
            self.terminal.stop()
            self.status_lbl.configure(text="stopped", fg=self.theme["fg_dim"])

    def update_theme(self, theme: Dict):
        """Update panel theme."""
        self.theme = theme
        t = theme

        self.configure(bg=t["card_bg"])
        self.header.configure(bg=t["card_bg"])
        self.title_lbl.configure(bg=t["card_bg"], fg=t["fg"])
        self.status_lbl.configure(bg=t["card_bg"])
        self.close_btn.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.sep.configure(bg=t["separator"])
        self.terminal_frame.configure(bg=t["bg"])

        # Update terminal theme if available
        if self.terminal and hasattr(self.terminal, 'update_theme'):
            term_theme = {
                "bg": t["bg"],
                "fg": t["fg"],
                "cursor": t["accent"],
                "selection": t.get("selection", "#264f78"),
            }
            self.terminal.update_theme(term_theme)


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM MODE PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class TeamModePanel(tk.Toplevel):
    """Team Mode panel for multi-agent orchestration."""

    def __init__(self, parent: tk.Widget, theme: Dict, dashboard: 'AgentDashboard'):
        super().__init__(parent)
        self.theme = theme
        self.dashboard = dashboard
        self._running = False

        self.title("Team Mode")
        self.configure(bg=theme["card_bg"])
        self.geometry("700x550")
        self.minsize(500, 400)
        self.resizable(True, True)

        # Don't use transient - allows independent window behavior
        self.after(50, lambda: set_title_bar_color(self, theme == THEMES["dark"]))

        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # Header
        header = tk.Frame(self, bg=t["card_bg"])
        header.pack(fill=tk.X, padx=12, pady=(10, 8))

        title = tk.Label(
            header, text="Team Mode",
            font=("Segoe UI Semibold", 14),
            bg=t["card_bg"], fg=t["fg"]
        )
        title.pack(side=tk.LEFT)

        subtitle = tk.Label(
            header, text="AutoGen + CrewAI + SWE-agent + Aider + MetaGPT",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        subtitle.pack(side=tk.LEFT, padx=(10, 0))

        # Usage bar (API limits) - right side
        self.usage_bar = UsageBar(
            header,
            theme=t,
            refresh_interval=30000
        )
        self.usage_bar.pack(side=tk.RIGHT)

        # Separator
        sep = tk.Frame(self, bg=t["separator"], height=1)
        sep.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Main content
        content = tk.Frame(self, bg=t["card_bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        # Left: Task input + buttons
        left = tk.Frame(content, bg=t["card_bg"], width=350)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Task description
        tk.Label(
            left, text="Task Description",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 4))

        self.task_text = tk.Text(
            left, font=("Consolas", 10),
            bg=t["btn_bg"], fg=t["fg"],
            relief="flat", height=5,
            wrap="word", padx=8, pady=8
        )
        self.task_text.pack(fill=tk.X, pady=(0, 8))
        self.task_text.insert("1.0", "Add user authentication with JWT tokens")

        # Project path
        tk.Label(
            left, text="Project Path",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 4))

        path_frame = tk.Frame(left, bg=t["btn_bg"])
        path_frame.pack(fill=tk.X, pady=(0, 8))

        self.path_entry = tk.Entry(
            path_frame, font=("Consolas", 10),
            bg=t["btn_bg"], fg=t["fg"],
            relief="flat"
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        self.path_entry.insert(0, ".")

        browse_btn = tk.Label(
            path_frame, text="...",
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg_dim"],
            cursor="hand2", padx=8
        )
        browse_btn.pack(side=tk.RIGHT, pady=6)
        browse_btn.bind("<Button-1>", lambda e: self._browse_folder())

        # Buttons
        btn_frame = tk.Frame(left, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self.run_btn = tk.Label(
            btn_frame, text="Run Team",
            font=("Segoe UI Semibold", 10),
            bg=t["accent"], fg="#fff",
            cursor="hand2", padx=16, pady=8
        )
        self.run_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.run_btn.bind("<Button-1>", lambda e: self._run_team())

        self.plan_btn = tk.Label(
            btn_frame, text="Create Plan",
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            cursor="hand2", padx=16, pady=8
        )
        self.plan_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.plan_btn.bind("<Button-1>", lambda e: self._create_plan())

        quality_btn = tk.Label(
            btn_frame, text="Quality Check",
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            cursor="hand2", padx=16, pady=8
        )
        quality_btn.pack(side=tk.LEFT)
        quality_btn.bind("<Button-1>", lambda e: self._run_quality())

        # Output area
        tk.Label(
            left, text="Output",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(8, 4))

        # Output with scrollbar
        output_frame = tk.Frame(left, bg=t["bg"])
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = tk.Text(
            output_frame, font=("Consolas", 9),
            bg=t["bg"], fg=t["fg"],
            relief="flat", height=12,
            wrap="word", padx=8, pady=8,
            cursor="arrow"
        )
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(output_frame, command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

        # Make read-only but allow copy
        def make_readonly(event):
            if event.state & 4 and event.keysym.lower() in ('c', 'a'):  # Ctrl+C, Ctrl+A
                return
            if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior', 'Next'):
                return
            return "break"
        self.output_text.bind("<Key>", make_readonly)

        # Right: Roles info
        right = tk.Frame(content, bg=t["btn_bg"], width=250)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)

        tk.Label(
            right, text="Agent Roles",
            font=("Segoe UI Semibold", 11),
            bg=t["btn_bg"], fg=t["fg"]
        ).pack(fill=tk.X, padx=12, pady=(12, 8))

        roles_data = [
            ("Architect", "Design architecture, APIs", "-"),
            ("Backend", "Server-side logic", "Architect"),
            ("Frontend", "UI components", "Architect, Backend"),
            ("QA", "Tests, quality", "Backend, Frontend"),
            ("Reviewer", "Code review", "QA"),
            ("Refactoring", "Code improvement", "Reviewer"),
        ]

        for role, desc, deps in roles_data:
            role_frame = tk.Frame(right, bg=t["btn_bg"])
            role_frame.pack(fill=tk.X, padx=12, pady=4)

            tk.Label(
                role_frame, text=role,
                font=("Segoe UI Semibold", 9),
                bg=t["btn_bg"], fg=t["accent"]
            ).pack(anchor="w")

            tk.Label(
                role_frame, text=desc,
                font=("Segoe UI", 8),
                bg=t["btn_bg"], fg=t["fg"]
            ).pack(anchor="w")

            tk.Label(
                role_frame, text=f"Waits: {deps}",
                font=("Segoe UI", 8),
                bg=t["btn_bg"], fg=t["fg_dim"]
            ).pack(anchor="w")

    def _browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def _log(self, msg: str):
        self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)

    def _run_team(self):
        if self._running:
            return

        task = self.task_text.get("1.0", tk.END).strip()
        project = self.path_entry.get().strip()

        if not task:
            self._log("[ERROR] Task description is empty")
            return

        self._running = True
        self.run_btn.configure(bg=self.theme["fg_dim"])
        self._log(f"[TEAM] Starting: {task[:50]}...")
        self._log(f"[TEAM] Project: {project}")

        # Run in thread
        import threading
        def run():
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-m", "claude_agent_manager.cli", "team", "run", task, "--project", project],
                    capture_output=True, text=True, timeout=300
                )
                self.after(0, lambda: self._log(result.stdout or result.stderr or "[DONE]"))
            except Exception as e:
                self.after(0, lambda: self._log(f"[ERROR] {e}"))
            finally:
                self._running = False
                self.after(0, lambda: self.run_btn.configure(bg=self.theme["accent"]))

        threading.Thread(target=run, daemon=True).start()

    def _create_plan(self):
        task = self.task_text.get("1.0", tk.END).strip()
        project = self.path_entry.get().strip()

        if not task:
            self._log("[ERROR] Task description is empty")
            return

        self._log(f"[PLAN] Creating plan for: {task[:50]}...")

        import threading
        def run():
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-m", "claude_agent_manager.cli", "team", "plan", task, "--project", project],
                    capture_output=True, text=True, timeout=60
                )
                self.after(0, lambda: self._log(result.stdout or result.stderr or "[DONE]"))
            except Exception as e:
                self.after(0, lambda: self._log(f"[ERROR] {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _run_quality(self):
        project = self.path_entry.get().strip()
        self._log(f"[QUALITY] Checking: {project}")

        import threading
        def run():
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-m", "claude_agent_manager.cli", "team", "quality", "--project", project],
                    capture_output=True, text=True, timeout=120
                )
                self.after(0, lambda: self._log(result.stdout or result.stderr or "[DONE]"))
            except Exception as e:
                self.after(0, lambda: self._log(f"[ERROR] {e}"))

        threading.Thread(target=run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY PANEL (Graph Memory Viewer)
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPanel(tk.Toplevel):
    """Memory viewer panel showing graph memory stats and shared knowledge."""

    def __init__(self, parent: tk.Widget, theme: Dict, dashboard: 'AgentDashboard'):
        super().__init__(parent)
        self.theme = theme
        self.dashboard = dashboard
        self.graph_memory = None

        self.title("Memory Viewer")
        self.configure(bg=theme["card_bg"])
        self.geometry("600x500")
        self.minsize(500, 400)

        # Make it transient to parent
        self.transient(parent)

        # Set title bar color
        self.after(50, lambda: set_title_bar_color(self, theme == THEMES["dark"]))

        self._build_ui()
        self._load_memory_data()

    def _build_ui(self):
        t = self.theme

        # Header
        header = tk.Frame(self, bg=t["card_bg"])
        header.pack(fill=tk.X, padx=12, pady=(10, 8))

        title = tk.Label(
            header, text="Graph Memory",
            font=("Segoe UI Semibold", 14),
            bg=t["card_bg"], fg=t["fg"]
        )
        title.pack(side=tk.LEFT)

        # Refresh button
        refresh_btn = tk.Label(
            header, text="⟳",
            font=("Segoe UI", 12),
            bg=t["card_bg"], fg=t["fg_dim"],
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.RIGHT)
        refresh_btn.bind("<Button-1>", lambda e: self._load_memory_data())
        refresh_btn.bind("<Enter>", lambda e: refresh_btn.configure(fg=t["accent"]))
        refresh_btn.bind("<Leave>", lambda e: refresh_btn.configure(fg=t["fg_dim"]))

        # Separator
        sep = tk.Frame(self, bg=t["separator"], height=1)
        sep.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Notebook for tabs
        self.notebook = tk.Frame(self, bg=t["card_bg"])
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        # Tab buttons
        tab_frame = tk.Frame(self.notebook, bg=t["card_bg"])
        tab_frame.pack(fill=tk.X, pady=(0, 8))

        self.tabs = {}
        self.current_tab = "stats"

        for tab_name, tab_label in [("stats", "Stats"), ("shared", "Shared"), ("search", "Search"), ("graph", "Graph")]:
            btn = tk.Label(
                tab_frame, text=tab_label,
                font=("Segoe UI", 10),
                bg=t["card_bg"],
                fg=t["accent"] if tab_name == self.current_tab else t["fg_dim"],
                cursor="hand2",
                padx=10, pady=4
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            btn.bind("<Button-1>", lambda e, n=tab_name: self._switch_tab(n))
            self.tabs[tab_name] = btn

        # Content area
        self.content = tk.Frame(self.notebook, bg=t["card_bg"])
        self.content.pack(fill=tk.BOTH, expand=True)

        # Create tab content frames
        self.stats_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.shared_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.search_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.graph_frame = tk.Frame(self.content, bg=t["card_bg"])

        self._build_stats_tab()
        self._build_shared_tab()
        self._build_search_tab()
        self._build_graph_tab()

        # Show initial tab
        self.stats_frame.pack(fill=tk.BOTH, expand=True)

    def _switch_tab(self, tab_name: str):
        """Switch to a different tab."""
        t = self.theme
        self.current_tab = tab_name

        # Update tab button colors
        for name, btn in self.tabs.items():
            btn.configure(fg=t["accent"] if name == tab_name else t["fg_dim"])

        # Hide all frames
        self.stats_frame.pack_forget()
        self.shared_frame.pack_forget()
        self.search_frame.pack_forget()
        self.graph_frame.pack_forget()

        # Show selected frame
        if tab_name == "stats":
            self.stats_frame.pack(fill=tk.BOTH, expand=True)
        elif tab_name == "shared":
            self.shared_frame.pack(fill=tk.BOTH, expand=True)
        elif tab_name == "search":
            self.search_frame.pack(fill=tk.BOTH, expand=True)
        elif tab_name == "graph":
            self.graph_frame.pack(fill=tk.BOTH, expand=True)
            self._render_graph()

    def _build_stats_tab(self):
        """Build the stats tab content."""
        t = self.theme

        # Stats display
        self.stats_text = tk.Text(
            self.stats_frame,
            font=("Consolas", 10),
            bg=t["card_bg"], fg=t["fg"],
            relief="flat",
            state="disabled",
            wrap="word",
            padx=8, pady=8
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True)

    def _build_shared_tab(self):
        """Build the shared knowledge tab."""
        t = self.theme

        # Scrollable list
        canvas = tk.Canvas(self.shared_frame, bg=t["card_bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.shared_frame, orient="vertical", command=canvas.yview)
        self.shared_list = tk.Frame(canvas, bg=t["card_bg"])

        self.shared_list.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.shared_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _build_search_tab(self):
        """Build the search tab."""
        t = self.theme

        # Search input
        search_frame = tk.Frame(self.search_frame, bg=t["card_bg"])
        search_frame.pack(fill=tk.X, pady=(0, 8))

        self.search_entry = tk.Entry(
            search_frame,
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat"
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self.search_entry.bind("<Return>", lambda e: self._do_search())

        search_btn = tk.Label(
            search_frame, text="Search",
            font=("Segoe UI", 10),
            bg=t["accent"], fg="#ffffff",
            cursor="hand2",
            padx=12, pady=6
        )
        search_btn.pack(side=tk.RIGHT, padx=(8, 0))
        search_btn.bind("<Button-1>", lambda e: self._do_search())

        # Results area
        self.search_results = tk.Text(
            self.search_frame,
            font=("Consolas", 10),
            bg=t["card_bg"], fg=t["fg"],
            relief="flat",
            wrap="word",
            padx=8, pady=8
        )
        self.search_results.pack(fill=tk.BOTH, expand=True)
        # Add placeholder
        self.search_results.insert("1.0", "Enter search term and press Enter or click Search...")
        self.search_results.configure(state="disabled")

    def _build_graph_tab(self):
        """Build the graph visualization tab."""
        import math
        import random

        t = self.theme

        # Controls frame
        controls = tk.Frame(self.graph_frame, bg=t["card_bg"])
        controls.pack(fill=tk.X, pady=(0, 8))

        # Filter by type
        tk.Label(controls, text="Filter:", font=("Segoe UI", 9),
                 bg=t["card_bg"], fg=t["fg_dim"]).pack(side=tk.LEFT)

        self.graph_filter = tk.StringVar(value="all")
        for ftype in ["all", "decision", "error", "pattern", "task", "fact"]:
            rb = tk.Radiobutton(
                controls, text=ftype.capitalize(),
                variable=self.graph_filter, value=ftype,
                font=("Segoe UI", 8),
                bg=t["card_bg"], fg=t["fg"],
                selectcolor=t["card_bg"],
                activebackground=t["card_bg"],
                command=self._render_graph
            )
            rb.pack(side=tk.LEFT, padx=2)

        # Canvas for graph
        self.graph_canvas = tk.Canvas(
            self.graph_frame,
            bg="#0f172a",  # Slate-900 dark background
            highlightthickness=1,
            highlightbackground="#334155"
        )
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)

        # Graph state
        self.graph_nodes = []  # List of {id, x, y, vx, vy, node_data}
        self.graph_edges = []  # List of {source_idx, target_idx}
        self.graph_selected = None
        self.graph_dragging = None  # Node index being dragged
        self.graph_panning = False  # Panning empty space
        self.graph_pan_start = (0, 0)  # Mouse start pos for pan
        self.graph_simulation_running = False
        self.graph_zoom = 1.0  # Zoom level
        self.graph_pan_x = 0   # Pan offset X
        self.graph_pan_y = 0   # Pan offset Y

        # Bind mouse events
        self.graph_canvas.bind("<Button-1>", self._on_graph_click)
        self.graph_canvas.bind("<B1-Motion>", self._on_graph_drag)
        self.graph_canvas.bind("<ButtonRelease-1>", self._on_graph_release)
        self.graph_canvas.bind("<MouseWheel>", self._on_graph_zoom)  # Windows
        self.graph_canvas.bind("<Button-4>", self._on_graph_zoom)    # Linux scroll up
        self.graph_canvas.bind("<Button-5>", self._on_graph_zoom)    # Linux scroll down

        # Info panel at bottom
        self.graph_info = tk.Label(
            self.graph_frame,
            text="Click a node to see details",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"],
            anchor="w", padx=8
        )
        self.graph_info.pack(fill=tk.X, pady=(4, 0))

    def _render_graph(self):
        """Render the graph with force-directed layout."""
        import math
        import random

        if not self.graph_memory:
            return

        # Clear canvas
        self.graph_canvas.delete("all")

        # Get canvas size
        self.graph_canvas.update_idletasks()
        width = self.graph_canvas.winfo_width()
        height = self.graph_canvas.winfo_height()
        if width < 100 or height < 100:
            width, height = 500, 350

        # Get filter
        filter_type = self.graph_filter.get()

        # Load nodes from memory
        try:
            if filter_type == "all":
                nodes = self.graph_memory.query(limit=50, include_shared=True)
            else:
                from claude_agent_manager.memory import NodeType
                type_map = {
                    "decision": NodeType.DECISION,
                    "error": NodeType.ERROR,
                    "pattern": NodeType.PATTERN,
                    "task": NodeType.TASK,
                    "fact": NodeType.FACT,
                }
                nodes = self.graph_memory.query(
                    node_type=type_map.get(filter_type),
                    limit=50,
                    include_shared=True
                )
        except Exception as e:
            self.graph_info.configure(text=f"Error: {e}")
            return

        if not nodes:
            self.graph_canvas.create_text(
                width // 2, height // 2,
                text="No memory nodes found.\nUse agents to build knowledge graph.",
                font=("Segoe UI", 11),
                fill=self.theme["fg_dim"],
                justify="center"
            )
            return

        # Initialize node positions randomly
        self.graph_nodes = []
        node_id_to_idx = {}
        margin = 80  # Keep nodes away from edges
        for i, node in enumerate(nodes):
            self.graph_nodes.append({
                "id": node.id,
                "x": random.uniform(margin, width - margin),
                "y": random.uniform(margin, height - margin),
                "vx": 0,
                "vy": 0,
                "data": node
            })
            node_id_to_idx[node.id] = i

        # Get relations
        self.graph_edges = []
        for i, node in enumerate(nodes):
            try:
                related = self.graph_memory.get_related(node.id, direction="outgoing")
                for rel_node, rel in related:
                    if rel_node.id in node_id_to_idx:
                        self.graph_edges.append({
                            "source": i,
                            "target": node_id_to_idx[rel_node.id]
                        })
            except:
                pass

        # Run force simulation
        self._run_force_simulation(width, height, iterations=300)

        # Draw using unified redraw method
        self._redraw_graph()
        self.graph_info.configure(text=f"{len(nodes)} nodes, {len(self.graph_edges)} edges")

    def _run_force_simulation(self, width: int, height: int, iterations: int = 50):
        """Run force-directed layout simulation (D3.js style)."""
        import math
        import random

        if not self.graph_nodes:
            return

        n_nodes = len(self.graph_nodes)
        margin = 60

        # Initialize velocities if not present
        for node in self.graph_nodes:
            if "vx" not in node:
                node["vx"] = 0
                node["vy"] = 0

        # D3-style parameters
        alpha = 1.0  # "temperature" - decreases over time
        alpha_decay = 1 - pow(0.001, 1 / iterations)
        alpha_min = 0.001
        velocity_decay = 0.6  # friction

        # Force strengths
        charge_strength = -400  # repulsion (negative = repel)
        link_strength = 0.3
        link_distance = 100
        center_strength = 0.05
        collision_radius_mult = 1.5  # multiply node radius for collision

        for iteration in range(iterations):
            # Decay alpha (cooling)
            alpha = max(alpha_min, alpha * (1 - alpha_decay))

            # === CHARGE FORCE (repulsion between all nodes) ===
            for i, n1 in enumerate(self.graph_nodes):
                for j, n2 in enumerate(self.graph_nodes):
                    if i >= j:
                        continue
                    dx = n2["x"] - n1["x"]
                    dy = n2["y"] - n1["y"]
                    dist_sq = dx * dx + dy * dy
                    if dist_sq < 1:
                        dist_sq = 1
                    dist = math.sqrt(dist_sq)

                    # Coulomb's law: F = k * q1 * q2 / r^2
                    force = charge_strength * alpha / dist_sq
                    fx = force * dx / dist
                    fy = force * dy / dist

                    n1["vx"] -= fx
                    n1["vy"] -= fy
                    n2["vx"] += fx
                    n2["vy"] += fy

            # === LINK FORCE (attraction along edges) ===
            for edge in self.graph_edges:
                n1 = self.graph_nodes[edge["source"]]
                n2 = self.graph_nodes[edge["target"]]
                dx = n2["x"] - n1["x"]
                dy = n2["y"] - n1["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 1

                # Spring force: F = k * (x - x0)
                force = (dist - link_distance) * link_strength * alpha
                fx = force * dx / dist
                fy = force * dy / dist

                n1["vx"] += fx
                n1["vy"] += fy
                n2["vx"] -= fx
                n2["vy"] -= fy

            # === CENTER FORCE ===
            cx, cy = width / 2, height / 2
            for node in self.graph_nodes:
                node["vx"] += (cx - node["x"]) * center_strength * alpha
                node["vy"] += (cy - node["y"]) * center_strength * alpha

            # === COLLISION FORCE (prevent overlap) ===
            for i, n1 in enumerate(self.graph_nodes):
                r1 = (6 + n1["data"].importance * 6) * collision_radius_mult
                for j, n2 in enumerate(self.graph_nodes):
                    if i >= j:
                        continue
                    r2 = (6 + n2["data"].importance * 6) * collision_radius_mult
                    min_dist = r1 + r2

                    dx = n2["x"] - n1["x"]
                    dy = n2["y"] - n1["y"]
                    dist = math.sqrt(dx * dx + dy * dy) or 1

                    if dist < min_dist:
                        # Push apart
                        overlap = (min_dist - dist) / 2
                        ux, uy = dx / dist, dy / dist
                        n1["x"] -= ux * overlap
                        n1["y"] -= uy * overlap
                        n2["x"] += ux * overlap
                        n2["y"] += uy * overlap

            # === APPLY VELOCITY WITH DECAY ===
            for node in self.graph_nodes:
                node["vx"] *= velocity_decay
                node["vy"] *= velocity_decay
                node["x"] += node["vx"]
                node["y"] += node["vy"]

                # Bounds
                node["x"] = max(margin, min(width - margin, node["x"]))
                node["y"] = max(margin, min(height - margin - 30, node["y"]))

    def _on_graph_click(self, event):
        """Handle click on graph canvas."""
        width = self.graph_canvas.winfo_width()
        height = self.graph_canvas.winfo_height()
        cx, cy = width / 2, height / 2
        zoom = self.graph_zoom

        # Check if clicked on a node (in screen coordinates)
        for i, gnode in enumerate(self.graph_nodes):
            # Transform node position to screen
            sx = cx + (gnode["x"] - cx) * zoom + self.graph_pan_x
            sy = cy + (gnode["y"] - cy) * zoom + self.graph_pan_y
            radius = (6 + gnode["data"].importance * 6) * zoom

            dx = event.x - sx
            dy = event.y - sy
            if dx * dx + dy * dy < (radius + 5) ** 2:  # +5 for easier clicking
                self.graph_selected = i
                self.graph_dragging = i
                node = gnode["data"]
                info = f"[{node.node_type.value.upper()}] {node.content} (importance: {node.importance:.2f})"
                self.graph_info.configure(text=info[:100])
                self._redraw_graph()
                return

        # Clicked on empty space - start panning
        self.graph_selected = None
        self.graph_panning = True
        self.graph_pan_start = (event.x - self.graph_pan_x, event.y - self.graph_pan_y)
        self.graph_info.configure(text="Drag to pan, scroll to zoom")

    def _on_graph_drag(self, event):
        """Handle drag on graph canvas."""
        if self.graph_dragging is not None:
            # Dragging a node - convert screen coords back to graph coords
            width = self.graph_canvas.winfo_width()
            height = self.graph_canvas.winfo_height()
            cx, cy = width / 2, height / 2
            zoom = self.graph_zoom

            # Reverse transform: screen -> graph
            gx = cx + (event.x - self.graph_pan_x - cx) / zoom
            gy = cy + (event.y - self.graph_pan_y - cy) / zoom
            self.graph_nodes[self.graph_dragging]["x"] = gx
            self.graph_nodes[self.graph_dragging]["y"] = gy
            self._redraw_graph()
        elif self.graph_panning:
            # Panning the view
            self.graph_pan_x = event.x - self.graph_pan_start[0]
            self.graph_pan_y = event.y - self.graph_pan_start[1]
            self._redraw_graph()

    def _on_graph_release(self, event):
        """Handle mouse release on graph canvas."""
        self.graph_dragging = None
        self.graph_panning = False

    def _on_graph_zoom(self, event):
        """Handle mouse wheel zoom like Obsidian."""
        # Get zoom direction
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            factor = 1.15  # zoom in
        else:
            factor = 0.85  # zoom out

        # Limit zoom range
        new_zoom = self.graph_zoom * factor
        if 0.3 <= new_zoom <= 3.0:
            self.graph_zoom = new_zoom
            self._redraw_graph()

    def _redraw_graph(self):
        """Redraw graph without recalculating layout."""
        self.graph_canvas.delete("all")
        width = self.graph_canvas.winfo_width()
        height = self.graph_canvas.winfo_height()
        cx, cy = width / 2, height / 2  # center for zoom
        zoom = self.graph_zoom

        type_colors = {
            "decision": "#22c55e", "error": "#ef4444", "pattern": "#3b82f6",
            "task": "#f59e0b", "fact": "#a855f7", "file": "#64748b",
            "function": "#06b6d4", "class": "#ec4899",
        }

        # Helper to apply zoom and pan
        pan_x, pan_y = self.graph_pan_x, self.graph_pan_y
        def z(x, y):
            return cx + (x - cx) * zoom + pan_x, cy + (y - cy) * zoom + pan_y

        # Draw edges - Obsidian style: thin gray lines
        for edge in self.graph_edges:
            src = self.graph_nodes[edge["source"]]
            tgt = self.graph_nodes[edge["target"]]

            # Small node radii (smaller circles)
            src_radius = (6 + src["data"].importance * 6) * zoom
            tgt_radius = (6 + tgt["data"].importance * 6) * zoom

            # Apply zoom to positions
            sx, sy = z(src["x"], src["y"])
            tx, ty = z(tgt["x"], tgt["y"])

            # Direction vector
            dx, dy = tx - sx, ty - sy
            dist = (dx*dx + dy*dy) ** 0.5 + 0.1

            # Shorten line to node edges
            ux, uy = dx / dist, dy / dist
            x1 = sx + ux * (src_radius + 2)
            y1 = sy + uy * (src_radius + 2)
            x2 = tx - ux * (tgt_radius + 2)
            y2 = ty - uy * (tgt_radius + 2)

            # Skip if too short
            if ((x2-x1)**2 + (y2-y1)**2) ** 0.5 < 3:
                continue

            # Obsidian style: thin gray edge
            self.graph_canvas.create_line(x1, y1, x2, y2,
                fill="#475569", width=1)

        # Draw nodes - smaller circles with zoom
        if not hasattr(self, '_node_photo_refs'):
            self._node_photo_refs = []
        self._node_photo_refs.clear()

        for i, gnode in enumerate(self.graph_nodes):
            node = gnode["data"]
            color = type_colors.get(node.node_type.value, "#64748b")
            # Smaller base radius: 6-12px instead of 12-22px
            base_radius = 6 + node.importance * 6
            radius = int(base_radius * zoom)
            x, y = z(gnode["x"], gnode["y"])
            x, y = int(x), int(y)
            is_selected = (i == self.graph_selected)

            # Draw selection ring first (underneath)
            if is_selected:
                sel_r = radius + 4
                self.graph_canvas.create_oval(
                    x - sel_r, y - sel_r, x + sel_r, y + sel_r,
                    fill="", outline="#ffffff", width=2
                )

            # Draw node circle
            self.graph_canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=color, outline=""
            )

            # Label (only show if zoomed in enough)
            if zoom > 0.6:
                label = node.content[:15] + "..." if len(node.content) > 15 else node.content
                label_y = y + radius + 10
                font_size = max(7, int(8 * zoom))
                self.graph_canvas.create_text(
                    x, label_y, text=label,
                    font=("Segoe UI", font_size), fill="#94a3b8"
                )

        # Legend
        if height > 50:
            legend_y = height - 20
            legend_x = 10
            for ntype, lbl in [("decision", "Decision"), ("error", "Error"), ("pattern", "Pattern"), ("task", "Task"), ("fact", "Fact")]:
                color = type_colors.get(ntype, "#64748b")
                self.graph_canvas.create_oval(legend_x, legend_y - 4, legend_x + 8, legend_y + 4, fill=color, outline="")
                self.graph_canvas.create_text(legend_x + 14, legend_y, text=lbl, anchor="w", font=("Segoe UI", 7), fill="#94a3b8")
                legend_x += 65

    def _load_memory_data(self):
        """Load memory data from GraphMemory."""
        if not HAS_MEMORY:
            self._show_stats_error("Memory module not available")
            return

        try:
            # Get or create shared memory instance
            if self.graph_memory is None:
                # Use a shared memory instance
                self.graph_memory = GraphMemory(agent_id="shared")
                # Register for cleanup
                self.dashboard._open_graph_memories["_viewer"] = self.graph_memory

            self._update_stats()
            self._update_shared_list()
        except Exception as e:
            self._show_stats_error(f"Error loading memory: {e}")

    def _update_stats(self):
        """Update statistics display."""
        if not self.graph_memory:
            return

        try:
            stats = self.graph_memory.get_stats()

            text = f"""Database: {stats['db_path']}

=== Agent Memory ({stats['agent_id']}) ===
Total Nodes: {stats['total_nodes']}
Total Relations: {stats['total_relations']}

Nodes by Type:
"""
            for node_type, count in stats.get('nodes_by_type', {}).items():
                text += f"  • {node_type}: {count}\n"

            text += f"""
=== Shared Memory ===
Total Nodes: {stats['shared']['total_nodes']}
Total Relations: {stats['shared']['total_relations']}

Shared Nodes by Type:
"""
            for node_type, count in stats['shared'].get('nodes_by_type', {}).items():
                text += f"  • {node_type}: {count}\n"

            self.stats_text.configure(state="normal")
            self.stats_text.delete("1.0", tk.END)
            self.stats_text.insert("1.0", text)
            self.stats_text.configure(state="disabled")

        except Exception as e:
            self._show_stats_error(f"Error getting stats: {e}")

    def _update_shared_list(self):
        """Update shared knowledge list."""
        if not self.graph_memory:
            return

        # Clear existing items
        for widget in self.shared_list.winfo_children():
            widget.destroy()

        try:
            t = self.theme
            shared_nodes = self.graph_memory.query_shared_only(limit=50)

            if not shared_nodes:
                empty_lbl = tk.Label(
                    self.shared_list,
                    text="No shared knowledge yet.\nPromote nodes using 'cam memory-promote'",
                    font=("Segoe UI", 10),
                    bg=t["card_bg"], fg=t["fg_dim"],
                    justify="center"
                )
                empty_lbl.pack(expand=True, pady=20)
                return

            for node in shared_nodes:
                item = tk.Frame(self.shared_list, bg=t["card_bg"])
                item.pack(fill=tk.X, pady=2)

                # Type badge
                type_colors = {
                    "decision": "#22c55e",
                    "error": "#ef4444",
                    "pattern": "#3b82f6",
                    "task": "#f59e0b",
                    "fact": "#8b5cf6",
                    "file": "#6b7280",
                }
                type_color = type_colors.get(node.node_type.value, t["fg_dim"])

                type_lbl = tk.Label(
                    item, text=node.node_type.value[:3].upper(),
                    font=("Segoe UI", 8),
                    bg=type_color, fg="#ffffff",
                    padx=4, pady=1
                )
                type_lbl.pack(side=tk.LEFT, padx=(8, 8), pady=6)

                # Content
                content = node.content[:80] + "..." if len(node.content) > 80 else node.content
                content_lbl = tk.Label(
                    item, text=content,
                    font=("Segoe UI", 9),
                    bg=t["card_bg"], fg=t["fg"],
                    anchor="w"
                )
                content_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)

                # Importance
                imp_lbl = tk.Label(
                    item, text=f"{node.importance:.1f}",
                    font=("Segoe UI", 8),
                    bg=t["card_bg"], fg=t["fg_dim"],
                    padx=8
                )
                imp_lbl.pack(side=tk.RIGHT, pady=6)

        except Exception as e:
            error_lbl = tk.Label(
                self.shared_list,
                text=f"Error loading shared knowledge: {e}",
                font=("Segoe UI", 10),
                bg=self.theme["card_bg"], fg="#ef4444"
            )
            error_lbl.pack(expand=True, pady=20)

    def _do_search(self):
        """Perform search."""
        query = self.search_entry.get().strip()
        if not query or not self.graph_memory:
            return

        try:
            results = self.graph_memory.query(
                search_term=query,
                limit=50,
                include_shared=True
            )

            text = f"Search: '{query}'\nFound: {len(results)} results\n\n"

            for node in results:
                text += f"[{node.node_type.value.upper()}] (imp: {node.importance:.2f})\n"
                text += f"  {node.content}\n\n"

            self.search_results.configure(state="normal")
            self.search_results.delete("1.0", tk.END)
            self.search_results.insert("1.0", text)
            self.search_results.configure(state="disabled")

        except Exception as e:
            self.search_results.configure(state="normal")
            self.search_results.delete("1.0", tk.END)
            self.search_results.insert("1.0", f"Search error: {e}")
            self.search_results.configure(state="disabled")

    def _show_stats_error(self, message: str):
        """Show error in stats tab."""
        self.stats_text.configure(state="normal")
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", f"Error: {message}")
        self.stats_text.configure(state="disabled")

    def destroy(self):
        """Cleanup on close."""
        # Remove from tracked memories
        if "_viewer" in self.dashboard._open_graph_memories:
            try:
                self.dashboard._open_graph_memories["_viewer"].close()
            except:
                pass
            del self.dashboard._open_graph_memories["_viewer"]
        super().destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT CONFIGURATION DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class AgentConfigDialog:
    """Dialog for configuring Claude Code agent settings."""

    # Predefined MCP servers
    MCP_PRESETS = {
        "sequential-thinking": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/sequential-thinking-server"]
        },
        "filesystem": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/filesystem-server"]
        },
        "github": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@anthropic/github-server"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""}
        },
    }

    def __init__(self, root: tk.Tk, agent_data: Dict, theme: Dict, on_save: Callable):
        self.root = root
        self.agent_data = agent_data
        self.theme = theme
        self.on_save = on_save
        self.project_path = Path(agent_data["project_path"])

        # Get agent_dir from manager
        self.agent_dir = None
        if HAS_BACKEND and manager:
            try:
                agent_root = manager.get_agent_root()
                self.agent_dir = agent_root / agent_data["id"]
            except Exception:
                pass

        # Load current config
        self._load_current_config()
        self._create_dialog()

    def _load_current_config(self):
        """Load current configuration from agent directory (per-agent isolation)."""
        if ac and self.agent_dir and self.agent_dir.exists():
            # Read from agent_dir (per-agent config)
            config = ac.read_agent_local_config(self.agent_dir)
            self.current_prompt = config.get("claude_md") or ""
            self.current_mcp = config.get("mcp_json") or {}
            self.current_settings = {}
        elif ac:
            # Fallback to project_path
            config = ac.read_agent_config(self.project_path)
            self.current_prompt = config.get("claude_md") or ""
            self.current_mcp = config.get("mcp_json") or {}
            self.current_settings = config.get("claude_settings") or {}
        else:
            self.current_prompt = ""
            self.current_mcp = {}
            self.current_settings = {}

    def _create_dialog(self):
        t = self.theme
        self.dialog = tk.Toplevel(self.root)
        self.dialog.title(f"Configure: {self.agent_data['id'][:12]}")
        self.dialog.configure(bg=t["bg"])
        self.dialog.geometry("520x480")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.root)
        self.dialog.grab_set()

        # Center
        self.dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 520) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 480) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Set title bar color
        self.dialog.after(50, lambda: set_title_bar_color(self.dialog, t == THEMES["dark"]))

        # Main frame
        main = tk.Frame(self.dialog, bg=t["card_bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Tab buttons
        self.tab_frame = tk.Frame(main, bg=t["card_bg"])
        self.tab_frame.pack(fill=tk.X, padx=12, pady=(8, 0))

        self.tabs = ["System Prompt", "MCP Servers", "Settings", "Permissions"]
        self.tab_buttons = []
        self.current_tab = 0

        for i, tab_name in enumerate(self.tabs):
            btn = tk.Label(
                self.tab_frame, text=tab_name,
                font=("Segoe UI", 9),
                bg=t["accent"] if i == 0 else t["btn_bg"],
                fg="#fff" if i == 0 else t["fg"],
                padx=12, pady=6, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 2))
            btn.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            self.tab_buttons.append(btn)

        # Content area
        self.content = tk.Frame(main, bg=t["card_bg"])
        self.content.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # Build all tab contents
        self._build_prompt_tab()
        self._build_mcp_tab()
        self._build_settings_tab()
        self._build_permissions_tab()

        # Show first tab
        self._show_tab(0)

        # Buttons at bottom
        btn_frame = tk.Frame(main, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        save_btn = AnimatedButton(
            btn_frame, text="Save & Apply",
            command=self._on_save,
            theme=t, style="primary",
            font_size=9, padx=20, pady=6
        )
        save_btn.pack(side=tk.RIGHT)

        cancel_btn = AnimatedButton(
            btn_frame, text="Cancel",
            command=self.dialog.destroy,
            theme=t, style="default",
            font_size=9, padx=16, pady=6
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

    def _switch_tab(self, idx: int):
        t = self.theme
        self.current_tab = idx

        # Update tab button appearance
        for i, btn in enumerate(self.tab_buttons):
            if i == idx:
                btn.configure(bg=t["accent"], fg="#fff")
            else:
                btn.configure(bg=t["btn_bg"], fg=t["fg"])

        self._show_tab(idx)

    def _show_tab(self, idx: int):
        # Hide all tab frames
        self.prompt_frame.pack_forget()
        self.mcp_frame.pack_forget()
        self.settings_frame.pack_forget()
        if hasattr(self, 'permissions_frame'):
            self.permissions_frame.pack_forget()

        # Show selected tab
        if idx == 0:
            self.prompt_frame.pack(fill=tk.BOTH, expand=True)
        elif idx == 1:
            self.mcp_frame.pack(fill=tk.BOTH, expand=True)
        elif idx == 2:
            self.settings_frame.pack(fill=tk.BOTH, expand=True)
        elif idx == 3:
            self.permissions_frame.pack(fill=tk.BOTH, expand=True)

    def _build_prompt_tab(self):
        """Build System Prompt tab."""
        t = self.theme
        self.prompt_frame = tk.Frame(self.content, bg=t["card_bg"])

        # Label
        tk.Label(
            self.prompt_frame, text="CLAUDE.md (System Prompt)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(0, 4))

        # Text area with scrollbar
        text_frame = tk.Frame(self.prompt_frame, bg=t["btn_bg"])
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.prompt_text = tk.Text(
            text_frame,
            font=("Consolas", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0,
            wrap=tk.WORD,
            padx=8, pady=8
        )
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=self.prompt_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.prompt_text.config(yscrollcommand=scrollbar.set)

        # Insert current content
        self.prompt_text.insert("1.0", self.current_prompt)

        # Hint
        tk.Label(
            self.prompt_frame,
            text="This file provides context and instructions to Claude Code",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(4, 0))

    def _build_mcp_tab(self):
        """Build MCP Servers tab."""
        t = self.theme
        self.mcp_frame = tk.Frame(self.content, bg=t["card_bg"])

        # Label
        tk.Label(
            self.mcp_frame, text="MCP Servers (.mcp.json)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(0, 4))

        # Current servers
        servers = self.current_mcp.get("mcpServers", {})
        self.mcp_vars = {}

        servers_frame = tk.Frame(self.mcp_frame, bg=t["card_bg"])
        servers_frame.pack(fill=tk.X, pady=(0, 8))

        # Checkboxes for preset servers
        for name in self.MCP_PRESETS.keys():
            var = tk.BooleanVar(value=name in servers)
            self.mcp_vars[name] = var

            cb = tk.Checkbutton(
                servers_frame, text=name,
                variable=var,
                font=("Segoe UI", 9),
                bg=t["card_bg"], fg=t["fg"],
                selectcolor=t["btn_bg"],
                activebackground=t["card_bg"],
                activeforeground=t["fg"]
            )
            cb.pack(anchor="w", pady=1)

        # Custom servers section
        tk.Label(
            self.mcp_frame, text="Custom Servers (JSON)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(8, 4))

        # Filter out preset servers from current config for custom display
        custom_servers = {k: v for k, v in servers.items() if k not in self.MCP_PRESETS}

        custom_frame = tk.Frame(self.mcp_frame, bg=t["btn_bg"])
        custom_frame.pack(fill=tk.BOTH, expand=True)

        self.custom_mcp_text = tk.Text(
            custom_frame,
            font=("Consolas", 8),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0,
            height=6, wrap=tk.WORD,
            padx=8, pady=8
        )
        self.custom_mcp_text.pack(fill=tk.BOTH, expand=True)

        import json
        if custom_servers:
            self.custom_mcp_text.insert("1.0", json.dumps(custom_servers, indent=2))

        # Hint
        tk.Label(
            self.mcp_frame,
            text="Add custom MCP servers as JSON: {\"name\": {\"type\": \"stdio\", ...}}",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(4, 0))

    def _build_settings_tab(self):
        """Build Claude Settings tab."""
        t = self.theme
        self.settings_frame = tk.Frame(self.content, bg=t["card_bg"])

        # Environment variables section
        tk.Label(
            self.settings_frame, text="Environment Variables",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(0, 4))

        # Disable auto-update
        self.disable_autoupdate_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.settings_frame, text="Disable auto-update",
            variable=self.disable_autoupdate_var,
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg"],
            selectcolor=t["btn_bg"],
            activebackground=t["card_bg"],
            activeforeground=t["fg"]
        ).pack(anchor="w", pady=1)

        # Disable telemetry
        self.disable_telemetry_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.settings_frame, text="Disable telemetry",
            variable=self.disable_telemetry_var,
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg"],
            selectcolor=t["btn_bg"],
            activebackground=t["card_bg"],
            activeforeground=t["fg"]
        ).pack(anchor="w", pady=1)

        # Max output tokens
        tokens_frame = tk.Frame(self.settings_frame, bg=t["card_bg"])
        tokens_frame.pack(fill=tk.X, pady=(12, 0))

        tk.Label(
            tokens_frame, text="Max Output Tokens",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        self.max_tokens_entry = tk.Entry(
            tokens_frame, font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0, width=10
        )
        self.max_tokens_entry.pack(side=tk.LEFT, padx=(8, 0), ipady=4)

        # Bash timeout
        timeout_frame = tk.Frame(self.settings_frame, bg=t["card_bg"])
        timeout_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            timeout_frame, text="Bash Timeout (ms)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        self.bash_timeout_entry = tk.Entry(
            timeout_frame, font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0, width=10
        )
        self.bash_timeout_entry.pack(side=tk.LEFT, padx=(8, 0), ipady=4)

        # Hint
        tk.Label(
            self.settings_frame,
            text="Settings are applied via environment variables in run.cmd",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(16, 0))

    def _build_permissions_tab(self):
        """Build Permissions tab for agent."""
        t = self.theme
        self.permissions_frame = tk.Frame(self.content, bg=t["card_bg"])

        # Load current permissions from agent
        from claude_agent_manager.registry import PermissionConfig, PERMISSION_PRESETS, get_permission_preset
        self.current_permissions = PermissionConfig()
        self.agent_autopilot_enabled = False

        if HAS_BACKEND and manager:
            try:
                from claude_agent_manager.registry import load_agent
                agent_root = manager.get_agent_root()
                agent = load_agent(agent_root, self.agent_data["id"])
                self.current_permissions = agent.permissions
                self.agent_autopilot_enabled = getattr(agent, 'autopilot_enabled', False)
                # If autopilot is enabled, override preset to show "autopilot"
                if self.agent_autopilot_enabled:
                    self.current_permissions.preset = "autopilot"
            except Exception:
                pass

        # ═══════════════════════════════════════════════════════════════════════
        # AUTOPILOT TOGGLE - Card style with ToggleSwitch
        # ═══════════════════════════════════════════════════════════════════════
        # Outer card with border
        autopilot_card = tk.Frame(
            self.permissions_frame,
            bg=t["btn_bg"],
            highlightbackground="#ff9500" if self.agent_autopilot_enabled else t["border"],
            highlightthickness=1
        )
        autopilot_card.pack(fill=tk.X, pady=(0, 16))

        # Inner content
        autopilot_inner = tk.Frame(autopilot_card, bg=t["btn_bg"])
        autopilot_inner.pack(fill=tk.X, padx=12, pady=10)

        # Left side: icon + text
        autopilot_left = tk.Frame(autopilot_inner, bg=t["btn_bg"])
        autopilot_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Title row
        title_row = tk.Frame(autopilot_left, bg=t["btn_bg"])
        title_row.pack(fill=tk.X)

        tk.Label(
            title_row, text="⚡",
            font=("Segoe UI", 14), bg=t["btn_bg"], fg="#ff9500"
        ).pack(side=tk.LEFT)

        tk.Label(
            title_row, text="Autopilot Mode",
            font=("Segoe UI", 10, "bold"), bg=t["btn_bg"],
            fg="#ff9500" if self.agent_autopilot_enabled else t["fg"]
        ).pack(side=tk.LEFT, padx=(4, 0))

        # Status badge
        status_text = "ACTIVE" if self.agent_autopilot_enabled else "OFF"
        status_color = "#4ade80" if self.agent_autopilot_enabled else t["fg_dim"]
        self.autopilot_status = tk.Label(
            title_row, text=f" {status_text} ",
            font=("Consolas", 7, "bold"), bg=t["btn_bg"], fg=status_color
        )
        self.autopilot_status.pack(side=tk.LEFT, padx=(8, 0))

        # Description
        tk.Label(
            autopilot_left,
            text="Full autonomy - no permission prompts",
            font=("Segoe UI", 8), bg=t["btn_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(2, 0))

        # Right side: Toggle switch
        self.autopilot_enabled = self.agent_autopilot_enabled

        def on_autopilot_switch(state: bool):
            self.autopilot_enabled = state
            # Update visual feedback
            status_text = "ACTIVE" if state else "OFF"
            status_color = "#4ade80" if state else t["fg_dim"]
            self.autopilot_status.configure(text=f" {status_text} ", fg=status_color)
            # Update card border
            border_color = "#ff9500" if state else t["border"]
            autopilot_card.configure(highlightbackground=border_color)
            # If enabling, auto-select autopilot preset
            if state:
                self.perm_preset_var.set("autopilot")
                for i, btn in enumerate(self.preset_buttons):
                    preset = ["default", "strict", "permissive", "autopilot", "custom"][i]
                    if preset == "autopilot":
                        btn.configure(bg=t["accent"], fg="#fff")
                    else:
                        btn.configure(bg=t["btn_bg"], fg=t["fg"])
                self._update_preset_desc()

            # Auto-save autopilot state immediately
            if HAS_BACKEND and manager:
                try:
                    from claude_agent_manager.registry import update_agent_autopilot
                    agent_root = manager.get_agent_root()
                    update_agent_autopilot(agent_root, self.agent_data["id"], state)
                    # Trigger card refresh via on_save callback
                    if self.on_save:
                        self.on_save(self.agent_data["id"], None)
                except Exception:
                    pass

        self.autopilot_switch = ToggleSwitch(
            autopilot_inner,
            width=44, height=22,
            on_toggle=on_autopilot_switch,
            initial=self.agent_autopilot_enabled,
            bg=t["btn_bg"]
        )
        self.autopilot_switch.pack(side=tk.RIGHT, padx=(8, 0))

        # Warning text below card
        tk.Label(
            self.permissions_frame,
            text="⚠️ Autopilot allows ALL actions without confirmation. Use with caution!",
            font=("Segoe UI", 7), bg=t["card_bg"], fg="#f87171"
        ).pack(anchor="w", pady=(0, 12))

        # Preset selector
        tk.Label(
            self.permissions_frame, text="Permission Preset",
            font=("Segoe UI", 9, "bold"), bg=t["card_bg"], fg=t["fg"]
        ).pack(anchor="w", pady=(0, 6))

        self.perm_preset_var = tk.StringVar(value=self.current_permissions.preset)
        preset_frame = tk.Frame(self.permissions_frame, bg=t["btn_bg"])
        preset_frame.pack(fill=tk.X, pady=(0, 12))

        self.preset_buttons = []
        for preset in ["default", "strict", "permissive", "autopilot", "custom"]:
            btn = tk.Label(
                preset_frame, text=preset.title(),
                font=("Segoe UI", 8),
                bg=t["accent"] if self.current_permissions.preset == preset else t["btn_bg"],
                fg="#fff" if self.current_permissions.preset == preset else t["fg"],
                padx=10, pady=4, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 1))
            btn.bind("<Button-1>", lambda e, p=preset, b=btn: self._select_preset(p, b))
            self.preset_buttons.append(btn)

        # Preset description
        self.preset_desc = tk.Label(
            self.permissions_frame, text="",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"],
            wraplength=450, justify="left"
        )
        self.preset_desc.pack(anchor="w", pady=(0, 8))
        self._update_preset_desc()

        # Custom allow rules
        tk.Label(
            self.permissions_frame, text="Additional Allow Rules (one per line)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(8, 2))

        allow_frame = tk.Frame(self.permissions_frame, bg=t["btn_bg"], bd=1)
        allow_frame.pack(fill=tk.X, pady=(0, 8))

        self.allow_text = tk.Text(
            allow_frame, height=4, font=("Consolas", 9),
            bg=t["btn_bg"], fg=t["fg"], insertbackground=t["fg"],
            relief="flat", bd=0, wrap="word"
        )
        self.allow_text.pack(fill=tk.X, padx=4, pady=4)
        self.allow_text.insert("1.0", "\n".join(self.current_permissions.allow))

        # Custom deny rules
        tk.Label(
            self.permissions_frame, text="Additional Deny Rules (one per line)",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(0, 2))

        deny_frame = tk.Frame(self.permissions_frame, bg=t["btn_bg"], bd=1)
        deny_frame.pack(fill=tk.X, pady=(0, 8))

        self.deny_text = tk.Text(
            deny_frame, height=3, font=("Consolas", 9),
            bg=t["btn_bg"], fg=t["fg"], insertbackground=t["fg"],
            relief="flat", bd=0, wrap="word"
        )
        self.deny_text.pack(fill=tk.X, padx=4, pady=4)
        self.deny_text.insert("1.0", "\n".join(self.current_permissions.deny))

        # Hint
        tk.Label(
            self.permissions_frame,
            text="Permissions written to .claude/settings.json in project directory",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(8, 0))

    def _select_preset(self, preset: str, btn):
        """Handle preset selection."""
        t = self.theme
        self.perm_preset_var.set(preset)
        for b in self.preset_buttons:
            b.configure(bg=t["btn_bg"], fg=t["fg"])
        btn.configure(bg=t["accent"], fg="#fff")
        self._update_preset_desc()

    def _update_preset_desc(self):
        """Update preset description."""
        from claude_agent_manager.registry import PERMISSION_PRESETS
        preset = self.perm_preset_var.get()
        descriptions = {
            "default": "Balanced permissions - read access, common dev tools (git, npm, pip, python), MCP servers. Blocks dangerous commands.",
            "strict": "Minimal permissions - read-only, limited git (status/diff/log), grep/ls/cat only. No network tools.",
            "permissive": "Full development access - read/write/edit, all dev tools, docker, process management. Only blocks destructive root commands.",
            "autopilot": "⚠️ FULL AUTONOMY - No permission prompts! Agent can execute ANY action without confirmation. Use with extreme caution.",
            "custom": "Define your own allow/deny rules manually in the text fields below."
        }
        self.preset_desc.configure(text=descriptions.get(preset, ""))

    def _on_save(self):
        """Save all configuration to agent directory (per-agent isolation)."""
        import json

        # Determine save location (agent_dir for per-agent isolation)
        save_dir = self.agent_dir if self.agent_dir else self.project_path

        # 1. Save System Prompt (CLAUDE.md) to agent_dir
        prompt_content = self.prompt_text.get("1.0", tk.END).strip()
        if prompt_content and ac and self.agent_dir:
            ac.write_agent_local_claude_md(self.agent_dir, prompt_content)

        # 2. Save MCP configuration to agent_dir
        mcp_servers = {}

        # Add selected preset servers
        for name, var in self.mcp_vars.items():
            if var.get():
                mcp_servers[name] = self.MCP_PRESETS[name]

        # Add custom servers
        custom_text = self.custom_mcp_text.get("1.0", tk.END).strip()
        if custom_text:
            try:
                custom_servers = json.loads(custom_text)
                mcp_servers.update(custom_servers)
            except json.JSONDecodeError:
                pass  # Invalid JSON, skip

        if mcp_servers and ac and self.agent_dir:
            ac.write_agent_local_mcp_json(self.agent_dir, {"mcpServers": mcp_servers})

        # 3. Sync config to project immediately
        if ac and self.agent_dir:
            ac.sync_agent_config_to_project(self.agent_dir, self.project_path)

        # 4. Build AgentConfigOptions for env vars
        max_tokens_str = self.max_tokens_entry.get().strip()
        bash_timeout_str = self.bash_timeout_entry.get().strip()

        config_options = None
        if AgentConfigOptions:
            config_options = AgentConfigOptions(
                system_prompt=prompt_content if prompt_content else None,
                mcp_servers=mcp_servers if mcp_servers else None,
                disable_autoupdate=self.disable_autoupdate_var.get(),
                disable_telemetry=self.disable_telemetry_var.get(),
                max_output_tokens=int(max_tokens_str) if max_tokens_str.isdigit() else None,
                bash_timeout_ms=int(bash_timeout_str) if bash_timeout_str.isdigit() else None,
            )

        # 5. Save permissions
        if HAS_BACKEND and manager and hasattr(self, 'perm_preset_var'):
            try:
                from claude_agent_manager.registry import PermissionConfig, update_agent_permissions, update_agent_autopilot

                # Parse allow/deny rules from text
                allow_text = self.allow_text.get("1.0", tk.END).strip()
                deny_text = self.deny_text.get("1.0", tk.END).strip()

                allow_rules = [r.strip() for r in allow_text.split("\n") if r.strip()]
                deny_rules = [r.strip() for r in deny_text.split("\n") if r.strip()]

                preset = self.perm_preset_var.get()
                perm_config = PermissionConfig(
                    preset=preset,
                    allow=allow_rules,
                    deny=deny_rules
                )

                # Update agent and write .claude/settings.json
                agent_root = manager.get_agent_root()
                update_agent_permissions(agent_root, self.agent_data["id"], perm_config)

                # Update autopilot_enabled flag from toggle switch
                is_autopilot = getattr(self, 'autopilot_enabled', False)
                update_agent_autopilot(agent_root, self.agent_data["id"], is_autopilot)

                print(f"Permissions saved to .claude/settings.json (autopilot={is_autopilot})")
            except Exception as e:
                print(f"Error saving permissions: {e}")
                import traceback
                traceback.print_exc()

        # Call save callback
        if self.on_save:
            self.on_save(self.agent_data["id"], config_options)

        self.dialog.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT CARD
# ═══════════════════════════════════════════════════════════════════════════════

class AgentCard(tk.Frame):
    """Compact clickable agent card."""

    def __init__(
        self,
        parent: tk.Widget,
        agent_data: Dict,
        theme: Dict,
        on_click: Callable,
        on_toggle: Callable,
        on_name_change: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.agent_data = agent_data
        self.theme = theme
        self.on_click_cb = on_click
        self.on_toggle_cb = on_toggle
        self.on_name_change_cb = on_name_change
        self._editing_name = False

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        t = self.theme
        agent = self.agent_data
        status = agent["status"]

        self.configure(bg=t["card_bg"], highlightbackground=t["border"], highlightthickness=1)

        # Content
        self.content = tk.Frame(self, bg=t["card_bg"], padx=10, pady=6, cursor="hand2")
        self.content.pack(fill=tk.BOTH, expand=True)

        # Left
        self.left = tk.Frame(self.content, bg=t["card_bg"])
        self.left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Top row: Status dot + Name (editable) + Port
        self.top = tk.Frame(self.left, bg=t["card_bg"])
        self.top.pack(fill=tk.X)

        self.status_dot = StatusDot(self.top, online=(status == "online"), theme=t)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        self.status_dot.configure(bg=t["card_bg"])

        # Name/Purpose - главный элемент (с иконкой редактирования)
        name = agent.get("display_name") or agent["purpose"]
        name_truncated = name[:18] + "…" if len(name) > 18 else name

        self.purpose_lbl = tk.Label(
            self.top,
            text=f"{name_truncated} ✎",
            font=("Segoe UI Semibold", 9),
            bg=t["card_bg"],
            fg=t["fg"],
            cursor="hand2",
            anchor="w"
        )
        self.purpose_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Bottom row: ID + Memory indicator
        self.info_frame = tk.Frame(self.left, bg=t["card_bg"])
        self.info_frame.pack(fill=tk.X, pady=(2, 0))

        # Short ID
        short_id = agent["id"][:12] if len(agent["id"]) > 12 else agent["id"]
        self.id_lbl = tk.Label(
            self.info_frame, 
            text=short_id, 
            font=("Consolas", 7), 
            bg=t["card_bg"], 
            fg=t["fg_dim"]
        )
        self.id_lbl.pack(side=tk.LEFT)

        # Memory indicator (worker status)
        mem_color = t["online"] if status == "online" else t["fg_dim"]
        self.mem_lbl = tk.Label(
            self.info_frame,
            text="● mem",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=mem_color
        )
        self.mem_lbl.pack(side=tk.LEFT, padx=(8, 0))

        # Port label - compact, in info row
        self.port_lbl = tk.Label(
            self.info_frame,
            text=f":{agent['port']}",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.port_lbl.pack(side=tk.LEFT, padx=(8, 0))

        # Autopilot indicator
        self.autopilot_badge = None
        if agent.get("autopilot_enabled", False):
            self.autopilot_badge = tk.Label(
                self.info_frame,
                text="⚡auto",
                font=("Consolas", 7),
                bg=t["card_bg"],
                fg=t["accent"]
            )
            self.autopilot_badge.pack(side=tk.LEFT, padx=(6, 0))

        # Right side: Toggle button only
        btn_style = "stop" if status == "online" else "start"
        btn_text = "Stop" if status == "online" else "Start"

        self.toggle_btn = AnimatedButton(
            self.content,
            text=btn_text,
            command=self._do_toggle,
            theme=t,
            style=btn_style,
            font_size=8,
            padx=10,
            pady=3,
            bg=t["card_bg"]
        )
        self.toggle_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self._widgets = [self.content, self.left, self.top, self.purpose_lbl, self.port_lbl, self.info_frame, self.id_lbl, self.mem_lbl]
        if self.autopilot_badge:
            self._widgets.append(self.autopilot_badge)

    def _bind_events(self):
        for w in self._widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            # Don't bind card click to purpose_lbl - it has its own click handler
            if w != self.purpose_lbl:
                w.bind("<Button-1>", self._on_card_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_card_click)
        # Single click on name to edit
        self.purpose_lbl.bind("<Button-1>", self._on_name_click)

    def _on_enter(self, event=None):
        t = self.theme
        bg = t["card_hover"]
        self.configure(bg=bg)
        for w in self._widgets:
            try:
                w.configure(bg=bg)
            except:
                pass
        self.status_dot.configure(bg=bg)
        self.toggle_btn.set_bg(bg)

    def _on_leave(self, event=None):
        t = self.theme
        bg = t["card_bg"]
        self.configure(bg=bg)
        for w in self._widgets:
            try:
                w.configure(bg=bg)
            except:
                pass
        self.status_dot.configure(bg=bg)
        self.toggle_btn.set_bg(bg)

    def _on_card_click(self, event=None):
        self.on_click_cb(self.agent_data)

    def _do_toggle(self):
        self.on_toggle_cb(self.agent_data["id"], self.agent_data["status"])

    def _on_name_click(self, event=None):
        """Inline edit name on click."""
        if self._editing_name or not self.on_name_change_cb:
            return
        self._editing_name = True
        t = self.theme

        # Get current name
        current_name = self.agent_data.get("display_name") or self.agent_data["purpose"]

        # Hide label
        self.purpose_lbl.pack_forget()

        # Create entry in same parent as purpose_lbl (self.top)
        self._name_entry = tk.Entry(
            self.top,
            font=("Segoe UI Semibold", 9),
            bg=t["btn_bg"],
            fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=t["accent"],
            highlightcolor=t["accent"],
            width=18
        )
        self._name_entry.insert(0, current_name)
        self._name_entry.pack(side=tk.LEFT)  # Same position as purpose_lbl
        self._name_entry.focus_set()
        self._name_entry.select_range(0, tk.END)

        def save_name(event=None):
            if not self._editing_name:
                return
            new_name = self._name_entry.get().strip()
            if new_name == self.agent_data["purpose"]:
                new_name = None
            else:
                new_name = new_name or None

            # Finish editing FIRST (before callback destroys card)
            self._finish_card_editing()

            try:
                manager.update_display_name(self.agent_data["id"], new_name)
                self.agent_data["display_name"] = new_name
                if self.on_name_change_cb:
                    self.on_name_change_cb()
            except Exception as e:
                print(f"Error updating name: {e}")

        def cancel_edit(event=None):
            self._finish_card_editing()

        self._name_entry.bind("<Return>", save_name)
        self._name_entry.bind("<Escape>", cancel_edit)

        # Global click handler to save when clicking outside
        def on_global_click(event):
            if not self._editing_name:
                return
            # Check if click is outside the entry
            try:
                widget = event.widget
                if widget != self._name_entry:
                    save_name()
            except:
                pass

        # Bind to root window
        self._global_click_id = self.winfo_toplevel().bind("<Button-1>", on_global_click, "+")
        self._save_func = save_name  # Store for cleanup

        # Prevent event propagation to card click
        return "break"

    def _finish_card_editing(self):
        """Restore label after edit."""
        if not self._editing_name:
            return

        self._editing_name = False  # Set first to prevent re-entry

        # Unbind global click handler
        if hasattr(self, '_global_click_id') and self._global_click_id:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._global_click_id)
            except:
                pass
            self._global_click_id = None

        if hasattr(self, '_name_entry') and self._name_entry:
            try:
                self._name_entry.destroy()
            except:
                pass
            self._name_entry = None

        # Restore label with pencil (may fail if card destroyed)
        try:
            name = self.agent_data.get("display_name") or self.agent_data["purpose"]
            name_truncated = name[:20] + "..." if len(name) > 20 else name
            self.purpose_lbl.configure(text=f"{name_truncated} ✎")
            self.purpose_lbl.pack(anchor="w", pady=(1, 0))
        except:
            pass  # Widget may have been destroyed

    def update_theme(self, theme: Dict):
        self.theme = theme
        t = theme
        bg = t["card_bg"]
        
        # Update border
        self.configure(highlightbackground=t["border"], bg=bg)
        
        # Update all frames
        self.content.configure(bg=bg)
        self.left.configure(bg=bg)
        self.top.configure(bg=bg)
        self.info_frame.configure(bg=bg)
        
        # Update labels with correct colors from new layout
        self.purpose_lbl.configure(bg=bg, fg=t["fg"])  # Name is primary - fg color
        self.id_lbl.configure(bg=bg, fg=t["fg_dim"])  # ID is dimmed
        self.port_lbl.configure(bg=bg, fg=t["fg_dim"])  # Port is dimmed (in info row)
        
        # Update memory indicator
        status = self.agent_data.get("status", "offline")
        mem_color = t["online"] if status == "online" else t["fg_dim"]
        self.mem_lbl.configure(bg=bg, fg=mem_color)
        
        # Update status dot and button
        self.status_dot.configure(bg=bg)
        self.status_dot.update_theme(t)
        self.toggle_btn.update_theme(t)
        self.toggle_btn.set_bg(bg)


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE BAR (Session limits display - Real API)
# ═══════════════════════════════════════════════════════════════════════════════

class UsageBar(tk.Frame):
    """
    Usage progress bar widget showing real Claude API limits.

    Displays two bars:
    - 5h: 5-hour rolling usage (green)
    - 7d: 7-day rolling usage (gray)

    Auto-refreshes from Anthropic API every 30 seconds.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: Dict,
        plan_name: str = "Max",
        daily_limit: int = 100000,
        refresh_interval: int = 30000,  # 30 seconds
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.plan_name = plan_name
        self.daily_limit = daily_limit
        self.refresh_interval = refresh_interval
        self._five_hour_pct: float = 0.0
        self._seven_day_pct: float = 0.0
        self._active = True

        self.configure(bg=theme["card_bg"])
        self._build_ui()
        self._refresh_usage()

    def _build_ui(self):
        t = self.theme

        # Container for all elements (horizontal layout)
        self.content = tk.Frame(self, bg=t["card_bg"])
        self.content.pack(fill=tk.X, pady=(0, 4))

        # --- 5-hour bar (green) ---
        self.bar_5h_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.bar_5h_frame.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_5h = tk.Label(
            self.bar_5h_frame,
            text="5h",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.lbl_5h.pack(side=tk.LEFT, padx=(0, 2))

        self.canvas_5h = tk.Canvas(
            self.bar_5h_frame,
            width=60,
            height=10,
            bg=t["btn_bg"],
            highlightthickness=0
        )
        self.canvas_5h.pack(side=tk.LEFT)

        self._bar_5h_fill = self.canvas_5h.create_rectangle(
            0, 0, 0, 10,
            fill="#4ade80",  # Green
            outline=""
        )

        self.pct_5h = tk.Label(
            self.bar_5h_frame,
            text="0%",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.pct_5h.pack(side=tk.LEFT, padx=(2, 0))

        # --- 7-day bar (gray) ---
        self.bar_7d_frame = tk.Frame(self.content, bg=t["card_bg"])
        self.bar_7d_frame.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_7d = tk.Label(
            self.bar_7d_frame,
            text="7d",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.lbl_7d.pack(side=tk.LEFT, padx=(0, 2))

        self.canvas_7d = tk.Canvas(
            self.bar_7d_frame,
            width=60,
            height=10,
            bg=t["btn_bg"],
            highlightthickness=0
        )
        self.canvas_7d.pack(side=tk.LEFT)

        self._bar_7d_fill = self.canvas_7d.create_rectangle(
            0, 0, 0, 10,
            fill="#888888",  # Gray
            outline=""
        )

        self.pct_7d = tk.Label(
            self.bar_7d_frame,
            text="0%",
            font=("Consolas", 7),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.pct_7d.pack(side=tk.LEFT, padx=(2, 0))

        # Plan label (e.g., "Max")
        self.plan_lbl = tk.Label(
            self.content,
            text=self.plan_name,
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["accent"]
        )
        self.plan_lbl.pack(side=tk.LEFT, padx=(4, 0))

    def _refresh_usage(self):
        """Refresh usage data from Anthropic API."""
        if not self._active:
            return

        try:
            import json
            import urllib.request
            from pathlib import Path

            creds_path = Path.home() / ".claude" / ".credentials.json"
            if not creds_path.exists():
                return

            with open(creds_path, "r", encoding="utf-8") as f:
                creds = json.load(f)

            token = creds.get("claudeAiOauth", {}).get("accessToken")
            if not token:
                return

            # Update plan from credentials
            sub_type = creds.get("claudeAiOauth", {}).get("subscriptionType", "")
            if sub_type:
                self.plan_name = sub_type.capitalize()
                self.plan_lbl.configure(text=self.plan_name)

            req = urllib.request.Request(
                "https://api.anthropic.com/api/oauth/usage",
                headers={
                    "Authorization": f"Bearer {token}",
                    "anthropic-beta": "oauth-2025-04-20",
                }
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            # Data already in % (0-100)
            five_hour = data.get("five_hour", {})
            self._five_hour_pct = five_hour.get("utilization", 0)

            seven_day = data.get("seven_day", {})
            self._seven_day_pct = seven_day.get("utilization", 0)

            self._update_display()

        except Exception:
            # Silently fail, keep last data
            pass

        # Schedule next refresh
        if self._active:
            self.after(self.refresh_interval, self._refresh_usage)

    def _update_display(self):
        """Update UI with current usage data."""
        t = self.theme
        bar_width = 60

        # 5-hour bar
        pct_5h = min(self._five_hour_pct, 100)
        fill_5h = int(bar_width * pct_5h / 100)
        self.canvas_5h.coords(self._bar_5h_fill, 0, 0, fill_5h, 10)
        self.pct_5h.configure(text=f"{pct_5h:.0f}%")

        # Color based on usage level
        if pct_5h >= 90:
            self.canvas_5h.itemconfig(self._bar_5h_fill, fill="#ef4444")  # Red
        elif pct_5h >= 70:
            self.canvas_5h.itemconfig(self._bar_5h_fill, fill="#f59e0b")  # Orange
        else:
            self.canvas_5h.itemconfig(self._bar_5h_fill, fill="#4ade80")  # Green

        # 7-day bar
        pct_7d = min(self._seven_day_pct, 100)
        fill_7d = int(bar_width * pct_7d / 100)
        self.canvas_7d.coords(self._bar_7d_fill, 0, 0, fill_7d, 10)
        self.pct_7d.configure(text=f"{pct_7d:.0f}%")

        # Color based on usage level
        if pct_7d >= 90:
            self.canvas_7d.itemconfig(self._bar_7d_fill, fill="#ef4444")  # Red
        elif pct_7d >= 70:
            self.canvas_7d.itemconfig(self._bar_7d_fill, fill="#f59e0b")  # Orange
        else:
            self.canvas_7d.itemconfig(self._bar_7d_fill, fill="#888888")  # Gray

    def update_theme(self, theme: Dict):
        """Update widget theme."""
        self.theme = theme
        t = theme

        self.configure(bg=t["card_bg"])
        self.content.configure(bg=t["card_bg"])

        # 5h bar
        self.bar_5h_frame.configure(bg=t["card_bg"])
        self.lbl_5h.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.canvas_5h.configure(bg=t["btn_bg"])
        self.pct_5h.configure(bg=t["card_bg"], fg=t["fg_dim"])

        # 7d bar
        self.bar_7d_frame.configure(bg=t["card_bg"])
        self.lbl_7d.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.canvas_7d.configure(bg=t["btn_bg"])
        self.pct_7d.configure(bg=t["card_bg"], fg=t["fg_dim"])

        self.plan_lbl.configure(bg=t["card_bg"], fg=t["accent"])

        # Re-update display to apply colors
        self._update_display()

    def set_plan(self, plan_name: str, daily_limit: int = None):
        """Update plan and optionally limit, then refresh display."""
        self.plan_name = plan_name
        self.plan_lbl.configure(text=plan_name)
        if daily_limit is not None:
            self.daily_limit = daily_limit
        self._refresh_usage()

    def destroy(self):
        """Stop refresh loop before destroying."""
        self._active = False
        super().destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

class AgentDashboard:
    """Main dashboard with smooth theme transitions."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Claude Agents")
        self.is_dark = True
        self.theme = THEMES["dark"]

        self.agents_data: List[Dict] = []
        self.agent_cards: List[AgentCard] = []
        self.settings_visible = False
        self.terminal_visible = False
        self._theme_transition_step = 0
        self._terminal_windows: Dict[str, tk.Toplevel] = {}  # agent_id -> window

        # Memory tracking for cleanup
        self._open_graph_memories: Dict[str, Any] = {}  # agent_id -> GraphMemory
        self._open_session_memories: Dict[str, Any] = {}  # agent_id -> SessionMemory

        self._build_ui()
        self._load_agents()
        self._schedule_refresh()

        # Initialize global hotkeys
        self._setup_hotkeys()

        # Set initial title bar color
        self.root.after(50, lambda: set_title_bar_color(self.root, self.is_dark))

        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_app_close)

    def _build_ui(self):
        t = self.theme
        self.root.configure(bg=t["bg"])

        # Main container - disable propagation to prevent layout jumps
        self.main = tk.Frame(self.root, bg=t["bg"], padx=10, pady=8)
        self.main.pack(fill=tk.BOTH, expand=True)
        self.main.pack_propagate(False)

        # Card - fixed width, doesn't change when window expands
        self.card = tk.Frame(self.main, bg=t["card_bg"], padx=12, pady=8, width=440)
        self.card.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.card.pack_propagate(False)

        # Header: Agents | count | toggle (all on same baseline)
        self.header = tk.Frame(self.card, bg=t["card_bg"])
        self.header.pack(fill=tk.X, pady=(0, 8))

        # Left side container for title + count (baseline aligned)
        left_frame = tk.Frame(self.header, bg=t["card_bg"])
        left_frame.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(
            left_frame, text="Agents",
            font=("Segoe UI Semibold", 12),
            bg=t["card_bg"], fg=t["fg"]
        )
        self.title_lbl.pack(side=tk.LEFT)

        # Count label (same font size for alignment)
        self.count_lbl = tk.Label(
            left_frame, text="0",
            font=("Segoe UI", 12),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        self.count_lbl.pack(side=tk.LEFT, padx=(8, 0))

        # Toggle (right side)
        self.theme_toggle = ToggleSwitch(
            self.header,
            on_toggle=self._on_theme_toggle,
            initial=self.is_dark
        )
        self.theme_toggle.pack(side=tk.RIGHT)
        self.theme_toggle.set_bg(t["card_bg"])

        # Add button (right side, before toggle)
        self.add_btn = tk.Label(
            self.header, text="+",
            font=("Segoe UI", 12),
            bg=t["card_bg"], fg=t["accent"],
            cursor="hand2"
        )
        self.add_btn.pack(side=tk.RIGHT, padx=(0, 10), pady=(0, 2))
        self.add_btn.bind("<Button-1>", lambda e: self._create_agent())
        self.add_btn.bind("<Enter>", lambda e: self.add_btn.configure(fg=self.theme["fg"]))
        self.add_btn.bind("<Leave>", lambda e: self.add_btn.configure(fg=self.theme["accent"]))

        self.left_frame = left_frame

        # Usage bar (session limits display - real API data)
        self.usage_bar = UsageBar(
            self.card,
            theme=t,
            refresh_interval=30000  # 30 seconds
        )
        self.usage_bar.pack(fill=tk.X, pady=(4, 0))

        # Separator
        self.sep = tk.Frame(self.card, bg=t["separator"], height=1)
        self.sep.pack(fill=tk.X, pady=(4, 8))

        # Agents container - disable grid propagation
        self.agents_frame = tk.Frame(self.card, bg=t["card_bg"])
        self.agents_frame.pack(fill=tk.BOTH, expand=True)
        self.agents_frame.grid_propagate(False)

        # Worktree panel (below agent cards)
        self.worktree_panel = None
        if HAS_WORKTREE_UI and WorktreePanel:
            # Separator before worktrees
            self.worktree_sep = tk.Frame(self.card, bg=t["separator"], height=1)
            self.worktree_sep.pack(fill=tk.X, pady=(4, 4))

            self.worktree_panel = WorktreePanel(
                self.card,
                theme=t,
                project_path=self._get_active_project_path(),
                on_merge=self._handle_worktree_merge,
                on_discard=self._handle_worktree_discard,
                on_create=self._handle_worktree_create,
                refresh_interval=5000
            )
            self.worktree_panel.pack(fill=tk.X, pady=(0, 4))

        # Footer with settings gear (bottom right, same vertical as toggle)
        self.footer = tk.Frame(self.card, bg=t["card_bg"])
        self.footer.pack(fill=tk.X, pady=(4, 0))

        self.settings_btn = tk.Label(
            self.footer, text="☰",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"],
            cursor="hand2"
        )
        self.settings_btn.pack(side=tk.RIGHT)
        self.settings_btn.bind("<Button-1>", lambda e: self._show_app_settings())
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.configure(fg=self.theme["fg"]))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.configure(fg=self.theme["fg_dim"]))

        # Tile button (before settings)
        self.tile_btn = tk.Label(
            self.footer, text="⊞",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"],
            cursor="hand2"
        )
        self.tile_btn.pack(side=tk.RIGHT, padx=(0, 10))
        self.tile_btn.bind("<Button-1>", lambda e: self._tile_agent_windows())
        self.tile_btn.bind("<Enter>", lambda e: self.tile_btn.configure(fg=self.theme["accent"]))
        self.tile_btn.bind("<Leave>", lambda e: self.tile_btn.configure(fg=self.theme["fg_dim"]))

        # Team Mode button (before memory button)
        self.team_btn = tk.Label(
            self.footer, text="⚡",  # Team/lightning symbol
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"],
            cursor="hand2"
        )
        self.team_btn.pack(side=tk.RIGHT, padx=(0, 10))
        self.team_btn.bind("<Button-1>", lambda e: self._show_team_panel())
        self.team_btn.bind("<Enter>", lambda e: self.team_btn.configure(fg=self.theme["accent"]))
        self.team_btn.bind("<Leave>", lambda e: self.team_btn.configure(fg=self.theme["fg_dim"]))

        # Memory button (before tile button)
        self.memory_btn = tk.Label(
            self.footer, text="⟁",  # Memory/brain-like symbol
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["fg_dim"],
            cursor="hand2"
        )
        self.memory_btn.pack(side=tk.RIGHT, padx=(0, 10))
        self.memory_btn.bind("<Button-1>", lambda e: self._show_memory_panel())
        self.memory_btn.bind("<Enter>", lambda e: self.memory_btn.configure(fg=self.theme["accent"]))
        self.memory_btn.bind("<Leave>", lambda e: self.memory_btn.configure(fg=self.theme["fg_dim"]))

        # Settings panel (hidden) - disable propagation
        self.settings_panel = AgentSettingsPanel(
            self.main, theme=t, on_close=self._close_settings
        )
        self.settings_panel.pack_propagate(False)

        # Terminal panel (hidden) - shows embedded CLI
        self.terminal_panel = TerminalPanel(
            self.main, theme=t, on_close=self._close_terminal
        )
        self.terminal_panel.pack_propagate(False)

    def _on_theme_toggle(self, is_dark: bool):
        self.is_dark = is_dark
        self.theme = THEMES["dark" if is_dark else "light"]

        # Apply all changes, let Tk batch them naturally
        self._apply_theme()
        self.root.after_idle(lambda: set_title_bar_color(self.root, is_dark))

    def _show_memory_panel(self):
        """Show the memory viewer panel."""
        # Check if already open
        if hasattr(self, '_memory_panel') and self._memory_panel:
            try:
                self._memory_panel.lift()
                self._memory_panel.focus_force()
                return
            except tk.TclError:
                # Window was destroyed
                pass

        # Create new memory panel
        self._memory_panel = MemoryPanel(self.root, self.theme, self)

        # Center on parent
        self._memory_panel.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 500) // 2
        self._memory_panel.geometry(f"+{x}+{y}")

    def _show_team_panel(self):
        """Switch to Team Mode view."""
        self.card.pack_forget()
        if hasattr(self, 'settings_panel'):
            self.settings_panel.pack_forget()
        if hasattr(self, 'terminal_panel'):
            self.terminal_panel.pack_forget()

        # Build team frame if not exists
        if not hasattr(self, 'team_frame') or not self.team_frame:
            self._build_team_frame()

        self.team_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.root.title("Claude Agents - Team Mode")

        # Resize window to fit Team Mode content (2-column layout)
        self.root.geometry("1050x620")

    def _show_agents_panel(self):
        """Switch back to Agents view."""
        if hasattr(self, 'team_frame') and self.team_frame:
            self.team_frame.pack_forget()

        self.card.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.root.title("Claude Agents")

        # Resize back to agents view size
        self.root.geometry("460x400")

    def _build_team_frame(self):
        """Build the Team Mode frame (inline, not separate window)."""
        t = self.theme

        self.team_frame = tk.Frame(self.main, bg=t["card_bg"], padx=12, pady=8)

        # Header with back button
        header = tk.Frame(self.team_frame, bg=t["card_bg"])
        header.pack(fill=tk.X, pady=(0, 8))

        back_btn = tk.Label(
            header, text="< Back",
            font=("Segoe UI", 10),
            bg=t["card_bg"], fg=t["accent"],
            cursor="hand2"
        )
        back_btn.pack(side=tk.LEFT)
        back_btn.bind("<Button-1>", lambda e: self._show_agents_panel())
        back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=t["fg"]))
        back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=t["accent"]))

        title = tk.Label(
            header, text="Team Mode",
            font=("Segoe UI Semibold", 14),
            bg=t["card_bg"], fg=t["fg"]
        )
        title.pack(side=tk.LEFT, padx=(20, 0))

        subtitle = tk.Label(
            header, text="AutoGen + CrewAI + SWE-agent + Aider + MetaGPT",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"]
        )
        subtitle.pack(side=tk.LEFT, padx=(10, 0))

        # Usage bar on right
        self.team_usage_bar = UsageBar(header, theme=t, refresh_interval=30000)
        self.team_usage_bar.pack(side=tk.RIGHT)

        # Separator
        tk.Frame(self.team_frame, bg=t["separator"], height=1).pack(fill=tk.X, pady=(0, 8))

        # Content
        content = tk.Frame(self.team_frame, bg=t["card_bg"])
        content.pack(fill=tk.BOTH, expand=True)

        # Left: Task input
        left = tk.Frame(content, bg=t["card_bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        tk.Label(left, text="Task Description", font=("Segoe UI", 10),
                 bg=t["card_bg"], fg=t["fg_dim"], anchor="w").pack(fill=tk.X, pady=(0, 4))

        self.team_task_text = tk.Text(left, font=("Consolas", 10), bg=t["btn_bg"], fg=t["fg"],
                                       relief="flat", height=5, wrap="word", padx=8, pady=8)
        self.team_task_text.pack(fill=tk.X, pady=(0, 8))
        self.team_task_text.insert("1.0", "Add user authentication with JWT tokens")

        tk.Label(left, text="Project Path", font=("Segoe UI", 10),
                 bg=t["card_bg"], fg=t["fg_dim"], anchor="w").pack(fill=tk.X, pady=(0, 4))

        path_frame = tk.Frame(left, bg=t["btn_bg"])
        path_frame.pack(fill=tk.X, pady=(0, 8))

        self.team_path_entry = tk.Entry(path_frame, font=("Consolas", 10),
                                         bg=t["btn_bg"], fg=t["fg"], relief="flat")
        self.team_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        self.team_path_entry.insert(0, ".")

        browse_btn = tk.Label(path_frame, text="...", font=("Segoe UI", 10),
                              bg=t["btn_bg"], fg=t["fg_dim"], cursor="hand2", padx=8)
        browse_btn.pack(side=tk.RIGHT, pady=6)
        browse_btn.bind("<Button-1>", lambda e: self._team_browse_folder())

        # Buttons
        btn_frame = tk.Frame(left, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self.team_run_btn = tk.Label(btn_frame, text="Run Team", font=("Segoe UI Semibold", 10),
                                      bg=t["accent"], fg="#fff", cursor="hand2", padx=16, pady=8)
        self.team_run_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.team_run_btn.bind("<Button-1>", lambda e: self._team_run())

        plan_btn = tk.Label(btn_frame, text="Create Plan", font=("Segoe UI", 10),
                            bg=t["btn_bg"], fg=t["fg"], cursor="hand2", padx=16, pady=8)
        plan_btn.pack(side=tk.LEFT, padx=(0, 8))
        plan_btn.bind("<Button-1>", lambda e: self._team_plan())

        quality_btn = tk.Label(btn_frame, text="Quality Check", font=("Segoe UI", 10),
                               bg=t["btn_bg"], fg=t["fg"], cursor="hand2", padx=16, pady=8)
        quality_btn.pack(side=tk.LEFT)
        quality_btn.bind("<Button-1>", lambda e: self._team_quality())

        # Model Selector row
        model_frame = tk.Frame(left, bg=t["card_bg"])
        model_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(model_frame, text="Model:", font=("Segoe UI", 9),
                bg=t["card_bg"], fg=t["fg_dim"]).pack(side=tk.LEFT)

        # Model options with costs
        self.model_options = {
            "auto": ("Auto", "Auto-select by complexity", "#6366F1"),
            "haiku": ("Haiku", "$0.004/1k fast", "#10B981"),
            "sonnet": ("Sonnet", "$0.015/1k balanced", "#F59E0B"),
            "opus": ("Opus", "$0.075/1k smart", "#8B5CF6"),
            "local": ("Local", "Free (Ollama)", "#059669"),
        }

        self.selected_model = tk.StringVar(value="auto")
        self.model_btns = {}

        for model_id, (name, desc, color) in self.model_options.items():
            def make_click_handler(mid=model_id, col=color):
                def handler(e=None):
                    self.selected_model.set(mid)
                    # Update button styles
                    for m, btn in self.model_btns.items():
                        if m == mid:
                            btn.configure(bg=col, fg="#fff")
                        else:
                            btn.configure(bg=t["btn_bg"], fg=t["fg_dim"])
                return handler

            is_selected = model_id == "auto"
            btn = tk.Label(model_frame, text=name, font=("Segoe UI", 8),
                          bg=color if is_selected else t["btn_bg"],
                          fg="#fff" if is_selected else t["fg_dim"],
                          cursor="hand2", padx=8, pady=2)
            btn.pack(side=tk.LEFT, padx=(6, 0))
            btn.bind("<Button-1>", make_click_handler())

            # Tooltip on hover
            def show_tip(e, tip=desc):
                e.widget._tip = tk.Label(self.root, text=tip, font=("Segoe UI", 8),
                                         bg="#333", fg="#fff", padx=4, pady=2)
                e.widget._tip.place(x=e.x_root - self.root.winfo_rootx(),
                                   y=e.y_root - self.root.winfo_rooty() + 20)

            def hide_tip(e):
                if hasattr(e.widget, '_tip') and e.widget._tip:
                    e.widget._tip.destroy()
                    e.widget._tip = None

            btn.bind("<Enter>", show_tip)
            btn.bind("<Leave>", hide_tip)
            self.model_btns[model_id] = btn

        # Cost indicator
        self.cost_label = tk.Label(model_frame, text="Est: $0.00", font=("Segoe UI", 8),
                                   bg=t["card_bg"], fg=t["accent"])
        self.cost_label.pack(side=tk.RIGHT)

        # Output
        tk.Label(left, text="Output", font=("Segoe UI", 10),
                 bg=t["card_bg"], fg=t["fg_dim"], anchor="w").pack(fill=tk.X, pady=(8, 4))

        output_frame = tk.Frame(left, bg=t["bg"])
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.team_output = tk.Text(output_frame, font=("Consolas", 9), bg=t["bg"], fg=t["fg"],
                                    relief="flat", wrap="word", padx=8, pady=8)
        self.team_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(output_frame, command=self.team_output.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.team_output.config(yscrollcommand=scrollbar.set)

        # Read-only: block all keys except Ctrl+C, Ctrl+A, arrows, etc
        def on_key(event):
            # Allow Ctrl+C (copy), Ctrl+A (select all)
            if event.state & 0x4:  # Ctrl pressed
                if event.keysym.lower() in ('c', 'a'):
                    return  # Allow
            # Allow navigation keys
            if event.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Prior', 'Next'):
                return  # Allow
            return "break"  # Block everything else

        self.team_output.bind("<Key>", on_key)

        # Right-click context menu for copy
        def show_context_menu(event):
            menu = tk.Menu(self.team_output, tearoff=0)
            menu.add_command(label="Copy", command=lambda: self._copy_team_output())
            menu.add_command(label="Select All", command=lambda: self.team_output.tag_add("sel", "1.0", "end"))
            menu.tk_popup(event.x_root, event.y_root)

        self.team_output.bind("<Button-3>", show_context_menu)

        # Right: 2-column panel (Roles + Reasoning Patterns)
        right = tk.Frame(content, bg=t["btn_bg"], width=420)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)

        # Split into 2 columns
        right_left = tk.Frame(right, bg=t["btn_bg"], width=200)
        right_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))
        right_left.pack_propagate(False)

        right_right = tk.Frame(right, bg=t["btn_bg"], width=200)
        right_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        right_right.pack_propagate(False)

        # === LEFT COLUMN: Agent Roles ===
        roles_header = tk.Frame(right_left, bg=t["btn_bg"])
        roles_header.pack(fill=tk.X, padx=8, pady=(8, 6))

        tk.Label(roles_header, text="Agent Roles", font=("Segoe UI Semibold", 10),
                 bg=t["btn_bg"], fg=t["fg"]).pack(side=tk.LEFT)

        # Scrollable canvas for roles
        roles_canvas = tk.Canvas(right_left, bg=t["btn_bg"], highlightthickness=0)
        roles_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 2))

        roles_scrollable = tk.Frame(roles_canvas, bg=t["btn_bg"])
        canvas_window = roles_canvas.create_window((0, 0), window=roles_scrollable, anchor="nw", width=180)

        def on_frame_configure(e):
            roles_canvas.configure(scrollregion=roles_canvas.bbox("all"))

        def on_canvas_configure(e):
            roles_canvas.itemconfig(canvas_window, width=e.width - 4)

        roles_scrollable.bind("<Configure>", on_frame_configure)
        roles_canvas.bind("<Configure>", on_canvas_configure)

        # Mouse wheel scrolling
        def on_mousewheel(e):
            roles_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        roles_canvas.bind("<MouseWheel>", on_mousewheel)
        roles_scrollable.bind("<MouseWheel>", on_mousewheel)

        # Role definitions with colors
        roles_data = [
            ("Architect", "System design & APIs", "#8B5CF6", ["memory", "fs"], None),
            ("Backend", "Server-side logic", "#10B981", ["memory", "fs", "git"], "Architect"),
            ("Frontend", "React/TypeScript UI", "#F59E0B", ["memory", "fs"], "Backend"),
            ("Telegram", "Bot handlers", "#0EA5E9", ["memory", "fs"], "Backend"),
            ("Database", "Schema & migrations", "#6366F1", ["memory", "db"], "Architect"),
            ("QA", "Tests & quality", "#EF4444", ["memory", "fs"], "Backend"),
            ("Security", "OWASP audit", "#DC2626", ["memory"], "Backend"),
            ("Reviewer", "Code review", "#EC4899", ["memory"], "QA"),
            ("DevOps", "Docker & K8s", "#059669", ["memory", "fs"], "All"),
        ]

        self.role_checkboxes = {}
        self.role_toggles = {}

        def create_toggle(parent, var, color, bg_color):
            """Create custom toggle switch."""
            toggle_frame = tk.Frame(parent, bg=bg_color, width=32, height=16)
            toggle_frame.pack_propagate(False)

            # Track and knob
            track_color = color if var.get() else t["bg"]
            track = tk.Frame(toggle_frame, bg=track_color, height=14)
            track.place(x=0, y=1, width=32, height=14)

            knob_x = 17 if var.get() else 1
            knob = tk.Frame(toggle_frame, bg="#fff", width=12, height=12)
            knob.place(x=knob_x, y=2)

            def toggle_click(e=None):
                new_val = not var.get()
                var.set(new_val)
                track.configure(bg=color if new_val else t["bg"])
                knob.place(x=17 if new_val else 1, y=2)

            toggle_frame.bind("<Button-1>", toggle_click)
            track.bind("<Button-1>", toggle_click)
            knob.bind("<Button-1>", toggle_click)

            return toggle_frame

        for role, desc, color, mcp, deps in roles_data:
            # Role card
            rf = tk.Frame(roles_scrollable, bg=t["btn_bg"], pady=6)
            rf.pack(fill=tk.X, padx=(0, 4))
            rf.bind("<MouseWheel>", on_mousewheel)

            # Left color bar
            color_bar = tk.Frame(rf, bg=color, width=3)
            color_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

            # Content
            role_content = tk.Frame(rf, bg=t["btn_bg"])
            role_content.pack(side=tk.LEFT, fill=tk.X, expand=True)
            role_content.bind("<MouseWheel>", on_mousewheel)

            # Header row with toggle
            role_header = tk.Frame(role_content, bg=t["btn_bg"])
            role_header.pack(fill=tk.X)
            role_header.bind("<MouseWheel>", on_mousewheel)

            # Default enabled: Architect, Backend, QA
            var = tk.BooleanVar(value=role in ["Architect", "Backend", "QA"])
            self.role_checkboxes[role.lower()] = var

            # Custom toggle
            toggle = create_toggle(role_header, var, color, t["btn_bg"])
            toggle.pack(side=tk.LEFT, padx=(0, 6))

            # Role name
            name_lbl = tk.Label(role_header, text=role, font=("Segoe UI Semibold", 9),
                               bg=t["btn_bg"], fg=color, cursor="hand2")
            name_lbl.pack(side=tk.LEFT)
            name_lbl.bind("<MouseWheel>", on_mousewheel)

            # Description
            desc_lbl = tk.Label(role_content, text=desc, font=("Segoe UI", 8),
                               bg=t["btn_bg"], fg=t["fg_dim"])
            desc_lbl.pack(anchor="w", padx=(38, 0))
            desc_lbl.bind("<MouseWheel>", on_mousewheel)

            # MCP pills row
            mcp_frame = tk.Frame(role_content, bg=t["btn_bg"])
            mcp_frame.pack(anchor="w", padx=(38, 0), pady=(2, 0))
            mcp_frame.bind("<MouseWheel>", on_mousewheel)

            for perm in mcp:
                pill = tk.Label(mcp_frame, text=perm, font=("Segoe UI", 7),
                               bg=t["bg"], fg=t["fg_dim"], padx=4, pady=0)
                pill.pack(side=tk.LEFT, padx=(0, 3))
                pill.bind("<MouseWheel>", on_mousewheel)

            # Dependency arrow
            if deps:
                dep_lbl = tk.Label(role_content, text=f"-> {deps}", font=("Segoe UI", 7),
                                  bg=t["btn_bg"], fg=t["separator"])
                dep_lbl.pack(anchor="w", padx=(38, 0))
                dep_lbl.bind("<MouseWheel>", on_mousewheel)

        # Separator
        tk.Frame(roles_scrollable, bg=t["separator"], height=1).pack(fill=tk.X, pady=(8, 6))

        # Graph Memory toggle
        gm_frame = tk.Frame(roles_scrollable, bg=t["btn_bg"])
        gm_frame.pack(fill=tk.X, pady=(0, 4))
        gm_frame.bind("<MouseWheel>", on_mousewheel)

        self.use_graph_memory = tk.BooleanVar(value=True)
        gm_toggle = create_toggle(gm_frame, self.use_graph_memory, t["accent"], t["btn_bg"])
        gm_toggle.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(gm_frame, text="Graph Memory", font=("Segoe UI", 9),
                bg=t["btn_bg"], fg=t["fg"]).pack(side=tk.LEFT)

        tk.Label(gm_frame, text="MCP", font=("Segoe UI", 7),
                bg=t["accent"], fg="#fff", padx=4, pady=1).pack(side=tk.LEFT, padx=(4, 0))

        # === RIGHT COLUMN: Reasoning Patterns ===
        patterns_header = tk.Frame(right_right, bg=t["btn_bg"])
        patterns_header.pack(fill=tk.X, padx=8, pady=(8, 6))

        tk.Label(patterns_header, text="Reasoning Pattern", font=("Segoe UI Semibold", 10),
                 bg=t["btn_bg"], fg=t["fg"]).pack(side=tk.LEFT)

        # Pattern definitions with colors and icons
        self.reasoning_patterns = {
            "auto": ("Auto", "Task-based selection", "#6366F1", "⚡"),
            "cot": ("Chain-of-Thought", "Step-by-step", "#10B981", "→"),
            "tot": ("Tree-of-Thoughts", "Multiple paths", "#8B5CF6", "🌳"),
            "reflection": ("Reflection", "Self-critique", "#F59E0B", "🔄"),
            "self_consistency": ("Self-Consistency", "N attempts", "#EF4444", "✓✓"),
            "react": ("ReAct", "Reason + Act", "#0EA5E9", "⚙"),
        }

        self.selected_reasoning = tk.StringVar(value="auto")
        self.pattern_buttons = {}

        patterns_frame = tk.Frame(right_right, bg=t["btn_bg"])
        patterns_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        def create_pattern_button(parent, pattern_id, name, desc, color, icon):
            """Create styled pattern selector button."""
            is_selected = self.selected_reasoning.get() == pattern_id

            btn_frame = tk.Frame(parent, bg=t["btn_bg"])
            btn_frame.pack(fill=tk.X, pady=2)

            # Card with color accent
            card = tk.Frame(btn_frame, bg=color if is_selected else t["bg"])
            card.pack(fill=tk.X, padx=1, pady=1)

            inner = tk.Frame(card, bg=t["bg"] if is_selected else t["btn_bg"])
            inner.pack(fill=tk.X, padx=2, pady=2)

            # Icon + Name row
            top_row = tk.Frame(inner, bg=inner["bg"])
            top_row.pack(fill=tk.X, padx=6, pady=(4, 0))

            icon_lbl = tk.Label(top_row, text=icon, font=("Segoe UI", 10),
                               bg=inner["bg"], fg=color)
            icon_lbl.pack(side=tk.LEFT)

            name_lbl = tk.Label(top_row, text=name, font=("Segoe UI Semibold", 9),
                               bg=inner["bg"], fg=t["fg"] if is_selected else t["fg_dim"])
            name_lbl.pack(side=tk.LEFT, padx=(4, 0))

            # Selected indicator
            if is_selected:
                sel_indicator = tk.Label(top_row, text="●", font=("Segoe UI", 8),
                                        bg=inner["bg"], fg=color)
                sel_indicator.pack(side=tk.RIGHT)

            # Description
            desc_lbl = tk.Label(inner, text=desc, font=("Segoe UI", 8),
                               bg=inner["bg"], fg=t["fg_dim"], anchor="w")
            desc_lbl.pack(fill=tk.X, padx=6, pady=(0, 4))

            # Click handler
            def on_click(e=None, pid=pattern_id):
                self.selected_reasoning.set(pid)
                refresh_pattern_buttons()

            for widget in [btn_frame, card, inner, top_row, icon_lbl, name_lbl, desc_lbl]:
                widget.bind("<Button-1>", on_click)
                widget.configure(cursor="hand2")

            return btn_frame

        def refresh_pattern_buttons():
            """Refresh all pattern buttons to reflect selection."""
            for widget in patterns_frame.winfo_children():
                widget.destroy()
            for pattern_id, (name, desc, color, icon) in self.reasoning_patterns.items():
                create_pattern_button(patterns_frame, pattern_id, name, desc, color, icon)

        # Initial render
        refresh_pattern_buttons()

    def _team_browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            self.team_path_entry.delete(0, tk.END)
            self.team_path_entry.insert(0, folder)

    def _team_log(self, msg: str):
        self.team_output.insert(tk.END, msg + "\n")
        self.team_output.see(tk.END)

    def _copy_team_output(self):
        """Copy selected text or all text from team output."""
        try:
            if self.team_output.tag_ranges("sel"):
                text = self.team_output.get("sel.first", "sel.last")
            else:
                text = self.team_output.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            pass

    def _get_selected_roles(self):
        """Get list of selected agent roles."""
        selected = []
        if hasattr(self, 'role_checkboxes'):
            for role, var in self.role_checkboxes.items():
                if var.get():
                    selected.append(role)
        return selected if selected else ["architect", "backend", "qa"]

    def _get_reasoning_pattern(self):
        """Get selected reasoning pattern."""
        if hasattr(self, 'selected_reasoning'):
            return self.selected_reasoning.get()
        return "auto"

    def _get_selected_model(self):
        """Get selected model tier."""
        if hasattr(self, 'selected_model'):
            return self.selected_model.get()
        return "auto"

    def _update_cost_estimate(self, tokens: int = 0, cost: float = 0.0):
        """Update cost label with estimate."""
        if hasattr(self, 'cost_label'):
            self.root.after(0, lambda: self.cost_label.configure(text=f"Est: ${cost:.3f}"))

    def _team_run(self):
        task = self.team_task_text.get("1.0", tk.END).strip()
        project = self.team_path_entry.get().strip() or "."
        if not task:
            self._team_log("[ERROR] Task is empty")
            return

        selected_roles = self._get_selected_roles()
        use_graph = self.use_graph_memory.get() if hasattr(self, 'use_graph_memory') else True
        reasoning_pattern = self._get_reasoning_pattern()
        selected_model = self._get_selected_model()

        pattern_names = {
            "auto": "Auto-select",
            "cot": "Chain-of-Thought",
            "tot": "Tree-of-Thoughts",
            "reflection": "Reflection",
            "self_consistency": "Self-Consistency",
            "react": "ReAct"
        }

        model_names = {
            "auto": "Auto (by complexity)",
            "haiku": "Claude Haiku",
            "sonnet": "Claude Sonnet",
            "opus": "Claude Opus",
            "local": "Local (Ollama)"
        }

        self._team_log(f"[TEAM] Starting with roles: {', '.join(selected_roles)}")
        self._team_log(f"[TEAM] Model: {model_names.get(selected_model, selected_model)}")
        self._team_log(f"[TEAM] Reasoning: {pattern_names.get(reasoning_pattern, reasoning_pattern)}")
        self._team_log(f"[TEAM] Graph Memory: {'ON' if use_graph else 'OFF'}")
        self._team_log(f"[TEAM] Task: {task[:60]}...")

        import threading
        def run():
            try:
                import asyncio
                try:
                    from .team import TeamOrchestrator, create_agent
                    from .advanced_reasoning import AdvancedReasoningEngine, ReasoningPattern
                except ImportError:
                    from claude_agent_manager.team import TeamOrchestrator, create_agent
                    from claude_agent_manager.advanced_reasoning import AdvancedReasoningEngine, ReasoningPattern

                self.root.after(0, lambda: self._team_log("[TEAM] Initializing orchestrator..."))

                orchestrator = TeamOrchestrator(Path(project).resolve())

                # Add selected agents
                for role in selected_roles:
                    agent = create_agent(role, project_path=Path(project).resolve())
                    orchestrator.agents.append(agent)
                    self.root.after(0, lambda r=role: self._team_log(f"[TEAM] Added agent: {r}"))

                self.root.after(0, lambda: self._team_log(f"[TEAM] Creating plan for: {task[:40]}..."))

                # Create and execute plan
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    plan = loop.run_until_complete(orchestrator.create_plan(task))
                    self.root.after(0, lambda: self._team_log(f"[TEAM] Plan created with {len(plan.tasks)} tasks"))

                    for t in plan.tasks:
                        self.root.after(0, lambda t=t: self._team_log(f"  - {t.name}: {t.description[:50]}"))

                    self.root.after(0, lambda: self._team_log("[TEAM] Executing plan..."))
                    result = loop.run_until_complete(orchestrator.execute_plan())
                    self.root.after(0, lambda: self._team_log(f"[DONE] Execution completed!"))
                finally:
                    loop.close()

            except Exception as e:
                import traceback
                err_msg = str(e)
                tb = traceback.format_exc()
                self.root.after(0, lambda m=err_msg: self._team_log(f"[ERROR] {m}"))
                self.root.after(0, lambda t=tb: self._team_log(t))

        threading.Thread(target=run, daemon=True).start()

    def _team_plan(self):
        task = self.team_task_text.get("1.0", tk.END).strip()
        project = self.team_path_entry.get().strip() or "."
        if not task:
            self._team_log("[ERROR] Task is empty")
            return

        selected_roles = self._get_selected_roles()
        self._team_log(f"[PLAN] Creating plan for: {task[:60]}...")
        self._team_log(f"[PLAN] Roles: {', '.join(selected_roles)}")

        import threading
        def run():
            try:
                import asyncio
                try:
                    from .team import TeamOrchestrator, create_agent
                except ImportError:
                    from claude_agent_manager.team import TeamOrchestrator, create_agent

                orchestrator = TeamOrchestrator(Path(project).resolve())

                # Add selected agents
                for role in selected_roles:
                    agent = create_agent(role, project_path=Path(project).resolve())
                    orchestrator.agents.append(agent)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    plan = loop.run_until_complete(orchestrator.create_plan(task))

                    self.root.after(0, lambda: self._team_log(f"\n[PLAN] Generated {len(plan.tasks)} tasks:\n"))

                    for i, t in enumerate(plan.tasks, 1):
                        self.root.after(0, lambda i=i, t=t: self._team_log(
                            f"{i}. [{t.assigned_role}] {t.name}\n"
                            f"   {t.description[:80]}...\n"
                            f"   Dependencies: {', '.join(t.depends_on) or 'None'}\n"
                        ))

                    self.root.after(0, lambda: self._team_log("[PLAN] Done!"))
                finally:
                    loop.close()

            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: self._team_log(f"[ERROR] {m}"))

        threading.Thread(target=run, daemon=True).start()

    def _team_quality(self):
        project = self.team_path_entry.get().strip() or "."
        self._team_log(f"[QUALITY] Checking: {project}")

        import threading
        def run():
            try:
                try:
                    from .team import QualityGates
                except ImportError:
                    from claude_agent_manager.team import QualityGates

                self.root.after(0, lambda: self._team_log("[QUALITY] Running checks..."))

                gates = QualityGates(Path(project).resolve())

                # Run linting
                self.root.after(0, lambda: self._team_log("[QUALITY] Linting..."))
                lint_ok = gates.run_linting()
                self.root.after(0, lambda: self._team_log(f"  Lint: {'PASS' if lint_ok else 'FAIL'}"))

                # Run type checking
                self.root.after(0, lambda: self._team_log("[QUALITY] Type checking..."))
                type_ok = gates.run_type_check()
                self.root.after(0, lambda: self._team_log(f"  Types: {'PASS' if type_ok else 'FAIL'}"))

                # Run security scan
                self.root.after(0, lambda: self._team_log("[QUALITY] Security scan..."))
                sec_ok = gates.run_security_scan()
                self.root.after(0, lambda: self._team_log(f"  Security: {'PASS' if sec_ok else 'FAIL'}"))

                # Summary
                all_ok = lint_ok and type_ok and sec_ok
                self.root.after(0, lambda: self._team_log(
                    f"\n[QUALITY] {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}"
                ))

            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: self._team_log(f"[ERROR] {m}"))

        threading.Thread(target=run, daemon=True).start()

    def _show_app_settings(self):
        """Show application settings dialog."""
        from claude_agent_manager import settings as app_settings

        t = self.theme
        current = app_settings.get_settings(reload=True)

        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.configure(bg=t["card_bg"])
        dialog.geometry("380x520")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        dialog.geometry(f"+{x}+{y}")

        # Form
        form = tk.Frame(dialog, bg=t["card_bg"])
        form.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Tile layout
        tk.Label(
            form, text="Tile Layout", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 2))

        layout_var = tk.StringVar(value=current.tile_layout)
        layout_frame = tk.Frame(form, bg=t["btn_bg"])
        layout_frame.pack(fill=tk.X, pady=(0, 10))

        for layout in ["smart", "grid", "horizontal", "vertical"]:
            btn = tk.Label(
                layout_frame, text=layout.title(),
                font=("Segoe UI", 8),
                bg=t["accent"] if current.tile_layout == layout else t["btn_bg"],
                fg="#fff" if current.tile_layout == layout else t["fg"],
                padx=8, pady=4, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 1))

            def select_layout(ly=layout, b=btn):
                layout_var.set(ly)
                for child in layout_frame.winfo_children():
                    child.configure(bg=t["btn_bg"], fg=t["fg"])
                b.configure(bg=t["accent"], fg="#fff")

            btn.bind("<Button-1>", lambda e, ly=layout, b=btn: select_layout(ly, b))

        # Auto-tile checkboxes
        auto_start_var = tk.BooleanVar(value=current.auto_tile_on_start)
        tk.Checkbutton(
            form, text="Auto-tile on start", variable=auto_start_var,
            bg=t["card_bg"], fg=t["fg"], selectcolor=t["btn_bg"],
            activebackground=t["card_bg"], activeforeground=t["fg"]
        ).pack(anchor="w", pady=2)

        auto_change_var = tk.BooleanVar(value=current.auto_tile_on_change)
        tk.Checkbutton(
            form, text="Auto-tile on agent change", variable=auto_change_var,
            bg=t["card_bg"], fg=t["fg"], selectcolor=t["btn_bg"],
            activebackground=t["card_bg"], activeforeground=t["fg"]
        ).pack(anchor="w", pady=2)

        # Poll interval
        tk.Label(
            form, text="Poll Interval (ms)", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(8, 2))

        poll_entry = tk.Entry(
            form, font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=0, width=8
        )
        poll_entry.insert(0, str(current.poll_interval_ms))
        poll_entry.pack(anchor="w", ipady=4)

        # Hotkeys section
        tk.Label(
            form, text="Hotkeys", font=("Segoe UI", 9, "bold"),
            bg=t["card_bg"], fg=t["fg"], anchor="w"
        ).pack(fill=tk.X, pady=(12, 4))

        tk.Label(
            form, text="Format: ctrl+alt+key (e.g., ctrl+alt+t) or 'none' to disable",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 6))

        hotkey_entries = {}
        hotkey_labels = [
            ("hotkey_tile_all", "Tile windows"),
            ("hotkey_minimize_all", "Minimize all"),
            ("hotkey_toggle_dashboard", "Toggle dashboard"),
            ("hotkey_focus_agent_1", "Focus agent 1"),
            ("hotkey_focus_agent_2", "Focus agent 2"),
            ("hotkey_focus_agent_3", "Focus agent 3"),
            ("hotkey_focus_agent_4", "Focus agent 4"),
        ]

        for attr, label in hotkey_labels:
            row = tk.Frame(form, bg=t["card_bg"])
            row.pack(fill=tk.X, pady=1)

            tk.Label(
                row, text=label, font=("Segoe UI", 8),
                bg=t["card_bg"], fg=t["fg_dim"], width=14, anchor="w"
            ).pack(side=tk.LEFT)

            entry = tk.Entry(
                row, font=("Segoe UI", 9),
                bg=t["btn_bg"], fg=t["fg"],
                insertbackground=t["fg"], relief="flat", bd=0, width=16
            )
            entry.insert(0, getattr(current, attr, "none"))
            entry.pack(side=tk.LEFT, padx=4, ipady=2)
            hotkey_entries[attr] = entry

        # Buttons
        btn_frame = tk.Frame(dialog, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        def on_save():
            poll_val = poll_entry.get().strip()

            # Collect hotkey values
            hotkey_values = {}
            for attr, entry in hotkey_entries.items():
                val = entry.get().strip().lower()
                hotkey_values[attr] = val if val else "none"

            new_settings = app_settings.AppSettings(
                theme="dark" if self.is_dark else "light",
                tile_layout=layout_var.get(),
                auto_tile_on_start=auto_start_var.get(),
                auto_tile_on_change=auto_change_var.get(),
                poll_interval_ms=int(poll_val) if poll_val.isdigit() else 1500,
                hotkey_tile_all=hotkey_values.get("hotkey_tile_all", "ctrl+alt+t"),
                hotkey_minimize_all=hotkey_values.get("hotkey_minimize_all", "ctrl+alt+m"),
                hotkey_focus_agent_1=hotkey_values.get("hotkey_focus_agent_1", "ctrl+alt+1"),
                hotkey_focus_agent_2=hotkey_values.get("hotkey_focus_agent_2", "ctrl+alt+2"),
                hotkey_focus_agent_3=hotkey_values.get("hotkey_focus_agent_3", "ctrl+alt+3"),
                hotkey_focus_agent_4=hotkey_values.get("hotkey_focus_agent_4", "ctrl+alt+4"),
                hotkey_toggle_dashboard=hotkey_values.get("hotkey_toggle_dashboard", "ctrl+alt+d"),
            )
            app_settings.save_settings(new_settings)
            app_settings.invalidate_cache()
            dialog.destroy()

            # Notify about hotkey changes
            print("Settings saved. Restart app for hotkey changes to take effect.")

        save_btn = AnimatedButton(
            btn_frame, text="Save",
            command=on_save,
            theme=t, style="primary",
            font_size=9, padx=20, pady=6
        )
        save_btn.pack(side=tk.RIGHT)

        cancel_btn = AnimatedButton(
            btn_frame, text="Cancel",
            command=dialog.destroy,
            theme=t, style="default",
            font_size=9, padx=16, pady=6
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

        dialog.bind("<Escape>", lambda e: dialog.destroy())

    # ───────────────────────────────────────────────────────────────────────────
    # WORKTREE HANDLERS
    # ───────────────────────────────────────────────────────────────────────────

    def _get_active_project_path(self) -> Path:
        """Get project path from first agent or None."""
        if self.agents_data:
            for agent in self.agents_data:
                project = agent.get("project_path")
                if project:
                    return Path(project)
        return None

    def _handle_worktree_merge(self, wt):
        """Show merge confirmation dialog."""
        if not HAS_WORKTREE_UI:
            return

        def on_confirm(worktree, squash):
            project_path = self._get_active_project_path()
            if not project_path:
                return

            try:
                wm = WorktreeManager(project_path)
                success = wm.merge_worktree(
                    worktree.path,
                    target_branch="main",
                    delete_after=True,
                    squash=squash
                )
                if success:
                    self._show_notification("Merge successful", "green")
                else:
                    self._show_notification("Merge failed - check for conflicts", "red")
            except Exception as e:
                self._show_notification(f"Error: {str(e)[:50]}", "red")

        MergeConfirmDialog(self.root, self.theme, wt, on_confirm)

    def _handle_worktree_discard(self, wt):
        """Show discard confirmation dialog."""
        if not HAS_WORKTREE_UI:
            return

        def on_confirm(worktree):
            project_path = self._get_active_project_path()
            if not project_path:
                return

            try:
                wm = WorktreeManager(project_path)
                wm.discard_worktree(worktree.path, force=True)
                self._show_notification("Worktree discarded", "orange")
            except Exception as e:
                self._show_notification(f"Error: {str(e)[:50]}", "red")

        DiscardConfirmDialog(self.root, self.theme, wt, on_confirm)

    def _handle_worktree_create(self):
        """Show create worktree dialog."""
        if not HAS_WORKTREE_UI:
            return

        def on_create(agent_id, task_name):
            project_path = self._get_active_project_path()
            if not project_path:
                self._show_notification("No project path configured", "red")
                return

            try:
                wm = WorktreeManager(project_path)
                wm.create_task_worktree(agent_id, task_name)
                self._show_notification(f"Created worktree: {task_name}", "green")
            except Exception as e:
                self._show_notification(f"Error: {str(e)[:50]}", "red")

        CreateWorktreeDialog(self.root, self.theme, self.agents_data, on_create)

    def _show_notification(self, message: str, color: str = "accent"):
        """Show temporary notification in title area."""
        original_text = self.title_lbl.cget("text")
        original_fg = self.title_lbl.cget("fg")

        color_map = {
            "green": "#4ade80",
            "red": "#ef4444",
            "orange": "#f59e0b",
            "accent": self.theme["accent"]
        }

        self.title_lbl.configure(text=message, fg=color_map.get(color, color))

        def restore():
            self.title_lbl.configure(text=original_text, fg=original_fg)

        self.root.after(3000, restore)

    def _apply_theme(self):
        """Apply theme colors to all widgets without re-rendering."""
        t = self.theme

        # Update main containers
        self.root.configure(bg=t["bg"])
        self.main.configure(bg=t["bg"])
        self.card.configure(bg=t["card_bg"])
        self.header.configure(bg=t["card_bg"])
        self.left_frame.configure(bg=t["card_bg"])
        self.title_lbl.configure(bg=t["card_bg"], fg=t["fg"])
        self.count_lbl.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.add_btn.configure(bg=t["card_bg"], fg=t["accent"])
        self.theme_toggle.set_bg(t["card_bg"])
        self.footer.configure(bg=t["card_bg"])
        self.settings_btn.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.tile_btn.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.memory_btn.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.sep.configure(bg=t["separator"])
        self.agents_frame.configure(bg=t["card_bg"])

        # Update usage bar
        self.usage_bar.update_theme(t)

        # Update worktree panel
        if self.worktree_panel:
            self.worktree_panel.update_theme(t)
            if hasattr(self, 'worktree_sep'):
                self.worktree_sep.configure(bg=t["separator"])

        # Update existing cards
        for card in self.agent_cards:
            card.update_theme(t)

        # Update settings panel
        self.settings_panel.update_theme(t)

        # Update terminal panel
        self.terminal_panel.update_theme(t)

        # Update empty state if shown
        for w in self.agents_frame.winfo_children():
            if isinstance(w, tk.Frame) and w not in [c for c in self.agent_cards]:
                w.configure(bg=t["card_bg"])
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(bg=t["card_bg"], fg=t["fg_dim"])
                    elif isinstance(child, AnimatedButton):
                        child.update_theme(t)

    def _schedule_refresh(self):
        self._refresh_agents()
        self._process_hotkey_callbacks()
        self.root.after(5000, self._schedule_refresh)

    def _setup_hotkeys(self):
        """Initialize global hotkeys from settings."""
        if not HAS_TILING or get_hotkey_manager is None:
            return

        from claude_agent_manager import settings as app_settings
        settings = app_settings.get_settings()

        hk_manager = get_hotkey_manager()

        # Register tile hotkey
        if settings.hotkey_tile_all and settings.hotkey_tile_all.lower() != "none":
            hk_manager.register(
                settings.hotkey_tile_all,
                lambda: self._tile_agent_windows("smart"),
                "Tile all agent windows"
            )

        # Register minimize hotkey
        if settings.hotkey_minimize_all and settings.hotkey_minimize_all.lower() != "none":
            hk_manager.register(
                settings.hotkey_minimize_all,
                self._minimize_agent_windows,
                "Minimize all agent windows"
            )

        # Register focus hotkeys for agents 1-4
        for i, hotkey_attr in enumerate([
            'hotkey_focus_agent_1', 'hotkey_focus_agent_2',
            'hotkey_focus_agent_3', 'hotkey_focus_agent_4'
        ]):
            hotkey = getattr(settings, hotkey_attr, "none")
            if hotkey and hotkey.lower() != "none":
                idx = i  # Capture loop variable
                hk_manager.register(
                    hotkey,
                    lambda idx=idx: self._focus_agent_window(idx),
                    f"Focus agent {i + 1}"
                )

        # Register toggle dashboard hotkey
        if settings.hotkey_toggle_dashboard and settings.hotkey_toggle_dashboard.lower() != "none":
            hk_manager.register(
                settings.hotkey_toggle_dashboard,
                self._toggle_dashboard_visibility,
                "Toggle dashboard visibility"
            )

        # Start hotkey listener
        hk_manager.start()

        # Process callbacks periodically
        self._hotkey_poll_id = self.root.after(100, self._process_hotkey_callbacks)

    def _process_hotkey_callbacks(self):
        """Process pending hotkey callbacks in main thread."""
        if HAS_TILING and get_hotkey_manager is not None:
            try:
                hk_manager = get_hotkey_manager()
                hk_manager.process_callbacks()
            except Exception as e:
                print(f"Hotkey callback error: {e}")

        # Schedule next check
        self._hotkey_poll_id = self.root.after(100, self._process_hotkey_callbacks)

    def _toggle_dashboard_visibility(self):
        """Toggle dashboard window visibility (always on top when shown)."""
        try:
            if self.root.state() == 'withdrawn' or self.root.state() == 'iconic':
                # Show window on top of all others
                self.root.deiconify()
                self.root.attributes('-topmost', True)
                self.root.lift()
                self.root.focus_force()
                # Remove topmost after a short delay so it doesn't stay always on top
                self.root.after(100, lambda: self.root.attributes('-topmost', False))
            else:
                # Hide window
                self.root.withdraw()
        except Exception as e:
            print(f"Toggle visibility error: {e}")

    def _refresh_agents(self):
        """Refresh agent data without full re-render if possible."""
        new_data = self._fetch_agents_data()

        # Check if data actually changed
        if self._data_equals(self.agents_data, new_data):
            return  # No changes, skip render

        self.agents_data = new_data
        self._render()

        # Update worktree panel project path
        if self.worktree_panel:
            project_path = self._get_active_project_path()
            if project_path:
                self.worktree_panel.set_project_path(project_path)

    def _data_equals(self, old: List[Dict], new: List[Dict]) -> bool:
        """Compare agent data lists."""
        if len(old) != len(new):
            return False
        for o, n in zip(old, new):
            if o.get("id") != n.get("id") or o.get("status") != n.get("status"):
                return False
        return True

    def _fetch_agents_data(self) -> List[Dict]:
        """Fetch current agents data using manager."""
        data = []
        print(f"[DEBUG] _fetch_agents_data: HAS_BACKEND={HAS_BACKEND}")

        if HAS_BACKEND:
            try:
                # Use manager to get agents with status
                agents = manager.list_agents()
                for agent in agents:
                    # Check if embedded window is open for this agent
                    has_embedded_window = (
                        hasattr(self, "_agent_windows")
                        and agent.id in self._agent_windows
                        and self._agent_windows[agent.id].winfo_exists()
                    )

                    # Status is online if worker is running OR embedded window is open
                    status = "online" if (agent.worker_online or has_embedded_window) else "offline"

                    display_name = getattr(agent, 'display_name', None)
                    data.append({
                        "id": agent.id,
                        "purpose": agent.purpose,
                        "display_name": display_name,
                        "port": agent.port,
                        "status": status,
                        "pm2_name": f"agent-{agent.id}",
                        "project_path": agent.project_path,
                        "use_browser": agent.use_browser,
                        "cmd_running": getattr(agent, 'cmd_running', False),
                        "viewer_running": getattr(agent, 'viewer_running', False),
                        "proxy": getattr(agent, 'proxy', None) or {},
                        "autopilot_enabled": getattr(agent, 'autopilot_enabled', False),
                    })
            except Exception as e:
                print(f"Fetch agents error: {e}")
                import traceback
                traceback.print_exc()

        return data

    def _load_agents(self):
        """Full load (initial or forced)."""
        print(f"[DEBUG] _load_agents called, current ui_mode: {getattr(self, '_ui_mode', 'none')}")

        # Remember selected agent to refresh settings panel
        selected_id = None
        if self.settings_visible and self.settings_panel.agent_data:
            selected_id = self.settings_panel.agent_data.get("id")

        self.agents_data = self._fetch_agents_data()
        print(f"[DEBUG] Fetched {len(self.agents_data)} agents: {[a.get('id') for a in self.agents_data]}")
        self._render()

        # Refresh settings panel if it was showing an agent
        if selected_id and self.settings_visible:
            for agent in self.agents_data:
                if agent["id"] == selected_id:
                    callbacks = {
                        "configure": self._configure_claude,
                        "memory": self._open_memory_viewer,
                        "restart_memory": self._restart_memory,
                        "proxy": self._configure_proxy,
                        "logs": self._view_logs,
                        "delete": self._delete_agent,
                        "refresh": lambda _: self._load_agents(),
                    }
                    self.settings_panel.show(agent, callbacks)
                    break

    def _get_demo_data(self) -> List[Dict]:
        # No demo data - show empty state for first launch
        return []

    def _render_welcome_form(self):
        """Render inline welcome form for first agent creation.

        Fixed layout (no responsive):
        - Left: Quick Start presets
        - Right: Custom Create form
        - Always shows 2 columns side-by-side
        """
        from tkinter import filedialog
        t = self.theme

        # Setup mode - hide card elements, use full window width
        if not hasattr(self, '_ui_mode') or self._ui_mode != 'setup':
            self._ui_mode = 'setup'
            self.root.minsize(900, 350)
            self.root.geometry("950x380")

            # Hide card chrome (header, usage_bar, separator, footer, worktree) for clean setup screen
            self.header.pack_forget()
            self.usage_bar.pack_forget()
            self.sep.pack_forget()
            if hasattr(self, 'worktree_sep') and self.worktree_sep:
                self.worktree_sep.pack_forget()
            if self.worktree_panel:
                self.worktree_panel.pack_forget()
            self.footer.pack_forget()

            # Make card fill entire window
            self.card.pack_forget()
            self.card.configure(width=0)  # Remove fixed width
            self.card.pack(fill=tk.BOTH, expand=True)

        # Simple container - no scroll needed for horizontal layout
        form_frame = tk.Frame(self.agents_frame, bg=t["card_bg"])
        form_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ═══════════════════════════════════════════════════════════════════════
        # SINGLE ROW LAYOUT: Header | Quick Start | Create Custom
        # ═══════════════════════════════════════════════════════════════════════

        # Main container - single row with 3 columns
        row_container = tk.Frame(form_frame, bg=t["card_bg"])
        row_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        row_container.columnconfigure(0, weight=1)  # Header
        row_container.columnconfigure(1, weight=2)  # Quick Start (wider)
        row_container.columnconfigure(2, weight=2)  # Create Custom (wider)
        row_container.rowconfigure(0, weight=1)

        # ─────────────────────────────────────────────────────────────────────
        # COLUMN 1: Header with logo (styled to match other blocks)
        # ─────────────────────────────────────────────────────────────────────
        header_card = tk.Frame(row_container, bg=t["card_bg"],
                              highlightthickness=1, highlightbackground=t.get("border", t["separator"]))
        header_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

        # Wrapper to center content vertically
        header_wrapper = tk.Frame(header_card, bg=t["card_bg"])
        header_wrapper.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        # Content frame - centered vertically with expand
        header_content = tk.Frame(header_wrapper, bg=t["card_bg"])
        header_content.pack(expand=True)  # This centers vertically

        # Welcome icon - use white version for dark theme
        icon_file = "icon_white.png" if self.is_dark else "icon.png"
        icon_path = get_asset_path(icon_file)
        if icon_path.exists():
            try:
                self._welcome_icon = tk.PhotoImage(file=str(icon_path))
                factor = max(1, self._welcome_icon.width() // 72)  # ~72px icon (bigger)
                self._welcome_icon = self._welcome_icon.subsample(factor, factor)
                tk.Label(
                    header_content, image=self._welcome_icon,
                    bg=t["card_bg"], borderwidth=0  # Match card background
                ).pack(pady=(0, 12))
            except:
                pass

        tk.Label(
            header_content, text="Create Agent",
            font=("Segoe UI Semibold", 13),
            bg=t["card_bg"], fg=t["fg"]
        ).pack(pady=(0, 6))

        tk.Label(
            header_content, text="Choose preset or\ncreate custom agent",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"],
            justify="center"
        ).pack()

        # ─────────────────────────────────────────────────────────────────────
        # COLUMN 2: Quick Start section
        # ─────────────────────────────────────────────────────────────────────
        qs_card = tk.Frame(row_container, bg=t["card_bg"],
                          highlightthickness=1, highlightbackground=t.get("border", t["separator"]))
        qs_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=0)
        left_col = tk.Frame(qs_card, bg=t["card_bg"])
        left_col.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ─────────────────────────────────────────────────────────────────────
        # COLUMN 3: Create Custom section
        # ─────────────────────────────────────────────────────────────────────
        custom_card_outer = tk.Frame(row_container, bg=t["card_bg"],
                                    highlightthickness=1, highlightbackground=t.get("border", t["separator"]))
        custom_card_outer.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=0)
        right_col = tk.Frame(custom_card_outer, bg=t["card_bg"])
        right_col.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Define presets with icons
        quick_presets = [
            ("🌐", "web-developer", "Web Dev", "Full-stack веб-разработка"),
            ("📊", "data-analyst", "Data", "Анализ данных, Python, ML"),
            ("🔍", "code-reviewer", "Review", "Code review (read-only)"),
            ("🚀", "devops", "DevOps", "Docker, K8s, Terraform"),
            ("📚", "researcher", "Research", "Веб-поиск, анализ"),
        ]

        def create_from_preset(preset_name: str):
            """Open dialog to select project and create agent from preset."""
            project = filedialog.askdirectory(parent=self.root, title="Select Project Directory")
            if not project:
                return

            if HAS_BACKEND:
                try:
                    from claude_agent_manager.sharing import get_builtin_preset
                    import uuid

                    preset = get_builtin_preset(preset_name)
                    if not preset:
                        print(f"Preset not found: {preset_name}")
                        return

                    # Generate ID
                    agent_id = f"{preset_name}-{uuid.uuid4().hex[:6]}"

                    # Use manager.create_agent with preset config
                    manager.create_agent(
                        purpose=preset.purpose_template or preset.metadata.name,
                        project_path=project,
                        agent_id=agent_id,
                        use_browser=False,
                        config=preset.config,
                    )

                    print(f"Created {preset.metadata.name} agent: {agent_id}")
                    self.root.after(500, self._load_agents)
                except Exception as e:
                    print(f"Create from preset error: {e}")
                    import traceback
                    traceback.print_exc()

        # ─────────────────────────────────────────────────────────────────────
        # LEFT COLUMN: Quick Start presets
        # ─────────────────────────────────────────────────────────────────────
        qs_content = tk.Frame(left_col, bg=t["card_bg"])
        qs_content.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            qs_content, text="⚡ QUICK START",
            font=("Segoe UI", 12, "bold"),
            bg=t["card_bg"], fg=t["accent"]
        ).pack(anchor="w", pady=(0, 8))

        # Preset buttons grid
        presets_grid = tk.Frame(qs_content, bg=t["card_bg"])
        presets_grid.pack(fill=tk.BOTH, expand=True)

        # Cache to prevent infinite rebuild loop
        self._welcome_last_cols = None
        self._welcome_preset_buttons = []

        def rebuild_preset_grid():
            """Rebuild preset grid - 2 columns for narrow Quick Start section."""
            cols = 2  # 2 columns for 1/3 width column

            # Only rebuild if columns changed (prevent infinite loop)
            if cols == self._welcome_last_cols:
                return

            self._welcome_last_cols = cols

            # Clear existing buttons
            for btn in self._welcome_preset_buttons:
                btn.destroy()
            self._welcome_preset_buttons.clear()

            # Helper: set card background color (card + all children)
            def set_card_bg(card: tk.Frame, bg: str):
                card.configure(bg=bg)
                for child in card.winfo_children():
                    child.configure(bg=bg)

            # Create buttons - 3 per row
            for i, (icon, preset_id, label, desc) in enumerate(quick_presets):
                btn_frame = tk.Frame(presets_grid, bg=t["btn_bg"], cursor="hand2")
                btn_frame.grid(row=i // cols, column=i % cols, padx=3, pady=3, sticky="nsew")
                self._welcome_preset_buttons.append(btn_frame)

                # Compact card: icon + label centered
                tk.Label(
                    btn_frame, text=icon,
                    font=("Segoe UI", 14),
                    bg=t["btn_bg"], fg=t["accent"]
                ).pack(pady=(4, 2))

                tk.Label(
                    btn_frame, text=label,
                    font=("Segoe UI", 8),
                    bg=t["btn_bg"], fg=t["fg"]
                ).pack(pady=(0, 4))

                # Bind click and hover to card
                def bind_to_card(widget, card, pid):
                    widget.bind("<Button-1>", lambda e: create_from_preset(pid))
                    widget.bind("<Enter>", lambda e: set_card_bg(card, t["btn_hover"]))
                    widget.bind("<Leave>", lambda e: set_card_bg(card, t["btn_bg"]))

                bind_to_card(btn_frame, btn_frame, preset_id)
                for child in btn_frame.winfo_children():
                    bind_to_card(child, btn_frame, preset_id)

            # Configure grid columns with equal weight
            for c in range(cols):
                presets_grid.columnconfigure(c, weight=1)

        # Initial build
        rebuild_preset_grid()

        # Rebuild on left_col resize
        def on_left_resize(e):
            rebuild_preset_grid()

        left_col.bind("<Configure>", on_left_resize, add="+")

        # ─────────────────────────────────────────────────────────────────────
        # RIGHT COLUMN: Custom Create form
        # ─────────────────────────────────────────────────────────────────────
        tk.Label(
            right_col, text="🔧 CREATE CUSTOM",
            font=("Segoe UI", 12, "bold"),
            bg=t["card_bg"], fg=t["accent"]
        ).pack(anchor="w", pady=(0, 8))

        # Purpose
        tk.Label(
            right_col, text="Purpose",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 4))

        self._welcome_purpose = tk.StringVar()
        purpose_entry = tk.Entry(
            right_col, textvariable=self._welcome_purpose,
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0
        )
        purpose_entry.pack(fill=tk.X, ipady=8)

        # Project path
        tk.Label(
            right_col, text="Project Directory",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(12, 4))

        path_frame = tk.Frame(right_col, bg=t["card_bg"])
        path_frame.pack(fill=tk.X)

        self._welcome_path = tk.StringVar()
        path_entry = tk.Entry(
            path_frame, textvariable=self._welcome_path,
            font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7)

        def browse():
            p = filedialog.askdirectory(parent=self.root)
            if p:
                self._welcome_path.set(p)

        browse_btn = tk.Label(
            path_frame, text="...",
            font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            cursor="hand2", padx=8
        )
        browse_btn.pack(side=tk.RIGHT, ipady=6, padx=(2, 0))
        browse_btn.bind("<Button-1>", lambda e: browse())
        browse_btn.bind("<Enter>", lambda e: browse_btn.configure(bg=t["btn_hover"]))
        browse_btn.bind("<Leave>", lambda e: browse_btn.configure(bg=t["btn_bg"]))

        # Hint/Error label
        hint_label = tk.Label(
            right_col, text="Fill both fields to enable Create",
            font=("Segoe UI", 8),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        )
        hint_label.pack(fill=tk.X, pady=(8, 0))

        # Create button
        btn_container = tk.Frame(right_col, bg=t["card_bg"])
        btn_container.pack(fill=tk.X, pady=(16, 0))

        def on_create():
            purpose = self._welcome_purpose.get().strip()
            project = self._welcome_path.get().strip()
            print(f"[DEBUG] on_create called: purpose={purpose}, project={project}, HAS_BACKEND={HAS_BACKEND}")
            if not purpose or not project:
                print("[DEBUG] Missing purpose or project, returning")
                return

            # Show creating state
            hint_label.configure(text="Creating agent...", fg=t["accent"])
            create_btn.configure(state="disabled")
            self.root.update()

            if HAS_BACKEND:
                try:
                    print(f"[DEBUG] Calling manager.create_agent...")
                    agent = manager.create_agent(
                        purpose=purpose,
                        project_path=project,
                        use_browser=False,
                    )
                    print(f"[DEBUG] Created agent: {agent.id if hasattr(agent, 'id') else agent}")
                    hint_label.configure(text="Agent created! Loading...", fg=t["accent"])
                except Exception as e:
                    print(f"[DEBUG] Create agent error: {e}")
                    import traceback
                    traceback.print_exc()
                    hint_label.configure(text=f"Error: {e}", fg=t["error"] if "error" in t else "#ff6b6b")
                    create_btn.configure(state="normal")
                    return
            else:
                print("[DEBUG] HAS_BACKEND is False, cannot create agent!")

            # Delay refresh to let agent register
            print("[DEBUG] Scheduling _load_agents in 1000ms")
            self.root.after(1000, self._load_agents)

        create_btn = AnimatedButton(
            btn_container, text="Create Agent",
            command=on_create,
            theme=t, style="primary",
            font_size=10, padx=24, pady=8
        )
        create_btn.pack()

        # Validation: Create enabled only if both fields filled
        def validate_fields(*args):
            is_valid = bool(self._welcome_purpose.get().strip() and self._welcome_path.get().strip())
            create_btn.configure(state="normal" if is_valid else "disabled")
            if is_valid:
                hint_label.configure(text="Ready to create!", fg=t["accent"])
            else:
                hint_label.configure(text="Fill both fields to enable Create", fg=t["fg_dim"])

        self._welcome_purpose.trace_add("write", validate_fields)
        self._welcome_path.trace_add("write", validate_fields)
        validate_fields()  # Initial state

        # Bind Enter key
        purpose_entry.bind("<Return>", lambda e: browse())
        path_entry.bind("<Return>", lambda e: on_create() if create_btn["state"] != "disabled" else None)

        # Data path hint at bottom
        tk.Label(
            form_frame,
            text=f"Data: {get_app_data_dir()}",
            font=("Consolas", 7),
            bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(side=tk.BOTTOM, pady=(12, 0))

    def _render(self):
        t = self.theme
        print(f"[DEBUG] _render called, agents_data count: {len(self.agents_data)}")

        # Clear
        for w in self.agents_frame.winfo_children():
            w.destroy()
        self.agent_cards.clear()

        # Update count with animation effect
        count = len(self.agents_data)
        self.count_lbl.configure(text=f"{count}")

        if not self.agents_data:
            # No agents - show inline creation form (setup mode - large window)
            print("[DEBUG] No agents, showing welcome form")
            self._render_welcome_form()
            return

        # Dashboard mode - restore card chrome, compact window
        print(f"[DEBUG] Has agents, switching to dashboard mode (current: {getattr(self, '_ui_mode', 'none')})")
        if not hasattr(self, '_ui_mode') or self._ui_mode != 'dashboard':
            self._ui_mode = 'dashboard'
            self.root.minsize(460, 400)

            # Unpack all card children first to reset order
            self.header.pack_forget()
            self.usage_bar.pack_forget()
            self.sep.pack_forget()
            self.agents_frame.pack_forget()
            if hasattr(self, 'worktree_sep') and self.worktree_sep:
                self.worktree_sep.pack_forget()
            if self.worktree_panel:
                self.worktree_panel.pack_forget()
            self.footer.pack_forget()

            # Repack in correct order
            self.header.pack(fill=tk.X, pady=(0, 8))
            self.usage_bar.pack(fill=tk.X, pady=(4, 0))
            self.sep.pack(fill=tk.X, pady=(4, 8))
            self.agents_frame.pack(fill=tk.BOTH, expand=True)
            # Worktree panel below agents (if available)
            if hasattr(self, 'worktree_sep') and self.worktree_sep:
                self.worktree_sep.pack(fill=tk.X, pady=(4, 4))
            if self.worktree_panel:
                self.worktree_panel.pack(fill=tk.X, pady=(0, 4))
            self.footer.pack(fill=tk.X, pady=(4, 0))

            # Restore card - fill entire window (no empty space)
            self.card.pack_forget()
            self.card.configure(width=0)  # Remove fixed width
            self.card.pack(fill=tk.BOTH, expand=True)

            # Compact window for dashboard
            self.root.geometry("460x420")

        # Render cards
        cols = 2 if count > 1 else 1

        for i, agent in enumerate(self.agents_data):
            row, col = divmod(i, cols)

            card = AgentCard(
                self.agents_frame,
                agent_data=agent,
                theme=t,
                on_click=self._show_settings,
                on_toggle=self._toggle_agent,
                on_name_change=self._sync_settings_panel  # Sync panel only, no card rebuild
            )
            card.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            self.agent_cards.append(card)

        for c in range(cols):
            self.agents_frame.columnconfigure(c, weight=1)

    def _sync_settings_panel(self):
        """Sync settings panel with current card data (no full reload)."""
        if not self.settings_visible or not self.settings_panel.agent_data:
            return

        selected_id = self.settings_panel.agent_data.get("id")
        if not selected_id:
            return

        # Find updated data from cards (they already have fresh data)
        for card in self.agent_cards:
            if card.agent_data.get("id") == selected_id:
                callbacks = {
                    "configure": self._configure_claude,
                    "memory": self._open_memory_viewer,
                    "restart_memory": self._restart_memory,
                    "proxy": self._configure_proxy,
                    "logs": self._view_logs,
                    "delete": self._delete_agent,
                    "refresh": lambda _: self._load_agents(),
                }
                self.settings_panel.show(card.agent_data, callbacks)
                break

    def _create_agent(self):
        """Show themed dialog to create new agent.

        Auto-sizing enabled for DPI/scaling support:
        - Minimum size 380x260 ensures buttons visible
        - Content can grow beyond minimum on high DPI (125-200%)
        - Create button disabled until fields filled
        - Works correctly on all Windows scaling settings
        """
        from tkinter import filedialog
        import subprocess

        t = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title("New Agent")
        dialog.configure(bg=t["bg"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Set title bar color
        dialog.after(50, lambda: set_title_bar_color(dialog, self.is_dark))

        # Main frame - auto-adjusts to content
        frame = tk.Frame(dialog, bg=t["card_bg"], padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Title
        tk.Label(
            frame, text="Create New Agent",
            font=("Segoe UI Semibold", 12),
            bg=t["card_bg"], fg=t["fg"]
        ).pack(anchor="w")

        # Purpose input
        tk.Label(
            frame, text="Purpose",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(12, 2))

        purpose_var = tk.StringVar()
        purpose_entry = tk.Entry(
            frame, textvariable=purpose_var,
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0,
            width=35  # Minimum width in characters
        )
        purpose_entry.pack(fill=tk.X, ipady=6)
        purpose_entry.focus_set()

        # Project path
        tk.Label(
            frame, text="Project Directory",
            font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(anchor="w", pady=(12, 2))

        path_frame = tk.Frame(frame, bg=t["card_bg"])
        path_frame.pack(fill=tk.X)

        path_var = tk.StringVar()
        path_entry = tk.Entry(
            path_frame, textvariable=path_var,
            font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat", bd=0
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        def browse():
            p = filedialog.askdirectory(parent=dialog)
            if p:
                path_var.set(p)

        browse_btn = tk.Label(
            path_frame, text="...",
            font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            cursor="hand2", padx=10
        )
        browse_btn.pack(side=tk.RIGHT, ipady=5)
        browse_btn.bind("<Button-1>", lambda e: browse())

        # Hint label - helps user understand what to fill
        hint_label = tk.Label(
            frame, text="Fill Purpose and Project Directory",
            font=("Segoe UI", 8),
            bg=t["card_bg"], fg=t["fg_dim"],
            anchor="w"
        )
        hint_label.pack(fill=tk.X, pady=(8, 0))

        # Buttons - packed at bottom (sticky)
        btn_frame = tk.Frame(frame, bg=t["card_bg"])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))

        def on_create():
            purpose = purpose_var.get().strip()
            project = path_var.get().strip()
            if not purpose or not project:
                return
            dialog.destroy()

            if HAS_BACKEND:
                try:
                    # Create without browser by default
                    manager.create_agent(
                        purpose=purpose,
                        project_path=project,
                        use_browser=False,
                    )
                except Exception as e:
                    print(f"Create agent error: {e}")

            self.root.after(1500, self._load_agents)

        cancel_btn = AnimatedButton(
            btn_frame, text="Cancel",
            command=dialog.destroy,
            theme=t, style="default",
            font_size=9, padx=16, pady=4
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

        create_btn = AnimatedButton(
            btn_frame, text="Create",
            command=on_create,
            theme=t, style="primary",
            font_size=9, padx=16, pady=4
        )
        create_btn.pack(side=tk.RIGHT)

        # Validation: Create enabled only if both fields filled
        def validate_fields(*args):
            is_valid = bool(purpose_var.get().strip() and path_var.get().strip())
            create_btn.configure(state="normal" if is_valid else "disabled")

        purpose_var.trace_add("write", validate_fields)
        path_var.trace_add("write", validate_fields)
        validate_fields()  # Initial state

        # Enter key to create
        dialog.bind("<Return>", lambda e: on_create())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        # Auto-size and center after all widgets are packed
        # Minimum 380x260 ensures Create/Cancel visible even on standard DPI
        # Content can grow beyond minimum on high DPI (125-200%)
        dialog.update_idletasks()
        req_w = dialog.winfo_reqwidth()
        req_h = dialog.winfo_reqheight()
        w = max(380, req_w)
        h = max(260, req_h)
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.minsize(w, h)

    def _show_settings(self, agent_data: Dict):
        callbacks = {
            "configure": self._configure_claude,
            "memory": self._open_memory_viewer,
            "restart_memory": self._restart_memory,
            "proxy": self._configure_proxy,
            "logs": self._view_logs,
            "delete": self._delete_agent,
            "refresh": lambda _: self._load_agents(),  # Refresh on name change
        }
        self.settings_panel.show(agent_data, callbacks)
        self._slide_in_settings()

    def _slide_in_settings(self):
        if self.settings_visible:
            return
        self.settings_visible = True

        panel_width = 200
        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        self._base_width = cur_w  # Remember original width

        # Make card fixed width when panel opens
        self.card.pack_forget()
        self.card.configure(width=420)
        self.card.pack(side=tk.LEFT, fill=tk.Y, expand=False)

        # Expand window to the right
        new_width = 420 + panel_width + 30  # card + panel + padding
        self.root.geometry(f"{new_width}x{cur_h}")
        self.root.update_idletasks()

        # Pack settings panel on the right
        main_h = self.main.winfo_height()
        self.settings_panel.place(
            x=430, y=0,  # Right after card
            width=panel_width - 10, height=main_h
        )

    def _close_settings(self):
        if not self.settings_visible:
            return
        self.settings_visible = False

        # Hide panel
        self.settings_panel.place_forget()

        # Restore card to fill entire window
        self.card.pack_forget()
        self.card.configure(width=0)
        self.card.pack(fill=tk.BOTH, expand=True)

        # Restore compact window size
        cur_h = self.root.winfo_height()
        self.root.geometry(f"{self._base_width}x{cur_h}")

    def _show_terminal(self, agent_data: Dict):
        """Show embedded terminal for the agent."""
        if self.terminal_visible:
            # Already visible - just switch agent
            self.terminal_panel.show(agent_data)
            return

        self.terminal_visible = True

        # Close settings panel if open
        if self.settings_visible:
            self.settings_panel.place_forget()
            self.settings_visible = False

        # Calculate terminal size - expand window downward
        term_height = 350
        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        self._base_height = cur_h  # Remember original height

        # Expand window downward
        self.root.geometry(f"{cur_w}x{cur_h + term_height}")
        self.root.update_idletasks()

        # Place terminal panel at bottom
        main_w = self.main.winfo_width()
        self.terminal_panel.place(
            x=0, y=cur_h - 18,  # Below existing content
            width=main_w, height=term_height
        )

        # Start terminal with agent
        self.terminal_panel.show(agent_data)

    def _close_terminal(self):
        """Close embedded terminal."""
        if not self.terminal_visible:
            return
        self.terminal_visible = False

        # Stop terminal
        self.terminal_panel.stop()
        self.terminal_panel.place_forget()

        # Restore original height
        cur_w = self.root.winfo_width()
        self.root.geometry(f"{cur_w}x{self._base_height}")

    def _open_terminal_window(self, agent_data: Dict):
        """Open a separate terminal window for the agent."""
        agent_id = agent_data["id"]

        # Check if window already exists
        if agent_id in self._terminal_windows:
            win = self._terminal_windows[agent_id]
            if win.winfo_exists():
                win.lift()
                win.focus_force()
                return
            else:
                del self._terminal_windows[agent_id]

        t = self.theme
        name = agent_data.get("display_name") or agent_data.get("purpose", agent_id[:8])

        # Create window
        win = tk.Toplevel(self.root)
        win.title(f"Claude: {name}")
        win.configure(bg=t["bg"])
        win.geometry("900x600")

        # Dark title bar on Windows
        self.root.after(50, lambda: set_title_bar_color(win, self.is_dark))

        # Terminal theme
        term_theme = {
            "bg": t["bg"],
            "fg": t["fg"],
            "cursor": t["accent"],
            "selection": t.get("selection", "#264f78"),
        }

        # Create terminal widget
        terminal = TerminalWidget(
            win,
            theme=term_theme,
            font_family="Consolas",
            font_size=11,
            scrollback=10000,
            on_exit=lambda code: self._on_terminal_window_exit(agent_id, code)
        )
        terminal.pack(fill=tk.BOTH, expand=True)

        # Start Claude CLI
        project_path = agent_data.get("project_path", ".")
        port = agent_data.get("port", 3100)

        import os
        env = {**os.environ, "CLAUDE_MEM_WORKER_PORT": str(port)}

        terminal.start(
            cmd=["claude"],
            cwd=project_path,
            env=env
        )

        # Store reference
        self._terminal_windows[agent_id] = win
        win._terminal = terminal  # Keep reference for cleanup

        # Handle window close
        def on_close():
            terminal.stop()
            win.destroy()
            if agent_id in self._terminal_windows:
                del self._terminal_windows[agent_id]

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _on_terminal_window_exit(self, agent_id: str, exit_code: int):
        """Handle terminal process exit in separate window."""
        # Process exited, window stays open to see output
        pass

    def _close_terminal_window(self, agent_id: str):
        """Close terminal window for agent."""
        # Close old-style terminal windows
        if hasattr(self, "_terminal_windows") and agent_id in self._terminal_windows:
            win = self._terminal_windows[agent_id]
            if win.winfo_exists():
                if hasattr(win, '_terminal'):
                    win._terminal.stop()
                win.destroy()
            del self._terminal_windows[agent_id]

        # Close embedded console windows
        if hasattr(self, "_agent_windows") and agent_id in self._agent_windows:
            win = self._agent_windows[agent_id]
            try:
                if win.winfo_exists():
                    win.destroy()
            except:
                pass
            del self._agent_windows[agent_id]

    def _toggle_agent(self, agent_id: str, current_status: str):
        if current_status == "online":
            self._stop_agent(agent_id)
        else:
            self._start_agent(agent_id)

    def _start_agent(self, agent_id: str):
        # Lock to prevent double-starts - ADD LOCK FIRST
        if not hasattr(self, "_starting_agents"):
            self._starting_agents = set()

        if agent_id in self._starting_agents:
            print(f"Agent {agent_id} is already starting...")
            return

        # Add lock IMMEDIATELY before any other checks
        self._starting_agents.add(agent_id)

        if not HAS_BACKEND:
            self._starting_agents.discard(agent_id)
            for a in self.agents_data:
                if a["id"] == agent_id:
                    a["status"] = "online"
            self._render()
            return

        # Find agent config
        agent_data = None
        for a in self.agents_data:
            if a["id"] == agent_id:
                agent_data = a
                break

        if not agent_data:
            print(f"Agent not found: {agent_id}")
            self._starting_agents.discard(agent_id)
            return

        # Check if agent is already running (has an open window)
        if hasattr(self, "_agent_windows") and agent_id in self._agent_windows:
            existing_window = self._agent_windows[agent_id]
            try:
                if existing_window.winfo_exists():
                    # Window exists - bring to front instead of creating new
                    existing_window.lift()
                    existing_window.focus_force()
                    self._starting_agents.discard(agent_id)
                    return
                else:
                    # Window was destroyed externally - clean up
                    del self._agent_windows[agent_id]
            except:
                # Window reference invalid - clean up
                del self._agent_windows[agent_id]

        # Check if already marked as online (prevent double-click race)
        if agent_data.get("status") == "online":
            print(f"Agent {agent_id} already running")
            self._starting_agents.discard(agent_id)
            return

        # Use embedded console if available
        if HAS_EMBEDDED_CONSOLE and create_agent_window:
            try:
                # Get working directory from agent config (project_path is the key!)
                cwd = agent_data.get("project_path", os.path.expanduser("~"))
                if not cwd or not os.path.isdir(cwd):
                    cwd = os.path.expanduser("~")

                # Build command
                cmd = "claude"

                # Create embedded console window
                theme = {
                    "bg": "#1e1e1e",
                    "fg": "#d4d4d4",
                    "accent": "#0078d4",
                    "button_bg": "#2d2d2d",
                    "button_hover": "#3d3d3d",
                }

                # Callback when window closes
                def on_window_closed(aid=agent_id):
                    # Update status to offline
                    for a in self.agents_data:
                        if a["id"] == aid:
                            a["status"] = "offline"
                    # Remove from tracked windows
                    if hasattr(self, "_agent_windows") and aid in self._agent_windows:
                        del self._agent_windows[aid]
                    # Re-render
                    self._render()

                window = create_agent_window(
                    agent_id=agent_id,
                    agent_name=agent_data.get("name", agent_id),
                    cmd=cmd,
                    cwd=cwd,
                    theme=theme,
                    on_window_close=on_window_closed,
                )

                # Track window
                if not hasattr(self, "_agent_windows"):
                    self._agent_windows = {}
                self._agent_windows[agent_id] = window

                # Update status
                for a in self.agents_data:
                    if a["id"] == agent_id:
                        a["status"] = "online"
                self._render()

                # Release lock
                self._starting_agents.discard(agent_id)
                # Don't call _load_agents - embedded console manages its own state
                return

            except Exception as e:
                # Release lock on error
                self._starting_agents.discard(agent_id)
                import traceback
                print(f"Embedded console error: {e}")
                traceback.print_exc()
                # Fallback to standard cmd (lock already released)
                try:
                    manager.start_agent(agent_id)
                except Exception as e2:
                    print(f"Start error: {e2}")
                # Don't re-add lock - it's released
        else:
            # Fallback to standard cmd window
            try:
                manager.start_agent(agent_id)
            except Exception as e:
                print(f"Start error: {e}")
            finally:
                self._starting_agents.discard(agent_id)

        # Only reload from manager for non-embedded consoles
        self.root.after(500, self._load_agents)

    def _stop_agent(self, agent_id: str):
        # Close our terminal window if open
        self._close_terminal_window(agent_id)

        # Close session memory for this agent
        self._close_agent_memory(agent_id)

        if not HAS_BACKEND:
            for a in self.agents_data:
                if a["id"] == agent_id:
                    a["status"] = "offline"
            self._render()
            return

        try:
            manager.stop_agent(agent_id)
        except Exception as e:
            print(f"Stop error: {e}")

        self.root.after(500, self._load_agents)

    def _close_agent_memory(self, agent_id: str):
        """Close memory instances for a specific agent."""
        # Close session memory
        if agent_id in self._open_session_memories:
            try:
                self._open_session_memories[agent_id].close()
                print(f"[MEMORY] Closed SessionMemory for {agent_id}")
            except Exception as e:
                print(f"[MEMORY] Error closing SessionMemory for {agent_id}: {e}")
            finally:
                del self._open_session_memories[agent_id]

        # Close graph memory
        if agent_id in self._open_graph_memories:
            try:
                self._open_graph_memories[agent_id].close()
                print(f"[MEMORY] Closed GraphMemory for {agent_id}")
            except Exception as e:
                print(f"[MEMORY] Error closing GraphMemory for {agent_id}: {e}")
            finally:
                del self._open_graph_memories[agent_id]

    def _close_all_memories(self):
        """Close all open memory instances."""
        print("[MEMORY] Closing all memory instances...")

        # Close all session memories
        for agent_id in list(self._open_session_memories.keys()):
            try:
                self._open_session_memories[agent_id].close()
                print(f"[MEMORY] Closed SessionMemory for {agent_id}")
            except Exception as e:
                print(f"[MEMORY] Error closing SessionMemory for {agent_id}: {e}")
        self._open_session_memories.clear()

        # Close all graph memories
        for agent_id in list(self._open_graph_memories.keys()):
            try:
                self._open_graph_memories[agent_id].close()
                print(f"[MEMORY] Closed GraphMemory for {agent_id}")
            except Exception as e:
                print(f"[MEMORY] Error closing GraphMemory for {agent_id}: {e}")
        self._open_graph_memories.clear()

        print("[MEMORY] All memory instances closed")

    def _on_app_close(self):
        """Handle application close - cleanup all resources."""
        print("[SHUTDOWN] Dashboard closing...")

        # Close all terminal windows
        for agent_id in list(self._terminal_windows.keys()):
            try:
                self._close_terminal_window(agent_id)
            except Exception as e:
                print(f"[SHUTDOWN] Error closing terminal for {agent_id}: {e}")

        # Close all memory instances
        self._close_all_memories()

        # Cleanup hotkeys
        if HAS_TILING and hasattr(self, '_hotkey_manager') and self._hotkey_manager:
            try:
                self._hotkey_manager.stop()
                print("[SHUTDOWN] Hotkey manager stopped")
            except Exception as e:
                print(f"[SHUTDOWN] Error stopping hotkey manager: {e}")

        print("[SHUTDOWN] Cleanup complete, destroying window")
        self.root.destroy()

    def _tile_agent_windows(self, layout: str = "smart"):
        """Tile all open agent windows."""
        if not HAS_TILING:
            print("Tiling not available")
            return

        # Get all open embedded windows
        if not hasattr(self, "_agent_windows"):
            print("No agent windows open")
            return

        hwnds = []
        for agent_id, window in list(self._agent_windows.items()):
            try:
                if window.winfo_exists():
                    # Get the HWND of the Toplevel window
                    hwnd = int(window.wm_frame(), 16)
                    if hwnd:
                        hwnds.append(hwnd)
            except Exception as e:
                print(f"Error getting hwnd for {agent_id}: {e}")

        if not hwnds:
            print("No windows to tile")
            return

        # Get settings for layout and gap
        from claude_agent_manager import settings as app_settings
        settings = app_settings.get_settings()
        gap = getattr(settings, 'tile_gap', 8)

        # Tile windows
        tile_windows(hwnds, layout=layout, gap=gap)
        print(f"Tiled {len(hwnds)} windows with layout '{layout}'")

    def _focus_agent_window(self, index: int):
        """Focus agent window by index (0-based)."""
        if not hasattr(self, "_agent_windows") or not self._agent_windows:
            return

        windows = list(self._agent_windows.values())
        if index >= len(windows):
            return

        try:
            window = windows[index]
            if window.winfo_exists():
                window.deiconify()  # Restore if minimized
                window.lift()
                window.focus_force()
        except Exception as e:
            print(f"Focus error: {e}")

    def _minimize_agent_windows(self):
        """Minimize all open agent windows."""
        if not hasattr(self, "_agent_windows"):
            return

        for agent_id, window in list(self._agent_windows.items()):
            try:
                if window.winfo_exists():
                    window.iconify()  # Minimize
            except Exception as e:
                print(f"Minimize error for {agent_id}: {e}")

        print(f"Minimized {len(self._agent_windows)} agent windows")

    # Settings actions
    def _configure_claude(self, agent: Dict):
        """Open Claude Code configuration dialog."""
        def on_config_save(agent_id: str, config: Optional[Any]):
            if config and HAS_BACKEND:
                try:
                    # Update agent record with new config
                    from claude_agent_manager.registry import load_agent, save_agent
                    agent_root = manager.get_agent_root()
                    rec = load_agent(agent_root, agent_id)
                    updated = rec.model_copy()
                    updated.config = config
                    save_agent(agent_root, updated)

                    # Regenerate run.cmd with new env vars
                    agent_dir = agent_root / agent_id
                    from claude_agent_manager.manager import _write_run_cmd
                    title = f"{rec.purpose} | :{rec.port}"
                    _write_run_cmd(
                        agent_dir, title=title, port=rec.port,
                        data_dir=agent_dir, project_path=Path(rec.project_path),
                        proxy=rec.proxy, config=config
                    )
                except Exception as e:
                    print(f"Config save error: {e}")
                    import traceback
                    traceback.print_exc()
            # Refresh cards to show updated autopilot badge
            self._load_agents()

        AgentConfigDialog(self.root, agent, self.theme, on_config_save)

    def _open_memory_viewer(self, agent: Dict):
        if HAS_BACKEND:
            try:
                manager.open_viewer(agent["id"])
            except Exception as e:
                print(f"Open viewer error: {e}")
                import webbrowser
                webbrowser.open(f"http://localhost:{agent['port']}")
        else:
            import webbrowser
            webbrowser.open(f"http://localhost:{agent['port']}")

    def _restart_memory(self, agent: Dict):
        if HAS_BACKEND:
            try:
                pm2_restart(agent["pm2_name"])
            except Exception as e:
                print(f"Restart error: {e}")
        self.root.after(500, self._load_agents)

    def _configure_proxy(self, agent: Dict):
        """Show proxy settings dialog for agent."""
        try:
            self._show_proxy_dialog(agent)
        except Exception as e:
            print(f"Proxy dialog error: {e}")
            import traceback
            traceback.print_exc()

    def _show_proxy_dialog(self, agent: Dict):
        """Internal proxy dialog."""
        t = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title("Proxy Settings")
        dialog.configure(bg=t["card_bg"])
        dialog.geometry("320x360")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 320) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 360) // 2
        dialog.geometry(f"+{x}+{y}")

        # Get current proxy config
        proxy_data = agent.get("proxy", {})
        enabled = proxy_data.get("enabled", False)
        proxy_type = proxy_data.get("type", "http")
        host = proxy_data.get("host", "")
        port = proxy_data.get("port", "")
        username = proxy_data.get("username", "")
        password = proxy_data.get("password", "")

        # Form
        form = tk.Frame(dialog, bg=t["card_bg"])
        form.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Enable toggle row
        enable_frame = tk.Frame(form, bg=t["card_bg"])
        enable_frame.pack(fill=tk.X, pady=(0, 12))

        enabled_var = tk.BooleanVar(value=enabled)
        tk.Label(
            enable_frame, text="Enable Proxy",
            font=("Segoe UI", 9), bg=t["card_bg"], fg=t["fg"]
        ).pack(side=tk.LEFT)

        # Simple toggle indicator
        toggle_lbl = tk.Label(
            enable_frame,
            text="ON" if enabled else "OFF",
            font=("Segoe UI", 8),
            bg=t["accent"] if enabled else t["btn_bg"],
            fg="#fff" if enabled else t["fg_dim"],
            padx=8, pady=2, cursor="hand2"
        )
        toggle_lbl.pack(side=tk.RIGHT)

        def toggle_proxy():
            new_val = not enabled_var.get()
            enabled_var.set(new_val)
            toggle_lbl.configure(
                text="ON" if new_val else "OFF",
                bg=t["accent"] if new_val else t["btn_bg"],
                fg="#fff" if new_val else t["fg_dim"]
            )
        toggle_lbl.bind("<Button-1>", lambda e: toggle_proxy())

        # Type
        tk.Label(
            form, text="Type", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 2))

        type_var = tk.StringVar(value=proxy_type)
        type_frame = tk.Frame(form, bg=t["btn_bg"])
        type_frame.pack(fill=tk.X, pady=(0, 8))

        for ptype in ["http", "https", "socks5"]:
            btn = tk.Label(
                type_frame, text=ptype.upper(),
                font=("Segoe UI", 8),
                bg=t["accent"] if proxy_type == ptype else t["btn_bg"],
                fg="#fff" if proxy_type == ptype else t["fg"],
                padx=10, pady=4, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 1))

            def select_type(p=ptype, b=btn):
                type_var.set(p)
                for child in type_frame.winfo_children():
                    child.configure(bg=t["btn_bg"], fg=t["fg"])
                b.configure(bg=t["accent"], fg="#fff")

            btn.bind("<Button-1>", lambda e, p=ptype, b=btn: select_type(p, b))

        # Host
        tk.Label(
            form, text="Host", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 2))

        host_entry = tk.Entry(
            form, font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=0
        )
        host_entry.insert(0, host or "")
        host_entry.pack(fill=tk.X, ipady=6, pady=(0, 8))

        # Port
        tk.Label(
            form, text="Port", font=("Segoe UI", 9),
            bg=t["card_bg"], fg=t["fg_dim"], anchor="w"
        ).pack(fill=tk.X, pady=(0, 2))

        port_entry = tk.Entry(
            form, font=("Segoe UI", 10),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=0
        )
        port_entry.insert(0, str(port) if port else "")
        port_entry.pack(fill=tk.X, ipady=6, pady=(0, 8))

        # Auth section (collapsible feel)
        auth_header = tk.Frame(form, bg=t["card_bg"])
        auth_header.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            auth_header, text="Authentication (optional)",
            font=("Segoe UI", 8), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        # Username & Password in row
        auth_frame = tk.Frame(form, bg=t["card_bg"])
        auth_frame.pack(fill=tk.X)

        user_entry = tk.Entry(
            auth_frame, font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=0, width=14
        )
        user_entry.insert(0, username or "")
        user_entry.pack(side=tk.LEFT, ipady=5, padx=(0, 4), expand=True, fill=tk.X)

        pass_entry = tk.Entry(
            auth_frame, font=("Segoe UI", 9),
            bg=t["btn_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=0, width=14, show="•"
        )
        pass_entry.insert(0, password or "")
        pass_entry.pack(side=tk.LEFT, ipady=5, expand=True, fill=tk.X)

        # Hint
        tk.Label(
            form, text="Applies on agent restart",
            font=("Segoe UI", 7), bg=t["card_bg"], fg=t["fg_dim"]
        ).pack(pady=(8, 0))

        # Buttons
        btn_frame = tk.Frame(dialog, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 16))

        def on_save():
            from claude_agent_manager.registry import ProxyConfig
            port_val = port_entry.get().strip()
            new_proxy = ProxyConfig(
                enabled=enabled_var.get(),
                type=type_var.get(),
                host=host_entry.get().strip() or None,
                port=int(port_val) if port_val.isdigit() else None,
                username=user_entry.get().strip() or None,
                password=pass_entry.get().strip() or None,
            )
            if HAS_BACKEND:
                try:
                    manager.update_proxy(agent["id"], new_proxy)
                except Exception as e:
                    print(f"Proxy update error: {e}")
            dialog.destroy()
            self._load_agents()

        save_btn = AnimatedButton(
            btn_frame, text="Save",
            command=on_save,
            theme=t, style="primary",
            font_size=9, padx=20, pady=6
        )
        save_btn.pack(side=tk.RIGHT)

        cancel_btn = AnimatedButton(
            btn_frame, text="Cancel",
            command=dialog.destroy,
            theme=t, style="secondary",
            font_size=9, padx=16, pady=6
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 8))

        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def _view_logs(self, agent: Dict):
        if HAS_BACKEND:
            try:
                import subprocess
                subprocess.Popen(
                    ["cmd", "/c", "start", "cmd", "/k", f"pm2 logs {agent['pm2_name']}"],
                    shell=True
                )
            except Exception as e:
                print(f"Logs error: {e}")

    def _delete_agent(self, agent: Dict):
        if HAS_BACKEND:
            try:
                manager.delete_agent(agent["id"])
            except Exception as e:
                print(f"Delete error: {e}")
        self._close_settings()
        self.root.after(500, self._load_agents)


# ═══════════════════════════════════════════════════════════════════════════════
# LAUNCH
# ═══════════════════════════════════════════════════════════════════════════════

def launch_dashboard() -> None:
    # Ensure app directories exist
    ensure_app_dirs()

    # Set AppUserModelID for Windows taskbar icon
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.claude.agentmanager")
        except Exception:
            pass

    root = tk.Tk()

    # Set app icon - use .ico for Windows taskbar, .png as fallback
    if sys.platform == "win32":
        ico_path = get_asset_path("icon.ico")
        if ico_path.exists():
            try:
                root.iconbitmap(str(ico_path))
            except Exception:
                pass
    # Fallback to PNG for other platforms or if ico fails
    png_path = get_asset_path("icon.png")
    if png_path.exists():
        try:
            icon = tk.PhotoImage(file=str(png_path))
            root.iconphoto(True, icon)
        except Exception:
            pass

    width, height = 460, 400
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(380, 380)

    AgentDashboard(root)

    root.lift()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))
    root.mainloop()


if __name__ == "__main__":
    launch_dashboard()
