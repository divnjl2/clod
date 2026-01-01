"""
Base Agent - Базовый агент на основе AutoGen ConversableAgent
=============================================================

Источник: Microsoft AutoGen (conversable_agent.py)
- generate_reply pattern
- register_reply mechanism
- message handling

Адаптация: Anthropic Claude API
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum

from anthropic import Anthropic


class MessageRole(Enum):
    """Роли сообщений (как в AutoGen)."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    Структура сообщения (из AutoGen + MetaGPT).

    Структурированное сообщение для коммуникации между агентами.
    """
    role: MessageRole
    content: str
    sender: Optional[str] = None
    receiver: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_api_format(self) -> Dict[str, str]:
        """Конвертация в формат Anthropic API."""
        return {
            "role": self.role.value if self.role != MessageRole.SYSTEM else "user",
            "content": self.content
        }


@dataclass
class AgentConfig:
    """Конфигурация агента."""
    name: str
    role: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4000
    temperature: float = 0.7
    worktree_path: Optional[Path] = None
    can_execute_code: bool = True
    max_consecutive_replies: int = 10
    mcp_tools: List[str] = None  # List of enabled MCP tools

    # Model name mapping (short -> full API name)
    MODEL_MAPPING = {
        "auto": "claude-sonnet-4-20250514",
        "haiku": "claude-3-haiku-20240307",
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "local": "llama3:70b",
    }

    def __post_init__(self):
        if self.mcp_tools is None:
            self.mcp_tools = []

    def get_api_model(self) -> str:
        """Get full API model name from short name or return as-is."""
        return self.MODEL_MAPPING.get(self.model, self.model)


# =============================================================================
# MCP TOOLS DEFINITIONS
# =============================================================================

MCP_TOOL_SCHEMAS = {
    "memory": {
        "name": "memory_store",
        "description": "Store information in long-term memory for later retrieval. Use for important facts, decisions, and learned patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Unique key for this memory"},
                "content": {"type": "string", "description": "The information to store"},
                "category": {"type": "string", "enum": ["fact", "decision", "pattern", "context"], "description": "Type of memory"}
            },
            "required": ["key", "content"]
        }
    },
    "memory_recall": {
        "name": "memory_recall",
        "description": "Recall information from long-term memory. Search by key or query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or key to look up"},
                "limit": {"type": "integer", "description": "Max results to return", "default": 5}
            },
            "required": ["query"]
        }
    },
    "filesystem": {
        "name": "read_file",
        "description": "Read contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"}
            },
            "required": ["path"]
        }
    },
    "filesystem_write": {
        "name": "write_file",
        "description": "Write content to a file in the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"}
            },
            "required": ["path", "content"]
        }
    },
    "database": {
        "name": "database_query",
        "description": "Execute a read-only SQL query on the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute"},
                "params": {"type": "array", "items": {"type": "string"}, "description": "Query parameters"}
            },
            "required": ["query"]
        }
    },
    "code_execution": {
        "name": "execute_code",
        "description": "Execute Python code in a sandboxed environment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Execution timeout in seconds", "default": 30}
            },
            "required": ["code"]
        }
    },
    "web_search": {
        "name": "web_search",
        "description": "Search the web for information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results", "default": 5}
            },
            "required": ["query"]
        }
    },
    "github": {
        "name": "github_operation",
        "description": "Perform GitHub operations like creating issues, PRs, or fetching repo info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["get_repo", "list_issues", "create_issue", "get_pr", "list_prs"], "description": "GitHub operation"},
                "repo": {"type": "string", "description": "Repository in owner/name format"},
                "params": {"type": "object", "description": "Operation-specific parameters"}
            },
            "required": ["operation", "repo"]
        }
    },
    "slack": {
        "name": "slack_message",
        "description": "Send a message to a Slack channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Slack channel name or ID"},
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["channel", "message"]
        }
    }
}


def get_tools_for_agent(mcp_tools: List[str]) -> List[dict]:
    """Get tool schemas for the agent's enabled MCP tools."""
    tools = []
    for tool_name in mcp_tools:
        if tool_name in MCP_TOOL_SCHEMAS:
            tools.append(MCP_TOOL_SCHEMAS[tool_name])
        # Add related tools (e.g., memory includes memory_recall)
        if tool_name == "memory" and "memory_recall" in MCP_TOOL_SCHEMAS:
            tools.append(MCP_TOOL_SCHEMAS["memory_recall"])
        if tool_name == "filesystem" and "filesystem_write" in MCP_TOOL_SCHEMAS:
            tools.append(MCP_TOOL_SCHEMAS["filesystem_write"])
    return tools


