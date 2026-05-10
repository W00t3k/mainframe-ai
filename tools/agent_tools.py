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

# TN3270 emulator - uses py3270 library
TN3270_AVAILABLE = False
Emulator = None

try:
    from py3270 import Emulator
    TN3270_AVAILABLE = True
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
    """Convert ReadBuffer(Ascii) output to a printable screen.
    
    ReadBuffer(Ascii) returns hex-encoded bytes with field markers like SF(c0=c8).
    We need to decode the hex bytes to get the actual text.
    """
    import re
    
    lines = normalize_screen_buffer(buffer)
    if not lines:
        return ""
    
    raw_text = "\n".join(lines)
    
    # Remove field markers like SF(c0=c8), SF(c0=c0), etc.
    text = re.sub(r'SF\([^)]*\)', ' ', raw_text)
    
    # Try to decode hex sequences (e.g., "49 4b 4a" -> "IKJ")
    def decode_hex_line(line):
        # Check if line looks like hex data (space-separated hex bytes)
        parts = line.split()
        if all(len(p) == 2 and all(c in '0123456789abcdefABCDEF' for c in p) for p in parts if p):
            try:
                # ReadBuffer(Ascii) returns ASCII hex, not EBCDIC
                decoded = bytes.fromhex(''.join(parts)).decode('ascii', errors='replace')
                # Filter out nulls and unprintable chars, replace with space
                return ''.join(c if (c.isprintable() and ord(c) >= 32) else ' ' for c in decoded)
            except Exception:
                pass
        return line
    
    # Process each line
    result_lines = []
    for line in text.split('\n'):
        decoded = decode_hex_line(line.strip())
        if decoded.strip():  # Skip empty lines
            result_lines.append(decoded)
    
    # If we got meaningful text, return it
    if result_lines:
        # Format as 80-column screen
        final_text = '\n'.join(result_lines)
        # Clean up multiple spaces but preserve structure
        final_text = re.sub(r'  +', '  ', final_text)
        return final_text
    
    return raw_text


# =============================================================================
# Emulator Command Execution
# =============================================================================

def exec_emulator_command(command: bytes, timeout: float = 5):
    """Execute emulator command with timeout to prevent hanging on non-input screens.

    On timeout: kills s3270 (unavoidable — it's blocked on readline) but then
    automatically reconnects so the next call works instead of leaving everything dead.
    """
    em = connection.emulator
    if not em:
        return None

    result_box = [None]
    exc_box = [None]

    def _run():
        try:
            with connection.command_lock:
                result_box[0] = em.exec_command(command)
        except BrokenPipeError:
            exc_box[0] = "broken_pipe"
        except OSError:
            exc_box[0] = "os_error"
        except Exception as e:
            exc_box[0] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        # Command hung — must kill s3270 to unblock readline()
        _host = connection.host
        _port = connection.port
        try:
            em.app.sp.kill()
        except Exception:
            pass
        connection.connected = False
        connection.emulator = None
        # Auto-reconnect so next call works
        if _host:
            _auto_reconnect(_host, _port)
        return None

    if exc_box[0] in ("broken_pipe", "os_error"):
        _host = connection.host
        _port = connection.port
        connection.connected = False
        connection.emulator = None
        if _host:
            _auto_reconnect(_host, _port)
        return None

    return result_box[0]


