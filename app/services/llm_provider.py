"""
Unified LLM Provider

Local Ollama is the only LLM backend. This module keeps a thin
``UnifiedLLMService`` wrapper so callers have a stable interface, but every
request goes to Ollama.

Environment variables:
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=llama3.1:8b
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OLLAMA = "ollama"


class UnifiedLLMService:
    """Thin wrapper around the local Ollama service."""

    def __init__(self):
        self._last_provider_used: Optional[str] = None

    @property
    def configured_provider(self) -> str:
        return "ollama"

    @configured_provider.setter
    def configured_provider(self, value: str):
        # Only Ollama is supported; ignore other values.
        if value and value.lower() != "ollama":
            logger.warning(f"Provider '{value}' not supported — using ollama")

    @property
    def last_provider_used(self) -> Optional[str]:
        return self._last_provider_used

    async def get_active_provider(self) -> str:
        return "ollama"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ) -> str:
        """Generate text via Ollama."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        ollama = get_ollama_service()
        return await ollama.generate(
            prompt, temperature=temperature, num_predict=max_tokens, timeout=timeout
        )

    async def chat_simple(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 2048,
    ) -> str:
        """Simple chat returning just text."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        return await get_ollama_service().chat_simple(messages)

    async def chat_compact(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 150,
        timeout: float = 30.0,
    ) -> str:
        """Compact chat for quick Q&A - lower token limit, faster timeout."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        ollama = get_ollama_service()
        prompt = system_prompt + "\n\n" if system_prompt else ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"User: {content}\n\n"
            else:
                prompt += f"Assistant: {content}\n\n"
        prompt += "Assistant: "
        return await ollama.generate(
            prompt, temperature=temperature, num_predict=max_tokens, timeout=timeout
        )

    async def quick_explain(self, screen_text: str, context: str = "") -> str:
        """Fast screen explanation."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        return await get_ollama_service().quick_explain(screen_text, context)

    async def check_available(self) -> bool:
        """Check if Ollama is available."""
        from app.services.ollama import get_ollama_service
        return await get_ollama_service().check_available()

    async def get_status(self) -> Dict[str, Any]:
        """Get provider status for the UI."""
        from app.services.ollama import get_ollama_service
        ollama = get_ollama_service()
        ollama_ok = await ollama.check_available()
        return {
            "active_provider": "ollama",
            "configured_provider": "ollama",
            "last_used": self._last_provider_used,
            "ollama": {
                "available": ollama_ok,
                "url": ollama.url,
                "model": ollama.model,
            },
        }


# Singleton
_unified_service: Optional[UnifiedLLMService] = None


def get_llm_service() -> UnifiedLLMService:
    """Get the singleton unified LLM service."""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedLLMService()
    return _unified_service
