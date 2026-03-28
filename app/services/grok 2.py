"""
Grok (xAI) Cloud LLM Service

Provides cloud-based LLM capability via xAI's Grok API.
Uses the OpenAI-compatible endpoint at api.x.ai.

Set XAI_API_KEY environment variable to enable.
Optionally set XAI_MODEL (default: grok-3-mini-fast).

This service acts as a fallback or alternative to local Ollama inference,
useful when GPU hardware is unavailable or for higher-quality responses.
"""

import os
import logging
from typing import List, Dict, Any, Optional

import httpx

from app.config import get_config

logger = logging.getLogger(__name__)

# API configuration
XAI_API_URL = "https://api.x.ai/v1"
XAI_DEFAULT_MODEL = "grok-3-mini-fast"

# Available Grok models (xAI — api.x.ai)
GROK_MODELS = {
    "grok-3-mini-fast": {
        "name": "Grok 3 Mini Fast",
        "description": "Fastest Grok model — low latency, good for interactive use",
        "context_window": 131072,
        "max_output": 4096,
    },
    "grok-3-mini": {
        "name": "Grok 3 Mini",
        "description": "Small but capable — good balance of speed and quality",
        "context_window": 131072,
        "max_output": 4096,
    },
    "grok-3-fast": {
        "name": "Grok 3 Fast",
        "description": "Full Grok 3 with fast inference — best for complex analysis",
        "context_window": 131072,
        "max_output": 16384,
    },
    "grok-3": {
        "name": "Grok 3",
        "description": "Full Grok 3 — highest quality, higher latency",
        "context_window": 131072,
        "max_output": 16384,
    },
}



class GrokService:
    """Service for interacting with xAI's Grok API (OpenAI-compatible)."""

    def __init__(self):
        self.config = get_config()
        self._api_key = os.getenv("XAI_API_KEY", "")
        self._model = os.getenv("XAI_MODEL", XAI_DEFAULT_MODEL)
        self._api_url = os.getenv("XAI_API_URL", XAI_API_URL)

    @property
    def is_configured(self) -> bool:
        """Check if xAI API key is set."""
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str):
        self._model = value

    @property
    def api_key(self) -> str:
        return self._api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def check_available(self) -> bool:
        """Check if Grok API is reachable and key is valid."""
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._api_url}/models",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Grok availability check failed: {e}")
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Grok models from the API."""
        if not self.is_configured:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._api_url}/models",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
        except Exception as e:
            logger.error(f"Grok list_models error: {e}")
        return []

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """Chat completion via xAI API (OpenAI-compatible format)."""
        if not self.is_configured:
            return {"error": "Grok API key not configured. Set XAI_API_KEY env var."}

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self._api_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return data
                elif resp.status_code == 401:
                    return {"error": "Invalid xAI API key. Check XAI_API_KEY."}
                elif resp.status_code == 429:
                    return {"error": "Grok rate limit exceeded. Try again shortly."}
                else:
                    return {"error": f"Grok API error: {resp.status_code} — {resp.text[:200]}"}

        except httpx.TimeoutException:
            return {"error": "Grok API request timed out."}
        except Exception as e:
            logger.error(f"Grok chat error: {e}")
            return {"error": f"Grok API error: {str(e)}"}

    async def chat_simple(self, messages: List[Dict[str, str]], system_prompt: str = "") -> str:
        """Simple chat that returns just the response text."""
        from app.constants.prompts import SYSTEM_PROMPT

        api_messages = []
        if system_prompt or SYSTEM_PROMPT:
            api_messages.append({
                "role": "system",
                "content": system_prompt or SYSTEM_PROMPT,
            })

        for msg in messages:
            api_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        result = await self.chat(api_messages)

        if "error" in result:
            return result["error"]

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return "No response from Grok."

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 120.0,
    ) -> str:
        """Generate a response from a raw prompt (compatibility with OllamaService)."""
        messages = [{"role": "user", "content": prompt}]
        result = await self.chat(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

        if "error" in result:
            return result["error"]

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return "No response from Grok."

    async def quick_explain(self, screen_text: str, context: str = "") -> str:
        """Fast screen explanation — mirrors OllamaService.quick_explain."""
        first_lines = "\n".join(screen_text.split("\n")[:15])
        prompt = f"""You are explaining a mainframe terminal screen. Context: {context or 'viewing screen'}.

Screen:
{first_lines}

In ONE sentence, explain what this shows and what to do next. Be specific (VTAM, TSO, RACF, JES). No markdown."""

        return await self.generate(prompt, temperature=0.3, max_tokens=150, timeout=15.0)


# Singleton instance
_grok_service: Optional[GrokService] = None


def get_grok_service() -> GrokService:
    """Get the singleton Grok service instance."""
    global _grok_service
    if _grok_service is None:
        _grok_service = GrokService()
    return _grok_service
