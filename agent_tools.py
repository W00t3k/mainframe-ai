#!/usr/bin/env python3
"""
Agent Tools - Shared tool definitions for Mainframe AI Assistant
Extracted from web_app.py for reuse by agentic loop and MCP server
"""

import os
import sys
import threading
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# BIRP modules - check current directory first, then fallback paths
BIRP_AVAILABLE = False
WrappedEmulator = None
Screen = None

# Try direct import first (if birpv2_modules is in same directory or PYTHONPATH)
try:
    from birpv2_modules.emulator.wrapper import WrappedEmulator
    from birpv2_modules.core.models import Screen
    BIRP_AVAILABLE = True
except ImportError:
    # Try adding the current script's directory to path
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    try:
        from birpv2_modules.emulator.wrapper import WrappedEmulator
        from birpv2_modules.core.models import Screen
        BIRP_AVAILABLE = True
    except ImportError:
        # Fallback: try ~/Desktop/STuFF /birp
        BIRP_PATH = os.path.expanduser("~/Desktop/STuFF /birp")
        if os.path.exists(BIRP_PATH) and BIRP_PATH not in sys.path:
            sys.path.insert(0, BIRP_PATH)
            try:
                from birpv2_modules.emulator.wrapper import WrappedEmulator
                from birpv2_modules.core.models import Screen
                BIRP_AVAILABLE = True
            except ImportError:
                pass


@dataclass
class ConnectionState:
    """Global TN3270 connection state"""
    host: str = ""
    port: int = 23
    connected: bool = False
    emulator: Optional[object] = None
    current_screen: str = ""
    screen_rows: int = 24
    screen_cols: int = 80
    cursor_row: int = 0
    cursor_col: int = 0
    poller_thread: Optional[threading.Thread] = None
    poller_stop: threading.Event = field(default_factory=threading.Event)
    command_lock: threading.Lock = field(default_factory=threading.Lock)


# Global connection instance
connection = ConnectionState()

# Callbacks for broadcasting updates (set by web_app.py)
_screen_update_callback = None
_graph_update_callback = None


def set_screen_update_callback(callback):
    """Set callback for screen updates (used by web_app for WebSocket broadcast)"""
    global _screen_update_callback
    _screen_update_callback = callback


def set_graph_update_callback(callback):
    """Set callback for graph updates (used for real-time visualization)"""
    global _graph_update_callback
    _graph_update_callback = callback


# =============================================================================
# Screen Buffer Helpers
# =============================================================================

def normalize_screen_buffer(buffer):
    """Ensure screen buffer is a list of text lines for Screen()."""
    if isinstance(buffer, bytes):
        text = buffer.decode("latin-1", errors="ignore")
        return text.splitlines()
    if isinstance(buffer, str):
        return buffer.splitlines()
    if isinstance(buffer, list):
        normalized = []
        for line in buffer:
            if isinstance(line, bytes):
                normalized.append(line.decode("latin-1", errors="ignore"))
            else:
                normalized.append(str(line))
        return normalized
    return [str(buffer)]


def normalize_screen_text(buffer):
    """Normalize screen output into a printable string."""
    if isinstance(buffer, bytes):
        return buffer.decode("latin-1", errors="ignore")
    if isinstance(buffer, str):
        return buffer
    if isinstance(buffer, list):
        lines = []
        for line in buffer:
            if isinstance(line, bytes):
                lines.append(line.decode("latin-1", errors="ignore"))
            else:
                lines.append(str(line))
        return "\n".join(lines)
    return str(buffer)


def screen_from_readbuffer(buffer):
    """Convert ReadBuffer(Ascii) output to a printable screen."""
    lines = normalize_screen_buffer(buffer)
    if not lines:
        return ""
    try:
        return str(Screen(lines))
    except Exception:
        return "\n".join(lines)


# =============================================================================
# Emulator Command Execution
# =============================================================================

def exec_emulator_command(command: bytes, timeout: float = 3):
    """Execute emulator command serialized to avoid s3270 desync."""
    em = connection.emulator
    if not em:
        return None
    with connection.command_lock:
        return em.exec_command(command)


