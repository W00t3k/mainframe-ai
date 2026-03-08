"""
Unified LLM Provider

Routes requests to either local Ollama or cloud Grok (xAI) based on
configuration and availability. Provides automatic fallback.

Provider priority:
1. If user explicitly selects a provider, use that
2. If Ollama is available locally, prefer it (no API cost, no data leaves machine)
3. If Ollama is down and Grok is configured, fall back to Grok
4. If neither is available, return error

Environment variables:
    LLM_PROVIDER=ollama|grok|auto   (default: auto)
    XAI_API_KEY=xai-...             (required for Grok)
    XAI_MODEL=grok-3-mini-fast      (optional)
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=llama3.1:8b
"""

import os
import logging
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    GROK = "grok"
    AUTO = "auto"


class UnifiedLLMService:
    """Routes LLM requests to the best available provider."""

    def __init__(self):
        self._provider = LLMProvider(os.getenv("LLM_PROVIDER", "auto").lower())
        self._last_provider_used: Optional[str] = None

    @property
    def configured_provider(self) -> str:
        return self._provider.value

    @configured_provider.setter
    def configured_provider(self, value: str):
        try:
            self._provider = LLMProvider(value.lower())
        except ValueError:
            logger.warning(f"Invalid provider '{value}', keeping {self._provider.value}")

    @property
    def last_provider_used(self) -> Optional[str]:
        return self._last_provider_used

    async def get_active_provider(self) -> str:
        """Determine which provider to use right now."""
        from app.services.ollama import get_ollama_service
        from app.services.grok import get_grok_service

        if self._provider == LLMProvider.OLLAMA:
            return "ollama"
        elif self._provider == LLMProvider.GROK:
            grok = get_grok_service()
            if grok.is_configured:
                return "grok"
            return "ollama"  # fallback if no API key
        else:  # AUTO
            ollama = get_ollama_service()
            if await ollama.check_available():
                return "ollama"
            grok = get_grok_service()
            if grok.is_configured:
                available = await grok.check_available()
                if available:
                    return "grok"
            return "ollama"  # will fail gracefully with Ollama error

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ) -> str:
        """Generate text from the best available provider."""
        provider = await self.get_active_provider()
        self._last_provider_used = provider

        if provider == "grok":
            from app.services.grok import get_grok_service
            grok = get_grok_service()
            return await grok.generate(prompt, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        else:
            from app.services.ollama import get_ollama_service
            ollama = get_ollama_service()
            return await ollama.generate(prompt, temperature=temperature, num_predict=max_tokens, timeout=timeout)

    async def chat_simple(self, messages: List[Dict[str, str]], system_prompt: str = "") -> str:
        """Simple chat returning just text."""
        provider = await self.get_active_provider()
        self._last_provider_used = provider

        if provider == "grok":
            from app.services.grok import get_grok_service
            grok = get_grok_service()
            return await grok.chat_simple(messages, system_prompt)
        else:
            from app.services.ollama import get_ollama_service
            ollama = get_ollama_service()
            return await ollama.chat_simple(messages)

    async def quick_explain(self, screen_text: str, context: str = "") -> str:
        """Fast screen explanation."""
        provider = await self.get_active_provider()
        self._last_provider_used = provider

        if provider == "grok":
            from app.services.grok import get_grok_service
            grok = get_grok_service()
            return await grok.quick_explain(screen_text, context)
        else:
            from app.services.ollama import get_ollama_service
            ollama = get_ollama_service()
            return await ollama.quick_explain(screen_text, context)

    async def check_available(self) -> bool:
        """Check if any provider is available."""
        provider = await self.get_active_provider()
        if provider == "grok":
            from app.services.grok import get_grok_service
            return await get_grok_service().check_available()
        else:
            from app.services.ollama import get_ollama_service
            return await get_ollama_service().check_available()

    async def get_status(self) -> Dict[str, Any]:
        """Get status of all providers for the UI."""
        from app.services.ollama import get_ollama_service
        from app.services.grok import get_grok_service

        ollama = get_ollama_service()
        grok = get_grok_service()

        ollama_ok = await ollama.check_available()
        grok_configured = grok.is_configured
        grok_ok = await grok.check_available() if grok_configured else False

        active = await self.get_active_provider()

        return {
            "active_provider": active,
            "configured_provider": self._provider.value,
            "last_used": self._last_provider_used,
            "ollama": {
                "available": ollama_ok,
                "url": ollama.url,
                "model": ollama.model,
            },
            "grok": {
                "configured": grok_configured,
                "available": grok_ok,
                "model": grok.model if grok_configured else None,
                "models": await _get_cloud_models(grok) if grok_configured else [],
            },
        }


async def _get_cloud_models(grok) -> list:
    """Fetch models dynamically from the connected cloud API."""
    try:
        api_models = await grok.list_models()
        if api_models:
            return [
                {
                    "id": m.get("id", ""),
                    "name": m.get("id", ""),
                    "description": m.get("owned_by", ""),
                    "context_window": m.get("context_window", 0),
                }
                for m in api_models
                if m.get("id")
            ]
    except Exception:
        pass
    # Fallback to static catalog if API fails
    from app.services.grok import GROK_MODELS
    return [{"id": k, **v} for k, v in GROK_MODELS.items()]


# Singleton
_unified_service: Optional[UnifiedLLMService] = None


def get_llm_service() -> UnifiedLLMService:
    """Get the singleton unified LLM service."""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedLLMService()
    return _unified_service
