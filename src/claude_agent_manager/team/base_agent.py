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
        """Вызов Claude API."""
        # Формируем system prompt с контекстом
        system = self.system_prompt

        if context:
            system += f"\n\nAdditional context:\n{json.dumps(context, indent=2)}"

        if self.worktree_path:
            system += f"\n\nYour working directory: {self.worktree_path}"

        # Конвертируем сообщения
        api_messages = [m.to_api_format() for m in messages]

        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=api_messages,
                temperature=self.config.temperature
            )

            return response.content[0].text

        except Exception as e:
            return f"ERROR: Failed to generate reply: {str(e)}"

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