# =============================================================================
# Connection Management
# =============================================================================

def connect_mainframe(target: str) -> tuple[bool, str]:
    """Connect to mainframe via TN3270.

    Args:
        target: Host and port in format "host:port" or just "host"

    Returns:
        Tuple of (success: bool, message: str)
    """
    global connection

    if not BIRP_AVAILABLE:
        return False, "BIRP modules not available. TN3270 connectivity disabled."

    try:
        if ":" in target:
            host, port = target.rsplit(":", 1)
            port = int(port)
        else:
            host = target
            port = 23

        # Disconnect existing connection
        if connection.connected and connection.emulator:
            try:
                connection.emulator.terminate()
            except:
                pass

        connection.emulator = WrappedEmulator(visible=False, command_timeout=5)
        try:
            connection.emulator.connect(f"{host}:{port}", timeout=5)
        except TypeError:
            connection.emulator.connect(f"{host}:{port}")

        connection.host = host
        connection.port = port
        connection.connected = True

        # Wait for 3270 mode and read initial screen
        try:
            exec_emulator_command(b'Wait(1,3270Mode)', timeout=5)
        except Exception:
            pass
        try:
            read_screen()
        except Exception:
            pass

        return True, f"Connected to {host}:{port}"

    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def disconnect_mainframe() -> str:
    """Disconnect from mainframe.

    Returns:
        Status message
    """
    global connection

    if connection.connected and connection.emulator:
        try:
            connection.emulator.terminate()
        except:
            pass

    connection.connected = False
    connection.emulator = None
    connection.current_screen = ""
    return "Disconnected"


# =============================================================================
# Screen Reading
# =============================================================================

def read_screen() -> str:
    """Read current 3270 screen content.

    Returns:
        Screen text or error message
    """
    global connection

    if not connection.connected or not connection.emulator:
        return "[Not connected]"

    try:
        response = exec_emulator_command(b'ReadBuffer(Ascii)', timeout=6)
        buffer = response.data if response else ""
        screen_text = screen_from_readbuffer(buffer)
        connection.current_screen = screen_text
        return connection.current_screen
    except Exception:
        return connection.current_screen or "[Screen unavailable]"


def get_screen_data() -> dict:
    """Get screen data for web terminal."""
    global connection

    if not connection.connected or not connection.emulator:
        return {
            "connected": False,
            "screen": "",
            "rows": 24,
            "cols": 80,
            "cursor_row": 0,
            "cursor_col": 0
        }

    return get_cached_screen_data()


def get_cached_screen_data() -> dict:
    """Return cached screen data without hitting the emulator."""
    return {
        "connected": connection.connected,
        "screen": connection.current_screen,
        "rows": connection.screen_rows,
        "cols": connection.screen_cols,
        "cursor_row": connection.cursor_row,
        "cursor_col": connection.cursor_col,
        "host": f"{connection.host}:{connection.port}" if connection.connected else ""
    }


# =============================================================================
# Terminal Input
# =============================================================================

