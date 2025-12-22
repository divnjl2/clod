"""
Tests for memory/graph_memory.py - Graph Memory system.

Phase 2: Cross-session Memory
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.memory.graph_memory import (
    GraphMemory,
    MemoryNode,
    MemoryRelation,
    NodeType,
    RelationType,
    print_memory_stats,
)


class TestMemoryNode:
    """Tests for MemoryNode dataclass."""

    def test_node_creation(self):
        """Test creating a memory node."""
        node = MemoryNode(
            id="test123",
            node_type=NodeType.FACT,
            content="Project uses FastAPI",
            metadata={"source": "analysis"},
            importance=0.8
        )

        assert node.id == "test123"
        assert node.node_type == NodeType.FACT
        assert node.content == "Project uses FastAPI"
        assert node.importance == 0.8

    def test_node_to_dict(self):
        """Test converting node to dictionary."""
        now = datetime.now()
        node = MemoryNode(
            id="test123",
            node_type=NodeType.DECISION,
            content="Use SQLAlchemy for ORM",
            metadata={"reason": "team familiarity"},
            importance=0.9,
            created_at=now,
            accessed_at=now
        )

        data = node.to_dict()

        assert data["id"] == "test123"
        assert data["node_type"] == "decision"
        assert data["content"] == "Use SQLAlchemy for ORM"
        assert data["importance"] == 0.9

    def test_node_from_dict(self):
        """Test creating node from dictionary."""
        data = {
            "id": "abc123",
            "node_type": "fact",
            "content": "Database is PostgreSQL",
            "metadata": {},
            "importance": 0.7,
            "created_at": "2024-01-01T10:00:00",
            "accessed_at": "2024-01-01T10:00:00",
            "access_count": 5
        }

        node = MemoryNode.from_dict(data)

        assert node.id == "abc123"
        assert node.node_type == NodeType.FACT
        assert node.access_count == 5


class TestMemoryRelation:
    """Tests for MemoryRelation dataclass."""

    def test_relation_creation(self):
        """Test creating a memory relation."""
        relation = MemoryRelation(
            source_id="node1",
            target_id="node2",
            relation_type=RelationType.DEPENDS_ON,
            weight=0.9
        )

        assert relation.source_id == "node1"
        assert relation.target_id == "node2"
        assert relation.relation_type == RelationType.DEPENDS_ON
        assert relation.weight == 0.9

    def test_relation_to_dict(self):
        """Test converting relation to dictionary."""
        relation = MemoryRelation(
            source_id="a",
            target_id="b",
            relation_type=RelationType.USES,
            weight=1.0
        )

        data = relation.to_dict()

        assert data["source_id"] == "a"
        assert data["target_id"] == "b"
        assert data["relation_type"] == "uses"


class TestGraphMemory:
    """Tests for GraphMemory class."""

    def test_memory_creation(self, temp_dir):
        """Test creating a graph memory instance."""
        db_path = temp_dir / "test_memory.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        assert memory.agent_id == "agent-1"
        assert memory.db_path == db_path
        assert db_path.exists()

        memory.close()

    def test_store_fact(self, temp_dir):
        """Test storing a fact."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        node = memory.store(
            "Project uses FastAPI framework",
            node_type=NodeType.FACT,
            importance=0.8
        )

        assert node.id is not None
        assert node.content == "Project uses FastAPI framework"
        assert node.importance == 0.8

        memory.close()

    def test_store_with_metadata(self, temp_dir):
        """Test storing with metadata."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        node = memory.store(
            "Auth uses JWT tokens",
            node_type=NodeType.DECISION,
            metadata={"file": "auth.py", "line": 42}
        )

        assert node.metadata["file"] == "auth.py"

        memory.close()

    def test_get_node(self, temp_dir):
        """Test retrieving a node."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        stored = memory.store("Test content", node_type=NodeType.FACT)
        retrieved = memory.get(stored.id)

        assert retrieved is not None
        assert retrieved.content == "Test content"
        assert retrieved.access_count == 1

        memory.close()

    def test_get_nonexistent(self, temp_dir):
        """Test retrieving non-existent node."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        result = memory.get("nonexistent")

        assert result is None

        memory.close()

    def test_query_by_search(self, temp_dir):
        """Test querying by search term."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.store("FastAPI is used", node_type=NodeType.FACT)
        memory.store("SQLAlchemy for ORM", node_type=NodeType.FACT)
        memory.store("FastAPI routes", node_type=NodeType.FACT)

        results = memory.query(search_term="FastAPI")

        assert len(results) == 2
        assert all("FastAPI" in n.content for n in results)

        memory.close()

    def test_query_by_type(self, temp_dir):
        """Test querying by node type."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.store("Fact 1", node_type=NodeType.FACT)
        memory.store("Fact 2", node_type=NodeType.FACT)
        memory.store("Decision 1", node_type=NodeType.DECISION)

        facts = memory.query(node_type=NodeType.FACT)
        decisions = memory.query(node_type=NodeType.DECISION)

        assert len(facts) == 2
        assert len(decisions) == 1

        memory.close()

    def test_query_by_importance(self, temp_dir):
        """Test querying by minimum importance."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.store("Low importance", importance=0.2)
        memory.store("Medium importance", importance=0.5)
        memory.store("High importance", importance=0.9)

        high_importance = memory.query(min_importance=0.8)

        assert len(high_importance) == 1
        assert high_importance[0].content == "High importance"

        memory.close()

    def test_create_relation(self, temp_dir):
        """Test creating a relation between nodes."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        node1 = memory.store("FastAPI app", node_type=NodeType.FACT)
        node2 = memory.store("Uvicorn server", node_type=NodeType.FACT)

        relation = memory.relate(
            node1.id,
            RelationType.DEPENDS_ON,
            node2.id,
            weight=0.9
        )

        assert relation.source_id == node1.id
        assert relation.target_id == node2.id
        assert relation.relation_type == RelationType.DEPENDS_ON

        memory.close()

    def test_get_related_nodes(self, temp_dir):
        """Test getting related nodes."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        main = memory.store("Main module", node_type=NodeType.FILE)
        dep1 = memory.store("Dependency 1", node_type=NodeType.FILE)
        dep2 = memory.store("Dependency 2", node_type=NodeType.FILE)

        memory.relate(main.id, RelationType.DEPENDS_ON, dep1.id)
        memory.relate(main.id, RelationType.DEPENDS_ON, dep2.id)

        related = memory.get_related(main.id, direction="outgoing")

        assert len(related) == 2
        related_contents = [node.content for node, rel in related]
        assert "Dependency 1" in related_contents
        assert "Dependency 2" in related_contents

        memory.close()

    def test_get_related_incoming(self, temp_dir):
        """Test getting incoming relations."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        parent = memory.store("Parent", node_type=NodeType.FILE)
        child1 = memory.store("Child 1", node_type=NodeType.FILE)
        child2 = memory.store("Child 2", node_type=NodeType.FILE)

        memory.relate(child1.id, RelationType.PART_OF, parent.id)
        memory.relate(child2.id, RelationType.PART_OF, parent.id)

        incoming = memory.get_related(parent.id, direction="incoming")

        assert len(incoming) == 2

        memory.close()

    def test_forget_node(self, temp_dir):
        """Test deleting a node."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        node = memory.store("To be forgotten")
        node_id = node.id

        result = memory.forget(node_id)

        assert result is True
        assert memory.get(node_id) is None

        memory.close()

    def test_forget_with_relations(self, temp_dir):
        """Test deleting a node removes its relations."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        node1 = memory.store("Node 1")
        node2 = memory.store("Node 2")

        memory.relate(node1.id, RelationType.RELATED_TO, node2.id)

        memory.forget(node1.id)

        related = memory.get_related(node2.id)
        assert len(related) == 0

        memory.close()

    def test_get_stats(self, temp_dir):
        """Test getting memory statistics."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.store("Fact 1", node_type=NodeType.FACT)
        memory.store("Fact 2", node_type=NodeType.FACT)
        memory.store("Decision 1", node_type=NodeType.DECISION)

        node1 = memory.store("A")
        node2 = memory.store("B")
        memory.relate(node1.id, RelationType.USES, node2.id)

        stats = memory.get_stats()

        assert stats["agent_id"] == "agent-1"
        assert stats["total_nodes"] == 5
        assert stats["total_relations"] == 1
        assert "fact" in stats["nodes_by_type"]

        memory.close()


