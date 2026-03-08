"""
Chat Service

Handles chat processing, conversation management, and RAG integration.
"""

import json
from typing import List, Dict, Any, Optional

from app.config import get_config
from app.services.ollama import get_ollama_service
from app.services.llm_provider import get_llm_service
from app.constants.prompts import SYSTEM_PROMPT


class ChatService:
    """Service for chat processing and conversation management."""
    
    def __init__(self):
        self.config = get_config()
        self.ollama = get_ollama_service()
        self.llm = get_llm_service()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 40
        
        # Import optional modules
        self._rag_engine = None
        self._agent_tools = None
        self._connection = None
        self._load_optional_modules()
    
    def _load_optional_modules(self):
        """Load optional modules if available."""
        try:
            from rag_engine import get_rag_engine
            self._rag_engine = get_rag_engine
        except ImportError:
            pass
        
        try:
            from agent_tools import (
                connection, TOOL_DEFINITIONS, execute_tool_async,
                connect_mainframe, disconnect_mainframe, read_screen
            )
            self._connection = connection
            self._tool_definitions = TOOL_DEFINITIONS
            self._execute_tool_async = execute_tool_async
            self._connect_mainframe = connect_mainframe
            self._disconnect_mainframe = disconnect_mainframe
            self._read_screen = read_screen
        except ImportError:
            self._connection = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to mainframe."""
        return self._connection is not None and self._connection.connected
    
    @property
    def connection_host(self) -> str:
        """Get the current connection host."""
        if self._connection and self._connection.connected:
            return f"{self._connection.host}:{self._connection.port}"
        return ""
    
    @property
    def current_screen(self) -> Optional[str]:
        """Get the current screen content."""
        if self._connection and self._connection.connected:
            return self._connection.current_screen
        return None
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    async def get_rag_context(self, query: str, n_results: int = 2) -> str:
        """Query RAG for relevant context."""
        if self._rag_engine is None:
            return ""
        
        try:
            engine = self._rag_engine()
            results = await engine.query_simple(query, n_results=n_results)
            if results:
                context = "\n\n[Relevant Knowledge Base Information]\n"
                for r in results:
                    context += f"---\n{r['content']}\n"
                return context
        except Exception as e:
            print(f"RAG query error: {e}")
        
        return ""
    
    async def process_command(self, command: str, args: str = "") -> Dict[str, Any]:
        """Process a slash command."""
        result = {
            "response": "",
            "connected": self.is_connected,
            "host": self.connection_host,
            "screen": self.current_screen,
            "model": self.config.OLLAMA_MODEL
        }
        
        if command == "/connect":
            if not args:
                result["response"] = "Usage: `/connect host:port`\n\nExample: `/connect localhost:3270`"
            elif self._connect_mainframe:
                success, message = self._connect_mainframe(args)
                result["response"] = message
                result["connected"] = self.is_connected
                result["host"] = self.connection_host
                result["screen"] = self.current_screen
            else:
                result["response"] = "Connection functionality not available."
        
        elif command == "/disconnect":
            if self._disconnect_mainframe:
                result["response"] = self._disconnect_mainframe()
            result["connected"] = False
            result["screen"] = None
        
        elif command == "/screen":
            if self.is_connected and self._read_screen:
                screen = self._read_screen()
                result["response"] = f"**Current Screen:**\n```\n{screen}\n```"
                result["screen"] = screen
            else:
                result["response"] = "Not connected. Use `/connect host:port` first."
        
        elif command == "/clear":
            self.clear_history()
            result["response"] = "Conversation cleared."
        
        elif command == "/model":
            if args:
                self.config.OLLAMA_MODEL = args
                result["response"] = f"Model changed to: `{args}`"
            else:
                result["response"] = f"Current model: `{self.config.OLLAMA_MODEL}`\n\nUsage: `/model llama3.1:8b`"
        
        elif command == "/help":
            result["response"] = """## Commands

| Command | Description |
|---------|-------------|
| `/connect host:port` | Connect to mainframe via TN3270 |
| `/disconnect` | Disconnect from mainframe |
| `/screen` | Show current 3270 screen |
| `/model [name]` | Show/change Ollama model |
| `/clear` | Clear conversation history |
| `/help` | Show this help |

## Terminal Shortcuts (when connected)
- **Enter** - Send Enter key
- **Esc** - Send Clear
- **F1-F12** - PF1-PF12
- **Shift+F1-F12** - PF13-PF24
- **Tab** - Next field
- **Ctrl+R** - Reset

## Example Questions
- What does ABEND S0C7 mean?
- Generate JCL to copy a dataset
- Explain this COBOL code: [paste code]"""
        
        else:
            result["response"] = f"Unknown command: `{command}`. Type `/help` for available commands."
        
        return result
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """Process a chat message."""
        result = {
            "response": "",
            "connected": self.is_connected,
            "host": self.connection_host,
            "screen": self.current_screen,
            "model": self.config.OLLAMA_MODEL
        }
        
        # Handle commands
        if user_message.startswith("/"):
            parts = user_message.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            return await self.process_command(cmd, args)
        
        # Check if any LLM provider is available
        if not await self.llm.check_available():
            result["response"] = """⚠️ **No LLM provider available!**

**Option 1 — Local (Ollama):**
```bash
ollama serve
ollama pull llama3.1:8b
```

**Option 2 — Cloud (Grok):**
Set `XAI_API_KEY` environment variable with your xAI API key.
Then switch provider: `POST /api/llm/provider/switch {"provider": "grok"}`
"""
            return result
        
        # Build context
        context = ""
        rag_context = await self.get_rag_context(user_message)
        
        if self.is_connected and self._read_screen:
            screen = self._read_screen()
            result["screen"] = screen
            context = f"\n\n[Current 3270 Screen]\n```\n{screen}\n```"
        
        full_message = user_message + rag_context + context
        
        self.conversation_history.append({
            "role": "user",
            "content": full_message
        })
        
        # Call LLM (routes to Ollama or Grok based on provider config)
        assistant_message = await self.llm.chat_simple(self.conversation_history)
        
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Cap history
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        result["response"] = assistant_message
        return result


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the singleton chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