def _auto_reconnect(host: str, port: int):
    """Silently reconnect after s3270 crash. No VTAM wait, just raw TCP."""
    import time as _time
    try:
        connection.emulator = Emulator(visible=False)
        connection.emulator.connect(f"{host}:{port}")
        connection.host = host
        connection.port = port
        connection.connected = True
        _time.sleep(1)
    except Exception:
        connection.connected = False
        connection.emulator = None


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

    if not TN3270_AVAILABLE:
        return False, "py3270 not available. Install with: pip install py3270"

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

        connection.emulator = Emulator(visible=False)
        connection.emulator.connect(f"{host}:{port}")

        connection.host = host
        connection.port = port
        connection.connected = True

        import time as _time
        _time.sleep(2)

        # Read initial screen
        try:
            read_screen()
        except Exception:
            pass

        screen = connection.current_screen or ""

        # If VTAM hasn't claimed the device yet (Hercules banner / connection rejected),
        # return failure so the frontend retries rather than displaying garbage.
        if "Connection rejected" in screen or "no available 3270" in screen:
            try:
                connection.emulator.terminate()
            except Exception:
                pass
            connection.connected = False
            connection.emulator = None
            return False, f"VTAM not ready — device not claimed yet"

        # If we see the TK5 splash (Hercules version banner, no LOGON ==>),
        # send Enter to trigger SNASOL handoff — with timeout in case kbd locked
        import threading as _thr
        if "LOGON ===>" not in screen and "HHC" in screen:
            def _dismiss():
                try:
                    connection.emulator.exec_command(b'Enter()')
                except Exception:
                    pass
            t = _thr.Thread(target=_dismiss, daemon=True)
            t.start()
            t.join(5)
            _time.sleep(2)
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

    Thread-safe: acquires command_lock to prevent concurrent s3270 access
    with exec_emulator_command. Returns cached screen if lock is busy.

    Returns:
        Screen text or error message
    """
    global connection

    if not connection.connected or not connection.emulator:
        return "[Not connected]"

    # Try to acquire lock — return cached data if busy (keeps UI responsive)
    acquired = connection.command_lock.acquire(timeout=2)
    if not acquired:
        return connection.current_screen or "[Screen busy]"

    try:
        em = connection.emulator
        if not em:
            return "[Not connected]"
        # Use py3270's string_get to read entire screen as plain text
        # string_get(ypos, xpos, length) - 1-indexed
        lines = []
        for row in range(1, 25):  # 24 rows, 1-indexed
            try:
                line = em.string_get(row, 1, 80)
                lines.append(line.rstrip() if line else '')
            except Exception:
                lines.append('')

        screen_text = '\n'.join(lines)
        connection.current_screen = screen_text
        return connection.current_screen
    except Exception as e:
        return connection.current_screen or f"[Screen unavailable: {e}]"
    finally:
        connection.command_lock.release()


def read_screen_with_color() -> str:
    """Read current 3270 screen with color styling.
    
    Returns HTML with color spans for proper 3270 rendering.
    Uses heuristic-based coloring since py3270 doesn't expose extended attributes.
    """
    global connection
    
    if not connection.connected or not connection.emulator:
        return "[Not connected]"
    
    try:
        # Get plain text screen
        screen_text = read_screen()
        if not screen_text or screen_text.startswith("["):
            return screen_text
        
        return colorize_3270_screen(screen_text)
    except Exception:
        return read_screen()


def colorize_3270_screen(screen_text: str) -> str:
    """Apply 3270-style coloring to screen text using heuristics.
    
    Standard 3270 color conventions:
    - Blue/Turquoise: Labels, titles, protected fields
    - Green: Input fields, general text
    - Red: Error messages, warnings
    - Yellow: Intensified/highlighted text
    - White: High-intensity fields
    - Pink: Special status
    """
    import html
    import re
    
    lines = screen_text.split('\n')
    result_lines = []
    
    # Patterns for different colors
    error_patterns = [
        r'ERROR', r'INVALID', r'FAILED', r'DENIED', r'NOT AUTHORIZED',
        r'ABEND', r'IKJ\d+E', r'IEF\d+E', r'IEC\d+E', r'IGD\d+E',
        r'NOT FOUND', r'REJECTED', r'VIOLATION'
    ]
    warning_patterns = [
        r'WARNING', r'CAUTION', r'IKJ\d+W', r'IEF\d+W'
    ]
    info_patterns = [
        r'IKJ\d+I', r'IEF\d+I', r'IGD\d+I', r'READY', r'LOGON', r'LOGOFF'
    ]
    title_patterns = [
        r'^[\s]*[A-Z][A-Z0-9\s\-]{10,}[\s]*$',  # All-caps titles
        r'={5,}', r'-{5,}', r'\*{5,}',  # Separators
        r'MENU', r'OPTION', r'COMMAND', r'ENTER', r'PF\d+',
        r'ISPF', r'TSO', r'SDSF', r'VTAM', r'CICS', r'KICKS', r'JCL'
    ]
    
    for line in lines:
        if not line.strip():
            result_lines.append('')
            continue
        
        escaped = html.escape(line)
        
        # Check for errors (red)
        if any(re.search(p, line, re.IGNORECASE) for p in error_patterns):
            result_lines.append(f'<span class="c3270-red">{escaped}</span>')
        # Check for warnings (yellow)
        elif any(re.search(p, line, re.IGNORECASE) for p in warning_patterns):
            result_lines.append(f'<span class="c3270-yellow">{escaped}</span>')
        # Check for info messages (turquoise)
        elif any(re.search(p, line, re.IGNORECASE) for p in info_patterns):
            result_lines.append(f'<span class="c3270-turquoise">{escaped}</span>')
        # Check for titles/headers (blue + bold)
        elif any(re.search(p, line) for p in title_patterns):
            result_lines.append(f'<span class="c3270-blue c3270-intensified">{escaped}</span>')
        # Check for input prompts (white for labels, green for input area)
        elif re.search(r'[=:]\s*$', line) or re.search(r'^[\s]*[A-Z][A-Za-z\s]+[=:]', line):
            # Colorize label vs input area
            match = re.match(r'^(.*?[=:]\s*)(.*?)$', escaped)
            if match and match.group(2).strip():
                result_lines.append(
                    f'<span class="c3270-turquoise">{match.group(1)}</span>'
                    f'<span class="c3270-green">{match.group(2)}</span>'
                )
            else:
                result_lines.append(f'<span class="c3270-turquoise">{escaped}</span>')
        # Version info, credits (cyan)
        elif re.search(r'Version|Copyright|Created|Update|\d+\.\d+\.\d+', line, re.IGNORECASE):
            result_lines.append(f'<span class="c3270-turquoise">{escaped}</span>')
        # Default: green
        else:
            result_lines.append(f'<span class="c3270-green">{escaped}</span>')
    
    return '\n'.join(result_lines)


def get_screen_data() -> dict:
    """Get screen data for web terminal."""
    global connection

    if not connection.connected or not connection.emulator:
        return {
            "connected": False,
            "screen": "",
            "screen_html": "",
            "rows": 24,
            "cols": 80,
            "cursor_row": 0,
            "cursor_col": 0
        }

    return get_cached_screen_data()


def get_cached_screen_data() -> dict:
    """Return cached screen data without hitting the emulator."""
    screen_html = ""
    if connection.current_screen:
        screen_html = colorize_3270_screen(connection.current_screen)

    return {
        "connected": connection.connected,
        "screen": connection.current_screen,
        "screen_html": screen_html,
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
        # Send the key
        if key_type == "string":
            if value:
                exec_emulator_command(f'String("{value}")'.encode())
            # String input: return immediately, no post-wait needed
            return {"success": True, "screen_data": get_cached_screen_data()}
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

        # Wait(1,Unlock): returns immediately if keyboard already unlocked,
        # waits at most 1s otherwise. Never hangs.
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
            connection.poller_stop.wait(3.0)

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENCAPS_DIR = os.path.join(BASE_DIR, "data", "screencaps")
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
        "tn3270_available": TN3270_AVAILABLE
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
                return f"Connected to {status['target']}"
            return f"Not connected (TN3270 available: {status['tn3270_available']})"

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
