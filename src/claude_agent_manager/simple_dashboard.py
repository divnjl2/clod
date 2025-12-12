"""Simple Tkinter dashboard for creating and controlling agents.

This module provides a minimalistic GUI with a dark gray theme. Users can
specify how many agents to create, start, and stop them, and view the agents in
an automatically sized grid layout.
"""

from __future__ import annotations

import shutil
import subprocess
import tkinter as tk
from dataclasses import dataclass, field
from math import ceil
from typing import Dict, List, Optional


@dataclass
class Agent:
    """Simple representation of an agent."""

    identifier: int
    running: bool = field(default=False)
    memory_type: str = field(default="Context")
    use_browser: bool = field(default=True)
    port: Optional[int] = field(default=None)
    pid: Optional[int] = field(default=None)

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False
        self.pid = None

    def delete(self) -> None:
        """Reset any runtime state before removal."""
        self.stop()


class AgentDashboard:
    """Minimalistic Tkinter dashboard for managing agents."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Agent Dashboard")
        self.root.configure(bg="#2b2b2b")

        self.agents: List[Agent] = []
        self.memory_types = ["Short-term", "Long-term", "Episodic"]
        self.agent_widgets: Dict[int, Dict[str, tk.Widget]] = {}
        self._pid_counter = 10_000

        self._setup_styles()
        self._build_layout()
        self.agent_count.trace_add("write", self._sync_agent_count)
        self._schedule_status_updates()

    def _setup_styles(self) -> None:
        self.bg_color = "#2b2b2b"
        self.fg_color = "#e6e6e6"
        self.button_bg = "#3c3c3c"
        self.accent_color = "#5a5a5a"

    def _build_layout(self) -> None:
        header = tk.Label(
            self.root,
            text="Agent Controller",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 16, "bold"),
        )
        header.pack(pady=(12, 8))

        self.counter_var = tk.StringVar(value="Agents: 0")
        counter = tk.Label(
            self.root,
            textvariable=self.counter_var,
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 10),
        )
        counter.pack(pady=(0, 6))

        control_frame = tk.Frame(self.root, bg=self.bg_color)
        control_frame.pack(fill=tk.X, padx=16, pady=8)

        tk.Label(
            control_frame,
            text="Number of agents:",
            bg=self.bg_color,
            fg=self.fg_color,
        ).grid(row=0, column=0, sticky="w")

        self.agent_count = tk.IntVar(value=4)
        self.count_scale = tk.Scale(
            control_frame,
            from_=1,
            to=25,
            orient=tk.HORIZONTAL,
            variable=self.agent_count,
            bg=self.bg_color,
            fg=self.fg_color,
            troughcolor=self.accent_color,
            highlightthickness=0,
            length=220,
        )
        self.count_scale.grid(row=0, column=1, padx=8, pady=4)

        button_frame = tk.Frame(control_frame, bg=self.bg_color)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(8, 0))

        tk.Button(
            button_frame,
            text="Create Agents",
            command=self.create_agents,
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground=self.accent_color,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            button_frame,
            text="Start Agents",
            command=self.start_agents,
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground=self.accent_color,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            button_frame,
            text="Stop Agents",
            command=self.stop_agents,
            bg=self.button_bg,
            fg=self.fg_color,
            activebackground=self.accent_color,
            activeforeground=self.fg_color,
            relief=tk.FLAT,
            width=14,
        ).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="No agents created yet")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=self.bg_color,
            fg=self.fg_color,
            anchor="w",
        )
        status.pack(fill=tk.X, padx=16, pady=(4, 8))

        self.grid_frame = tk.Frame(self.root, bg=self.bg_color)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

    def create_agents(self) -> None:
        count = max(1, self.agent_count.get())
        self.agents = [
            Agent(
                identifier=i + 1,
                memory_type=self.memory_types[i % len(self.memory_types)],
                use_browser=(i % 2 == 0),
                port=10_000 + i,
            )
            for i in range(count)
        ]
        self.status_var.set(f"Created {len(self.agents)} agents")
        self._update_agent_counter()
        self._render_agents()

    def start_agents(self) -> None:
        for agent in self.agents:
            agent.start()
            if agent.use_browser:
                agent.pid = self._launch_browser(agent, headless=True)
            else:
                agent.pid = self._start_headless_process(agent)
        self.status_var.set("Agents started")
        self._update_agent_counter()
        self._render_agents()

    def stop_agents(self) -> None:
        for agent in self.agents:
            agent.stop()
        self.status_var.set("Agents stopped")
        self._update_agent_counter()
        self._render_agents()

    def _start_agent(self, agent: Agent) -> None:
        agent.start()
        if agent.use_browser:
            agent.pid = self._launch_browser(agent, headless=True)
        else:
            agent.pid = self._start_headless_process(agent)
        self.status_var.set(f"Started agent {agent.identifier}")
        self._update_agent_counter()
        self._update_agent_card(agent)

    def _stop_agent(self, agent: Agent) -> None:
        agent.stop()
        self.status_var.set(f"Stopped agent {agent.identifier}")
        self._update_agent_counter()
        self._update_agent_card(agent)

    def _delete_agent(self, agent: Agent) -> None:
        agent.delete()
        self.agents = [a for a in self.agents if a is not agent]
        self.status_var.set(f"Deleted agent {agent.identifier}")
        self._update_agent_counter()
        self._render_agents()

    def _sync_agent_count(self, *_: object) -> None:
        """Adjust the grid when the agent count slider changes."""

        desired = max(1, self.agent_count.get())
        current = len(self.agents)

        if desired == current:
            return

        if desired > current:
            for i in range(current, desired):
                self.agents.append(
                    Agent(
                        identifier=i + 1,
                        running=False,
                        memory_type=self.memory_types[i % len(self.memory_types)],
                        use_browser=((i + 1) % 2 == 1),
                        port=10_000 + i,
                    )
                )
            self.status_var.set(f"Added agents up to {desired} total")
        else:
            self.agents = self.agents[:desired]
            self.status_var.set(f"Trimmed agents down to {desired} total")

        self._update_agent_counter()
        self._render_agents()

    def _update_agent_counter(self) -> None:
        """Refresh the visible count of agents."""

        self.counter_var.set(f"Agents: {len(self.agents)}")

    @staticmethod
    def _compute_grid_dimensions(count: int) -> tuple[int, int]:
        """Return rows and columns for a compact, near-square grid."""

        if count <= 0:
            return (0, 0)

        best_rows, best_cols = 1, count
        best_area = best_cols * best_rows

        for rows in range(1, count + 1):
            cols = ceil(count / rows)
            area = rows * cols
            if area < best_area or (area == best_area and cols - rows < best_cols - best_rows):
                best_rows, best_cols, best_area = rows, cols, area
            if rows > cols:
                break

        return best_rows, best_cols

    def _render_agents(self) -> None:
        tracked_frames = {info["frame"] for info in self.agent_widgets.values()}
        for widget in list(self.grid_frame.winfo_children()):
            if widget not in tracked_frames:
                widget.destroy()
            else:
                widget.pack_forget()
                widget.grid_forget()

        if not self.agents:
            for widget in self.grid_frame.winfo_children():
                widget.destroy()
            empty = tk.Label(
                self.grid_frame,
                text="No agents yet",
                bg=self.bg_color,
                fg=self.fg_color,
            )
            empty.pack()
            self.agent_widgets.clear()
            return

        rows, cols = self._compute_grid_dimensions(len(self.agents))

        # Remove widgets for agents that were deleted
        existing_ids = {agent.identifier for agent in self.agents}
        for identifier in list(self.agent_widgets.keys()):
            if identifier not in existing_ids:
                frame = self.agent_widgets[identifier]["frame"]
                frame.destroy()
                del self.agent_widgets[identifier]

        for index, agent in enumerate(self.agents):
            row, col = divmod(index, cols)
            card = self.agent_widgets.get(agent.identifier)

            if not card:
                tile = tk.Frame(
                    self.grid_frame,
                    bg=self.button_bg,
                    bd=1,
                    relief=tk.RIDGE,
                    width=150,
                    height=110,
                )
                tile.grid_propagate(False)

                title_label = tk.Label(
                    tile,
                    text=f"Agent {agent.identifier}",
                    bg=self.button_bg,
                    fg=self.fg_color,
                    font=("Segoe UI", 11, "bold"),
                )
                title_label.pack(pady=(8, 2))

                mode_label = tk.Label(
                    tile,
                    text="",
                    bg=self.button_bg,
                    fg=self.fg_color,
                    font=("Segoe UI", 9, "italic"),
                )
                mode_label.pack()

                state_label = tk.Label(
                    tile,
                    text="",
                    bg=self.button_bg,
                    fg=self.fg_color,
                    font=("Segoe UI", 10),
                )
                state_label.pack()

                pid_label = tk.Label(
                    tile,
                    text="",
                    bg=self.button_bg,
                    fg=self.fg_color,
                    font=("Segoe UI", 9),
                )
                pid_label.pack(pady=(2, 0))

                tk.Label(
                    tile,
                    text=f"Memory: {agent.memory_type}",
                    bg=self.button_bg,
                    fg=self.fg_color,
                    font=("Segoe UI", 9),
                ).pack(pady=(2, 0))

                button_row = tk.Frame(tile, bg=self.button_bg)
                button_row.pack(pady=(8, 0))

                start_btn = tk.Button(
                    button_row,
                    text="Start",
                    command=lambda a=agent: self._start_agent(a),
                    bg=self.button_bg,
                    fg=self.fg_color,
                    activebackground=self.accent_color,
                    activeforeground=self.fg_color,
                    relief=tk.FLAT,
                    width=8,
                )
                start_btn.grid(row=0, column=0, padx=2)

                stop_btn = tk.Button(
                    button_row,
                    text="Stop",
                    command=lambda a=agent: self._stop_agent(a),
                    bg=self.button_bg,
                    fg=self.fg_color,
                    activebackground=self.accent_color,
                    activeforeground=self.fg_color,
                    relief=tk.FLAT,
                    width=8,
                )
                stop_btn.grid(row=0, column=1, padx=2)

                delete_btn = tk.Button(
                    button_row,
                    text="Delete",
                    command=lambda a=agent: self._delete_agent(a),
                    bg=self.button_bg,
                    fg=self.fg_color,
                    activebackground="#a94442",
                    activeforeground=self.fg_color,
                    relief=tk.FLAT,
                    width=8,
                )
                delete_btn.grid(row=0, column=2, padx=2)

                self.agent_widgets[agent.identifier] = {
                    "frame": tile,
                    "state": state_label,
                    "mode": mode_label,
                    "pid": pid_label,
                    "start": start_btn,
                    "stop": stop_btn,
                    "delete": delete_btn,
                }
                card = self.agent_widgets[agent.identifier]

            frame = card["frame"]
            frame.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._update_agent_card(agent)

        for i in range(cols):
            self.grid_frame.columnconfigure(i, weight=1)
        for i in range(rows):
            self.grid_frame.rowconfigure(i, weight=1)

    def _update_agent_card(self, agent: Agent) -> None:
        card = self.agent_widgets.get(agent.identifier)
        if not card:
            return

        status_text = "Running" if agent.running else "Stopped"
        status_color = "#8dc891" if agent.running else "#f47c7c"
        card["state"].configure(text=status_text, fg=status_color)

        mode_text = "With Browser" if agent.use_browser else "Headless"
        card["mode"].configure(text=mode_text)

        pid_text = f"PID: {agent.pid or 'n/a'}"
        card["pid"].configure(text=pid_text)

        start_state = tk.DISABLED if agent.running else tk.NORMAL
        stop_state = tk.NORMAL if agent.running else tk.DISABLED
        card["start"].configure(state=start_state)
        card["stop"].configure(state=stop_state)

    def _launch_browser(self, agent: Agent, *, headless: bool) -> Optional[int]:
        url = f"http://localhost:{agent.port or (10_000 + agent.identifier)}"
        edge = shutil.which("msedge") or shutil.which("msedge.exe")
        args = [
            f"--app={url}",
            "--new-window",
            "--force-dark-mode",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
        ]
        if headless:
            args.append("--headless=new")

        try:
            proc = subprocess.Popen([edge or "msedge", *args])
            self._show_browser_window(agent, url, proc.pid, headless=headless)
            return proc.pid
        except FileNotFoundError:
            self._show_browser_window(agent, url, None, headless=headless)
            return None

    def _show_browser_window(self, agent: Agent, url: str, pid: Optional[int], *, headless: bool) -> None:
        top = tk.Toplevel(self.root)
        top.title(f"Agent {agent.identifier} Browser")
        top.configure(bg=self.bg_color)

        tk.Label(
            top,
            text="With Browser" if agent.use_browser else "Headless",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=10, pady=(10, 4))

        tk.Label(
            top,
            text=f"URL: {url}\nMode: {'Headless' if headless else 'Windowed'}",
            bg=self.bg_color,
            fg=self.fg_color,
            justify=tk.LEFT,
        ).pack(padx=10, pady=(0, 6))

        status_line = "Edge launched" if pid else "Edge executable not found"
        tk.Label(
            top,
            text=status_line,
            bg=self.bg_color,
            fg=self.accent_color,
        ).pack(padx=10, pady=(0, 10))

    def _start_headless_process(self, agent: Agent) -> int:
        self._pid_counter += 1
        pseudo_pid = self._pid_counter
        top = tk.Toplevel(self.root)
        top.title(f"Agent {agent.identifier} Headless")
        top.configure(bg=self.bg_color)

        tk.Label(
            top,
            text="Headless",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=10, pady=(10, 4))

        tk.Label(
            top,
            text=f"Simulated process PID: {pseudo_pid}\nStatus: Running",
            bg=self.bg_color,
            fg=self.fg_color,
            justify=tk.LEFT,
        ).pack(padx=10, pady=(0, 10))

        return pseudo_pid

    def _schedule_status_updates(self) -> None:
        for agent in self.agents:
            self._update_agent_card(agent)
        self.root.after(2000, self._schedule_status_updates)


def launch_dashboard() -> None:
    root = tk.Tk()
    AgentDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    launch_dashboard()