class TestGraphMemoryIsolation:
    """Tests for agent isolation in graph memory."""

    def test_agents_isolated(self, temp_dir):
        """Test that different agents have isolated memories."""
        db_path = temp_dir / "shared.db"

        memory1 = GraphMemory("agent-1", db_path=db_path)
        memory2 = GraphMemory("agent-2", db_path=db_path)

        memory1.store("Agent 1 fact")
        memory2.store("Agent 2 fact")

        results1 = memory1.query()
        results2 = memory2.query()

        assert len(results1) == 1
        assert results1[0].content == "Agent 1 fact"

        assert len(results2) == 1
        assert results2[0].content == "Agent 2 fact"

        memory1.close()
        memory2.close()


class TestGraphMemoryExportImport:
    """Tests for export/import functionality."""

    def test_export_to_json(self, temp_dir):
        """Test exporting memory to JSON."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.store("Fact 1", node_type=NodeType.FACT)
        memory.store("Fact 2", node_type=NodeType.FACT)

        export_path = temp_dir / "export.json"
        memory.export_to_json(export_path)

        assert export_path.exists()

        with open(export_path) as f:
            data = json.load(f)

        assert data["agent_id"] == "agent-1"
        assert len(data["nodes"]) == 2

        memory.close()

    def test_import_from_json(self, temp_dir):
        """Test importing memory from JSON."""
        # Create export file
        export_data = {
            "agent_id": "agent-1",
            "exported_at": datetime.now().isoformat(),
            "nodes": [
                {
                    "id": "imported1",
                    "node_type": "fact",
                    "content": "Imported fact",
                    "metadata": {},
                    "importance": 0.7,
                    "created_at": datetime.now().isoformat(),
                    "accessed_at": datetime.now().isoformat(),
                    "access_count": 0
                }
            ],
            "relations": []
        }

        import_path = temp_dir / "import.json"
        with open(import_path, "w") as f:
            json.dump(export_data, f)

        db_path = temp_dir / "test.db"
        memory = GraphMemory("agent-1", db_path=db_path)

        memory.import_from_json(import_path)

        results = memory.query()

        assert len(results) == 1
        assert results[0].content == "Imported fact"

        memory.close()


class TestGraphMemoryContextManager:
    """Tests for context manager functionality."""

    def test_context_manager(self, temp_dir):
        """Test using memory as context manager."""
        db_path = temp_dir / "test.db"

        with GraphMemory("agent-1", db_path=db_path) as memory:
            memory.store("Test content")
            results = memory.query()
            assert len(results) == 1

        # Connection should be closed
        # Create new connection to verify data persisted
        with GraphMemory("agent-1", db_path=db_path) as memory:
            results = memory.query()
            assert len(results) == 1


class TestPrintMemoryStats:
    """Tests for print_memory_stats function."""

    def test_print_stats(self, temp_dir, capsys):
        """Test printing memory stats."""
        db_path = temp_dir / "test.db"
        memory = GraphMemory("test-agent", db_path=db_path)

        memory.store("Test fact", node_type=NodeType.FACT)

        print_memory_stats(memory)

        captured = capsys.readouterr()
        assert "test-agent" in captured.out

        memory.close()
