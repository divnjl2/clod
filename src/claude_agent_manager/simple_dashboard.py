"""Simple Tkinter dashboard for creating and controlling agents.

This module provides a minimalistic GUI with a dark gray theme. Users can
specify how many agents to create, start, and stop them, and view the agents in
an automatically sized grid layout.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from math import ceil
from typing import List


@dataclass
class Agent:
    """Simple representation of an agent."""

    identifier: int
    running: bool = field(default=False)
    memory_type: str = field(default="Context")

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

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

        self._setup_styles()
        self._build_layout()
        self.agent_count.trace_add("write", self._sync_agent_count)

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
            )
            for i in range(count)
        ]
        self.status_var.set(f"Created {len(self.agents)} agents")
        self._render_agents()

    def start_agents(self) -> None:
        for agent in self.agents:
            agent.start()
        self.status_var.set("Agents started")
        self._render_agents()

    def stop_agents(self) -> None:
        for agent in self.agents:
            agent.stop()
        self.status_var.set("Agents stopped")
        self._render_agents()

    def _start_agent(self, agent: Agent) -> None:
        agent.start()
        self.status_var.set(f"Started agent {agent.identifier}")
        self._render_agents()

    def _stop_agent(self, agent: Agent) -> None:
        agent.stop()
        self.status_var.set(f"Stopped agent {agent.identifier}")
        self._render_agents()

    def _delete_agent(self, agent: Agent) -> None:
        agent.delete()
        self.agents = [a for a in self.agents if a is not agent]
        self.status_var.set(f"Deleted agent {agent.identifier}")
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
                    )
                )
            self.status_var.set(f"Added agents up to {desired} total")
        else:
            self.agents = self.agents[:desired]
            self.status_var.set(f"Trimmed agents down to {desired} total")

        self._render_agents()

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
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        if not self.agents:
            empty = tk.Label(
                self.grid_frame,
                text="No agents yet",
                bg=self.bg_color,
                fg=self.fg_color,
            )
            empty.pack()
            return

        rows, cols = self._compute_grid_dimensions(len(self.agents))

        for index, agent in enumerate(self.agents):
            row, col = divmod(index, cols)
            tile = tk.Frame(
                self.grid_frame,
                bg=self.button_bg,
                bd=1,
                relief=tk.RIDGE,
                width=120,
                height=80,
            )
            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            tile.grid_propagate(False)

            tk.Label(
                tile,
                text=f"Agent {agent.identifier}",
                bg=self.button_bg,
                fg=self.fg_color,
                font=("Segoe UI", 11, "bold"),
            ).pack(pady=(10, 4))

            state_text = "Running" if agent.running else "Stopped"
            state_color = "#8dc891" if agent.running else "#e6e6e6"
            tk.Label(
                tile,
                text=state_text,
                bg=self.button_bg,
                fg=state_color,
                font=("Segoe UI", 10),
            ).pack()

            tk.Label(
                tile,
                text=f"Memory: {agent.memory_type}",
                bg=self.button_bg,
                fg=self.fg_color,
                font=("Segoe UI", 9),
            ).pack(pady=(4, 0))

            button_row = tk.Frame(tile, bg=self.button_bg)
            button_row.pack(pady=(8, 0))

            start_state = tk.DISABLED if agent.running else tk.NORMAL
            tk.Button(
                button_row,
                text="Start",
                command=lambda a=agent: self._start_agent(a),
                bg=self.button_bg,
                fg=self.fg_color,
                activebackground=self.accent_color,
                activeforeground=self.fg_color,
                relief=tk.FLAT,
                width=8,
                state=start_state,
            ).grid(row=0, column=0, padx=2)

            tk.Button(
                button_row,
                text="Stop",
                command=lambda a=agent: self._stop_agent(a),
                bg=self.button_bg,
                fg=self.fg_color,
                activebackground=self.accent_color,
                activeforeground=self.fg_color,
                relief=tk.FLAT,
                width=8,
            ).grid(row=0, column=1, padx=2)

            tk.Button(
                button_row,
                text="Delete",
                command=lambda a=agent: self._delete_agent(a),
                bg=self.button_bg,
                fg=self.fg_color,
                activebackground="#a94442",
                activeforeground=self.fg_color,
                relief=tk.FLAT,
                width=8,
            ).grid(row=0, column=2, padx=2)

        for i in range(cols):
            self.grid_frame.columnconfigure(i, weight=1)
        for i in range(rows):
            self.grid_frame.rowconfigure(i, weight=1)


def launch_dashboard() -> None:
    root = tk.Tk()
    AgentDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    launch_dashboard()
