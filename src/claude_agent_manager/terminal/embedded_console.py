"""
Embedded Windows Console using SetParent API.

Instead of trying to emulate terminal in Tkinter, we:
1. Spawn cmd.exe with our command
2. Find the console window by PID
3. Use SetParent to embed it into our Tkinter frame
4. Wrap it with custom Tkinter UI (buttons, menus)

This gives 100% compatibility with Claude's Ink-based TUI.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import time
import os
import sys
from typing import Optional, Callable, Dict

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Window styles
    GWL_STYLE = -16
    GWL_EXSTYLE = -20
    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_BORDER = 0x00800000
    WS_SYSMENU = 0x00080000
    WS_EX_APPWINDOW = 0x00040000
    WS_EX_TOOLWINDOW = 0x00000080

    # Window messages
    WM_CLOSE = 0x0010
    WM_SIZE = 0x0005
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_CHAR = 0x0102

    # EnumWindows callback type
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    # SendInput structures for keyboard forwarding
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_input", _INPUT),
        ]

    # Virtual key codes
    VK_MAP = {
        'Return': 0x0D, 'space': 0x20, 'BackSpace': 0x08, 'Tab': 0x09,
        'Escape': 0x1B, 'Delete': 0x2E, 'Insert': 0x2D,
        'Home': 0x24, 'End': 0x23, 'Prior': 0x21, 'Next': 0x22,  # PageUp/PageDown
        'Up': 0x26, 'Down': 0x28, 'Left': 0x25, 'Right': 0x27,
        'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74,
        'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79,
        'F11': 0x7A, 'F12': 0x7B,
        'Shift_L': 0x10, 'Shift_R': 0x10, 'Control_L': 0x11, 'Control_R': 0x11,
        'Alt_L': 0x12, 'Alt_R': 0x12,
    }


class EmbeddedConsole(tk.Frame):
    """
    Embeds a Windows console window inside a Tkinter frame.

    Provides custom toolbar and styling while the actual terminal
    rendering is done by Windows console (ConHost).
    """

    def __init__(
        self,
        parent,
        agent_id: str = "",
        agent_name: str = "Agent",
        theme: Optional[Dict] = None,
        on_close: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)

        self.agent_id = agent_id
        self.agent_name = agent_name
        self.theme = theme or {
            "bg": "#1e1e1e",
            "fg": "#d4d4d4",
            "accent": "#0078d4",
            "button_bg": "#2d2d2d",
            "button_hover": "#3d3d3d",
        }
        self.on_close_callback = on_close

        # Process and window handles
        self.process: Optional[subprocess.Popen] = None
        self.console_hwnd: Optional[int] = None
        self.embed_frame_hwnd: Optional[int] = None

        # State
        self.running = False
        self._check_thread: Optional[threading.Thread] = None

        # Build UI
        self._build_ui()
        self._setup_style()

    def _build_ui(self) -> None:
        """Build the wrapper UI around embedded console."""
        self.configure(bg=self.theme["bg"])

        # State for pin
        self._is_pinned = False

        # Top toolbar
        self.toolbar = tk.Frame(self, bg=self.theme["bg"], height=36)
        self.toolbar.pack(fill="x", side="top")
        self.toolbar.pack_propagate(False)

        # === LEFT SIDE: Agent info ===
        left_frame = tk.Frame(self.toolbar, bg=self.theme["bg"])
        left_frame.pack(side="left", padx=5)

        # Agent name label
        self.name_label = tk.Label(
            left_frame,
            text=f" {self.agent_name}",
            font=("Segoe UI", 10, "bold"),
            fg=self.theme["fg"],
            bg=self.theme["bg"],
            anchor="w",
        )
        self.name_label.pack(side="left", pady=5)

        # Status indicator
        self.status_dot = tk.Label(
            left_frame,
            text="●",
            font=("Segoe UI", 8),
            fg="#4ec9b0",  # Green for running
            bg=self.theme["bg"],
        )
        self.status_dot.pack(side="left", padx=(4, 8))

        # Separator
        sep1 = tk.Label(left_frame, text="│", fg="#404040", bg=self.theme["bg"], font=("Segoe UI", 10))
        sep1.pack(side="left", padx=2)

        # Path label (will be set when start() is called)
        self.path_label = tk.Label(
            left_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#808080",
            bg=self.theme["bg"],
            anchor="w",
        )
        self.path_label.pack(side="left", padx=(4, 0))

        # === CENTER: Action buttons ===
        center_frame = tk.Frame(self.toolbar, bg=self.theme["bg"])
        center_frame.pack(side="left", padx=10)

        # Open folder button
        self.folder_btn = tk.Button(
            center_frame,
            text="📁",
            font=("Segoe UI", 9),
            fg=self.theme["fg"],
            bg=self.theme["button_bg"],
            activebackground=self.theme["button_hover"],
            activeforeground=self.theme["fg"],
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_open_folder,
        )
        self.folder_btn.pack(side="left", padx=1, pady=4)
        self._bind_hover(self.folder_btn)
        self._add_tooltip(self.folder_btn, "Open memory folder")

        # Interrupt button (Ctrl+C)
        self.interrupt_btn = tk.Button(
            center_frame,
            text="⏹",
            font=("Segoe UI", 9),
            fg="#f87171",
            bg=self.theme["button_bg"],
            activebackground=self.theme["button_hover"],
            activeforeground="#f87171",
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_interrupt,
        )
        self.interrupt_btn.pack(side="left", padx=1, pady=4)
        self._bind_hover(self.interrupt_btn)
        self._add_tooltip(self.interrupt_btn, "Send Ctrl+C")

        # Clear screen button
        self.clear_btn = tk.Button(
            center_frame,
            text="🧹",
            font=("Segoe UI", 9),
            fg=self.theme["fg"],
            bg=self.theme["button_bg"],
            activebackground=self.theme["button_hover"],
            activeforeground=self.theme["fg"],
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_clear_screen,
        )
        self.clear_btn.pack(side="left", padx=1, pady=4)
        self._bind_hover(self.clear_btn)
        self._add_tooltip(self.clear_btn, "Clear screen (Ctrl+L)")

        # Pin on top button
        self.pin_btn = tk.Button(
            center_frame,
            text="📌",
            font=("Segoe UI", 9),
            fg=self.theme["fg"],
            bg=self.theme["button_bg"],
            activebackground=self.theme["button_hover"],
            activeforeground=self.theme["fg"],
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_toggle_pin,
        )
        self.pin_btn.pack(side="left", padx=1, pady=4)
        self._bind_hover(self.pin_btn)
        self._add_tooltip(self.pin_btn, "Pin on top")

        # === RIGHT SIDE: Window controls ===
        right_frame = tk.Frame(self.toolbar, bg=self.theme["bg"])
        right_frame.pack(side="right", padx=5)

        # Close button
        self.close_btn = tk.Button(
            right_frame,
            text="✕",
            font=("Segoe UI", 10),
            fg=self.theme["fg"],
            bg=self.theme["button_bg"],
            activebackground="#c42b1c",
            activeforeground="white",
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_close_click,
        )
        self.close_btn.pack(side="right", padx=2, pady=4)
        self._bind_hover(self.close_btn)
        self._add_tooltip(self.close_btn, "Close agent")

        # Restart button
        self.restart_btn = tk.Button(
            right_frame,
            text="↻",
            font=("Segoe UI", 10),
            fg=self.theme["fg"],
            bg=self.theme["button_bg"],
            activebackground=self.theme["button_hover"],
            activeforeground=self.theme["fg"],
            relief="flat",
            width=3,
            cursor="hand2",
            command=self._on_restart_click,
        )
        self.restart_btn.pack(side="right", padx=2, pady=4)
        self._bind_hover(self.restart_btn)
        self._add_tooltip(self.restart_btn, "Restart agent")

        # Separator
        sep = tk.Frame(self, bg="#3d3d3d", height=1)
        sep.pack(fill="x", side="top")

        # Container for embedded console
        self.console_container = tk.Frame(self, bg="#0c0c0c")
        self.console_container.pack(fill="both", expand=True, side="top")

        # Bind resize
        self.console_container.bind("<Configure>", self._on_container_resize)

    def _setup_style(self) -> None:
        """Setup ttk styles if needed."""
        pass

    def _bind_hover(self, button: tk.Button) -> None:
        """Add hover effect to button."""
        def on_enter(e):
            button.configure(bg=self.theme["button_hover"])
        def on_leave(e):
            button.configure(bg=self.theme["button_bg"])
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def start(self, cmd: str, cwd: str, env: Optional[Dict] = None) -> bool:
        """
        Start the console process and embed its window.

        Args:
            cmd: Command to run (e.g., "claude")
            cwd: Working directory
            env: Optional environment variables

        Returns:
            True if successfully started and embedded
        """
        if self.running:
            self.stop()

        # Save for restart
        self._last_cmd = cmd
        self._last_cwd = cwd

        # Update path label (shortened)
        self._update_path_label(cwd)

        try:
            # Prepare environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            # Start process with CREATE_NEW_CONSOLE
            CREATE_NEW_CONSOLE = 0x00000010

            self.process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=process_env,
                shell=True,
                creationflags=CREATE_NEW_CONSOLE,
            )

            self.running = True

            # Find and embed console window after short delay
            self.after(300, self._find_and_embed_console)

            # Start process monitor thread
            self._check_thread = threading.Thread(target=self._monitor_process, daemon=True)
            self._check_thread.start()

            return True

        except Exception as e:
            print(f"Failed to start process: {e}")
            return False

    def _find_and_embed_console(self) -> None:
        """Find the console window by PID and embed it."""
        if not self.process or not self.running:
            return

        pid = self.process.pid
        found_hwnd = None

        # Enumerate windows to find console for our PID
        def enum_callback(hwnd, lparam):
            nonlocal found_hwnd

            # Get window's process ID
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))

            if window_pid.value == pid:
                # Check if it's a console window
                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)

                if class_name.value in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
                    found_hwnd = hwnd
                    return False  # Stop enumeration

            return True  # Continue

        callback = WNDENUMPROC(enum_callback)
        user32.EnumWindows(callback, 0)

        if found_hwnd:
            self.console_hwnd = found_hwnd
            self._embed_window()
        else:
            # Retry after delay (console might take time to appear)
            self.after(200, self._find_and_embed_console)

    def _embed_window(self) -> None:
        """Embed the console window into our container frame."""
        if not self.console_hwnd:
            return

        # Get container's HWND
        self.update_idletasks()
        self.embed_frame_hwnd = self.console_container.winfo_id()

        # Get thread IDs for input sharing
        console_thread_id = user32.GetWindowThreadProcessId(self.console_hwnd, None)
        current_thread_id = kernel32.GetCurrentThreadId()

        # Remove window decorations
        style = user32.GetWindowLongW(self.console_hwnd, GWL_STYLE)
        style = style & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_SYSMENU
        style = style | WS_CHILD | WS_VISIBLE
        user32.SetWindowLongW(self.console_hwnd, GWL_STYLE, style)

        # Remove from taskbar
        ex_style = user32.GetWindowLongW(self.console_hwnd, GWL_EXSTYLE)
        ex_style = ex_style & ~WS_EX_APPWINDOW | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(self.console_hwnd, GWL_EXSTYLE, ex_style)

        # Set parent to our container
        user32.SetParent(self.console_hwnd, self.embed_frame_hwnd)

        # Attach input threads so keyboard works
        if console_thread_id != current_thread_id:
            user32.AttachThreadInput(current_thread_id, console_thread_id, True)
            self._attached_thread = console_thread_id

        # Resize to fill container
        self._resize_console()

        # Set focus to console
        self._focus_console()

        # Bind click on container to focus console
        self.console_container.bind("<Button-1>", lambda e: self._focus_console())
        self.console_container.bind("<FocusIn>", lambda e: self._focus_console())

        # Also bind to the frame itself and toolbar for better click coverage
        self.bind("<Button-1>", lambda e: self._focus_console())

        # Auto-focus console when toplevel window is activated
        toplevel = self.winfo_toplevel()
        toplevel.bind("<FocusIn>", lambda e: self._schedule_focus())
        toplevel.bind("<Activate>", lambda e: self._schedule_focus())

        # Bind keyboard events for forwarding to console
        toplevel.bind("<Key>", self._forward_key)
        toplevel.bind("<KeyRelease>", self._forward_key_release)

    def _forward_key(self, event) -> str:
        """Forward key press to embedded console."""
        if not self.console_hwnd or not self.running:
            return ""
        try:
            # First ensure console has focus
            user32.SetFocus(self.console_hwnd)

            # Get virtual key code
            vk = None
            if event.keysym in VK_MAP:
                vk = VK_MAP[event.keysym]
            elif len(event.char) == 1:
                # For regular characters, use VkKeyScan
                vk = user32.VkKeyScanW(ord(event.char)) & 0xFF

            if vk:
                # Send key down using PostMessage for better reliability
                scan = user32.MapVirtualKeyW(vk, 0)
                lparam = (scan << 16) | 1
                user32.PostMessageW(self.console_hwnd, WM_KEYDOWN, vk, lparam)

                # For printable chars, also send WM_CHAR
                if event.char and len(event.char) == 1 and ord(event.char) >= 32:
                    user32.PostMessageW(self.console_hwnd, WM_CHAR, ord(event.char), lparam)

            return "break"  # Prevent Tkinter from processing
        except Exception as e:
            print(f"Key forward error: {e}")
            return ""

    def _forward_key_release(self, event) -> str:
        """Forward key release to embedded console."""
        if not self.console_hwnd or not self.running:
            return ""
        try:
            vk = None
            if event.keysym in VK_MAP:
                vk = VK_MAP[event.keysym]
            elif len(event.char) == 1:
                vk = user32.VkKeyScanW(ord(event.char)) & 0xFF

            if vk:
                scan = user32.MapVirtualKeyW(vk, 0)
                lparam = (scan << 16) | 1 | (1 << 30) | (1 << 31)  # Key up flags
                user32.PostMessageW(self.console_hwnd, WM_KEYUP, vk, lparam)

            return "break"
        except:
            return ""

    def _schedule_focus(self) -> None:
        """Schedule focus to console after small delay."""
        if self.console_hwnd and self.running:
            self.after(50, self._focus_console)

    def _focus_console(self) -> None:
        """Set keyboard focus to the embedded console."""
        if not self.console_hwnd:
            return
        try:
            # For child windows, we need to:
            # 1. Bring the parent (toplevel) to foreground first
            # 2. Then set focus to the child console window
            toplevel = self.winfo_toplevel()
            toplevel_hwnd = toplevel.winfo_id()

            # Bring toplevel to foreground
            user32.SetForegroundWindow(toplevel_hwnd)

            # Small delay to ensure foreground is set
            self.after(10, self._set_console_focus)
        except Exception as e:
            print(f"Focus error: {e}")

    def _set_console_focus(self) -> None:
        """Actually set focus to console window."""
        if not self.console_hwnd:
            return
        try:
            # Re-attach thread input to ensure keyboard works after focus changes
            current_thread_id = kernel32.GetCurrentThreadId()
            console_thread_id = user32.GetWindowThreadProcessId(self.console_hwnd, None)

            if console_thread_id and console_thread_id != current_thread_id:
                # Detach first if was attached before
                if hasattr(self, '_attached_thread') and self._attached_thread:
                    try:
                        user32.AttachThreadInput(current_thread_id, self._attached_thread, False)
                    except:
                        pass
                # Attach to console thread
                user32.AttachThreadInput(current_thread_id, console_thread_id, True)
                self._attached_thread = console_thread_id

            # SetFocus works for child windows when parent is foreground
            user32.SetFocus(self.console_hwnd)
        except:
            pass

    def _resize_console(self) -> None:
        """Resize embedded console to fill container."""
        if not self.console_hwnd or not self.embed_frame_hwnd:
            return

        self.update_idletasks()
        width = self.console_container.winfo_width()
        height = self.console_container.winfo_height()

        if width > 0 and height > 0:
            user32.MoveWindow(self.console_hwnd, 0, 0, width, height, True)

    def _on_container_resize(self, event) -> None:
        """Handle container resize."""
        if self.console_hwnd:
            self._resize_console()

    def _monitor_process(self) -> None:
        """Monitor process status in background thread."""
        while self.running and self.process:
            try:
                ret = self.process.poll()
                if ret is not None:
                    # Process exited
                    self.after(0, self._on_process_exit, ret)
                    break
                time.sleep(0.5)
            except:
                break

    def _on_process_exit(self, exit_code: int) -> None:
        """Handle process exit."""
        self.running = False
        self.console_hwnd = None

        # Update status indicator
        self.status_dot.configure(fg="#f14c4c")  # Red for stopped

        # Show exit message in container
        exit_label = tk.Label(
            self.console_container,
            text=f"Process exited with code {exit_code}",
            font=("Segoe UI", 11),
            fg="#808080",
            bg="#0c0c0c",
        )
        exit_label.place(relx=0.5, rely=0.5, anchor="center")

    def stop(self) -> None:
        """Stop the embedded console process."""
        self.running = False

        # Detach thread input
        if hasattr(self, "_attached_thread") and self._attached_thread:
            try:
                current_thread_id = kernel32.GetCurrentThreadId()
                user32.AttachThreadInput(current_thread_id, self._attached_thread, False)
            except:
                pass
            self._attached_thread = None

        if self.console_hwnd:
            try:
                # Send WM_CLOSE to console
                user32.PostMessageW(self.console_hwnd, WM_CLOSE, 0, 0)
            except:
                pass
            self.console_hwnd = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None

        # Update status
        self.status_dot.configure(fg="#f14c4c")

    def _on_close_click(self) -> None:
        """Handle close button click."""
        self.stop()
        if self.on_close_callback:
            self.on_close_callback()

    def _on_restart_click(self) -> None:
        """Handle restart button click."""
        # Store current command/cwd and restart
        if hasattr(self, "_last_cmd") and hasattr(self, "_last_cwd"):
            self.stop()
            self.after(500, lambda: self.start(self._last_cmd, self._last_cwd))

    def _update_path_label(self, path: str) -> None:
        """Update path label with shortened path."""
        if not path:
            self.path_label.configure(text="")
            return

        # Shorten path for display
        max_len = 40
        if len(path) > max_len:
            # Show .../<last_two_parts>
            parts = path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                short = f".../{parts[-2]}/{parts[-1]}"
            else:
                short = f"...{path[-(max_len-3):]}"
        else:
            short = path

        self.path_label.configure(text=short)
        self._add_tooltip(self.path_label, f"Project: {path}")

    def _on_open_folder(self) -> None:
        """Open memory folder in explorer."""
        if hasattr(self, "_last_cwd") and self._last_cwd:
            try:
                os.startfile(self._last_cwd)
            except:
                pass

    def _on_interrupt(self) -> None:
        """Send Ctrl+C to the console."""
        if self.console_hwnd:
            try:
                # Send Ctrl+C by generating console event
                import signal
                if self.process:
                    self.process.send_signal(signal.CTRL_C_EVENT)
            except:
                pass
            self._focus_console()

    def _on_clear_screen(self) -> None:
        """Send Ctrl+L to clear screen."""
        if self.console_hwnd:
            try:
                # Send Ctrl+L (form feed) to clear
                # We need to send keystrokes to the console
                VK_L = 0x4C
                VK_CONTROL = 0x11
                KEYEVENTF_KEYUP = 0x0002

                user32.keybd_event(VK_CONTROL, 0, 0, 0)
                user32.keybd_event(VK_L, 0, 0, 0)
                user32.keybd_event(VK_L, 0, KEYEVENTF_KEYUP, 0)
                user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            except:
                pass
            self._focus_console()

    def _on_toggle_pin(self) -> None:
        """Toggle window always on top."""
        self._is_pinned = not self._is_pinned

        # Get the toplevel window
        toplevel = self.winfo_toplevel()

        if self._is_pinned:
            toplevel.attributes("-topmost", True)
            self.pin_btn.configure(fg="#4ec9b0", bg="#3d3d3d")  # Highlighted
        else:
            toplevel.attributes("-topmost", False)
            self.pin_btn.configure(fg=self.theme["fg"], bg=self.theme["button_bg"])

    def _add_tooltip(self, widget, text: str) -> None:
        """Add simple tooltip to widget."""
        tooltip = None

        def show_tooltip(event):
            nonlocal tooltip
            x, y, _, _ = widget.bbox("insert") if hasattr(widget, "bbox") else (0, 0, 0, 0)
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = tk.Label(
                tooltip,
                text=text,
                bg="#2d2d2d",
                fg="#d4d4d4",
                relief="flat",
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=6,
                pady=3,
            )
            label.pack()

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

    def focus_console(self) -> None:
        """Set focus to the embedded console (public method)."""
        self._focus_console()


def create_agent_window(
    agent_id: str,
    agent_name: str,
    cmd: str,
    cwd: str,
    theme: Optional[Dict] = None,
    on_window_close: Optional[Callable[[], None]] = None,
) -> tk.Toplevel:
    """
    Create a standalone window with embedded console for an agent.

    Args:
        agent_id: Agent identifier
        agent_name: Display name for the agent
        cmd: Command to run
        cwd: Working directory
        theme: Optional theme dict
        on_window_close: Callback when window is closed

    Returns:
        The Toplevel window
    """
    # Create window
    window = tk.Toplevel()
    window.title(f"Claude Agent - {agent_name}")
    window.geometry("1000x700")
    window.configure(bg=theme.get("bg", "#1e1e1e") if theme else "#1e1e1e")

    # Set icon if available
    try:
        window.iconbitmap(default="")
    except:
        pass

    # Create embedded console
    def on_close():
        window.destroy()
        if on_window_close:
            on_window_close()

    console = EmbeddedConsole(
        window,
        agent_id=agent_id,
        agent_name=agent_name,
        theme=theme,
        on_close=on_close,
    )
    console.pack(fill="both", expand=True)

    # Start the console
    console.start(cmd, cwd)

    # Handle window close (X button)
    def handle_window_close():
        console.stop()
        window.destroy()
        if on_window_close:
            on_window_close()

    window.protocol("WM_DELETE_WINDOW", handle_window_close)

    return window
