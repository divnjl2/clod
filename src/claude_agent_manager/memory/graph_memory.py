"""
Graph Memory - долговременная память для агентов.

Поддерживает:
- SQLite backend (по умолчанию, без дополнительных зависимостей)
- Neo4j/FalkorDB backend (опционально, для продвинутых сценариев)

Использование:
    from claude_agent_manager.memory import GraphMemory

    memory = GraphMemory(agent_id="agent-123")

    # Сохранить знание
    memory.store("project_uses_fastapi", related_to="tech_stack")

    # Найти связанные знания
    results = memory.query("tech_stack")

    # Добавить связь между сущностями
    memory.relate("fastapi", "requires", "uvicorn")
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import hashlib

from rich.console import Console
from rich.table import Table

console = Console()


class NodeType(Enum):
    """Типы узлов в графе памяти."""
    FACT = "fact"           # Факт о проекте/коде
    DECISION = "decision"   # Принятое решение
    TASK = "task"           # Задача
    FILE = "file"           # Файл в проекте
    FUNCTION = "function"   # Функция/метод
    CLASS = "class"         # Класс
    ERROR = "error"         # Ошибка, которую исправили
    PATTERN = "pattern"     # Паттерн кода


class RelationType(Enum):
    """Типы связей между узлами."""
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    PART_OF = "part_of"
    CAUSED_BY = "caused_by"
    FIXED_BY = "fixed_by"
    IMPLEMENTS = "implements"
    USES = "uses"
    CONTAINS = "contains"


@dataclass
class MemoryNode:
    """Узел в графе памяти."""
    id: str
    node_type: NodeType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0-1.0
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryNode:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            node_type=NodeType(data["node_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data.get("access_count", 0),
        )


@dataclass
class MemoryRelation:
    """Связь между узлами."""
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryRelation:
        """Create from dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=RelationType(data["relation_type"]),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class GraphMemory:
    """
    Граф-память для долговременного хранения знаний агента.

    Использует SQLite по умолчанию для хранения графа.
    Опционально может использовать Neo4j/FalkorDB для более
    продвинутых сценариев с большим объёмом данных.
    """

    def __init__(
        self,
        agent_id: str,
        db_path: Optional[Path] = None,
        backend: Literal["sqlite", "neo4j", "falkordb"] = "sqlite"
    ):
        """
        Initialize graph memory.

        Args:
            agent_id: ID агента
            db_path: путь к базе данных (для SQLite)
            backend: тип backend'а (sqlite по умолчанию)
        """
        self.agent_id = agent_id
        self.backend = backend

        if db_path is None:
            # Default to .clod directory
            db_path = Path.cwd() / ".clod" / "memory.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if backend == "sqlite":
            self._init_sqlite()
        else:
            raise NotImplementedError(f"Backend {backend} not yet implemented")

    def _init_sqlite(self):
        """Initialize SQLite database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # Create tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id),
                UNIQUE(source_id, target_id, relation_type)
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_agent ON nodes(agent_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_relations_agent ON relations(agent_id);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
        """)
        self.conn.commit()

    def _generate_id(self, content: str, node_type: NodeType) -> str:
        """Generate unique ID for a node."""
        hash_input = f"{self.agent_id}:{node_type.value}:{content}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def store(
        self,
        content: str,
        node_type: NodeType = NodeType.FACT,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        related_to: Optional[str] = None
    ) -> MemoryNode:
        """
        Store a piece of knowledge.

        Args:
            content: содержимое узла (факт, решение и т.д.)
            node_type: тип узла
            importance: важность (0.0-1.0)
            metadata: дополнительные данные
            related_to: ID узла для создания связи

        Returns:
            Созданный MemoryNode
        """
        node_id = self._generate_id(content, node_type)
        now = datetime.now()

        node = MemoryNode(
            id=node_id,
            node_type=node_type,
            content=content,
            metadata=metadata or {},
            importance=importance,
            created_at=now,
            accessed_at=now,
            access_count=0
        )

        # Insert or update
        self.conn.execute("""
            INSERT OR REPLACE INTO nodes
            (id, agent_id, node_type, content, metadata, importance, created_at, accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            node.id,
            self.agent_id,
            node.node_type.value,
            node.content,
            json.dumps(node.metadata),
            node.importance,
            node.created_at.isoformat(),
            node.accessed_at.isoformat(),
            node.access_count
        ))
        self.conn.commit()

        # Create relation if specified
        if related_to:
            self.relate(node_id, RelationType.RELATED_TO, related_to)

        return node

    def get(self, node_id: str) -> Optional[MemoryNode]:
        """
        Get a node by ID.

        Args:
            node_id: ID узла

        Returns:
            MemoryNode or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ? AND agent_id = ?",
            (node_id, self.agent_id)
        )
        row = cursor.fetchone()

        if row:
            # Update access stats
            now = datetime.now()
            self.conn.execute("""
                UPDATE nodes SET accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
            """, (now.isoformat(), node_id))
            self.conn.commit()

            return MemoryNode(
                id=row["id"],
                node_type=NodeType(row["node_type"]),
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                importance=row["importance"],
                created_at=datetime.fromisoformat(row["created_at"]),
                accessed_at=now,
                access_count=row["access_count"] + 1
            )

        return None

    def query(
        self,
        search_term: Optional[str] = None,
        node_type: Optional[NodeType] = None,
        min_importance: float = 0.0,
        limit: int = 100
    ) -> List[MemoryNode]:
        """
        Query nodes.

        Args:
            search_term: поисковый запрос (по содержимому)
            node_type: фильтр по типу
            min_importance: минимальная важность
            limit: максимальное количество результатов

        Returns:
            Список MemoryNode
        """
        query = "SELECT * FROM nodes WHERE agent_id = ?"
        params: List[Any] = [self.agent_id]

        if search_term:
            query += " AND content LIKE ?"
            params.append(f"%{search_term}%")

        if node_type:
            query += " AND node_type = ?"
            params.append(node_type.value)

        query += " AND importance >= ?"
        params.append(min_importance)

        query += " ORDER BY importance DESC, access_count DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        nodes = []

        for row in cursor.fetchall():
            nodes.append(MemoryNode(
                id=row["id"],
                node_type=NodeType(row["node_type"]),
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                importance=row["importance"],
                created_at=datetime.fromisoformat(row["created_at"]),
                accessed_at=datetime.fromisoformat(row["accessed_at"]),
                access_count=row["access_count"]
            ))

        return nodes

    def relate(
        self,
        source_id: str,
        relation_type: RelationType,
        target_id: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryRelation:
        """
        Create a relation between two nodes.

        Args:
            source_id: ID исходного узла
            relation_type: тип связи
            target_id: ID целевого узла
            weight: вес связи (для ranking)
            metadata: дополнительные данные

        Returns:
            Созданная MemoryRelation
        """
        relation = MemoryRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            metadata=metadata or {},
            created_at=datetime.now()
        )

        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO relations
                (agent_id, source_id, target_id, relation_type, weight, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.agent_id,
                relation.source_id,
                relation.target_id,
                relation.relation_type.value,
                relation.weight,
                json.dumps(relation.metadata),
                relation.created_at.isoformat()
            ))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # Relation already exists

        return relation

    def get_related(
        self,
        node_id: str,
        relation_type: Optional[RelationType] = None,
        direction: Literal["outgoing", "incoming", "both"] = "both"
    ) -> List[tuple[MemoryNode, MemoryRelation]]:
        """
        Get nodes related to a given node.

        Args:
            node_id: ID узла
            relation_type: фильтр по типу связи
            direction: направление связей

        Returns:
            Список кортежей (MemoryNode, MemoryRelation)
        """
        results = []
        relation_filter = ""
        params: List[Any] = [self.agent_id]

        if relation_type:
            relation_filter = " AND r.relation_type = ?"

        # Outgoing relations
        if direction in ("outgoing", "both"):
            query = f"""
                SELECT n.*, r.source_id, r.target_id, r.relation_type, r.weight, r.metadata as rel_metadata, r.created_at as rel_created
                FROM relations r
                JOIN nodes n ON n.id = r.target_id
                WHERE r.agent_id = ? AND r.source_id = ?{relation_filter}
            """
            cursor = self.conn.execute(query, params + [node_id] + ([relation_type.value] if relation_type else []))

            for row in cursor.fetchall():
                node = MemoryNode(
                    id=row["id"],
                    node_type=NodeType(row["node_type"]),
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                    importance=row["importance"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"]
                )
                relation = MemoryRelation(
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    relation_type=RelationType(row["relation_type"]),
                    weight=row["weight"],
                    metadata=json.loads(row["rel_metadata"]),
                    created_at=datetime.fromisoformat(row["rel_created"])
                )
                results.append((node, relation))

        # Incoming relations
        if direction in ("incoming", "both"):
            query = f"""
                SELECT n.*, r.source_id, r.target_id, r.relation_type, r.weight, r.metadata as rel_metadata, r.created_at as rel_created
                FROM relations r
                JOIN nodes n ON n.id = r.source_id
                WHERE r.agent_id = ? AND r.target_id = ?{relation_filter}
            """
            cursor = self.conn.execute(query, params + [node_id] + ([relation_type.value] if relation_type else []))

            for row in cursor.fetchall():
                node = MemoryNode(
                    id=row["id"],
                    node_type=NodeType(row["node_type"]),
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                    importance=row["importance"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"]
                )
                relation = MemoryRelation(
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    relation_type=RelationType(row["relation_type"]),
                    weight=row["weight"],
                    metadata=json.loads(row["rel_metadata"]),
                    created_at=datetime.fromisoformat(row["rel_created"])
                )
                results.append((node, relation))

        return results

    def forget(self, node_id: str) -> bool:
        """
        Delete a node and its relations.

        Args:
            node_id: ID узла

        Returns:
            True если узел удалён
        """
        # Delete relations first
        self.conn.execute(
            "DELETE FROM relations WHERE (source_id = ? OR target_id = ?) AND agent_id = ?",
            (node_id, node_id, self.agent_id)
        )

        # Delete node
        cursor = self.conn.execute(
            "DELETE FROM nodes WHERE id = ? AND agent_id = ?",
            (node_id, self.agent_id)
        )
        self.conn.commit()

        return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Dictionary with stats
        """
        node_count = self.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE agent_id = ?",
            (self.agent_id,)
        ).fetchone()[0]

        relation_count = self.conn.execute(
            "SELECT COUNT(*) FROM relations WHERE agent_id = ?",
            (self.agent_id,)
        ).fetchone()[0]

        type_counts = {}
        cursor = self.conn.execute(
            "SELECT node_type, COUNT(*) FROM nodes WHERE agent_id = ? GROUP BY node_type",
            (self.agent_id,)
        )
        for row in cursor.fetchall():
            type_counts[row[0]] = row[1]

        return {
            "agent_id": self.agent_id,
            "total_nodes": node_count,
            "total_relations": relation_count,
            "nodes_by_type": type_counts,
            "db_path": str(self.db_path)
        }

    def export_to_json(self, path: Path):
        """Export memory to JSON file."""
        nodes = self.query(limit=10000)
        relations = []

        cursor = self.conn.execute(
            "SELECT * FROM relations WHERE agent_id = ?",
            (self.agent_id,)
        )
        for row in cursor.fetchall():
            relations.append({
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relation_type": row["relation_type"],
                "weight": row["weight"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"]
            })

        data = {
            "agent_id": self.agent_id,
            "exported_at": datetime.now().isoformat(),
            "nodes": [n.to_dict() for n in nodes],
            "relations": relations
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_from_json(self, path: Path):
        """Import memory from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for node_data in data.get("nodes", []):
            node = MemoryNode.from_dict(node_data)
            self.conn.execute("""
                INSERT OR REPLACE INTO nodes
                (id, agent_id, node_type, content, metadata, importance, created_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id,
                self.agent_id,
                node.node_type.value,
                node.content,
                json.dumps(node.metadata),
                node.importance,
                node.created_at.isoformat(),
                node.accessed_at.isoformat(),
                node.access_count
            ))

        for rel_data in data.get("relations", []):
            self.conn.execute("""
                INSERT OR IGNORE INTO relations
                (agent_id, source_id, target_id, relation_type, weight, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.agent_id,
                rel_data["source_id"],
                rel_data["target_id"],
                rel_data["relation_type"],
                rel_data.get("weight", 1.0),
                json.dumps(rel_data.get("metadata", {})),
                rel_data["created_at"]
            ))

        self.conn.commit()

    def close(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def print_memory_stats(memory: GraphMemory):
    """Pretty print memory statistics."""
    stats = memory.get_stats()

    console.print(f"\n[bold cyan]Memory Stats for Agent: {stats['agent_id']}[/bold cyan]")
    console.print(f"Database: {stats['db_path']}")
    console.print(f"Total Nodes: {stats['total_nodes']}")
    console.print(f"Total Relations: {stats['total_relations']}")

    if stats["nodes_by_type"]:
        table = Table(title="Nodes by Type")
        table.add_column("Type")
        table.add_column("Count")

        for node_type, count in stats["nodes_by_type"].items():
            table.add_row(node_type, str(count))

        console.print(table)
