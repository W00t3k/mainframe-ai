"""
Groq Cloud LLM Service

Provides cloud-based LLM capability via Groq's inference API.
Uses the OpenAI-compatible endpoint at api.groq.com.

Set GROQ_API_KEY environment variable to enable.
Optionally set GROQ_MODEL (default: llama-3.3-70b-versatile).

This service acts as a fallback or alternative to local Ollama inference,
useful when GPU hardware is unavailable or for higher-quality responses.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from app.config import get_config

# Persistent key file — lives next to the project root, not committed
_KEY_FILE = Path(__file__).resolve().parent.parent.parent / ".groq_key"

logger = logging.getLogger(__name__)

# API configuration
XAI_API_URL = "https://api.groq.com/openai/v1"
XAI_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Available Groq models (groq.com — api.groq.com)
GROK_MODELS = {
    "llama-3.3-70b-versatile": {
        "name": "Llama 3.3 70B",
        "description": "Best quality — Llama 3.3 70B on Groq, great for analysis",
        "context_window": 131072,
        "max_output": 32768,
    },
    "llama-3.1-8b-instant": {
        "name": "Llama 3.1 8B Instant",
        "description": "Fastest — low latency, good for interactive use",
        "context_window": 131072,
        "max_output": 8192,
    },
    "mixtral-8x7b-32768": {
        "name": "Mixtral 8x7B",
        "description": "Strong reasoning — 32K context, good balance of speed and quality",
        "context_window": 32768,
        "max_output": 4096,
    },
    "gemma2-9b-it": {
        "name": "Gemma 2 9B",
        "description": "Google Gemma 2 — compact and capable",
        "context_window": 8192,
        "max_output": 8192,
    },
}



class GrokService:
    """Service for interacting with Groq's API (OpenAI-compatible)."""

    def __init__(self):
        self.config = get_config()
        self._api_key = os.getenv("GROQ_API_KEY", os.getenv("XAI_API_KEY", ""))
        # Fall back to persisted key file if env var not set
        if not self._api_key and _KEY_FILE.exists():
            try:
                self._api_key = _KEY_FILE.read_text().strip()
            except Exception:
                pass
        self._model = os.getenv("GROQ_MODEL", os.getenv("XAI_MODEL", XAI_DEFAULT_MODEL))
        self._api_url = os.getenv("GROQ_API_URL", XAI_API_URL)

    @property
    def is_configured(self) -> bool:
        """Check if Groq API key is set."""
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str):
        self._model = value

    def save_key(self, key: str) -> None:
        """Persist the API key to disk so it survives restarts."""
        try:
            _KEY_FILE.write_text(key)
            _KEY_FILE.chmod(0o600)
        except Exception as e:
            logger.warning(f"Could not save Groq key to disk: {e}")

    @property
    def api_key(self) -> str:
        return self._api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def check_available(self) -> bool:
        """Check if Groq API is reachable and key is valid."""
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
            logger.debug(f"Groq availability check failed: {e}")
            return False

    async def check_available_verbose(self) -> dict:
        """Check Groq API and return detail on failure."""
        if not self.is_configured:
            return {"ok": False, "error": "No API key set"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._api_url}/models",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return {"ok": True}
                return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
            return {"error": "Groq API key not configured. Set GROQ_API_KEY env var."}

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
                    return {"error": "Invalid Groq API key. Check GROQ_API_KEY."}
                elif resp.status_code == 429:
                    return {"error": "Groq rate limit exceeded. Try again shortly."}
                else:
                    return {"error": f"Groq API error: {resp.status_code} — {resp.text[:200]}"}

        except httpx.TimeoutException:
            return {"error": "Groq API request timed out."}
        except Exception as e:
            logger.error(f"Groq chat error: {e}")
            return {"error": f"Groq API error: {str(e)}"}

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
            return "No response from Groq."

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
            return "No response from Groq."

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
