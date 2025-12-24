"""
Worktree UI Components for Claude Agent Manager Dashboard.

Provides visual management of git worktrees with:
- WorktreeCard: Individual worktree display with actions
- WorktreePanel: Collapsible container with auto-refresh
- Dialogs: Create, Merge, Discard confirmation

Best practices from GitLens, Lazygit, GitKraken integrated.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import subprocess
import threading
import os


@dataclass
class WorktreeInfo:
    """Worktree data for UI display."""
    path: Path
    branch_name: str
    agent_id: str
    task_name: str
    commits_ahead: int = 0
    uncommitted_files: int = 0
    last_commit: str = ""
    has_conflicts: bool = False
    # New fields from Auto-Claude
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    base_branch: str = "main"


class WorktreeCard(tk.Frame):
    """
    Individual worktree card with status and action buttons.

    Displays:
    - Agent ID / Task name
    - Status: commits ahead, files changed
    - Actions: Merge, Discard, Open folder
    """

    def __init__(
        self,
        parent: tk.Widget,
        worktree: WorktreeInfo,
        theme: Dict,
        on_merge: Optional[Callable[[WorktreeInfo], None]] = None,
        on_discard: Optional[Callable[[WorktreeInfo], None]] = None,
        on_open: Optional[Callable[[WorktreeInfo], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.worktree = worktree
        self.theme = theme
        self.on_merge = on_merge
        self.on_discard = on_discard
        self.on_open = on_open

        self.configure(bg=theme["card_bg"], padx=8, pady=6)
        self._build_ui()

    def _build_ui(self):
        t = self.theme
        wt = self.worktree

        # Top row: agent/task name
        top_frame = tk.Frame(self, bg=t["card_bg"])
        top_frame.pack(fill=tk.X)

        # Agent icon + name
        name_text = f"{wt.agent_id} / {wt.task_name}"
        self.name_lbl = tk.Label(
            top_frame,
            text=name_text,
            font=("Consolas", 9, "bold"),
            bg=t["card_bg"],
            fg=t["fg"],
            anchor="w"
        )
        self.name_lbl.pack(side=tk.LEFT)

        # Branch indicator
        branch_short = wt.branch_name.split("/")[-1] if "/" in wt.branch_name else wt.branch_name
        self.branch_lbl = tk.Label(
            top_frame,
            text=f"  ({branch_short})",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.branch_lbl.pack(side=tk.LEFT)

        # Status row
        status_frame = tk.Frame(self, bg=t["card_bg"])
        status_frame.pack(fill=tk.X, pady=(2, 0))

        # Tree branch symbol
        tk.Label(
            status_frame,
            text="├─",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        # Commits ahead
        commits_color = t["accent"] if wt.commits_ahead > 0 else t["fg_dim"]
        commits_text = f"{wt.commits_ahead} commit{'s' if wt.commits_ahead != 1 else ''} ahead"
        tk.Label(
            status_frame,
            text=commits_text,
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=commits_color
        ).pack(side=tk.LEFT)

        # Separator
        tk.Label(
            status_frame,
            text="  •  ",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        # Additions (green)
        if wt.additions > 0:
            tk.Label(
                status_frame,
                text=f"+{wt.additions}",
                font=("Consolas", 8),
                bg=t["card_bg"],
                fg="#4ade80"  # green
            ).pack(side=tk.LEFT)

        # Deletions (red)
        if wt.deletions > 0:
            tk.Label(
                status_frame,
                text=f" -{wt.deletions}",
                font=("Consolas", 8),
                bg=t["card_bg"],
                fg="#ef4444"  # red
            ).pack(side=tk.LEFT)

        # Uncommitted indicator
        if wt.uncommitted_files > 0:
            tk.Label(
                status_frame,
                text=f"  ({wt.uncommitted_files} uncommitted)",
                font=("Consolas", 8),
                bg=t["card_bg"],
                fg="#f59e0b"  # orange
            ).pack(side=tk.LEFT)

        # Actions row
        actions_frame = tk.Frame(self, bg=t["card_bg"])
        actions_frame.pack(fill=tk.X, pady=(2, 0))

        # Tree end symbol
        tk.Label(
            actions_frame,
            text="└─",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(side=tk.LEFT)

        # Merge button
        self.merge_btn = tk.Label(
            actions_frame,
            text="Merge ↗",
            font=("Consolas", 8),
            bg=t["start_bg"],
            fg=t["start_fg"],
            padx=6,
            pady=1,
            cursor="hand2"
        )
        self.merge_btn.pack(side=tk.LEFT, padx=(4, 4))
        self.merge_btn.bind("<Button-1>", lambda e: self._on_merge())
        self.merge_btn.bind("<Enter>", lambda e: self.merge_btn.configure(bg=t["online"]))
        self.merge_btn.bind("<Leave>", lambda e: self.merge_btn.configure(bg=t["start_bg"]))

        # Discard button
        self.discard_btn = tk.Label(
            actions_frame,
            text="Discard ✕",
            font=("Consolas", 8),
            bg=t["stop_bg"],
            fg=t["stop_fg"],
            padx=6,
            pady=1,
            cursor="hand2"
        )
        self.discard_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.discard_btn.bind("<Button-1>", lambda e: self._on_discard())
        self.discard_btn.bind("<Enter>", lambda e: self.discard_btn.configure(bg="#ef4444"))
        self.discard_btn.bind("<Leave>", lambda e: self.discard_btn.configure(bg=t["stop_bg"]))

        # Open folder button
        self.open_btn = tk.Label(
            actions_frame,
            text="Open 📂",
            font=("Consolas", 8),
            bg=t["btn_bg"],
            fg=t["fg_dim"],
            padx=6,
            pady=1,
            cursor="hand2"
        )
        self.open_btn.pack(side=tk.LEFT)
        self.open_btn.bind("<Button-1>", lambda e: self._on_open())
        self.open_btn.bind("<Enter>", lambda e: self.open_btn.configure(fg=t["fg"]))
        self.open_btn.bind("<Leave>", lambda e: self.open_btn.configure(fg=t["fg_dim"]))

    def _on_merge(self):
        if self.on_merge:
            self.on_merge(self.worktree)

    def _on_discard(self):
        if self.on_discard:
            self.on_discard(self.worktree)

    def _on_open(self):
        if self.on_open:
            self.on_open(self.worktree)

    def update_theme(self, theme: Dict):
        """Update card theme."""
        self.theme = theme
        t = theme

        self.configure(bg=t["card_bg"])

        # Update all children recursively
        for widget in self.winfo_children():
            self._update_widget_theme(widget, t)

    def _update_widget_theme(self, widget, t):
        """Recursively update widget theme."""
        try:
            if isinstance(widget, tk.Frame):
                widget.configure(bg=t["card_bg"])
            elif isinstance(widget, tk.Label):
                widget.configure(bg=t["card_bg"])
                # Preserve special button colors
                if widget in (self.merge_btn,):
                    widget.configure(bg=t["start_bg"], fg=t["start_fg"])
                elif widget in (self.discard_btn,):
                    widget.configure(bg=t["stop_bg"], fg=t["stop_fg"])
                elif widget == self.open_btn:
                    widget.configure(bg=t["btn_bg"], fg=t["fg_dim"])
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self._update_widget_theme(child, t)


class WorktreePanel(tk.Frame):
    """
    Collapsible panel showing all worktrees with auto-refresh.

    Features:
    - Collapse/expand toggle
    - Create new worktree button
    - Auto-refresh every 5 seconds
    - Empty state message
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: Dict,
        project_path: Optional[Path] = None,
        on_merge: Optional[Callable[[WorktreeInfo], None]] = None,
        on_discard: Optional[Callable[[WorktreeInfo], None]] = None,
        on_create: Optional[Callable[[], None]] = None,
        refresh_interval: int = 5000,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.project_path = project_path
        self.on_merge = on_merge
        self.on_discard = on_discard
        self.on_create = on_create
        self.refresh_interval = refresh_interval

        self._expanded = True
        self._active = True
        self._cards: List[WorktreeCard] = []
        self._worktrees: List[WorktreeInfo] = []

        self.configure(bg=theme["card_bg"])
        self._build_ui()
        self._refresh_worktrees()

    def _build_ui(self):
        t = self.theme

        # Header with collapse toggle
        self.header = tk.Frame(self, bg=t["card_bg"])
        self.header.pack(fill=tk.X)

        # Collapse arrow + title
        self.toggle_frame = tk.Frame(self.header, bg=t["card_bg"], cursor="hand2")
        self.toggle_frame.pack(side=tk.LEFT)

        self.arrow_lbl = tk.Label(
            self.toggle_frame,
            text="▼",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.arrow_lbl.pack(side=tk.LEFT, padx=(0, 4))

        self.title_lbl = tk.Label(
            self.toggle_frame,
            text="Worktrees",
            font=("Consolas", 9, "bold"),
            bg=t["card_bg"],
            fg=t["fg"]
        )
        self.title_lbl.pack(side=tk.LEFT)

        # Count badge
        self.count_lbl = tk.Label(
            self.toggle_frame,
            text="(0)",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )
        self.count_lbl.pack(side=tk.LEFT, padx=(4, 0))

        # Bind toggle to header elements
        for widget in (self.toggle_frame, self.arrow_lbl, self.title_lbl, self.count_lbl):
            widget.bind("<Button-1>", lambda e: self._toggle_expand())

        # Create button (right side)
        self.create_btn = tk.Label(
            self.header,
            text="+ New",
            font=("Consolas", 8),
            bg=t["btn_bg"],
            fg=t["accent"],
            padx=6,
            pady=1,
            cursor="hand2"
        )
        self.create_btn.pack(side=tk.RIGHT)
        self.create_btn.bind("<Button-1>", lambda e: self._on_create())
        self.create_btn.bind("<Enter>", lambda e: self.create_btn.configure(bg=t["btn_hover"]))
        self.create_btn.bind("<Leave>", lambda e: self.create_btn.configure(bg=t["btn_bg"]))

        # Content container (collapsible)
        self.content = tk.Frame(self, bg=t["card_bg"])
        self.content.pack(fill=tk.X, pady=(4, 0))

        # Empty state
        self.empty_lbl = tk.Label(
            self.content,
            text="No active worktrees",
            font=("Consolas", 8),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        )

    def _toggle_expand(self):
        """Toggle panel expand/collapse."""
        self._expanded = not self._expanded

        if self._expanded:
            self.arrow_lbl.configure(text="▼")
            self.content.pack(fill=tk.X, pady=(4, 0))
        else:
            self.arrow_lbl.configure(text="▶")
            self.content.pack_forget()

    def _on_create(self):
        """Handle create button click."""
        if self.on_create:
            self.on_create()

    def _refresh_worktrees(self):
        """Refresh worktree list from git."""
        if not self._active:
            return

        # Run in background thread to avoid UI freeze
        def fetch():
            worktrees = self._get_worktrees()
            if self._active:
                # Store result for main thread to pick up
                self._pending_worktrees = worktrees

        def check_result():
            if hasattr(self, '_pending_worktrees') and self._pending_worktrees is not None:
                self._update_ui(self._pending_worktrees)
                self._pending_worktrees = None
            # Schedule next refresh
            if self._active:
                self.after(self.refresh_interval, self._refresh_worktrees)

        self._pending_worktrees = None
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

        # Check for result after short delay
        self.after(500, check_result)

    def _get_worktrees(self) -> List[WorktreeInfo]:
        """Get worktree list from git."""
        worktrees = []

        if not self.project_path or not self.project_path.exists():
            return worktrees

        try:
            # Get worktree list
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return worktrees

            lines = result.stdout.strip().split('\n')
            i = 0

            while i < len(lines):
                if lines[i].startswith('worktree '):
                    path_str = lines[i].split(' ', 1)[1]
                    path = Path(path_str)

                    # Skip main worktree
                    if path == self.project_path:
                        i += 1
                        while i < len(lines) and not lines[i].startswith('worktree '):
                            i += 1
                        continue

                    branch_name = ""
                    i += 1

                    while i < len(lines) and not lines[i].startswith('worktree '):
                        if lines[i].startswith('branch '):
                            branch_name = lines[i].split(' ', 1)[1].replace('refs/heads/', '')
                        i += 1

                    # Parse agent_id and task_name from branch
                    agent_id = "unknown"
                    task_name = "unknown"

                    if branch_name.startswith('agent/'):
                        parts = branch_name.split('/')
                        if len(parts) >= 3:
                            agent_id = parts[1]
                            task_name = '/'.join(parts[2:])

                    # Get status
                    status = self._get_worktree_status(path)

                    worktrees.append(WorktreeInfo(
                        path=path,
                        branch_name=branch_name,
                        agent_id=agent_id,
                        task_name=task_name,
                        commits_ahead=status.get("commits_ahead", 0),
                        uncommitted_files=status.get("uncommitted_files", 0),
                        last_commit=status.get("last_commit", ""),
                        files_changed=status.get("files_changed", 0),
                        additions=status.get("additions", 0),
                        deletions=status.get("deletions", 0),
                    ))
                else:
                    i += 1

        except Exception:
            pass

        return worktrees

    def _get_worktree_status(self, path: Path) -> Dict:
        """Get status for a specific worktree."""
        import re

        status = {
            "commits_ahead": 0,
            "uncommitted_files": 0,
            "last_commit": "",
            "files_changed": 0,
            "additions": 0,
            "deletions": 0,
        }

        try:
            # Uncommitted files
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                status["uncommitted_files"] = len([l for l in result.stdout.split('\n') if l.strip()])

            # Commits ahead
            result = subprocess.run(
                ["git", "rev-list", "--count", "main..HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                status["commits_ahead"] = int(result.stdout.strip() or 0)

            # Last commit
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                status["last_commit"] = result.stdout.strip()[:50]

            # Diff stats (additions/deletions/files)
            result = subprocess.run(
                ["git", "diff", "--shortstat", "main...HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse: "3 files changed, 50 insertions(+), 10 deletions(-)"
                match = re.search(r"(\d+) files? changed", result.stdout)
                if match:
                    status["files_changed"] = int(match.group(1))
                match = re.search(r"(\d+) insertions?", result.stdout)
                if match:
                    status["additions"] = int(match.group(1))
                match = re.search(r"(\d+) deletions?", result.stdout)
                if match:
                    status["deletions"] = int(match.group(1))

        except Exception:
            pass

        return status

    def _update_ui(self, worktrees: List[WorktreeInfo]):
        """Update UI with worktree list."""
        self._worktrees = worktrees

        # Update count
        self.count_lbl.configure(text=f"({len(worktrees)})")

        # Clear existing cards
        for card in self._cards:
            card.destroy()
        self._cards.clear()

        # Hide/show empty state
        if not worktrees:
            self.empty_lbl.pack(pady=4)
        else:
            self.empty_lbl.pack_forget()

            # Create cards
            for wt in worktrees:
                card = WorktreeCard(
                    self.content,
                    wt,
                    self.theme,
                    on_merge=self._handle_merge,
                    on_discard=self._handle_discard,
                    on_open=self._handle_open
                )
                card.pack(fill=tk.X, pady=(0, 4))
                self._cards.append(card)

    def _handle_merge(self, wt: WorktreeInfo):
        """Handle merge action."""
        if self.on_merge:
            self.on_merge(wt)

    def _handle_discard(self, wt: WorktreeInfo):
        """Handle discard action."""
        if self.on_discard:
            self.on_discard(wt)

    def _handle_open(self, wt: WorktreeInfo):
        """Open worktree folder in explorer."""
        if wt.path.exists():
            os.startfile(wt.path)

    def set_project_path(self, path: Path):
        """Update project path and refresh."""
        self.project_path = path
        self._refresh_worktrees()

    def update_theme(self, theme: Dict):
        """Update panel theme."""
        self.theme = theme
        t = theme

        self.configure(bg=t["card_bg"])
        self.header.configure(bg=t["card_bg"])
        self.toggle_frame.configure(bg=t["card_bg"])
        self.arrow_lbl.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.title_lbl.configure(bg=t["card_bg"], fg=t["fg"])
        self.count_lbl.configure(bg=t["card_bg"], fg=t["fg_dim"])
        self.create_btn.configure(bg=t["btn_bg"], fg=t["accent"])
        self.content.configure(bg=t["card_bg"])
        self.empty_lbl.configure(bg=t["card_bg"], fg=t["fg_dim"])

        for card in self._cards:
            card.update_theme(theme)

    def destroy(self):
        """Stop refresh loop before destroying."""
        self._active = False
        super().destroy()


class CreateWorktreeDialog(tk.Toplevel):
    """
    Dialog for creating a new worktree.

    Allows selecting agent and entering task name.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: Dict,
        agents: List[Dict],
        on_create: Callable[[str, str], None],
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.agents = agents
        self.on_create = on_create
        self.result = None

        self.title("Create Worktree")
        self.configure(bg=theme["bg"])
        self.resizable(False, False)

        # Center on parent
        self.transient(parent)
        self.grab_set()

        self._build_ui()

        # Center window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        t = self.theme

        # Main container
        container = tk.Frame(self, bg=t["card_bg"], padx=16, pady=16)
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Title
        tk.Label(
            container,
            text="Create New Worktree",
            font=("Segoe UI", 11, "bold"),
            bg=t["card_bg"],
            fg=t["fg"]
        ).pack(anchor="w", pady=(0, 12))

        # Agent selection
        tk.Label(
            container,
            text="Agent:",
            font=("Consolas", 9),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(anchor="w")

        self.agent_var = tk.StringVar()
        agent_names = [a.get("id", "unknown") for a in self.agents] if self.agents else ["No agents"]
        if agent_names:
            self.agent_var.set(agent_names[0])

        self.agent_menu = tk.OptionMenu(container, self.agent_var, *agent_names)
        self.agent_menu.configure(
            bg=t["btn_bg"],
            fg=t["fg"],
            activebackground=t["btn_hover"],
            activeforeground=t["fg"],
            highlightthickness=0,
            font=("Consolas", 9)
        )
        self.agent_menu["menu"].configure(
            bg=t["btn_bg"],
            fg=t["fg"],
            activebackground=t["accent"],
            activeforeground="#fff"
        )
        self.agent_menu.pack(fill=tk.X, pady=(4, 12))

        # Task name
        tk.Label(
            container,
            text="Task Name:",
            font=("Consolas", 9),
            bg=t["card_bg"],
            fg=t["fg_dim"]
        ).pack(anchor="w")

        self.task_entry = tk.Entry(
            container,
            font=("Consolas", 10),
            bg=t["btn_bg"],
            fg=t["fg"],
            insertbackground=t["fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"]
        )
        self.task_entry.pack(fill=tk.X, pady=(4, 16), ipady=4)
        self.task_entry.focus_set()

        # Buttons
        btn_frame = tk.Frame(container, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X)

        self.cancel_btn = tk.Label(
            btn_frame,
            text="Cancel",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg_dim"],
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.cancel_btn.bind("<Button-1>", lambda e: self.destroy())

        self.create_btn = tk.Label(
            btn_frame,
            text="Create",
            font=("Consolas", 9, "bold"),
            bg=t["accent"],
            fg="#fff",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.create_btn.pack(side=tk.RIGHT)
        self.create_btn.bind("<Button-1>", lambda e: self._create())

        # Bind Enter key
        self.task_entry.bind("<Return>", lambda e: self._create())
        self.bind("<Escape>", lambda e: self.destroy())

    def _create(self):
        agent_id = self.agent_var.get()
        task_name = self.task_entry.get().strip()

        if not task_name:
            self.task_entry.configure(highlightbackground="#ef4444", highlightcolor="#ef4444")
            return

        self.result = (agent_id, task_name)
        if self.on_create:
            self.on_create(agent_id, task_name)
        self.destroy()


class MergeConfirmDialog(tk.Toplevel):
    """
    Confirmation dialog for merging a worktree.

    Shows worktree info and squash option.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: Dict,
        worktree: WorktreeInfo,
        on_confirm: Callable[[WorktreeInfo, bool], None],
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.worktree = worktree
        self.on_confirm = on_confirm

        self.title("Merge Worktree")
        self.configure(bg=theme["bg"])
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

        # Center window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        t = self.theme
        wt = self.worktree

        container = tk.Frame(self, bg=t["card_bg"], padx=16, pady=16)
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Title
        tk.Label(
            container,
            text="Merge Worktree",
            font=("Segoe UI", 11, "bold"),
            bg=t["card_bg"],
            fg=t["fg"]
        ).pack(anchor="w", pady=(0, 12))

        # Info
        info_frame = tk.Frame(container, bg=t["btn_bg"], padx=8, pady=8)
        info_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            info_frame,
            text=f"Agent: {wt.agent_id}",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg"]
        ).pack(anchor="w")

        tk.Label(
            info_frame,
            text=f"Task: {wt.task_name}",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg"]
        ).pack(anchor="w")

        tk.Label(
            info_frame,
            text=f"Branch: {wt.branch_name}",
            font=("Consolas", 8),
            bg=t["btn_bg"],
            fg=t["fg_dim"]
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            info_frame,
            text=f"{wt.commits_ahead} commits • {wt.uncommitted_files} uncommitted files",
            font=("Consolas", 8),
            bg=t["btn_bg"],
            fg=t["accent"]
        ).pack(anchor="w")

        # Warning for uncommitted
        if wt.uncommitted_files > 0:
            tk.Label(
                container,
                text="⚠ Uncommitted changes will be lost!",
                font=("Consolas", 8),
                bg=t["card_bg"],
                fg="#f59e0b"
            ).pack(anchor="w", pady=(0, 8))

        # Squash option
        self.squash_var = tk.BooleanVar(value=False)
        squash_frame = tk.Frame(container, bg=t["card_bg"])
        squash_frame.pack(fill=tk.X, pady=(0, 12))

        self.squash_cb = tk.Checkbutton(
            squash_frame,
            text="Squash commits",
            variable=self.squash_var,
            font=("Consolas", 9),
            bg=t["card_bg"],
            fg=t["fg"],
            selectcolor=t["btn_bg"],
            activebackground=t["card_bg"],
            activeforeground=t["fg"]
        )
        self.squash_cb.pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(container, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X)

        self.cancel_btn = tk.Label(
            btn_frame,
            text="Cancel",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg_dim"],
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.cancel_btn.bind("<Button-1>", lambda e: self.destroy())

        self.merge_btn = tk.Label(
            btn_frame,
            text="Merge",
            font=("Consolas", 9, "bold"),
            bg=t["online"],
            fg="#fff",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.merge_btn.pack(side=tk.RIGHT)
        self.merge_btn.bind("<Button-1>", lambda e: self._confirm())

        self.bind("<Escape>", lambda e: self.destroy())

    def _confirm(self):
        if self.on_confirm:
            self.on_confirm(self.worktree, self.squash_var.get())
        self.destroy()


class DiscardConfirmDialog(tk.Toplevel):
    """
    Confirmation dialog for discarding a worktree.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: Dict,
        worktree: WorktreeInfo,
        on_confirm: Callable[[WorktreeInfo], None],
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.worktree = worktree
        self.on_confirm = on_confirm

        self.title("Discard Worktree")
        self.configure(bg=theme["bg"])
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

        # Center window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        t = self.theme
        wt = self.worktree

        container = tk.Frame(self, bg=t["card_bg"], padx=16, pady=16)
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Warning icon + title
        tk.Label(
            container,
            text="⚠ Discard Worktree",
            font=("Segoe UI", 11, "bold"),
            bg=t["card_bg"],
            fg="#ef4444"
        ).pack(anchor="w", pady=(0, 12))

        # Info
        tk.Label(
            container,
            text=f"This will permanently delete:",
            font=("Consolas", 9),
            bg=t["card_bg"],
            fg=t["fg"]
        ).pack(anchor="w")

        info_frame = tk.Frame(container, bg=t["btn_bg"], padx=8, pady=8)
        info_frame.pack(fill=tk.X, pady=(8, 12))

        tk.Label(
            info_frame,
            text=f"• Worktree: {wt.path.name}",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg"]
        ).pack(anchor="w")

        tk.Label(
            info_frame,
            text=f"• Branch: {wt.branch_name}",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg"]
        ).pack(anchor="w")

        tk.Label(
            info_frame,
            text=f"• {wt.commits_ahead} commits",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["accent"] if wt.commits_ahead > 0 else t["fg_dim"]
        ).pack(anchor="w")

        # Strong warning
        if wt.commits_ahead > 0 or wt.uncommitted_files > 0:
            tk.Label(
                container,
                text="All changes will be PERMANENTLY LOST!",
                font=("Consolas", 9, "bold"),
                bg=t["card_bg"],
                fg="#ef4444"
            ).pack(pady=(0, 12))

        # Buttons
        btn_frame = tk.Frame(container, bg=t["card_bg"])
        btn_frame.pack(fill=tk.X)

        self.cancel_btn = tk.Label(
            btn_frame,
            text="Cancel",
            font=("Consolas", 9),
            bg=t["btn_bg"],
            fg=t["fg_dim"],
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.cancel_btn.bind("<Button-1>", lambda e: self.destroy())

        self.discard_btn = tk.Label(
            btn_frame,
            text="Discard",
            font=("Consolas", 9, "bold"),
            bg="#ef4444",
            fg="#fff",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.discard_btn.pack(side=tk.RIGHT)
        self.discard_btn.bind("<Button-1>", lambda e: self._confirm())

        self.bind("<Escape>", lambda e: self.destroy())

    def _confirm(self):
        if self.on_confirm:
            self.on_confirm(self.worktree)
        self.destroy()
