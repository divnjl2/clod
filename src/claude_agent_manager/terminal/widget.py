"""
Tkinter Terminal Widget with full VT100 emulation.

Uses pyte for terminal emulation, pywinpty for PTY on Windows.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
import threading
import queue
import time
import signal
import sys
from typing import Dict, Optional, Callable, Tuple

import pyte

from .pty_backend import create_pty_backend, PTYBackend


class TerminalWidget(tk.Frame):
    """
    Cross-platform terminal emulator widget with full VT100 support.

    Uses pyte for terminal emulation which handles:
    - Cursor movement and positioning
    - Alternate screen buffer
    - Colors (256 + true color)
    - All standard escape sequences
    """

    def __init__(
        self,
        parent,
        theme: Optional[Dict] = None,
        font_family: str = "Consolas",
        font_size: int = 10,
        scrollback: int = 10000,
        on_exit: Optional[Callable[[int], None]] = None,
    ):
        super().__init__(parent)

        # Theme
        self.theme = theme or {
            "bg": "#1e1e1e",
            "fg": "#d4d4d4",
            "cursor": "#ffffff",
            "selection": "#264f78",
        }

        # Config
        self.font_family = font_family
        self.font_size = font_size
        self.scrollback = scrollback
        self.on_exit_callback = on_exit

        # Terminal size
        self.cols = 120
        self.rows = 30

        # State
        self.pty: Optional[PTYBackend] = None
        self.running = False
        self.output_queue: queue.Queue = queue.Queue()
        self.read_thread: Optional[threading.Thread] = None

        # pyte screen and stream for VT100 emulation
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self.screen)

        # Build UI
        self._build_ui()
        self._setup_bindings()

        # Start render loop
        self._render_loop()

    def _build_ui(self) -> None:
        """Build terminal UI components."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Create text widget
        self.text = tk.Text(
            self,
            bg=self.theme["bg"],
            fg=self.theme["fg"],
            font=(self.font_family, self.font_size),
            insertbackground=self.theme["cursor"],
            selectbackground=self.theme["selection"],
            wrap="none",
            undo=False,
            autoseparators=False,
            maxundo=0,
            padx=4,
            pady=4,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            cursor="xterm",
        )

        # Scrollbar
        self.scrollbar = tk.Scrollbar(
            self,
            command=self.text.yview,
            bg=self.theme["bg"],
            troughcolor=self.theme["bg"],
            activebackground="#404040",
        )
        self.text.configure(yscrollcommand=self.scrollbar.set)

        # Grid layout
        self.text.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # Configure color tags
        self._setup_color_tags()

    def _setup_color_tags(self) -> None:
        """Setup text tags for ANSI colors."""
        # Basic 16 colors
        self.ansi_colors = [
            "#000000", "#cd0000", "#00cd00", "#cdcd00",
            "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
            "#7f7f7f", "#ff0000", "#00ff00", "#ffff00",
            "#5c5cff", "#ff00ff", "#00ffff", "#ffffff",
        ]
        # Cache for dynamically created tags
        self._color_tags = set()

    def _get_color_hex(self, color) -> str:
        """Convert pyte color to hex."""
        if color == "default" or color is None:
            return None

        # Tuple (r, g, b) for true color
        if isinstance(color, tuple) and len(color) == 3:
            r, g, b = color
            return f"#{r:02x}{g:02x}{b:02x}"

        # Integer index
        if isinstance(color, int):
            if color < 16:
                return self.ansi_colors[color]
            elif color < 232:
                # 216 color cube
                idx = color - 16
                r = (idx // 36) * 51
                g = ((idx // 6) % 6) * 51
                b = (idx % 6) * 51
                return f"#{r:02x}{g:02x}{b:02x}"
            else:
                # Grayscale
                gray = (color - 232) * 10 + 8
                return f"#{gray:02x}{gray:02x}{gray:02x}"

        # Convert to string for processing
        color_str = str(color)

        if color_str.startswith("#"):
            # Valid 6-char hex
            if len(color_str) == 7:
                return color_str
            # Long hex - truncate to 6 chars
            if len(color_str) > 7:
                return f"#{color_str[1:7]}"

        # Try to parse as int
        try:
            return self._get_color_hex(int(color_str))
        except:
            pass

        return None

    def _get_tag_for_char(self, char) -> str:
        """Get or create tag for character style."""
        fg = self._get_color_hex(char.fg) or self.theme["fg"]
        bg = self._get_color_hex(char.bg)
        bold = char.bold
        italic = char.italics
        underline = char.underscore

        # Build tag name
        parts = [f"c{fg.replace('#', '')}"]
        if bg:
            parts.append(f"b{bg.replace('#', '')}")
        if bold:
            parts.append("B")
        if italic:
            parts.append("I")
        if underline:
            parts.append("U")

        tag_name = "_".join(parts)

        # Create tag if needed
        if tag_name not in self._color_tags:
            config = {"foreground": fg}
            if bg and bg != self.theme["bg"]:
                config["background"] = bg
            if bold and italic:
                config["font"] = (self.font_family, self.font_size, "bold italic")
            elif bold:
                config["font"] = (self.font_family, self.font_size, "bold")
            elif italic:
                config["font"] = (self.font_family, self.font_size, "italic")
            if underline:
                config["underline"] = True

            self.text.tag_configure(tag_name, **config)
            self._color_tags.add(tag_name)

        return tag_name

    def _setup_bindings(self) -> None:
        """Setup keyboard and mouse bindings."""
        # All keyboard input
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<BackSpace>", self._on_backspace)
        self.text.bind("<Delete>", self._on_delete)
        self.text.bind("<Escape>", self._on_escape)

        # Arrow keys
        self.text.bind("<Up>", self._on_arrow)
        self.text.bind("<Down>", self._on_arrow)
        self.text.bind("<Left>", self._on_arrow)
        self.text.bind("<Right>", self._on_arrow)
        self.text.bind("<Home>", self._on_home_end)
        self.text.bind("<End>", self._on_home_end)
        self.text.bind("<Tab>", self._on_tab)

        # Ctrl combinations
        self.text.bind("<Control-c>", self._on_ctrl_c)
        self.text.bind("<Control-d>", self._on_ctrl_d)
        self.text.bind("<Control-z>", self._on_ctrl_z)
        self.text.bind("<Control-l>", self._on_ctrl_l)

        # Copy/paste
        self.text.bind("<Control-Shift-c>", self._on_copy)
        self.text.bind("<Control-Shift-v>", self._on_paste)
        self.text.bind("<Control-Insert>", self._on_copy)
        self.text.bind("<Shift-Insert>", self._on_paste)

        # Mouse
        self.text.bind("<Button-3>", self._on_right_click)

        # Resize
        self.bind("<Configure>", self._on_resize)

        # Focus
        self.text.bind("<FocusIn>", lambda e: self.text.configure(insertofftime=0))
        self.text.bind("<FocusOut>", lambda e: self.text.configure(insertofftime=300))

    def start(self, cmd: list[str], cwd: str, env: Optional[Dict] = None) -> None:
        """Start terminal with given command."""
        if self.running:
            self.stop()

        # Calculate terminal size
        self._calculate_size()

        # Reset pyte screen
        self.screen.reset()
        self.screen.resize(self.rows, self.cols)

        # Create PTY backend
        self.pty = create_pty_backend()

        # Spawn process
        self.pty.spawn(cmd, cwd, size=(self.rows, self.cols))
        self.running = True

        # Start read thread
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        # Focus terminal
        self.text.focus_set()

    def stop(self) -> None:
        """Stop terminal and terminate process."""
        self.running = False

        if self.pty:
            self.pty.terminate()
            self.pty = None

        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            self.read_thread = None

    def write(self, data: str) -> None:
        """Write data to terminal."""
        if self.pty and self.running:
            self.pty.write(data)

    def clear(self) -> None:
        """Clear terminal screen."""
        self.screen.reset()
        self._render_screen()

    def _calculate_size(self) -> None:
        """Calculate terminal size in characters."""
        self.update_idletasks()

        f = tkfont.Font(family=self.font_family, size=self.font_size)
        char_width = f.measure("M")
        char_height = f.metrics("linespace")

        width = self.text.winfo_width()
        height = self.text.winfo_height()

        if width > 10 and height > 10:
            self.cols = max(40, (width - 8) // char_width)
            self.rows = max(10, (height - 8) // char_height)

    def _read_loop(self) -> None:
        """Background thread: read PTY output."""
        while self.running and self.pty:
            try:
                data = self.pty.read(4096)
                if data:
                    self.output_queue.put(("output", data))
                else:
                    time.sleep(0.01)

                if not self.pty.is_alive():
                    self.output_queue.put(("exit", 0))
                    break

            except Exception as e:
                self.output_queue.put(("error", str(e)))
                break

    def _render_loop(self) -> None:
        """Process queued output and render (runs in main thread)."""
        try:
            while True:
                msg_type, data = self.output_queue.get_nowait()

                if msg_type == "output":
                    # Feed to pyte stream
                    self.stream.feed(data)
                elif msg_type == "exit":
                    self._on_process_exit(data)
                elif msg_type == "error":
                    self._render_error(data)

        except queue.Empty:
            pass

        # Render screen state
        self._render_screen()

        # Schedule next render
        if self.winfo_exists():
            self.after(33, self._render_loop)  # ~30 FPS

    def _render_screen(self) -> None:
        """Render pyte screen to text widget with colors."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        for y in range(self.screen.lines):
            line = self.screen.buffer[y]

            # Build line with color segments
            x = 0
            while x < self.screen.columns:
                char = line[x]
                char_data = char.data if char.data else " "

                # Find consecutive chars with same style
                segment = char_data
                tag = self._get_tag_for_char(char)
                x += 1

                while x < self.screen.columns:
                    next_char = line[x]
                    next_tag = self._get_tag_for_char(next_char)
                    if next_tag != tag:
                        break
                    segment += next_char.data if next_char.data else " "
                    x += 1

                # Insert segment with tag
                self.text.insert("end", segment, tag)

            # Add newline except for last line
            if y < self.screen.lines - 1:
                self.text.insert("end", "\n")

        # Position cursor
        cursor_y = self.screen.cursor.y + 1
        cursor_x = self.screen.cursor.x
        try:
            self.text.mark_set("insert", f"{cursor_y}.{cursor_x}")
        except:
            pass

        self.text.configure(state="normal")
        self.text.see("insert")

    def _render_error(self, error: str) -> None:
        """Render error message."""
        self.text.configure(state="normal")
        self.text.insert("end", f"\n[ERROR] {error}\n")
        self.text.configure(state="normal")

    def _on_process_exit(self, exit_code: int) -> None:
        """Handle process exit."""
        self.running = False
        self.text.configure(state="normal")
        self.text.insert("end", f"\n[Process exited with code {exit_code}]\n")
        self.text.configure(state="normal")

        if self.on_exit_callback:
            self.on_exit_callback(exit_code)

    # ═══════════════════════════════════════════════════════════════════════════════
    # INPUT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _on_key(self, event) -> str:
        """Handle regular key press."""
        if not self.running:
            return "break"

        char = event.char
        if char and ord(char) >= 32:
            self.write(char)

        return "break"

    def _on_return(self, event) -> str:
        """Handle Enter key."""
        if self.running:
            self.write("\r")
        return "break"

    def _on_backspace(self, event) -> str:
        """Handle Backspace."""
        if self.running:
            self.write("\x7f")
        return "break"

    def _on_delete(self, event) -> str:
        """Handle Delete key."""
        if self.running:
            self.write("\x1b[3~")
        return "break"

    def _on_arrow(self, event) -> str:
        """Handle arrow keys."""
        if not self.running:
            return "break"

        arrow_codes = {
            "Up": "\x1b[A",
            "Down": "\x1b[B",
            "Right": "\x1b[C",
            "Left": "\x1b[D",
        }

        if event.keysym in arrow_codes:
            self.write(arrow_codes[event.keysym])

        return "break"

    def _on_home_end(self, event) -> str:
        """Handle Home/End keys."""
        if not self.running:
            return "break"

        if event.keysym == "Home":
            self.write("\x1b[H")
        elif event.keysym == "End":
            self.write("\x1b[F")

        return "break"

    def _on_tab(self, event) -> str:
        """Handle Tab key."""
        if self.running:
            self.write("\t")
        return "break"

    def _on_ctrl_c(self, event) -> str:
        """Handle Ctrl+C (interrupt)."""
        if self.running and self.pty:
            self.pty.send_signal(signal.SIGINT)
        return "break"

    def _on_ctrl_d(self, event) -> str:
        """Handle Ctrl+D (EOF)."""
        if self.running:
            self.write("\x04")
        return "break"

    def _on_ctrl_z(self, event) -> str:
        """Handle Ctrl+Z (suspend - Unix only)."""
        if self.running and sys.platform != "win32":
            self.pty.send_signal(signal.SIGTSTP)
        return "break"

    def _on_ctrl_l(self, event) -> str:
        """Handle Ctrl+L (clear screen)."""
        if self.running:
            self.write("\x0c")
        return "break"

    def _on_escape(self, event) -> str:
        """Handle Escape key."""
        if self.running:
            self.write("\x1b")  # ESC character
        return "break"

    def _on_copy(self, event) -> str:
        """Handle copy."""
        try:
            selection = self.text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selection)
        except tk.TclError:
            pass
        return "break"

    def _on_paste(self, event) -> str:
        """Handle paste."""
        if self.running:
            try:
                text = self.clipboard_get()
                self.write(text)
            except tk.TclError:
                pass
        return "break"

    def _on_right_click(self, event) -> None:
        """Show context menu."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy", command=lambda: self._on_copy(None))
        menu.add_command(label="Paste", command=lambda: self._on_paste(None))
        menu.add_separator()
        menu.add_command(label="Clear", command=self.clear)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_resize(self, event) -> None:
        """Handle widget resize."""
        self._calculate_size()

        # Resize pyte screen
        if self.screen.lines != self.rows or self.screen.columns != self.cols:
            self.screen.resize(self.rows, self.cols)

        # Notify PTY
        if self.pty and self.running:
            self.pty.resize(self.rows, self.cols)

    def update_theme(self, theme: Dict) -> None:
        """Update terminal theme."""
        self.theme = theme
        self.text.configure(
            bg=theme["bg"],
            fg=theme["fg"],
            insertbackground=theme.get("cursor", "#ffffff"),
            selectbackground=theme.get("selection", "#264f78"),
        )
