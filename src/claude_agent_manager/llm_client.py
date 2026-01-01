"""
Multi-Provider LLM Client
==========================

Unified interface для работы с разными провайдерами:
- Anthropic (Claude)
- OpenAI (GPT)
- OpenRouter (любые модели)
- Local (Ollama, vLLM, etc)
"""

import os
from typing import Dict, List, Any, Optional, AsyncIterator
from abc import ABC, abstractmethod
import httpx
import json
from dataclasses import dataclass


@dataclass
class LLMMessage:
    """Сообщение для LLM."""
    role: str  # system, user, assistant
    content: str


@dataclass
class LLMResponse:
    """Ответ от LLM."""
    content: str
    model: str
    usage: Dict[str, int]  # tokens
    finish_reason: str
    thinking: Optional[str] = None  # For o1-style models


class BaseLLMProvider(ABC):
    """Базовый класс для LLM провайдера."""
    
    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Получить completion."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Получить streaming completion."""
        pass


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"
    
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Complete using Anthropic API."""
        
        # Convert messages
        system_msgs = [m.content for m in messages if m.role == "system"]
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages if m.role != "system"
        ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "system": "\n\n".join(system_msgs) if system_msgs else None,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
            )
            
            data = response.json()
            
            return LLMResponse(
                content=data["content"][0]["text"],
                model=data["model"],
                usage={
                    "input_tokens": data["usage"]["input_tokens"],
                    "output_tokens": data["usage"]["output_tokens"]
                },
                finish_reason=data["stop_reason"]
            )
    
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion."""
        
        system_msgs = [m.content for m in messages if m.role == "system"]
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages if m.role != "system"
        ]
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "system": "\n\n".join(system_msgs) if system_msgs else None,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                    **kwargs
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "content_block_delta":
                            yield data["delta"]["text"]


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT API."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Complete using OpenAI API."""
        
        # Convert messages
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
            )
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage={
                    "input_tokens": data["usage"]["prompt_tokens"],
                    "output_tokens": data["usage"]["completion_tokens"]
                },
                finish_reason=choice["finish_reason"]
            )
    
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion."""
        
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                    **kwargs
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        if line.strip() == "data: [DONE]":
                            break
                        
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter - unified API для всех моделей.
    
    Поддерживает:
    - Claude (все версии)
    - GPT (все версии)
    - Llama, Mistral, Gemini
    - И много других моделей
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Complete using OpenRouter."""
        
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/your-repo",  # Optional
                    "X-Title": "Claude Agent Manager",  # Optional
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
            )
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage={
                    "input_tokens": data["usage"]["prompt_tokens"],
                    "output_tokens": data["usage"]["completion_tokens"]
                },
                finish_reason=choice["finish_reason"]
            )
    
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion."""
        
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                    **kwargs
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        if line.strip() == "data: [DONE]":
                            break
                        
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]


class LocalProvider(BaseLLMProvider):
    """
    Local models через Ollama, vLLM, etc.
    
    Compatible с:
    - Ollama (llama3, deepseek-coder, etc)
    - vLLM
    - text-generation-webui
    - Любой OpenAI-compatible endpoint
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
    
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Complete using local model."""
        
        # Ollama format
        if "ollama" in self.base_url or ":11434" in self.base_url:
            return await self._complete_ollama(
                messages, model, max_tokens, temperature, **kwargs
            )
        
        # OpenAI-compatible format (vLLM, etc)
        else:
            return await self._complete_openai_compatible(
                messages, model, max_tokens, temperature, **kwargs
            )
    
    async def _complete_ollama(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Complete using Ollama."""
        
        # Build prompt from messages
        prompt = "\n\n".join([
            f"{m.role}: {m.content}"
            for m in messages
        ])
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature
                    }
                }
            )
            
            data = response.json()
            
            return LLMResponse(
                content=data["response"],
                model=model,
                usage={
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0)
                },
                finish_reason="stop"
            )
    
    async def _complete_openai_compatible(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """Complete using OpenAI-compatible endpoint."""
        
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": chat_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
            )
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", model),
                usage={
                    "input_tokens": data["usage"]["prompt_tokens"],
                    "output_tokens": data["usage"]["completion_tokens"]
                },
                finish_reason=choice["finish_reason"]
            )
    
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion."""
        
        if "ollama" in self.base_url or ":11434" in self.base_url:
            # Ollama streaming
            prompt = "\n\n".join([
                f"{m.role}: {m.content}"
                for m in messages
            ])
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature
                        }
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
        else:
            # OpenAI-compatible streaming
            chat_msgs = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": chat_msgs,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                        **kwargs
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if line.strip() == "data: [DONE]":
                                break
                            
                            data = json.loads(line[6:])
                            if "choices" in data:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]


class UnifiedLLMClient:
    """
    Unified client для работы с любым LLM провайдером.
    
    Usage:
        client = UnifiedLLMClient()
        
        # Anthropic
        response = await client.complete(
            messages=[...],
            model="claude-sonnet-4-20250514",
            provider="anthropic"
        )
        
        # OpenRouter (any model)
        response = await client.complete(
            messages=[...],
            model="deepseek/deepseek-coder",
            provider="openrouter"
        )
        
        # Local
        response = await client.complete(
            messages=[...],
            model="llama3:70b",
            provider="local",
            base_url="http://localhost:11434"
        )
    """
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
    
    def _get_provider(
        self,
        provider: str,
        api_key: str = None,
        base_url: str = None
    ) -> BaseLLMProvider:
        """Get or create provider."""
        
        cache_key = f"{provider}_{api_key}_{base_url}"
        
        if cache_key not in self.providers:
            if provider == "anthropic":
                self.providers[cache_key] = AnthropicProvider(api_key)
            elif provider == "openai":
                self.providers[cache_key] = OpenAIProvider(api_key)
            elif provider == "openrouter":
                self.providers[cache_key] = OpenRouterProvider(api_key)
            elif provider == "local":
                self.providers[cache_key] = LocalProvider(base_url or "http://localhost:11434")
            else:
                raise ValueError(f"Unknown provider: {provider}")
        
        return self.providers[cache_key]
    
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        provider: str = "anthropic",
        api_key: str = None,
        base_url: str = None,
        **kwargs
    ) -> LLMResponse:
        """Get completion from any provider."""
        
        llm = self._get_provider(provider, api_key, base_url)
        return await llm.complete(messages, model, **kwargs)
    
    async def stream(
        self,
        messages: List[LLMMessage],
        model: str,
        provider: str = "anthropic",
        api_key: str = None,
        base_url: str = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Get streaming completion."""
        
        llm = self._get_provider(provider, api_key, base_url)
        async for chunk in llm.stream(messages, model, **kwargs):
            yield chunk