class ReplyTrigger:
    """
    Триггер для кастомных ответов (из AutoGen register_reply pattern).

    Позволяет регистрировать специальные обработчики для определенных условий.
    """
    def __init__(
        self,
        trigger: Union[str, Callable[[Message], bool]],
        reply_func: Callable[[Message], str],
        priority: int = 0
    ):
        self.trigger = trigger
        self.reply_func = reply_func
        self.priority = priority

    def matches(self, message: Message) -> bool:
        """Проверка соответствия триггеру."""
        if callable(self.trigger):
            return self.trigger(message)
        elif isinstance(self.trigger, str):
            return self.trigger.lower() in message.content.lower()
        return False


class BaseAgent(ABC):
    """
    Базовый агент - основа для всех специализированных агентов.

    Источники:
    - AutoGen: ConversableAgent pattern (generate_reply, register_reply)
    - MetaGPT: Role-based structure
    - CrewAI: Context handling

    Каждый агент:
    - Имеет свой system prompt (роль)
    - Может генерировать ответы через Claude
    - Поддерживает кастомные reply triggers
    - Работает в изолированном worktree
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.role = config.role
        self.system_prompt = config.system_prompt
        self.worktree_path = config.worktree_path

        # Anthropic client
        self.client = Anthropic()

        # История сообщений
        self.messages: List[Message] = []

        # Reply triggers (AutoGen pattern)
        self._reply_triggers: List[ReplyTrigger] = []

        # Состояние
        self.is_active = False
        self.consecutive_replies = 0

        # Артефакты (выходные данные)
        self.artifacts: Dict[str, Any] = {}

    def register_reply(
        self,
        trigger: Union[str, Callable[[Message], bool]],
        reply_func: Callable[[Message], str],
        priority: int = 0
    ):
        """
        Регистрация кастомного обработчика ответов.

        Источник: AutoGen ConversableAgent.register_reply()

        Args:
            trigger: Строка или функция для определения когда вызывать
            reply_func: Функция генерации ответа
            priority: Приоритет (выше = раньше проверяется)
        """
        self._reply_triggers.append(ReplyTrigger(trigger, reply_func, priority))
        # Сортируем по приоритету
        self._reply_triggers.sort(key=lambda x: -x.priority)

    async def generate_reply(
        self,
        messages: Optional[List[Message]] = None,
        sender: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Генерация ответа (главный метод из AutoGen pattern).

        1. Проверяет кастомные triggers
        2. Если нет match - вызывает Claude API

        Args:
            messages: Сообщения для обработки (если None - используем историю)
            sender: Кто отправил
            context: Дополнительный контекст (из CrewAI pattern)

        Returns:
            Сгенерированный ответ
        """
        work_messages = messages or self.messages

        if not work_messages:
            return ""

        last_message = work_messages[-1]

        # Проверяем кастомные triggers
        for trigger in self._reply_triggers:
            if trigger.matches(last_message):
                return trigger.reply_func(last_message)

        # Генерируем через Claude
        return await self._call_llm(work_messages, context)

    async def _call_llm(
        self,
        messages: List[Message],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Вызов Claude API с поддержкой MCP tools."""
        # Формируем system prompt с контекстом
        system = self.system_prompt

        if context:
            system += f"\n\nAdditional context:\n{json.dumps(context, indent=2)}"

        if self.worktree_path:
            system += f"\n\nYour working directory: {self.worktree_path}"

        # Конвертируем сообщения
        api_messages = [m.to_api_format() for m in messages]

        try:
            # Get full API model name (handles short names like "sonnet" -> "claude-sonnet-4-20250514")
            api_model = self.config.get_api_model()

            # Get tools based on config.mcp_tools
            tools = get_tools_for_agent(self.config.mcp_tools) if self.config.mcp_tools else []

            # Build API call parameters
            api_params = {
                "model": api_model,
                "max_tokens": self.config.max_tokens,
                "system": system,
                "messages": api_messages,
                "temperature": self.config.temperature
            }

            # Add tools if available
            if tools:
                api_params["tools"] = tools

            response = self.client.messages.create(**api_params)

            # Handle response - might be text or tool_use
            result_parts = []
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    result_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            # If there are tool calls, execute them and continue
            if tool_calls:
                tool_results = await self._execute_tool_calls(tool_calls)

                # Add assistant message with tool use and tool results
                api_messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                api_messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Make another API call with tool results
                continuation = self.client.messages.create(**{
                    **api_params,
                    "messages": api_messages
                })

                for block in continuation.content:
                    if block.type == "text":
                        result_parts.append(block.text)

            return "\n".join(result_parts) if result_parts else ""

        except Exception as e:
            return f"ERROR: Failed to generate reply: {str(e)}"

    async def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute MCP tool calls and return results."""
        results = []

        for call in tool_calls:
            tool_name = call["name"]
            tool_input = call["input"]
            tool_id = call["id"]

            try:
                result = await self._execute_single_tool(tool_name, tool_input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result)
                })
            except Exception as e:
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Error executing {tool_name}: {str(e)}",
                    "is_error": True
                })

        return results

    async def _execute_single_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a single MCP tool."""
        # Memory tools
        if tool_name == "memory_store":
            return await self._tool_memory_store(tool_input)
        elif tool_name == "memory_recall":
            return await self._tool_memory_recall(tool_input)

        # Filesystem tools
        elif tool_name == "read_file":
            return await self._tool_read_file(tool_input)
        elif tool_name == "write_file":
            return await self._tool_write_file(tool_input)

        # Database tools
        elif tool_name == "database_query":
            return await self._tool_database_query(tool_input)

        # Code execution
        elif tool_name == "execute_code":
            return await self._tool_execute_code(tool_input)

        # Web search
        elif tool_name == "web_search":
            return await self._tool_web_search(tool_input)

        # GitHub
        elif tool_name == "github_operation":
            return await self._tool_github(tool_input)

        # Slack
        elif tool_name == "slack_message":
            return await self._tool_slack(tool_input)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    # =========================================================================
    # TOOL IMPLEMENTATIONS
    # =========================================================================

    async def _tool_memory_store(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Store in memory."""
        key = input.get("key")
        content = input.get("content")
        category = input.get("category", "fact")

        # Store in shared context if available
        if hasattr(self, 'shared_context') and self.shared_context:
            await self.shared_context.store_memory(key, content, category)
            return {"status": "stored", "key": key}

        # Fallback: store locally
        if not hasattr(self, '_local_memory'):
            self._local_memory = {}
        self._local_memory[key] = {"content": content, "category": category}
        return {"status": "stored_locally", "key": key}

    async def _tool_memory_recall(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Recall from memory."""
        query = input.get("query")
        limit = input.get("limit", 5)

        # Search in shared context
        if hasattr(self, 'shared_context') and self.shared_context:
            results = await self.shared_context.search_memory(query, limit)
            return {"results": results}

        # Fallback: search locally
        if hasattr(self, '_local_memory'):
            matches = [
                {"key": k, **v}
                for k, v in self._local_memory.items()
                if query.lower() in k.lower() or query.lower() in v.get("content", "").lower()
            ][:limit]
            return {"results": matches}

        return {"results": []}

    async def _tool_read_file(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Read file from filesystem."""
        path = input.get("path")
        base_path = self.worktree_path or Path.cwd()

        try:
            file_path = base_path / path if not Path(path).is_absolute() else Path(path)
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                return {"path": str(file_path), "content": content}
            return {"error": f"File not found: {path}"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_write_file(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Write file to filesystem."""
        path = input.get("path")
        content = input.get("content")
        base_path = self.worktree_path or Path.cwd()

        try:
            file_path = base_path / path if not Path(path).is_absolute() else Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            return {"status": "written", "path": str(file_path), "bytes": len(content)}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_database_query(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database query (stub - needs DB connection)."""
        query = input.get("query")
        return {"status": "not_implemented", "query": query, "message": "Database not configured"}

    async def _tool_execute_code(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code in sandbox."""
        code = input.get("code")
        timeout = input.get("timeout", 30)

        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.worktree_path) if self.worktree_path else None
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Execution timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_web_search(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Web search (stub - needs search API)."""
        query = input.get("query")
        return {"status": "not_implemented", "query": query, "message": "Web search not configured"}

    async def _tool_github(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """GitHub operation (stub - needs GitHub token)."""
        operation = input.get("operation")
        repo = input.get("repo")
        return {"status": "not_implemented", "operation": operation, "repo": repo}

    async def _tool_slack(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Slack message (stub - needs Slack token)."""
        channel = input.get("channel")
        message = input.get("message")
        return {"status": "not_implemented", "channel": channel}

    async def receive(
        self,
        message: Union[str, Message],
        sender: Optional['BaseAgent'] = None
    ) -> str:
        """
        Получить сообщение и сгенерировать ответ.

        Источник: AutoGen ConversableAgent.receive()
        """
        # Конвертируем строку в Message
        if isinstance(message, str):
            message = Message(
                role=MessageRole.USER,
                content=message,
                sender=sender.name if sender else "user"
            )

        # Добавляем в историю
        self.messages.append(message)

        # Генерируем ответ
        reply = await self.generate_reply(sender=message.sender)

        # Добавляем ответ в историю
        reply_message = Message(
            role=MessageRole.ASSISTANT,
            content=reply,
            sender=self.name,
            receiver=message.sender
        )
        self.messages.append(reply_message)

        self.consecutive_replies += 1

        return reply

    async def send(
        self,
        message: str,
        recipient: 'BaseAgent',
        request_reply: bool = True
    ) -> Optional[str]:
        """
        Отправить сообщение другому агенту.

        Источник: AutoGen ConversableAgent.send()
        """
        msg = Message(
            role=MessageRole.USER,
            content=message,
            sender=self.name,
            receiver=recipient.name
        )

        if request_reply:
            return await recipient.receive(msg, sender=self)
        else:
            recipient.messages.append(msg)
            return None

    def add_artifact(self, name: str, value: Any):
        """Добавить артефакт (выходные данные)."""
        self.artifacts[name] = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "agent": self.name
        }

    def get_artifact(self, name: str) -> Optional[Any]:
        """Получить артефакт."""
        if name in self.artifacts:
            return self.artifacts[name]["value"]
        return None

    def reset(self):
        """Сброс состояния агента."""
        self.messages = []
        self.consecutive_replies = 0
        self.artifacts = {}

    @abstractmethod
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполнить задачу (должен быть реализован в наследниках).

        Args:
            task_description: Описание задачи
            context: Контекст от других агентов (CrewAI pattern)

        Returns:
            Результат выполнения с артефактами
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} role={self.role}>"


class SimpleAgent(BaseAgent):
    """
    Простой агент без специализации.

    Используется как базовый класс или для простых задач.
    """

    async def execute_task(
        self,
        task_description: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Выполнить задачу."""
        # Формируем запрос
        prompt = f"Task: {task_description}"

        if context:
            prompt += f"\n\nContext from other agents:\n{json.dumps(context, indent=2)}"

        # Получаем ответ
        response = await self.receive(prompt)

        return {
            "agent": self.name,
            "role": self.role,
            "task": task_description,
            "response": response,
            "artifacts": self.artifacts,
            "timestamp": datetime.now().isoformat()
        }
