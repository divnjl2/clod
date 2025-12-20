"""
Floating overlay для отображения метрик агентов.

Компактный, неинтрузивный виджет который показывает:
- Статус агентов
- Текущие действия
- Использование токенов
- Системные метрики
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Callable, List
from datetime import datetime, timedelta

from .monitoring import AgentMetrics, get_monitoring_service, MonitoringService
from .custom_hotkeys import get_custom_hotkey_manager, HotkeyAction


# ============================================================================
# THEMES
# ============================================================================

OVERLAY_THEMES = {
    "dark": {
        "bg": "#1a1a1aee",  # Semi-transparent
        "card_bg": "#252525",
        "fg": "#e8e8e8",
        "fg_dim": "#888",
        "accent": "#4a9eff",
        "success": "#4ade80",
        "warning": "#fbbf24",
        "error": "#f87171",
        "border": "#333",
    },
    "light": {
        "bg": "#f0f0f0ee",
        "card_bg": "#ffffff",
        "fg": "#1a1a1a",
        "fg_dim": "#666",
        "accent": "#2563eb",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#dc2626",
        "border": "#ddd",
    }
}


# ============================================================================
# OVERLAY WIDGET
# ============================================================================

class MetricsOverlay:
    """
    Floating overlay с метриками агентов.

    Особенности:
    - Always on top
    - Draggable
    - Collapsible
    - Semi-transparent
    - Автообновление
    """

    def __init__(
        self,
        theme: str = "dark",
        position: str = "top-right",  # top-left, top-right, bottom-left, bottom-right
        width: int = 280,
        update_interval: int = 2000,  # ms
    ):
        self.theme_name = theme
        self.theme = OVERLAY_THEMES[theme]
        self.position = position
        self.width = width
        self.update_interval = update_interval

        self._root: Optional[tk.Toplevel] = None
        self._visible = False
        self._collapsed = False
        self._agent_frames: Dict[str, tk.Frame] = {}
        self._monitoring: Optional[MonitoringService] = None

        # Dragging state
        self._drag_start_x = 0
        self._drag_start_y = 0

    def create(self, parent: Optional[tk.Tk] = None) -> tk.Toplevel:
        """Создать окно overlay."""
        if parent:
            self._root = tk.Toplevel(parent)
        else:
            self._root = tk.Toplevel()

        self._setup_window()
        self._create_ui()
        self._position_window()

        # Start monitoring
        self._monitoring = get_monitoring_service()
        self._monitoring.add_callback(self._on_metrics_update)
        self._monitoring.start()

        # Schedule updates
        self._schedule_update()

        return self._root

    def show(self) -> None:
        """Показать overlay."""
        if self._root:
            self._root.deiconify()
            self._root.lift()
            self._visible = True

    def hide(self) -> None:
        """Скрыть overlay."""
        if self._root:
            self._root.withdraw()
            self._visible = False

    def toggle(self) -> None:
        """Переключить видимость."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def destroy(self) -> None:
        """Уничтожить overlay."""
        if self._monitoring:
            self._monitoring.stop()
        if self._root:
            self._root.destroy()
            self._root = None

    def _setup_window(self) -> None:
        """Настроить параметры окна."""
        self._root.overrideredirect(True)  # No title bar
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.95)

        # Transparent background (Windows)
        try:
            self._root.wm_attributes("-transparentcolor", "")
        except:
            pass

        self._root.configure(bg=self.theme["bg"])

    def _create_ui(self) -> None:
        """Создать UI."""
        t = self.theme

        # Main container with border
        main = tk.Frame(
            self._root,
            bg=t["bg"],
            highlightbackground=t["border"],
            highlightthickness=1
        )
        main.pack(fill=tk.BOTH, expand=True)

        # Header (draggable)
        header = tk.Frame(main, bg=t["card_bg"], height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Drag bindings
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._do_drag)

        # Title
        title = tk.Label(
            header,
            text="⚡ Agents",
            font=("Segoe UI", 9, "bold"),
            bg=t["card_bg"],
            fg=t["fg"],
            cursor="fleur"
        )
        title.pack(side=tk.LEFT, padx=8, pady=4)
        title.bind("<Button-1>", self._start_drag)
        title.bind("<B1-Motion>", self._do_drag)

        # Controls
        controls = tk.Frame(header, bg=t["card_bg"])
        controls.pack(side=tk.RIGHT, padx=4)

        # Collapse button
        self._collapse_btn = tk.Label(
            controls,
            text="−",
            font=("Segoe UI", 10),
            bg=t["card_bg"],
            fg=t["fg_dim"],
            cursor="hand2",
            padx=4
        )
        self._collapse_btn.pack(side=tk.LEFT)
        self._collapse_btn.bind("<Button-1>", lambda e: self._toggle_collapse())
        self._collapse_btn.bind("<Enter>", lambda e: self._collapse_btn.configure(fg=t["fg"]))
        self._collapse_btn.bind("<Leave>", lambda e: self._collapse_btn.configure(fg=t["fg_dim"]))

        # Close button
        close_btn = tk.Label(
            controls,
            text="×",
            font=("Segoe UI", 10),
            bg=t["card_bg"],
            fg=t["fg_dim"],
            cursor="hand2",
            padx=4
        )
        close_btn.pack(side=tk.LEFT)
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=t["error"]))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=t["fg_dim"]))

        # Content area
        self._content = tk.Frame(main, bg=t["bg"])
        self._content.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Footer with totals
        self._footer = tk.Frame(main, bg=t["card_bg"], height=24)
        self._footer.pack(fill=tk.X)
        self._footer.pack_propagate(False)

        self._total_label = tk.Label(
            self._footer,
            text="0 agents • 0 tokens",
            font=("Segoe UI", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self._total_label.pack(side=tk.LEFT, padx=8, pady=2)

    def _position_window(self) -> None:
        """Позиционировать окно."""
        self._root.update_idletasks()

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()

        # Margin from edges
        margin = 20

        if "right" in self.position:
            x = screen_w - self.width - margin
        else:
            x = margin

        if "bottom" in self.position:
            y = screen_h - 200 - margin  # Approximate height
        else:
            y = margin + 30  # Below taskbar

        self._root.geometry(f"{self.width}x200+{x}+{y}")

    def _start_drag(self, event) -> None:
        """Начать перетаскивание."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_drag(self, event) -> None:
        """Продолжить перетаскивание."""
        x = self._root.winfo_x() + event.x - self._drag_start_x
        y = self._root.winfo_y() + event.y - self._drag_start_y
        self._root.geometry(f"+{x}+{y}")

    def _toggle_collapse(self) -> None:
        """Свернуть/развернуть содержимое."""
        self._collapsed = not self._collapsed

        if self._collapsed:
            self._content.pack_forget()
            self._footer.pack_forget()
            self._collapse_btn.configure(text="+")
            self._root.geometry(f"{self.width}x28")
        else:
            self._content.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            self._footer.pack(fill=tk.X)
            self._collapse_btn.configure(text="−")
            self._root.geometry(f"{self.width}x200")

    def _schedule_update(self) -> None:
        """Запланировать следующее обновление."""
        if self._root:
            self._root.after(self.update_interval, self._schedule_update)

    def _on_metrics_update(self, all_metrics: Dict[str, AgentMetrics]) -> None:
        """Callback при обновлении метрик."""
        if not self._root or self._collapsed:
            return

        try:
            self._root.after(0, lambda: self._update_ui(all_metrics))
        except:
            pass

    def _update_ui(self, all_metrics: Dict[str, AgentMetrics]) -> None:
        """Обновить UI с новыми метриками."""
        t = self.theme

        # Clear old frames
        for frame in self._agent_frames.values():
            frame.destroy()
        self._agent_frames.clear()

        total_tokens = 0

        for agent_id, metrics in all_metrics.items():
            frame = self._create_agent_card(agent_id, metrics)
            self._agent_frames[agent_id] = frame
            total_tokens += metrics.session_tokens.total_tokens

        # Update footer
        agent_count = len(all_metrics)
        tokens_str = f"{total_tokens:,}" if total_tokens < 1000000 else f"{total_tokens/1000000:.1f}M"
        self._total_label.configure(text=f"{agent_count} agent{'s' if agent_count != 1 else ''} • {tokens_str} tokens")

    def _create_agent_card(self, agent_id: str, metrics: AgentMetrics) -> tk.Frame:
        """Создать карточку агента."""
        t = self.theme

        card = tk.Frame(self._content, bg=t["card_bg"])
        card.pack(fill=tk.X, pady=2)

        # Status indicator color
        status_colors = {
            "running": t["success"],
            "working": t["accent"],
            "idle": t["warning"],
            "stopped": t["fg_dim"],
            "error": t["error"],
        }
        status_color = status_colors.get(metrics.status, t["fg_dim"])

        # Header row
        header = tk.Frame(card, bg=t["card_bg"])
        header.pack(fill=tk.X, padx=6, pady=(4, 2))

        # Status dot
        status_dot = tk.Label(
            header,
            text="●",
            font=("Segoe UI", 8),
            bg=t["card_bg"],
            fg=status_color
        )
        status_dot.pack(side=tk.LEFT)

        # Agent name
        name = tk.Label(
            header,
            text=agent_id[:20],
            font=("Segoe UI", 9, "bold"),
            bg=t["card_bg"],
            fg=t["fg"]
        )
        name.pack(side=tk.LEFT, padx=(4, 0))

        # Status text
        status_text = tk.Label(
            header,
            text=metrics.status_detail[:25] if metrics.status_detail else metrics.status,
            font=("Segoe UI", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        status_text.pack(side=tk.RIGHT)

        # Metrics row
        metrics_frame = tk.Frame(card, bg=t["card_bg"])
        metrics_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

        # Tokens
        tokens = metrics.session_tokens.total_tokens
        tokens_str = f"{tokens:,}" if tokens < 10000 else f"{tokens/1000:.1f}k"
        tk.Label(
            metrics_frame,
            text=f"🎯 {tokens_str}",
            font=("Segoe UI", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        # Memory
        if metrics.system.memory_mb > 0:
            mem_str = f"{metrics.system.memory_mb:.0f}MB"
            tk.Label(
                metrics_frame,
                text=f"💾 {mem_str}",
                font=("Segoe UI", 8),
                bg=t["card_bg"],
                fg=t["fg_dim"]
            ).pack(side=tk.LEFT, padx=(8, 0))

        # Git branch
        if metrics.context.git_branch:
            branch = metrics.context.git_branch[:15]
            dirty = "•" if metrics.context.git_dirty else ""
            tk.Label(
                metrics_frame,
                text=f"⎇ {branch}{dirty}",
                font=("Segoe UI", 8),
                bg=t["card_bg"],
                fg=t["warning"] if metrics.context.git_dirty else t["fg_dim"]
            ).pack(side=tk.RIGHT)

        # Current action (if any)
        if metrics.current_action:
            action_frame = tk.Frame(card, bg=t["bg"])
            action_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

            action_icons = {
                "bash": "⚡",
                "edit": "✏️",
                "read": "📖",
                "write": "💾",
                "mcp": "🔌",
                "think": "🤔",
            }
            icon = action_icons.get(metrics.current_action.action_type, "▶")

            tk.Label(
                action_frame,
                text=f"{icon} {metrics.current_action.description[:40]}",
                font=("Segoe UI", 8),
                bg=t["bg"],
                fg=t["accent"]
            ).pack(side=tk.LEFT)

        return card


# ============================================================================
# QUICK STATUS BAR (Alternative simpler widget)
# ============================================================================

class QuickStatusBar:
    """
    Простая строка статуса в углу экрана.

    Показывает только:
    - Количество активных агентов
    - Общее использование токенов
    - Текущее действие (если есть)
    """

    def __init__(self, theme: str = "dark"):
        self.theme = OVERLAY_THEMES[theme]
        self._root: Optional[tk.Toplevel] = None
        self._label: Optional[tk.Label] = None
        self._visible = False

    def create(self, parent: Optional[tk.Tk] = None) -> tk.Toplevel:
        if parent:
            self._root = tk.Toplevel(parent)
        else:
            self._root = tk.Toplevel()

        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.85)
        self._root.configure(bg=self.theme["bg"])

        self._label = tk.Label(
            self._root,
            text="⚡ 0 agents",
            font=("Segoe UI", 9),
            bg=self.theme["bg"],
            fg=self.theme["fg"],
            padx=10,
            pady=4
        )
        self._label.pack()

        # Position in bottom-right
        self._root.update_idletasks()
        x = self._root.winfo_screenwidth() - 150
        y = self._root.winfo_screenheight() - 60
        self._root.geometry(f"+{x}+{y}")

        return self._root

    def update(self, text: str) -> None:
        if self._label:
            self._label.configure(text=text)

    def show(self) -> None:
        if self._root:
            self._root.deiconify()
            self._visible = True

    def hide(self) -> None:
        if self._root:
            self._root.withdraw()
            self._visible = False

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def create_overlay_with_hotkey(
    parent: tk.Tk,
    hotkey: str = "ctrl+alt+o",
    theme: str = "dark"
) -> MetricsOverlay:
    """
    Создать overlay с хоткеем для показа/скрытия.

    Args:
        parent: Родительское окно Tk
        hotkey: Хоткей для toggle
        theme: Тема (dark/light)

    Returns:
        MetricsOverlay instance
    """
    overlay = MetricsOverlay(theme=theme)
    overlay.create(parent)
    overlay.hide()  # Start hidden

    # Register hotkey
    manager = get_custom_hotkey_manager()
    manager.register_action(HotkeyAction.TOGGLE_OVERLAY, overlay.toggle)

    return overlay
