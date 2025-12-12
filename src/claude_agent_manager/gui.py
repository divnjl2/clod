"""
Claude Agent Manager - Tkinter GUI
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Optional

from .config import load_config, save_config, AppConfig
from .registry import AgentRecord, iter_agents, load_agent, save_agent
from .processes import (
    is_pid_running,
    kill_tree,
    pm2_delete,
    pm2_exists,
    spawn_browser,
    spawn_cmd_window,
    which,
)
from .worker import pick_port, start_worker
from .tile import tile_two_in_cell
import random
import shutil
import subprocess
import ctypes
from ctypes import wintypes


class AgentManagerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Claude Agent Manager")
        self.root.geometry("800x600")
        self.root.configure(bg="#1e1e1e")

        # Dark theme colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#007acc"
        self.button_bg = "#333333"
        self.listbox_bg = "#252526"
        self.selected_bg = "#094771"

        self.cfg = load_config()

        self._setup_styles()
        self._create_widgets()
        self._refresh_agents()
        self._schedule_status_refresh()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Dark.TFrame", background=self.bg_color)
        style.configure("Dark.TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("Dark.TButton", background=self.button_bg, foreground=self.fg_color)
        style.configure("Accent.TButton", background=self.accent_color, foreground=self.fg_color)
        style.configure("Dark.TEntry", fieldbackground=self.listbox_bg, foreground=self.fg_color)
        style.configure("Dark.TLabelframe", background=self.bg_color, foreground=self.fg_color)
        style.configure("Dark.TLabelframe.Label", background=self.bg_color, foreground=self.fg_color)

    def _create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, style="Dark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # === Top: Config section ===
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", style="Dark.TLabelframe")
        config_frame.pack(fill=tk.X, pady=(0, 10))

        # Claude-mem root
        ttk.Label(config_frame, text="Claude-Mem Root:", style="Dark.TLabel").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.mem_root_var = tk.StringVar(value=self.cfg.claude_mem_root or "")
        self.mem_root_entry = ttk.Entry(config_frame, textvariable=self.mem_root_var, width=50)
        self.mem_root_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(config_frame, text="Browse", command=self._browse_mem_root).grid(row=0, column=2, padx=5)

        # Worker script
        ttk.Label(config_frame, text="Worker Script:", style="Dark.TLabel").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.worker_script_var = tk.StringVar(value=self.cfg.worker_script or "")
        self.worker_script_entry = ttk.Entry(config_frame, textvariable=self.worker_script_var, width=50)
        self.worker_script_entry.grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(config_frame, text="Browse", command=self._browse_worker_script).grid(row=1, column=2, padx=5)

        ttk.Button(config_frame, text="Save Config", command=self._save_config).grid(row=2, column=1, pady=5)

        # === Middle: Agent list ===
        list_frame = ttk.LabelFrame(main_frame, text="Agents", style="Dark.TLabelframe")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview for agents
        columns = ("id", "status", "purpose", "mode", "port", "pm2", "cmd", "viewer", "project")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)

        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("purpose", text="Purpose")
        self.tree.heading("mode", text="Mode")
        self.tree.heading("port", text="Port")
        self.tree.heading("pm2", text="PM2")
        self.tree.heading("cmd", text="CMD")
        self.tree.heading("viewer", text="Viewer")
        self.tree.heading("project", text="Project")

        self.tree.column("id", width=90)
        self.tree.column("status", width=80)
        self.tree.column("purpose", width=100)
        self.tree.column("mode", width=110)
        self.tree.column("port", width=60)
        self.tree.column("pm2", width=70)
        self.tree.column("cmd", width=70)
        self.tree.column("viewer", width=70)
        self.tree.column("project", width=240)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # === Bottom: Actions ===
        actions_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        actions_frame.pack(fill=tk.X)

        # New agent section
        new_frame = ttk.LabelFrame(actions_frame, text="Create New Agent", style="Dark.TLabelframe")
        new_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(new_frame, text="Purpose:", style="Dark.TLabel").grid(row=0, column=0, padx=5, pady=2)
        self.purpose_var = tk.StringVar(value="dev")
        ttk.Entry(new_frame, textvariable=self.purpose_var, width=15).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(new_frame, text="Project:", style="Dark.TLabel").grid(row=1, column=0, padx=5, pady=2)
        self.project_var = tk.StringVar(value=str(Path.home() / "Desktop"))
        ttk.Entry(new_frame, textvariable=self.project_var, width=30).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(new_frame, text="...", command=self._browse_project, width=3).grid(row=1, column=2, padx=2)

        self.browser_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(new_frame, text="Open Browser", variable=self.browser_var).grid(row=2, column=0, columnspan=2, pady=2)

        ttk.Button(new_frame, text="Create Agent", command=self._create_agent).grid(row=3, column=0, columnspan=3, pady=5)

        # Control buttons
        btn_frame = ttk.LabelFrame(actions_frame, text="Actions", style="Dark.TLabelframe")
        btn_frame.pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="Refresh", command=self._refresh_agents).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Open Browser", command=self._open_browser).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Stop Selected", command=self._stop_selected).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Stop All", command=self._stop_all).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(btn_frame, text="Tile Windows", command=self._tile_windows).pack(side=tk.LEFT, padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, style="Dark.TLabel")
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def _browse_mem_root(self):
        path = filedialog.askdirectory()
        if path:
            self.mem_root_var.set(path)

    def _browse_worker_script(self):
        path = filedialog.askopenfilename(filetypes=[("JavaScript", "*.cjs *.js"), ("All", "*.*")])
        if path:
            self.worker_script_var.set(path)

    def _browse_project(self):
        path = filedialog.askdirectory()
        if path:
            self.project_var.set(path)

    def _save_config(self):
        try:
            data = self.cfg.model_dump()
            data["claude_mem_root"] = self.mem_root_var.get() or None
            data["worker_script"] = self.worker_script_var.get() or None
            self.cfg = AppConfig(**data)
            save_config(self.cfg)
            self.status_var.set("Config saved")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_agent_root(self) -> Path:
        p = Path(self.cfg.agent_root)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _refresh_agents(self, preserve_selection: bool = False):
        selected_ids = []
        if preserve_selection:
            selected_ids = [self.tree.item(item)["values"][0] for item in self.tree.selection()]

        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Load agents
        agent_root = self._get_agent_root()
        agents = iter_agents(agent_root)

        for a in agents:
            pm2_state = "ONLINE" if pm2_exists(a.pm2_name) else "OFFLINE"
            cmd_state = "RUNNING" if is_pid_running(a.cmd_pid) else "STOPPED"
            view_state = "RUNNING" if is_pid_running(a.viewer_pid) else "STOPPED"
            browser_state = "With Browser" if a.use_browser else "Headless"

            is_running = pm2_state == "ONLINE" or cmd_state == "RUNNING" or view_state == "RUNNING"
            status_text = "Running" if is_running else "Stopped"
            tag = "running" if is_running else "stopped"

            self.tree.insert("", tk.END, values=(
                a.id,
                status_text,
                a.purpose,
                browser_state,
                a.port,
                pm2_state,
                cmd_state,
                view_state,
                a.project_path
            ), tags=(tag,))

        self.tree.tag_configure("running", foreground="#4ec9b0")
        self.tree.tag_configure("stopped", foreground="#f14c4c")

        if preserve_selection and selected_ids:
            for item in self.tree.get_children():
                values = self.tree.item(item)["values"]
                if values and values[0] in selected_ids:
                    self.tree.selection_add(item)

        self.status_var.set(f"Loaded {len(agents)} agents")

    def _schedule_status_refresh(self) -> None:
        self._refresh_agents(preserve_selection=True)
        self.root.after(2000, self._schedule_status_refresh)

    def _launch_browser_view(self, agent_id: str, url: str, *, headless: bool) -> Optional[int]:
        """Open a viewer window and surface it inside the Tk app."""
        top = tk.Toplevel(self.root)
        top.title(f"Viewer for {agent_id}")
        top.configure(bg=self.bg_color)

        mode_label = tk.Label(top, text="With Browser", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 12, "bold"))
        mode_label.pack(padx=10, pady=(10, 5))

        tk.Label(
            top,
            text=f"Launching embedded browser view for {agent_id}\n{url}\n(Edge headless mode)",
            bg=self.bg_color,
            fg=self.fg_color,
            justify=tk.LEFT,
        ).pack(padx=10, pady=(0, 10))

        viewer_pid = spawn_browser(url, self.cfg.browser, agent_id=agent_id, headless=headless)

        status_text = "Browser process started" if viewer_pid else "Browser launched externally"
        tk.Label(top, text=status_text, bg=self.bg_color, fg=self.accent_color).pack(padx=10, pady=(0, 10))

        return viewer_pid

    def _show_headless_info(self, agent_id: str, url: str) -> None:
        """Show a textual summary for headless-only agents."""
        top = tk.Toplevel(self.root)
        top.title(f"Headless agent {agent_id}")
        top.configure(bg=self.bg_color)

        tk.Label(
            top,
            text="Headless",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=10, pady=(10, 5))

        tk.Label(
            top,
            text=("Этому агенту не нужен браузер.\n"
                  f"Порт сервера: {url}\n"
                  "Вся работа выполняется в памяти."),
            bg=self.bg_color,
            fg=self.fg_color,
            justify=tk.LEFT,
        ).pack(padx=10, pady=(0, 10))

    def _create_agent(self):
        def do_create():
            try:
                self.cfg = load_config()
                if not self.cfg.claude_mem_root or not self.cfg.worker_script:
                    messagebox.showerror("Error", "Please configure claude_mem_root and worker_script first")
                    return

                agent_root = self._get_agent_root()
                used_ports = {a.port for a in iter_agents(agent_root)}
                port = pick_port(self.cfg, used_ports)
                agent_id = f"{random.randint(1000, 9999)}-{port}"

                agent_dir = agent_root / agent_id
                agent_dir.mkdir(parents=True, exist_ok=True)

                pm2_name = f"agent-{agent_id}"
                project_path = Path(self.project_var.get()).resolve()

                if not project_path.exists():
                    messagebox.showerror("Error", f"Project path not found: {project_path}")
                    return

                self.status_var.set(f"Creating agent {agent_id}...")
                self.root.update()

                # Start worker
                start_worker(self.cfg, pm2_name=pm2_name, port=port, data_dir=agent_dir)

                # Open browser if requested
                viewer_pid = None
                use_browser = self.browser_var.get()
                url = f"http://localhost:{port}"
                if use_browser:
                    viewer_pid = self._launch_browser_view(agent_id, url, headless=True)
                else:
                    self._show_headless_info(agent_id, url)

                # Create run.cmd and spawn claude window
                run_cmd = agent_dir / "run.cmd"
                title = f"Agent {agent_id} @ {port} ({self.purpose_var.get()})"
                content = (
                    "@echo off\n"
                    "chcp 65001 >nul 2>&1\n"
                    f"title {title}\n"
                    f"set CLAUDE_MEM_WORKER_PORT={port}\n"
                    f"set CLAUDE_MEM_DATA_DIR={agent_dir}\n"
                    f"cd /d \"{project_path}\"\n"
                    "claude\n"
                )
                run_cmd.write_text(content, encoding="utf-8")
                cmd_pid = spawn_cmd_window(run_cmd, workdir=str(project_path))

                # Save agent record
                rec = AgentRecord(
                    id=agent_id,
                    purpose=self.purpose_var.get(),
                    project_path=str(project_path),
                    port=port,
                    pm2_name=pm2_name,
                    cmd_pid=cmd_pid,
                    viewer_pid=viewer_pid,
                    use_browser=use_browser,
                )
                save_agent(agent_root, rec)

                self.status_var.set(f"Created agent: {agent_id}")
                self._refresh_agents()

            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.status_var.set("Error creating agent")

        threading.Thread(target=do_create, daemon=True).start()

    def _get_selected_agent(self) -> Optional[AgentRecord]:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an agent")
            return None

        item = self.tree.item(selection[0])
        agent_id = item["values"][0]
        agent_root = self._get_agent_root()
        return load_agent(agent_root, agent_id)

    def _open_browser(self):
        agent = self._get_selected_agent()
        if agent:
            url = f"http://localhost:{agent.port}"
            if agent.use_browser:
                self._launch_browser_view(agent.id, url, headless=True)
                self.status_var.set(f"Opened browser for {agent.id}")
            else:
                self._show_headless_info(agent.id, url)
                self.status_var.set(f"Agent {agent.id} is headless; browser not required")

    def _stop_selected(self):
        agent = self._get_selected_agent()
        if agent:
            self._stop_agent(agent)
            self._refresh_agents()

    def _stop_agent(self, agent: AgentRecord, purge: bool = False):
        try:
            pm2_delete(agent.pm2_name)
        except:
            pass

        if agent.cmd_pid and is_pid_running(agent.cmd_pid):
            try:
                kill_tree(agent.cmd_pid)
            except:
                pass

        if agent.viewer_pid and is_pid_running(agent.viewer_pid):
            try:
                kill_tree(agent.viewer_pid)
            except:
                pass

        if purge:
            agent_root = self._get_agent_root()
            shutil.rmtree(agent_root / agent.id, ignore_errors=True)

        self.status_var.set(f"Stopped agent: {agent.id}")

    def _stop_all(self):
        if messagebox.askyesno("Confirm", "Stop all agents?"):
            agent_root = self._get_agent_root()
            for agent in iter_agents(agent_root):
                self._stop_agent(agent)
            self._refresh_agents()

    def _tile_windows(self):
        try:
            # Get screen work area
            SPI_GETWORKAREA = 0x0030
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)

            work_x, work_y = rect.left, rect.top
            work_w, work_h = rect.right - rect.left, rect.bottom - rect.top

            agent_root = self._get_agent_root()
            agents = iter_agents(agent_root)
            agents.sort(key=lambda a: a.created_at, reverse=True)
            agents = agents[:4]

            cols, rows = 2, 2
            cell_w, cell_h = work_w // cols, work_h // rows

            for i, a in enumerate(agents):
                row = i // cols
                col = i % cols
                if row >= rows:
                    break
                x = work_x + col * cell_w
                y = work_y + row * cell_h
                tile_two_in_cell(a.cmd_pid, a.viewer_pid, x, y, cell_w, cell_h)

            self.status_var.set(f"Tiled {len(agents)} agents")
        except Exception as e:
            messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    app = AgentManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