# ============================================================================
# EXAMPLES
# ============================================================================

async def example_usage():
    """Examples of using different providers."""
    
    client = UnifiedLLMClient()
    
    messages = [
        LLMMessage(role="system", content="You are a helpful coding assistant."),
        LLMMessage(role="user", content="Write a Python function to sort a list.")
    ]
    
    # Example 1: Anthropic Claude
    print("1. Anthropic Claude:")
    response = await client.complete(
        messages=messages,
        model="claude-sonnet-4-20250514",
        provider="anthropic"
    )
    print(f"   {response.content[:100]}...")
    
    # Example 2: OpenAI GPT
    print("\n2. OpenAI GPT:")
    response = await client.complete(
        messages=messages,
        model="gpt-4o",
        provider="openai"
    )
    print(f"   {response.content[:100]}...")
    
    # Example 3: OpenRouter (DeepSeek Coder)
    print("\n3. OpenRouter (DeepSeek):")
    response = await client.complete(
        messages=messages,
        model="deepseek/deepseek-coder",
        provider="openrouter"
    )
    print(f"   {response.content[:100]}...")
    
    # Example 4: Local (Ollama)
    print("\n4. Local (Ollama):")
    response = await client.complete(
        messages=messages,
        model="llama3:70b",
        provider="local",
        base_url="http://localhost:11434"
    )
    print(f"   {response.content[:100]}...")
    
    # Example 5: Streaming
    print("\n5. Streaming:")
    async for chunk in client.stream(
        messages=messages,
        model="claude-sonnet-4-20250514",
        provider="anthropic"
    ):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
