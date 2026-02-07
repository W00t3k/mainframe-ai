"""
Ollama Service

Handles all communication with the Ollama LLM backend.
"""

import httpx
from typing import List, Dict, Any, Optional

from app.config import get_config
from app.constants.prompts import SYSTEM_PROMPT


class OllamaService:
    """Service for interacting with Ollama LLM."""
    
    def __init__(self):
        self.config = get_config()
    
    @property
    def url(self) -> str:
        return self.config.OLLAMA_URL
    
    @property
    def model(self) -> str:
        return self.config.OLLAMA_MODEL
    
    async def check_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.url}/api/tags", timeout=5.0)
                return response.status_code == 200
        except:
            return False
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        num_predict: int = 2048,
        timeout: float = 120.0
    ) -> str:
        """Generate a response from Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": num_predict,
                        }
                    },
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "No response generated.")
                else:
                    return f"Ollama error: {response.status_code}"
                    
        except httpx.TimeoutException:
            return "Request timed out. The model may be loading - please try again."
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        num_predict: int = 2048,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """Chat with Ollama using the chat API (supports tools)."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                }
            }
            
            if tools:
                payload["tools"] = tools
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/chat",
                    json=payload,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Ollama error: {response.status_code}"}
                    
        except httpx.TimeoutException:
            return {"error": "Request timed out. The model may be loading - please try again."}
        except Exception as e:
            return {"error": f"Error communicating with Ollama: {str(e)}"}
    
    async def chat_simple(self, messages: List[Dict[str, str]]) -> str:
        """Simple chat that returns just the response text."""
        prompt = SYSTEM_PROMPT + "\n\n"
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"User: {content}\n\n"
            else:
                prompt += f"Assistant: {content}\n\n"
        prompt += "Assistant: "
        
        return await self.generate(prompt)


# Singleton instance
_ollama_service: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    """Get the singleton Ollama service instance."""
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service
