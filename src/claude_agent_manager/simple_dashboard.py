"""Modern minimalist Tkinter dashboard for Claude agents.

Compact card-based UI with smooth animations, theme toggle and agent settings.
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

# Import real agent registry if available
try:
    from .registry import iter_agents, AgentRecord, load_agent, save_agent
    from .config import load_config
    from .processes import pm2_stop, pm2_start_worker, pm2_status, spawn_browser, spawn_cmd, pm2_restart
    HAS_BACKEND = True
except ImportError:
    HAS_BACKEND = False


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
        self.purpose_lbl.configure(text=agent_data["purpose"])

        status = agent_data["status"]
        status_color = t["online"] if status == "online" else t["offline"]
        self.status_lbl.configure(text=f"● {status}", fg=status_color)

        # Clear old buttons
        for btn in self.action_buttons:
            btn.destroy()
        self.action_buttons.clear()

        # Create action buttons with emoji
        actions = [
            ("🧠  Memory Viewer", "memory"),
            ("🔄  Restart Memory", "restart_memory"),
            ("🌐  Open Browser", "browser"),
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
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.agent_data = agent_data
        self.theme = theme
        self.on_click_cb = on_click
        self.on_toggle_cb = on_toggle

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

        # Top row
        self.top = tk.Frame(self.left, bg=t["card_bg"])
        self.top.pack(anchor="w")

        self.status_dot = StatusDot(self.top, online=(status == "online"), theme=t)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        self.status_dot.configure(bg=t["card_bg"])

        short_id = agent["id"][:10] if len(agent["id"]) > 10 else agent["id"]
        self.id_lbl = tk.Label(self.top, text=short_id, font=("Segoe UI Semibold", 9), bg=t["card_bg"], fg=t["fg"])
        self.id_lbl.pack(side=tk.LEFT)

        # Purpose
        purpose = agent["purpose"][:22] + "..." if len(agent["purpose"]) > 22 else agent["purpose"]
        self.purpose_lbl = tk.Label(self.left, text=purpose, font=("Segoe UI", 8), bg=t["card_bg"], fg=t["fg_dim"])
        self.purpose_lbl.pack(anchor="w", pady=(1, 0))

        # Port
        self.port_lbl = tk.Label(self.left, text=f":{agent['port']}", font=("Consolas", 7), bg=t["card_bg"], fg=t["fg_dim"])
        self.port_lbl.pack(anchor="w")

        # Toggle button
        btn_style = "stop" if status == "online" else "start"
        btn_text = "Stop" if status == "online" else "Start"

        self.toggle_btn = AnimatedButton(
            self.content,
            text=btn_text,
            command=self._do_toggle,
            theme=t,
            style=btn_style,
            font_size=8,
            padx=8,
            pady=2,
            bg=t["card_bg"]  # Match parent bg to hide corners
        )
        self.toggle_btn.pack(side=tk.RIGHT, padx=(6, 0))

        self._widgets = [self.content, self.left, self.top, self.id_lbl, self.purpose_lbl, self.port_lbl]

    def _bind_events(self):
        for w in self._widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_card_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_card_click)

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

    def update_theme(self, theme: Dict):
        self.theme = theme
        t = theme
        # Update border
        self.configure(highlightbackground=t["border"])
        # Update all widgets
        bg = t["card_bg"]
        self.configure(bg=bg)
        self.content.configure(bg=bg)
        self.left.configure(bg=bg)
        self.top.configure(bg=bg)
        self.id_lbl.configure(bg=bg, fg=t["fg"])
        self.purpose_lbl.configure(bg=bg, fg=t["fg_dim"])
        self.port_lbl.configure(bg=bg, fg=t["fg_dim"])
        self.status_dot.configure(bg=bg)
        self.status_dot.update_theme(t)
        self.toggle_btn.update_theme(t)
        self.toggle_btn.set_bg(bg)


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
        self._theme_transition_step = 0

        self._build_ui()
        self._load_agents()
        self._schedule_refresh()

        # Set initial title bar color
        self.root.after(50, lambda: set_title_bar_color(self.root, self.is_dark))

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

        # Separator
        self.sep = tk.Frame(self.card, bg=t["separator"], height=1)
        self.sep.pack(fill=tk.X, pady=(0, 8))

        # Agents container - disable grid propagation
        self.agents_frame = tk.Frame(self.card, bg=t["card_bg"])
        self.agents_frame.pack(fill=tk.BOTH, expand=True)
        self.agents_frame.grid_propagate(False)

        # Settings panel (hidden) - disable propagation
        self.settings_panel = AgentSettingsPanel(
            self.main, theme=t, on_close=self._close_settings
        )
        self.settings_panel.pack_propagate(False)

    def _on_theme_toggle(self, is_dark: bool):
        self.is_dark = is_dark
        self.theme = THEMES["dark" if is_dark else "light"]

        # Apply all changes, let Tk batch them naturally
        self._apply_theme()
        self.root.after_idle(lambda: set_title_bar_color(self.root, is_dark))

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
        self.sep.configure(bg=t["separator"])
        self.agents_frame.configure(bg=t["card_bg"])

        # Update existing cards
        for card in self.agent_cards:
            card.update_theme(t)

        # Update settings panel
        self.settings_panel.update_theme(t)

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
        self.root.after(5000, self._schedule_refresh)

    def _refresh_agents(self):
        """Refresh agent data without full re-render if possible."""
        new_data = self._fetch_agents_data()

        # Check if data actually changed
        if self._data_equals(self.agents_data, new_data):
            return  # No changes, skip render

        self.agents_data = new_data
        self._render()

    def _data_equals(self, old: List[Dict], new: List[Dict]) -> bool:
        """Compare agent data lists."""
        if len(old) != len(new):
            return False
        for o, n in zip(old, new):
            if o.get("id") != n.get("id") or o.get("status") != n.get("status"):
                return False
        return True

    def _fetch_agents_data(self) -> List[Dict]:
        """Fetch current agents data."""
        data = []
        if HAS_BACKEND:
            try:
                cfg = load_config()
                agent_root = Path(cfg.agent_root)
                agents = iter_agents(agent_root)

                for agent in agents:
                    status = "offline"
                    try:
                        info = pm2_status(agent.pm2_name)
                        if info and info.get("status") == "online":
                            status = "online"
                    except:
                        pass

                    data.append({
                        "id": agent.id,
                        "purpose": agent.purpose,
                        "port": agent.port,
                        "status": status,
                        "pm2_name": agent.pm2_name,
                        "project_path": agent.project_path,
                        "use_browser": agent.use_browser,
                    })
            except:
                data = self._get_demo_data()
        else:
            data = self._get_demo_data()
        return data

    def _load_agents(self):
        """Full load (initial or forced)."""
        self.agents_data = self._fetch_agents_data()
        self._render()

    def _get_demo_data(self) -> List[Dict]:
        return [
            {"id": "kyc-proc-01", "purpose": "KYC Processing", "port": 37701, "status": "online", "pm2_name": "kyc-01", "use_browser": True},
            {"id": "order-mgr-02", "purpose": "Order Management", "port": 37702, "status": "offline", "pm2_name": "order-02", "use_browser": True},
            {"id": "pay-gate-03", "purpose": "Payment Gateway", "port": 37703, "status": "online", "pm2_name": "pay-03", "use_browser": False},
            {"id": "support-04", "purpose": "User Support", "port": 37704, "status": "offline", "pm2_name": "support-04", "use_browser": True},
        ]

    def _render(self):
        t = self.theme

        # Clear
        for w in self.agents_frame.winfo_children():
            w.destroy()
        self.agent_cards.clear()

        # Update count with animation effect
        count = len(self.agents_data)
        self.count_lbl.configure(text=f"{count}")

        if not self.agents_data:
            # No agents - show create button
            empty_frame = tk.Frame(self.agents_frame, bg=t["card_bg"])
            empty_frame.pack(expand=True, pady=20)

            tk.Label(
                empty_frame,
                text="No agents yet",
                font=("Segoe UI", 10),
                bg=t["card_bg"],
                fg=t["fg_dim"]
            ).pack(pady=(0, 8))

            create_btn = AnimatedButton(
                empty_frame,
                text="+ Create Agent",
                command=self._create_agent,
                theme=t,
                style="primary",
                font_size=10,
                padx=16,
                pady=6
            )
            create_btn.pack()
            return

        # Render cards
        cols = 2 if count > 1 else 1

        for i, agent in enumerate(self.agents_data):
            row, col = divmod(i, cols)

            card = AgentCard(
                self.agents_frame,
                agent_data=agent,
                theme=t,
                on_click=self._show_settings,
                on_toggle=self._toggle_agent
            )
            card.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            self.agent_cards.append(card)

        for c in range(cols):
            self.agents_frame.columnconfigure(c, weight=1)

    def _create_agent(self):
        """Show themed dialog to create new agent."""
        from tkinter import filedialog
        import subprocess

        t = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title("New Agent")
        dialog.configure(bg=t["bg"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        w, h = 340, 200
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # Set title bar color
        dialog.after(50, lambda: set_title_bar_color(dialog, self.is_dark))

        # Main frame
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
            relief="flat", bd=0
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

        # Buttons
        btn_frame = tk.Frame(frame, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        def on_create():
            purpose = purpose_var.get().strip()
            project = path_var.get().strip()
            if not purpose or not project:
                return
            dialog.destroy()

            cmd = f'cam new --purpose "{purpose}" --project "{project}"'
            subprocess.Popen(
                ["cmd.exe", "/k", cmd],
                creationflags=0x00000010
            )
            self.root.after(2000, self._load_agents)

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

        # Enter key to create
        dialog.bind("<Return>", lambda e: on_create())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def _show_settings(self, agent_data: Dict):
        callbacks = {
            "memory": self._open_memory_viewer,
            "restart_memory": self._restart_memory,
            "browser": self._open_browser,
            "proxy": self._configure_proxy,
            "logs": self._view_logs,
            "delete": self._delete_agent,
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

        # Expand window to the right
        self.root.geometry(f"{cur_w + panel_width}x{cur_h}")
        self.root.update_idletasks()

        # Place panel in the new space (right of fixed card)
        main_h = self.main.winfo_height()
        self.settings_panel.place(
            x=450, y=0,  # Right after card (440 + padding)
            width=panel_width - 10, height=main_h
        )

    def _close_settings(self):
        if not self.settings_visible:
            return
        self.settings_visible = False

        # Hide panel and restore original width
        self.settings_panel.place_forget()
        cur_h = self.root.winfo_height()
        self.root.geometry(f"{self._base_width}x{cur_h}")

    def _toggle_agent(self, agent_id: str, current_status: str):
        if current_status == "online":
            self._stop_agent(agent_id)
        else:
            self._start_agent(agent_id)

    def _start_agent(self, agent_id: str):
        if not HAS_BACKEND:
            for a in self.agents_data:
                if a["id"] == agent_id:
                    a["status"] = "online"
            self._render()
            return

        try:
            cfg = load_config()
            agent_root = Path(cfg.agent_root)
            agent = load_agent(agent_root, agent_id)

            from .worker import start_worker
            data_dir = agent_root / agent_id / "data"
            start_worker(cfg, agent.pm2_name, agent.port, data_dir)
            spawn_cmd(agent.project_path, agent.port)

            if agent.use_browser:
                spawn_browser(f"http://localhost:{agent.port}", cfg.browser, agent_id)
        except Exception as e:
            print(f"Start error: {e}")

        self.root.after(500, self._load_agents)

    def _stop_agent(self, agent_id: str):
        if not HAS_BACKEND:
            for a in self.agents_data:
                if a["id"] == agent_id:
                    a["status"] = "offline"
            self._render()
            return

        try:
            cfg = load_config()
            agent_root = Path(cfg.agent_root)
            agent = load_agent(agent_root, agent_id)
            pm2_stop(agent.pm2_name)
        except Exception as e:
            print(f"Stop error: {e}")

        self.root.after(500, self._load_agents)

    # Settings actions
    def _open_memory_viewer(self, agent: Dict):
        url = f"http://localhost:{agent['port']}"
        if HAS_BACKEND:
            try:
                cfg = load_config()
                spawn_browser(url, cfg.browser, agent["id"])
            except:
                import webbrowser
                webbrowser.open(url)
        else:
            import webbrowser
            webbrowser.open(url)

    def _restart_memory(self, agent: Dict):
        if HAS_BACKEND:
            try:
                pm2_restart(agent["pm2_name"])
            except Exception as e:
                print(f"Restart error: {e}")
        self.root.after(500, self._load_agents)

    def _open_browser(self, agent: Dict):
        self._open_memory_viewer(agent)

    def _configure_proxy(self, agent: Dict):
        print(f"Configure proxy for {agent['id']}")

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
                cfg = load_config()
                agent_root = Path(cfg.agent_root)
                pm2_stop(agent["pm2_name"])
                import shutil
                agent_dir = agent_root / agent["id"]
                if agent_dir.exists():
                    shutil.rmtree(agent_dir)
            except Exception as e:
                print(f"Delete error: {e}")
        self._close_settings()
        self.root.after(500, self._load_agents)


# ═══════════════════════════════════════════════════════════════════════════════
# LAUNCH
# ═══════════════════════════════════════════════════════════════════════════════

def launch_dashboard() -> None:
    root = tk.Tk()

    # Set app icon
    icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        try:
            icon = tk.PhotoImage(file=str(icon_path))
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
