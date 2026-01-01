"""
Memory Graph - Координация между агентами через граф памяти с MCP

Использует:
- MCP memory server для персистентной памяти
- Graph структуру для связей между агентами
- Shared context для real-time обмена
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from enum import Enum


class NodeType(Enum):
    """Типы узлов в графе."""
    AGENT = "agent"
    TASK = "task"
    INTERFACE = "interface"
    ARTIFACT = "artifact"
    BLOCKER = "blocker"


class EdgeType(Enum):
    """Типы связей в графе."""
    DEPENDS_ON = "depends_on"
    PRODUCES = "produces"
    CONSUMES = "consumes"
    BLOCKS = "blocks"
    RESOLVES = "resolves"


@dataclass
class GraphNode:
    """Узел в графе памяти."""
    id: str
    type: NodeType
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class GraphEdge:
    """Связь в графе."""
    from_node: str
    to_node: str
    type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "type": self.type.value,
            "weight": self.weight,
            "metadata": self.metadata
        }


class MemoryGraph:
    """
    Граф памяти для координации агентов.
    
    Функции:
    - Хранит состояние агентов
    - Отслеживает зависимости
    - Управляет интерфейсами
    - Персистентность через MCP
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.mcp_available = False
        
        # Папка для хранения графа
        self.graph_dir = self.project_path / ".claude-team" / "graph"
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        
        # Загрузить существующий граф
        self.load()
    
    # ========================================================================
    # УЗЛЫ (Nodes)
    # ========================================================================
    
    async def add_node(
        self, 
        node_id: str, 
        node_type: NodeType,
        data: Dict[str, Any]
    ) -> GraphNode:
        """Добавить узел в граф."""
        node = GraphNode(
            id=node_id,
            type=node_type,
            data=data
        )
        
        self.nodes[node_id] = node
        await self.save()
        
        # Сохранить в MCP memory если доступно
        if self.mcp_available:
            await self._save_to_mcp(node_id, node.to_dict())
        
        return node
    
    async def update_node(
        self,
        node_id: str,
        updates: Dict[str, Any]
    ) -> Optional[GraphNode]:
        """Обновить узел."""
        if node_id not in self.nodes:
            return None
        
        node = self.nodes[node_id]
        node.data.update(updates)
        node.updated_at = datetime.now()
        
        await self.save()
        
        if self.mcp_available:
            await self._save_to_mcp(node_id, node.to_dict())
        
        return node
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Получить узел по ID."""
        return self.nodes.get(node_id)
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Получить все узлы определенного типа."""
        return [n for n in self.nodes.values() if n.type == node_type]
    
    # ========================================================================
    # СВЯЗИ (Edges)
    # ========================================================================
    
    async def add_edge(
        self,
        from_node: str,
        to_node: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> GraphEdge:
        """Добавить связь между узлами."""
        edge = GraphEdge(
            from_node=from_node,
            to_node=to_node,
            type=edge_type,
            weight=weight,
            metadata=metadata or {}
        )
        
        self.edges.append(edge)
        await self.save()
        
        return edge
    
    def get_edges(
        self,
        from_node: Optional[str] = None,
        to_node: Optional[str] = None,
        edge_type: Optional[EdgeType] = None
    ) -> List[GraphEdge]:
        """Получить связи с фильтрацией."""
        edges = self.edges
        
        if from_node:
            edges = [e for e in edges if e.from_node == from_node]
        
        if to_node:
            edges = [e for e in edges if e.to_node == to_node]
        
        if edge_type:
            edges = [e for e in edges if e.type == edge_type]
        
        return edges
    
    def get_dependencies(self, node_id: str) -> List[str]:
        """Получить зависимости узла."""
        edges = self.get_edges(from_node=node_id, edge_type=EdgeType.DEPENDS_ON)
        return [e.to_node for e in edges]
    
    def get_dependents(self, node_id: str) -> List[str]:
        """Получить узлы, зависящие от данного."""
        edges = self.get_edges(to_node=node_id, edge_type=EdgeType.DEPENDS_ON)
        return [e.from_node for e in edges]
    
    def get_blockers(self, node_id: str) -> List[str]:
        """Получить блокеры для узла."""
        edges = self.get_edges(to_node=node_id, edge_type=EdgeType.BLOCKS)
        return [e.from_node for e in edges]
    
    # ========================================================================
    # AGENT-SPECIFIC METHODS
    # ========================================================================
    
    async def register_agent(
        self,
        agent_id: str,
        role: str,
        tech_stack: List[str],
        depends_on: List[str] = None
    ) -> GraphNode:
        """Зарегистрировать агента в графе."""
        node = await self.add_node(
            node_id=agent_id,
            node_type=NodeType.AGENT,
            data={
                "role": role,
                "tech_stack": tech_stack,
                "status": "pending",
                "progress": 0.0
            }
        )
        
        # Добавить зависимости
        if depends_on:
            for dep in depends_on:
                await self.add_edge(
                    from_node=agent_id,
                    to_node=dep,
                    edge_type=EdgeType.DEPENDS_ON
                )
        
        return node
    
    async def update_agent_status(
        self,
        agent_id: str,
        status: str,
        progress: float = None,
        current_task: str = None
    ):
        """Обновить статус агента."""
        updates = {"status": status}
        
        if progress is not None:
            updates["progress"] = progress
        
        if current_task:
            updates["current_task"] = current_task
        
        await self.update_node(agent_id, updates)
    
    async def register_interface(
        self,
        interface_id: str,
        owner_agent: str,
        interface_type: str,
        spec: Dict[str, Any]
    ) -> GraphNode:
        """Зарегистрировать интерфейс (API, schema, etc)."""
        # Создать узел интерфейса
        node = await self.add_node(
            node_id=interface_id,
            node_type=NodeType.INTERFACE,
            data={
                "type": interface_type,
                "spec": spec,
                "status": "ready"
            }
        )
        
        # Связь: агент производит интерфейс
        await self.add_edge(
            from_node=owner_agent,
            to_node=interface_id,
            edge_type=EdgeType.PRODUCES
        )
        
        return node
    
    async def check_interface_available(self, interface_id: str) -> bool:
        """Проверить доступность интерфейса."""
        node = self.get_node(interface_id)
        if not node:
            return False
        
        return node.data.get("status") == "ready"
    
    async def add_blocker(
        self,
        blocked_agent: str,
        blocker_interface: str,
        reason: str
    ):
        """Добавить блокер для агента."""
        # Создать узел блокера
        blocker_id = f"blocker_{blocked_agent}_{blocker_interface}"
        await self.add_node(
            node_id=blocker_id,
            node_type=NodeType.BLOCKER,
            data={
                "agent": blocked_agent,
                "interface": blocker_interface,
                "reason": reason,
                "active": True
            }
        )
        
        # Связь: блокер блокирует агента
        await self.add_edge(
            from_node=blocker_id,
            to_node=blocked_agent,
            edge_type=EdgeType.BLOCKS
        )
    
    async def resolve_blocker(
        self,
        blocked_agent: str,
        interface_id: str
    ):
        """Разрешить блокер."""
        blocker_id = f"blocker_{blocked_agent}_{interface_id}"
        node = self.get_node(blocker_id)
        
        if node:
            await self.update_node(blocker_id, {"active": False})
    
    async def get_ready_agents(self) -> List[str]:
        """Получить агентов готовых к запуску (нет активных блокеров)."""
        ready = []
        
        for node in self.get_nodes_by_type(NodeType.AGENT):
            if node.data.get("status") != "pending":
                continue
            
            # Проверить блокеры
            blockers = self.get_blockers(node.id)
            active_blockers = [
                b for b in blockers
                if self.get_node(b).data.get("active", False)
            ]
            
            if not active_blockers:
                ready.append(node.id)
        
        return ready
    
    # ========================================================================
    # MCP INTEGRATION
    # ========================================================================
    
    async def _save_to_mcp(self, key: str, value: Dict[str, Any]):
        """Сохранить в MCP memory."""
        try:
            # Используем MCP memory server для персистентности
            # TODO: Интеграция с реальным MCP client
            pass
        except Exception as e:
            print(f"Failed to save to MCP: {e}")
    
    async def _load_from_mcp(self, key: str) -> Optional[Dict[str, Any]]:
        """Загрузить из MCP memory."""
        try:
            # TODO: Интеграция с реальным MCP client
            pass
        except Exception as e:
            print(f"Failed to load from MCP: {e}")
            return None
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def save(self):
        """Сохранить граф на диск."""
        graph_file = self.graph_dir / "memory_graph.json"
        
        data = {
            "nodes": {
                node_id: node.to_dict()
                for node_id, node in self.nodes.items()
            },
            "edges": [edge.to_dict() for edge in self.edges]
        }
        
        graph_file.write_text(json.dumps(data, indent=2))
    
    def load(self):
        """Загрузить граф с диска."""
        graph_file = self.graph_dir / "memory_graph.json"
        
        if not graph_file.exists():
            return
        
        try:
            data = json.loads(graph_file.read_text())
            
            # Загрузить узлы
            for node_id, node_data in data.get("nodes", {}).items():
                self.nodes[node_id] = GraphNode(
                    id=node_data["id"],
                    type=NodeType(node_data["type"]),
                    data=node_data["data"],
                    created_at=datetime.fromisoformat(node_data["created_at"]),
                    updated_at=datetime.fromisoformat(node_data["updated_at"])
                )
            
            # Загрузить связи
            for edge_data in data.get("edges", []):
                self.edges.append(GraphEdge(
                    from_node=edge_data["from"],
                    to_node=edge_data["to"],
                    type=EdgeType(edge_data["type"]),
                    weight=edge_data.get("weight", 1.0),
                    metadata=edge_data.get("metadata", {})
                ))
        
        except Exception as e:
            print(f"Failed to load graph: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать граф в словарь."""
        return {
            "nodes": {
                node_id: node.to_dict()
                for node_id, node in self.nodes.items()
            },
            "edges": [edge.to_dict() for edge in self.edges],
            "statistics": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "agents": len(self.get_nodes_by_type(NodeType.AGENT)),
                "interfaces": len(self.get_nodes_by_type(NodeType.INTERFACE)),
                "active_blockers": len([
                    n for n in self.get_nodes_by_type(NodeType.BLOCKER)
                    if n.data.get("active", False)
                ])
            }
        }
    
    # ========================================================================
    # VISUALIZATION
    # ========================================================================
    
    def to_mermaid(self) -> str:
        """Генерировать Mermaid диаграмму."""
        lines = ["graph TD"]
        
        # Узлы
        for node in self.nodes.values():
            shape = {
                NodeType.AGENT: "[{}]",
                NodeType.TASK: "{{{}}}",
                NodeType.INTERFACE: "({})",
                NodeType.ARTIFACT: "[/{}\\]",
                NodeType.BLOCKER: "{{{}}}",
            }.get(node.type, "{}")
            
            label = node.data.get("role", node.id)
            lines.append(f"    {node.id}{shape.format(label)}")
        
        # Связи
        for edge in self.edges:
            arrow = {
                EdgeType.DEPENDS_ON: "-->",
                EdgeType.PRODUCES: "-.->",
                EdgeType.CONSUMES: "==>",
                EdgeType.BLOCKS: "-.-x",
                EdgeType.RESOLVES: "==o"
            }.get(edge.type, "-->")
            
            lines.append(f"    {edge.from_node} {arrow} {edge.to_node}")
        
        return "\n".join(lines)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Пример использования MemoryGraph."""
    
    graph = MemoryGraph("/tmp/test_project")
    
    # Регистрируем агентов
    await graph.register_agent(
        "architect_001",
        role="architect",
        tech_stack=["Architecture", "Design"]
    )
    
    await graph.register_agent(
        "backend_001",
        role="backend",
        tech_stack=["Python", "FastAPI"],
        depends_on=["architect_001"]
    )
    
    await graph.register_agent(
        "frontend_001",
        role="frontend",
        tech_stack=["React", "TypeScript"],
        depends_on=["backend_001"]
    )
    
    # Architect создает интерфейс
    await graph.register_interface(
        "api_contracts",
        owner_agent="architect_001",
        interface_type="contracts",
        spec={"endpoints": ["/users", "/posts"]}
    )
    
    # Backend блокирован пока нет контрактов
    await graph.add_blocker(
        "backend_001",
        "api_contracts",
        "Waiting for API contracts"
    )
    
    # Architect закончил - разблокируем backend
    await graph.resolve_blocker("backend_001", "api_contracts")
    
    # Получить готовых агентов
    ready = await graph.get_ready_agents()
    print(f"Ready agents: {ready}")
    
    # Mermaid диаграмма
    print(graph.to_mermaid())


if __name__ == "__main__":
    asyncio.run(example_usage())
