"""
Shared Context Manager - Координация между агентами
===================================================

Агенты общаются через shared context файл:
- API endpoints и их статусы
- Database schemas
- Shared interfaces
- Dependencies status
- Questions и blockers
"""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum


class TaskStatus(Enum):
    """Статус задачи агента."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


@dataclass
class AgentUpdate:
    """Обновление от агента."""
    agent_id: str
    role: str
    timestamp: str
    status: TaskStatus
    message: str
    artifacts: Dict[str, Any] = field(default_factory=dict)  # API endpoints, schemas, etc
    questions: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)


@dataclass
class SharedInterface:
    """Интерфейс между агентами (API, schema, etc)."""
    name: str
    type: str  # "api", "schema", "interface", "contract"
    owner: str  # agent_id который создал
    spec: Dict[str, Any]
    status: str  # "draft", "ready", "deprecated"
    consumers: List[str] = field(default_factory=list)  # agent_ids которые используют


class SharedContext:
    """
    Управляет shared context между агентами.
    
    Каждый агент читает и пишет в shared context файл.
    """
    
    def __init__(self, context_path: Path):
        self.context_path = context_path
        self.context_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._init_context()
    
    def _init_context(self):
        """Инициализация пустого контекста."""
        if not self.context_path.exists():
            initial = {
                "created_at": datetime.now().isoformat(),
                "agents": {},
                "interfaces": {},
                "global_state": {},
                "history": []
            }
            self.context_path.write_text(json.dumps(initial, indent=2))
    
    async def read(self) -> Dict[str, Any]:
        """Прочитать текущий контекст."""
        async with self._lock:
            if not self.context_path.exists():
                self._init_context()
            return json.loads(self.context_path.read_text())
    
    async def write(self, context: Dict[str, Any]):
        """Записать контекст."""
        async with self._lock:
            context["updated_at"] = datetime.now().isoformat()
            self.context_path.write_text(json.dumps(context, indent=2))
    
    async def update_agent_status(self, update: AgentUpdate):
        """Обновить статус агента."""
        context = await self.read()
        
        # Обновляем статус агента
        context["agents"][update.agent_id] = {
            "role": update.role,
            "status": update.status.value,
            "last_update": update.timestamp,
            "message": update.message,
            "artifacts": update.artifacts,
            "questions": update.questions,
            "blockers": update.blockers
        }
        
        # Добавляем в историю
        context["history"].append({
            "timestamp": update.timestamp,
            "agent_id": update.agent_id,
            "event": update.message
        })
        
        await self.write(context)
    
    async def register_interface(self, interface: SharedInterface):
        """Зарегистрировать новый интерфейс."""
        context = await self.read()
        
        context["interfaces"][interface.name] = {
            "type": interface.type,
            "owner": interface.owner,
            "spec": interface.spec,
            "status": interface.status,
            "consumers": interface.consumers,
            "created_at": datetime.now().isoformat()
        }
        
        await self.write(context)
    
    async def get_interface(self, name: str) -> Optional[Dict[str, Any]]:
        """Получить интерфейс по имени."""
        context = await self.read()
        return context["interfaces"].get(name)
    
    async def add_consumer(self, interface_name: str, consumer_agent_id: str):
        """Добавить потребителя интерфейса."""
        context = await self.read()
        
        if interface_name in context["interfaces"]:
            consumers = context["interfaces"][interface_name].get("consumers", [])
            if consumer_agent_id not in consumers:
                consumers.append(consumer_agent_id)
                context["interfaces"][interface_name]["consumers"] = consumers
                await self.write(context)
    
    async def check_dependencies(self, agent_id: str, required_interfaces: List[str]) -> Dict[str, bool]:
        """Проверить готовность зависимостей."""
        context = await self.read()
        
        status = {}
        for interface_name in required_interfaces:
            if interface_name in context["interfaces"]:
                status[interface_name] = context["interfaces"][interface_name]["status"] == "ready"
            else:
                status[interface_name] = False
        
        return status
    
    async def get_blockers(self) -> Dict[str, List[str]]:
        """Получить все blockers по агентам."""
        context = await self.read()
        
        blockers = {}
        for agent_id, data in context["agents"].items():
            if data.get("blockers"):
                blockers[agent_id] = data["blockers"]
        
        return blockers
    
    async def resolve_blocker(self, agent_id: str, blocker: str):
        """Убрать blocker."""
        context = await self.read()
        
        if agent_id in context["agents"]:
            blockers = context["agents"][agent_id].get("blockers", [])
            if blocker in blockers:
                blockers.remove(blocker)
                context["agents"][agent_id]["blockers"] = blockers
                await self.write(context)
    
    async def set_global_state(self, key: str, value: Any):
        """Установить глобальное состояние."""
        context = await self.read()
        context["global_state"][key] = value
        await self.write(context)
    
    async def get_global_state(self, key: str) -> Optional[Any]:
        """Получить глобальное состояние."""
        context = await self.read()
        return context["global_state"].get(key)
    
    async def get_agent_artifacts(self, agent_id: str) -> Dict[str, Any]:
        """Получить артефакты агента."""
        context = await self.read()
        
        if agent_id in context["agents"]:
            return context["agents"][agent_id].get("artifacts", {})
        return {}
    
    async def export_summary(self) -> str:
        """Экспорт краткого резюме для агентов."""
        context = await self.read()
        
        summary = {
            "agents_status": {
                agent_id: {
                    "role": data["role"],
                    "status": data["status"],
                    "message": data["message"]
                }
                for agent_id, data in context["agents"].items()
            },
            "interfaces": {
                name: {
                    "type": spec["type"],
                    "owner": spec["owner"],
                    "status": spec["status"]
                }
                for name, spec in context["interfaces"].items()
            },
            "active_blockers": await self.get_blockers()
        }
        
        return json.dumps(summary, indent=2)
