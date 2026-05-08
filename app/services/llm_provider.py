"""
Unified LLM Provider

Routes requests to local Ollama for LLM inference.

Environment variables:
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=llama-fast
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class UnifiedLLMService:
    """Routes LLM requests to Ollama."""

    def __init__(self):
        self._last_provider_used: Optional[str] = None

    @property
    def configured_provider(self) -> str:
        return "ollama"

    @configured_provider.setter
    def configured_provider(self, value: str):
        pass  # Only ollama supported

    @property
    def last_provider_used(self) -> Optional[str]:
        return self._last_provider_used

    async def get_active_provider(self) -> str:
        """Always returns ollama."""
        return "ollama"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        timeout: float = 60.0,
    ) -> str:
        """Generate text from Ollama."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        ollama = get_ollama_service()
        return await ollama.generate(prompt, temperature=temperature, num_predict=max_tokens, timeout=timeout)

    async def chat_simple(self, messages: List[Dict[str, str]], system_prompt: str = "") -> str:
        """Simple chat returning just text."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        ollama = get_ollama_service()
        return await ollama.chat_simple(messages, system_prompt)

    async def quick_explain(self, screen_text: str, context: str = "") -> str:
        """Fast screen explanation."""
        from app.services.ollama import get_ollama_service
        self._last_provider_used = "ollama"
        ollama = get_ollama_service()
        return await ollama.quick_explain(screen_text, context)

    async def check_available(self) -> bool:
        """Check if Ollama is available."""
        from app.services.ollama import get_ollama_service
        return await get_ollama_service().check_available()

    async def get_status(self) -> Dict[str, Any]:
        """Get status for the UI."""
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