def send_terminal_key(key_type: str, value: str = "") -> dict:
    """Send a key to the terminal.

    Args:
        key_type: Type of key (string, enter, pf, pa, clear, tab, etc.)
        value: Value for string or key number for pf/pa

    Returns:
        Dict with success status and screen data
    """
    global connection

    if not connection.connected or not connection.emulator:
        return {"success": False, "error": "Not connected"}

    try:
        # Wait for keyboard unlock
        try:
            exec_emulator_command(b'Wait(1,Unlock)')
        except Exception:
            try:
                exec_emulator_command(b'Reset()')
            except Exception:
                pass

        # Send the key
        if key_type == "string":
            if value:
                exec_emulator_command(f'String("{value}")'.encode())
        elif key_type == "enter":
            exec_emulator_command(b'Enter()')
        elif key_type == "pf":
            exec_emulator_command(f'PF({value})'.encode())
        elif key_type == "pa":
            exec_emulator_command(f'PA({value})'.encode())
        elif key_type == "clear":
            exec_emulator_command(b'Clear()')
        elif key_type == "tab":
            exec_emulator_command(b'Tab()')
        elif key_type == "backtab":
            exec_emulator_command(b'BackTab()')
        elif key_type == "up":
            exec_emulator_command(b'Up()')
        elif key_type == "down":
            exec_emulator_command(b'Down()')
        elif key_type == "left":
            exec_emulator_command(b'Left()')
        elif key_type == "right":
            exec_emulator_command(b'Right()')
        elif key_type == "home":
            exec_emulator_command(b'Home()')
        elif key_type == "delete":
            exec_emulator_command(b'Delete()')
        elif key_type == "backspace":
            exec_emulator_command(b'BackSpace()')
        elif key_type == "eraseeof":
            exec_emulator_command(b'EraseEOF()')
        elif key_type == "reset":
            exec_emulator_command(b'Reset()')

        # Wait and read updated screen
        try:
            exec_emulator_command(b'Wait(1,Unlock)')
        except Exception:
            pass
        try:
            read_screen()
        except Exception:
            pass

        return {"success": True, "screen_data": get_cached_screen_data()}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Screen Polling
# =============================================================================

def start_screen_poller():
    """Start background screen polling."""
    connection.poller_stop.clear()

    def poll():
        while not connection.poller_stop.is_set() and connection.connected and connection.emulator:
            try:
                read_screen()
            except Exception:
                pass
            connection.poller_stop.wait(1.0)

    if connection.poller_thread and connection.poller_thread.is_alive():
        return
    connection.poller_thread = threading.Thread(target=poll, daemon=True)
    connection.poller_thread.start()


def stop_screen_poller():
    """Stop background screen polling."""
    connection.poller_stop.set()


# =============================================================================
# Screen Capture
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENCAPS_DIR = os.path.join(BASE_DIR, "screencaps")
os.makedirs(SCREENCAPS_DIR, exist_ok=True)

# In-memory screencap store
screencaps = []


def capture_screen() -> dict:
    """Capture and save current screen.

    Returns:
        Dict with success status and capture info
    """
    global screencaps

    if not connection.connected:
        return {"success": False, "error": "Not connected"}

    screen = read_screen()
    import time
    epoch_time = int(time.time())
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    host = f"{connection.host}:{connection.port}"
    cap_id = f"{timestamp_str}_{connection.host.replace('.', '_')}"

    cap = {
        "id": cap_id,
        "screen": screen,
        "host": host,
        "timestamp": epoch_time,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    screencaps.append(cap)

    # Save to file
    filename = f"screencap_{cap_id}.txt"
    filepath = os.path.join(SCREENCAPS_DIR, filename)
    with open(filepath, "w") as f:
        f.write(f"Host: {host}\n")
        f.write(f"Time: {cap['time']}\n")
        f.write("=" * 80 + "\n")
        f.write(screen)

    return {"success": True, "screencap": cap, "file": filename}


def get_connection_status() -> dict:
    """Get current connection status.

    Returns:
        Dict with connection info
    """
    return {
        "connected": connection.connected,
        "host": connection.host if connection.connected else "",
        "port": connection.port if connection.connected else 0,
        "target": f"{connection.host}:{connection.port}" if connection.connected else "",
        "birp_available": BIRP_AVAILABLE
    }


# =============================================================================
# Tool Definitions (Ollama /api/chat format)
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "connect_mainframe",
            "description": "Connect to a mainframe via TN3270 protocol. Use host:port format like 'localhost:3270'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Host and port to connect to, e.g. 'localhost:3270' or 'mainframe.example.com:23'"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "disconnect_mainframe",
            "description": "Disconnect from the currently connected mainframe.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Read the current 3270 terminal screen content. Returns the text visible on screen.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_text",
            "description": "Type text into the terminal at the current cursor position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type into the terminal"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_enter",
            "description": "Press the Enter key on the terminal.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_pf_key",
            "description": "Press a PF (Program Function) key. PF3 typically goes back, PF1 is help.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "integer",
                        "description": "PF key number (1-24)"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_clear",
            "description": "Press the Clear key to clear the screen.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_tab",
            "description": "Press Tab to move to the next input field.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": "Search the RAG knowledge base for mainframe information (ABEND codes, JCL syntax, COBOL, CICS, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the knowledge base"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 3)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Capture and save the current screen as a screenshot for later reference.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_connection_status",
            "description": "Get the current connection status (connected/disconnected, host, port).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# =============================================================================
