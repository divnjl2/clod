"""
Claude-Mem Bridge
=================

Bridge between claude-mem (session observations) and clod GraphMemory (structured knowledge).

claude-mem captures:
- observations: decision, bugfix, feature, refactor, discovery, change
- session_summaries: request, investigated, learned, completed, next_steps
- user_prompts: prompt history

This bridge syncs observations into GraphMemory nodes with proper type mapping:
- decision → DECISION
- bugfix → ERROR (with FIXED_BY relation if fix is mentioned)
- feature → TASK
- refactor → FACT (metadata: refactor=true)
- discovery → PATTERN or FACT
- change → FACT

Usage:
    from claude_agent_manager.memory import ClaudeMemBridge

    bridge = ClaudeMemBridge(agent_id="my-agent")

    # Sync all observations from claude-mem to GraphMemory
    stats = bridge.sync_from_claude_mem()

    # Get combined context
    context = bridge.get_unified_context(query="authentication")
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from .graph_memory import GraphMemory, NodeType, RelationType, MemoryNode

logger = logging.getLogger(__name__)


# Type mapping: claude-mem observation type → GraphMemory NodeType
OBSERVATION_TYPE_MAP = {
    "decision": NodeType.DECISION,
    "bugfix": NodeType.ERROR,
    "feature": NodeType.TASK,
    "refactor": NodeType.FACT,
    "discovery": NodeType.PATTERN,
    "change": NodeType.FACT,
}

# Importance weights by observation type
IMPORTANCE_WEIGHTS = {
    "decision": 0.8,   # Decisions are important
    "bugfix": 0.9,     # Don't repeat mistakes
    "feature": 0.7,    # Features are noteworthy
    "refactor": 0.5,   # Refactors are context
    "discovery": 0.85, # Discoveries are valuable
    "change": 0.4,     # Changes are basic context
}


@dataclass
class ClaudeMemObservation:
    """Observation from claude-mem database."""
    id: int
    sdk_session_id: str
    project: str
    text: Optional[str]
    type: str
    title: Optional[str]
    subtitle: Optional[str]
    facts: Optional[str]
    narrative: Optional[str]
    concepts: Optional[str]
    files_read: Optional[str]
    files_modified: Optional[str]
    prompt_number: Optional[int]
    created_at: str
    created_at_epoch: int


@dataclass
class ClaudeMemSession:
    """Session from claude-mem database."""
    id: int
    claude_session_id: str
    sdk_session_id: Optional[str]
    project: str
    user_prompt: Optional[str]
    started_at: str
    started_at_epoch: int
    completed_at: Optional[str]
    status: str


@dataclass
class SyncStats:
    """Statistics from sync operation."""
    observations_synced: int = 0
    sessions_synced: int = 0
    nodes_created: int = 0
    relations_created: int = 0
    errors: int = 0
    skipped: int = 0


class ClaudeMemBridge:
    """
    Bridge between claude-mem and GraphMemory.

    Reads observations from claude-mem SQLite database and converts them
    to GraphMemory nodes with proper type mapping and relations.
    """

    DEFAULT_CLAUDE_MEM_PATHS = [
        Path.home() / ".claude-mem" / "claude-mem.db",
        Path.home() / ".claude-agents",  # Will search for claude-mem.db files
    ]

    def __init__(
        self,
        agent_id: str,
        claude_mem_db: Optional[Path] = None,
        graph_memory: Optional[GraphMemory] = None,
    ):
        """
        Initialize bridge.

        Args:
            agent_id: Agent ID for GraphMemory
            claude_mem_db: Path to claude-mem database (auto-detect if None)
            graph_memory: Existing GraphMemory instance (creates new if None)
        """
        self.agent_id = agent_id
        self.claude_mem_db = claude_mem_db or self._find_claude_mem_db()
        self._graph_memory = graph_memory
        self._synced_observation_ids: set = set()

    def _find_claude_mem_db(self) -> Optional[Path]:
        """Find claude-mem database file."""
        # Check default location
        default_path = Path.home() / ".claude-mem" / "claude-mem.db"
        if default_path.exists():
            return default_path

        # Search in .claude-agents directory
        agents_dir = Path.home() / ".claude-agents"
        if agents_dir.exists():
            db_files = list(agents_dir.rglob("claude-mem.db"))
            if db_files:
                # Return most recently modified
                return max(db_files, key=lambda p: p.stat().st_mtime)

        return None

    @property
    def graph_memory(self) -> GraphMemory:
        """Get or create GraphMemory instance."""
        if self._graph_memory is None:
            self._graph_memory = GraphMemory(agent_id=self.agent_id)
        return self._graph_memory

    def _connect_claude_mem(self) -> Optional[sqlite3.Connection]:
        """Connect to claude-mem database."""
        if not self.claude_mem_db or not self.claude_mem_db.exists():
            logger.warning(f"Claude-mem database not found: {self.claude_mem_db}")
            return None

        conn = sqlite3.connect(str(self.claude_mem_db))
        conn.row_factory = sqlite3.Row
        return conn

    def get_observations(
        self,
        limit: int = 100,
        offset: int = 0,
        obs_type: Optional[str] = None,
        project: Optional[str] = None,
        since_epoch: Optional[int] = None,
    ) -> List[ClaudeMemObservation]:
        """
        Get observations from claude-mem.

        Args:
            limit: Maximum number of observations
            offset: Offset for pagination
            obs_type: Filter by type (decision, bugfix, etc.)
            project: Filter by project
            since_epoch: Only get observations after this timestamp

        Returns:
            List of ClaudeMemObservation
        """
        conn = self._connect_claude_mem()
        if not conn:
            return []

        try:
            query = "SELECT * FROM observations WHERE 1=1"
            params: List[Any] = []

            if obs_type:
                query += " AND type = ?"
                params.append(obs_type)

            if project:
                query += " AND project = ?"
                params.append(project)

            if since_epoch:
                query += " AND created_at_epoch > ?"
                params.append(since_epoch)

            query += " ORDER BY created_at_epoch DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)

            observations = []
            for row in cursor.fetchall():
                observations.append(ClaudeMemObservation(
                    id=row["id"],
                    sdk_session_id=row["sdk_session_id"],
                    project=row["project"],
                    text=row["text"],
                    type=row["type"],
                    title=row["title"],
                    subtitle=row["subtitle"],
                    facts=row["facts"],
                    narrative=row["narrative"],
                    concepts=row["concepts"],
                    files_read=row["files_read"],
                    files_modified=row["files_modified"],
                    prompt_number=row["prompt_number"],
                    created_at=row["created_at"],
                    created_at_epoch=row["created_at_epoch"],
                ))

            return observations

        finally:
            conn.close()

    def get_sessions(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        project: Optional[str] = None,
    ) -> List[ClaudeMemSession]:
        """
        Get sessions from claude-mem.

        Args:
            limit: Maximum number of sessions
            status: Filter by status (active, completed, failed)
            project: Filter by project

        Returns:
            List of ClaudeMemSession
        """
        conn = self._connect_claude_mem()
        if not conn:
            return []

        try:
            query = "SELECT * FROM sdk_sessions WHERE 1=1"
            params: List[Any] = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if project:
                query += " AND project = ?"
                params.append(project)

            query += " ORDER BY started_at_epoch DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)

            sessions = []
            for row in cursor.fetchall():
                sessions.append(ClaudeMemSession(
                    id=row["id"],
                    claude_session_id=row["claude_session_id"],
                    sdk_session_id=row["sdk_session_id"],
                    project=row["project"],
                    user_prompt=row["user_prompt"],
                    started_at=row["started_at"],
                    started_at_epoch=row["started_at_epoch"],
                    completed_at=row["completed_at"],
                    status=row["status"],
                ))

            return sessions

        finally:
            conn.close()

    def _observation_to_node(self, obs: ClaudeMemObservation) -> Tuple[MemoryNode, Dict[str, Any]]:
        """
        Convert claude-mem observation to GraphMemory node.

        Returns:
            Tuple of (MemoryNode, metadata for relations)
        """
        node_type = OBSERVATION_TYPE_MAP.get(obs.type, NodeType.FACT)
        importance = IMPORTANCE_WEIGHTS.get(obs.type, 0.5)

        # Build content from available fields
        content_parts = []
        if obs.title:
            content_parts.append(obs.title)
        if obs.subtitle:
            content_parts.append(obs.subtitle)
        if obs.narrative:
            content_parts.append(obs.narrative)
        if obs.text and obs.text not in content_parts:
            content_parts.append(obs.text)

        content = " | ".join(filter(None, content_parts))
        if not content:
            content = f"[{obs.type}] Observation #{obs.id}"

        # Parse concepts and facts
        concepts = []
        if obs.concepts:
            try:
                concepts = json.loads(obs.concepts) if obs.concepts.startswith("[") else [obs.concepts]
            except json.JSONDecodeError:
                concepts = [obs.concepts]

        facts = []
        if obs.facts:
            try:
                facts = json.loads(obs.facts) if obs.facts.startswith("[") else [obs.facts]
            except json.JSONDecodeError:
                facts = [obs.facts]

        # Parse files
        files_read = []
        if obs.files_read:
            try:
                files_read = json.loads(obs.files_read) if obs.files_read.startswith("[") else [obs.files_read]
            except json.JSONDecodeError:
                files_read = [obs.files_read]

        files_modified = []
        if obs.files_modified:
            try:
                files_modified = json.loads(obs.files_modified) if obs.files_modified.startswith("[") else [obs.files_modified]
            except json.JSONDecodeError:
                files_modified = [obs.files_modified]

        # Build metadata
        metadata = {
            "source": "claude-mem",
            "observation_id": obs.id,
            "observation_type": obs.type,
            "session_id": obs.sdk_session_id,
            "project": obs.project,
            "prompt_number": obs.prompt_number,
            "concepts": concepts,
            "facts": facts,
            "files_read": files_read,
            "files_modified": files_modified,
        }

        node = self.graph_memory.store(
            content=content,
            node_type=node_type,
            importance=importance,
            metadata=metadata,
        )

        # Return node and relation hints
        relation_hints = {
            "files_read": files_read,
            "files_modified": files_modified,
            "concepts": concepts,
        }

        return node, relation_hints

    def sync_from_claude_mem(
        self,
        limit: int = 500,
        since_epoch: Optional[int] = None,
        project: Optional[str] = None,
        create_file_relations: bool = True,
    ) -> SyncStats:
        """
        Sync observations from claude-mem to GraphMemory.

        Args:
            limit: Maximum observations to sync
            since_epoch: Only sync observations after this timestamp
            project: Filter by project
            create_file_relations: Create FILE nodes for referenced files

        Returns:
            SyncStats with sync results
        """
        stats = SyncStats()

        observations = self.get_observations(
            limit=limit,
            since_epoch=since_epoch,
            project=project,
        )

        # Track file nodes for relation creation
        file_nodes: Dict[str, str] = {}  # file_path → node_id

        for obs in observations:
            # Skip already synced
            if obs.id in self._synced_observation_ids:
                stats.skipped += 1
                continue

            try:
                node, relation_hints = self._observation_to_node(obs)
                stats.nodes_created += 1
                stats.observations_synced += 1
                self._synced_observation_ids.add(obs.id)

                if create_file_relations:
                    # Create FILE nodes and relations
                    all_files = set(relation_hints.get("files_read", []) + relation_hints.get("files_modified", []))

                    for file_path in all_files:
                        if file_path not in file_nodes:
                            # Create file node
                            file_node = self.graph_memory.store(
                                content=file_path,
                                node_type=NodeType.FILE,
                                importance=0.3,
                                metadata={"path": file_path},
                            )
                            file_nodes[file_path] = file_node.id
                            stats.nodes_created += 1

                        # Create relation
                        if file_path in relation_hints.get("files_modified", []):
                            # Modified files get USES relation
                            self.graph_memory.relate(
                                node.id,
                                RelationType.USES,
                                file_nodes[file_path],
                            )
                        else:
                            # Read files get RELATED_TO relation
                            self.graph_memory.relate(
                                node.id,
                                RelationType.RELATED_TO,
                                file_nodes[file_path],
                            )
                        stats.relations_created += 1

            except Exception as e:
                logger.error(f"[BRIDGE] Failed to sync observation {obs.id}: {e}")
                stats.errors += 1

        logger.info(
            f"[BRIDGE] sync_from_claude_mem | "
            f"observations={stats.observations_synced} "
            f"nodes={stats.nodes_created} "
            f"relations={stats.relations_created} "
            f"errors={stats.errors}"
        )

        return stats

    def get_unified_context(
        self,
        query: str,
        include_claude_mem: bool = True,
        include_graph_memory: bool = True,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get unified context from both claude-mem and GraphMemory.

        Args:
            query: Search query
            include_claude_mem: Search in claude-mem
            include_graph_memory: Search in GraphMemory
            limit: Maximum results per source

        Returns:
            Dict with results from both sources
        """
        context = {
            "query": query,
            "graph_memory": [],
            "claude_mem": [],
        }

        if include_graph_memory:
            # Search GraphMemory
            nodes = self.graph_memory.query(search_term=query, limit=limit)
            context["graph_memory"] = [
                {
                    "id": n.id,
                    "type": n.node_type.value,
                    "content": n.content,
                    "importance": n.importance,
                    "metadata": n.metadata,
                }
                for n in nodes
            ]

        if include_claude_mem:
            # Search claude-mem via FTS
            conn = self._connect_claude_mem()
            if conn:
                try:
                    # Use FTS5 for full-text search
                    cursor = conn.execute("""
                        SELECT o.*
                        FROM observations o
                        JOIN observations_fts fts ON o.id = fts.rowid
                        WHERE observations_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """, (query, limit))

                    for row in cursor.fetchall():
                        context["claude_mem"].append({
                            "id": row["id"],
                            "type": row["type"],
                            "title": row["title"],
                            "subtitle": row["subtitle"],
                            "narrative": row["narrative"],
                            "project": row["project"],
                            "created_at": row["created_at"],
                        })
                except sqlite3.OperationalError:
                    # FTS might not work, try simple LIKE
                    cursor = conn.execute("""
                        SELECT * FROM observations
                        WHERE text LIKE ? OR title LIKE ? OR narrative LIKE ?
                        ORDER BY created_at_epoch DESC
                        LIMIT ?
                    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

                    for row in cursor.fetchall():
                        context["claude_mem"].append({
                            "id": row["id"],
                            "type": row["type"],
                            "title": row["title"],
                            "subtitle": row["subtitle"],
                            "narrative": row["narrative"],
                            "project": row["project"],
                            "created_at": row["created_at"],
                        })
                finally:
                    conn.close()

        return context

    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        stats = {
            "agent_id": self.agent_id,
            "claude_mem_db": str(self.claude_mem_db) if self.claude_mem_db else None,
            "claude_mem_available": bool(self.claude_mem_db and self.claude_mem_db.exists()),
            "synced_observations": len(self._synced_observation_ids),
            "graph_memory": self.graph_memory.get_stats(),
        }

        # Get claude-mem stats
        if stats["claude_mem_available"]:
            conn = self._connect_claude_mem()
            if conn:
                try:
                    obs_count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
                    session_count = conn.execute("SELECT COUNT(*) FROM sdk_sessions").fetchone()[0]
                    stats["claude_mem"] = {
                        "total_observations": obs_count,
                        "total_sessions": session_count,
                    }
                finally:
                    conn.close()

        return stats

    def close(self):
        """Close connections."""
        if self._graph_memory:
            self._graph_memory.close()
