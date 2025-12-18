from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Iterable

from .models import AgentSpec, RunSpec


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,
  run_dir TEXT,
  worktree_dir TEXT,
  FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);

CREATE TABLE IF NOT EXISTS run_pids (
  run_id TEXT NOT NULL,
  key TEXT NOT NULL,
  pid INTEGER NOT NULL,
  PRIMARY KEY(run_id, key),
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS resources_ports (
  name TEXT PRIMARY KEY,
  port INTEGER NOT NULL,
  run_id TEXT,
  allocated_at TEXT,
  UNIQUE(port),
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
"""


@dataclass(slots=True)
class Registry:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def upsert_agent(self, spec: AgentSpec) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO agents(agent_id, name, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                  name=excluded.name,
                  role=excluded.role
                """,
                (spec.agent_id, spec.name, spec.role, spec.created_at.isoformat()),
            )

    def create_run(self, run: RunSpec) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, agent_id, created_at, status, run_dir, worktree_dir)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.agent_id,
                    run.created_at.isoformat(),
                    run.status,
                    str(run.run_dir) if run.run_dir else None,
                    str(run.worktree_dir) if run.worktree_dir else None,
                ),
            )

    def set_run_status(self, run_id: str, status: str) -> None:
        with self.tx() as conn:
            conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))

    def attach_pid(self, run_id: str, key: str, pid: int) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO run_pids(run_id, key, pid)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id, key) DO UPDATE SET pid=excluded.pid
                """,
                (run_id, key, pid),
            )

    def allocate_port(self, name: str, port: int, run_id: str | None, allocated_at_iso: str) -> None:
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO resources_ports(name, port, run_id, allocated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, port, run_id, allocated_at_iso),
            )

    def release_port(self, name: str) -> None:
        with self.tx() as conn:
            conn.execute("DELETE FROM resources_ports WHERE name=?", (name,))

    def get_allocated_ports(self) -> set[int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT port FROM resources_ports").fetchall()
            return {int(r["port"]) for r in rows}

    def release_ports_for_runs(self, run_ids: Iterable[str]) -> None:
        run_ids_list = list(run_ids)
        if not run_ids_list:
            return
        placeholders = ",".join("?" for _ in run_ids_list)
        with self.tx() as conn:
            conn.execute(f"DELETE FROM resources_ports WHERE run_id IN ({placeholders})", run_ids_list)