# Tool Execution Dispatcher
# =============================================================================

def execute_tool(name: str, arguments: dict, rag_engine=None) -> str:
    """Execute a tool by name and return the result as a string.

    Args:
        name: Tool name from TOOL_DEFINITIONS
        arguments: Tool arguments as a dict
        rag_engine: Optional RAG engine instance for query_knowledge_base

    Returns:
        String result of tool execution
    """
    try:
        if name == "connect_mainframe":
            target = arguments.get("target", "localhost:3270")
            success, message = connect_mainframe(target)
            return message

        elif name == "disconnect_mainframe":
            return disconnect_mainframe()

        elif name == "read_screen":
            return read_screen()

        elif name == "send_text":
            text = arguments.get("text", "")
            result = send_terminal_key("string", text)
            if result.get("success"):
                return f"Typed: {text}"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "send_enter":
            result = send_terminal_key("enter")
            if result.get("success"):
                return "Pressed Enter"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "send_pf_key":
            key = arguments.get("key", 3)
            result = send_terminal_key("pf", str(key))
            if result.get("success"):
                return f"Pressed PF{key}"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "send_clear":
            result = send_terminal_key("clear")
            if result.get("success"):
                return "Pressed Clear"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "send_tab":
            result = send_terminal_key("tab")
            if result.get("success"):
                return "Pressed Tab"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "query_knowledge_base":
            if rag_engine is None:
                return "RAG engine not available"
            query = arguments.get("query", "")
            n_results = arguments.get("n_results", 3)
            import asyncio
            # Run async query in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, use await directly won't work here
                    # Return a message indicating async usage needed
                    return "[Use async version for RAG queries in async context]"
                results = loop.run_until_complete(rag_engine.query_simple(query, n_results))
            except RuntimeError:
                # No event loop, create one
                results = asyncio.run(rag_engine.query_simple(query, n_results))

            if not results:
                return f"No results found for: {query}"

            output = f"Knowledge base results for '{query}':\n\n"
            for i, r in enumerate(results, 1):
                content = r.get("content", "")[:500]  # Truncate
                output += f"[{i}] {content}\n\n"
            return output

        elif name == "capture_screen":
            result = capture_screen()
            if result.get("success"):
                return f"Screen captured: {result.get('file')}"
            return f"Error: {result.get('error', 'Unknown error')}"

        elif name == "get_connection_status":
            status = get_connection_status()
            if status["connected"]:
                return f"Connected to {status['target']} (BIRP: {status['birp_available']})"
            return f"Not connected (BIRP available: {status['birp_available']})"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error ({name}): {str(e)}"


async def execute_tool_async(name: str, arguments: dict, rag_engine=None) -> str:
    """Async version of execute_tool for use in async contexts.

    Args:
        name: Tool name from TOOL_DEFINITIONS
        arguments: Tool arguments as a dict
        rag_engine: Optional RAG engine instance for query_knowledge_base

    Returns:
        String result of tool execution
    """
    # Most tools are sync, only RAG query needs special handling
    if name == "query_knowledge_base" and rag_engine is not None:
        query = arguments.get("query", "")
        n_results = arguments.get("n_results", 3)
        results = await rag_engine.query_simple(query, n_results)

        if not results:
            return f"No results found for: {query}"

        output = f"Knowledge base results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
            content = r.get("content", "")[:500]
            output += f"[{i}] {content}\n\n"
        return output

    # All other tools are sync
    return execute_tool(name, arguments, rag_engine)
