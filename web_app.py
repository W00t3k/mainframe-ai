#!/usr/bin/env python3
"""
Mainframe AI Assistant - Web Application
FastAPI backend with chat interface and TN3270 connectivity
Uses LOCAL LLM via Ollama (no API key required!)
"""

import os
import sys
import json
import re
import asyncio
import httpx
import ipaddress
import threading
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Import RAG engine
try:
    from rag_engine import get_rag_engine, initialize_builtin_knowledge
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"RAG import error: {e}")
    RAG_AVAILABLE = False

# BIRP modules are now local
BIRP_AVAILABLE = False
try:
    from birpv2_modules.emulator.wrapper import WrappedEmulator
    from birpv2_modules.core.models import Screen
    BIRP_AVAILABLE = True
except ImportError as e:
    print(f"BIRP import error: {e}")
    # Fallback: try from original location
    BIRP_PATH = os.path.expanduser("~/Desktop/STuFF /birp")
    if os.path.exists(BIRP_PATH):
        sys.path.insert(0, BIRP_PATH)
        try:
            from birpv2_modules.emulator.wrapper import WrappedEmulator
            from birpv2_modules.core.models import Screen
            BIRP_AVAILABLE = True
        except ImportError:
            pass

# Initialize FastAPI
app = FastAPI(title="Mainframe AI Assistant")

# Mount static files and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Ollama configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

SYSTEM_PROMPT = """You are an expert mainframe systems programmer and z/OS administrator assistant.

## Your Capabilities
- Explain z/OS concepts, JCL, COBOL, REXX, CLIST, Assembler
- Help navigate TSO/ISPF, CICS, JES2/JES3
- Interpret ABEND codes and system messages
- Generate JCL for common tasks
- Explain screen output from 3270 terminals
- Assist with RACF security, SMS, catalog management
- Debug batch jobs and analyze SYSOUT

## When Connected to a Mainframe
You can see the current 3270 screen content. Analyze it and help the user navigate.
Suggest what keys to press (Enter, PF3, PF1, etc.) or what to type.

## Response Guidelines
- Be concise but thorough
- For JCL/code, always explain key parameters
- Warn about potentially destructive operations
- Use markdown formatting

## Common ABEND Codes
- S0C1: Operation exception
- S0C4: Protection exception
- S0C7: Data exception (invalid packed decimal)
- S0CB: Division by zero
- S222: Job cancelled
- S322: CPU time exceeded
- S806: Module not found
- S913: RACF authorization failure
- SB37: Dataset out of space"""


@dataclass
class ConnectionState:
    """Global connection state"""
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


# Global state
connection = ConnectionState()
conversation_history = []
websocket_clients = set()
screencaps = []  # Store captured screens

# Screencaps storage directory
SCREENCAPS_DIR = os.path.join(BASE_DIR, "screencaps")
os.makedirs(SCREENCAPS_DIR, exist_ok=True)


async def check_ollama() -> bool:
    """Check if Ollama is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            return response.status_code == 200
    except:
        return False


async def chat_with_ollama(messages: list) -> str:
    """Send messages to Ollama and get response"""
    try:
        # Format messages for Ollama
        prompt = SYSTEM_PROMPT + "\n\n"
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"User: {content}\n\n"
            else:
                prompt += f"Assistant: {content}\n\n"
        prompt += "Assistant: "

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2048,
                    }
                },
                timeout=120.0
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


def connect_mainframe(target: str) -> tuple[bool, str]:
    """Connect to mainframe via TN3270"""
    global connection

    if not BIRP_AVAILABLE:
        return False, "BIRP modules not available. Install from ~/Desktop/STuFF /birp/"

    try:
        if ":" in target:
            host, port = target.rsplit(":", 1)
            port = int(port)
        else:
            host = target
            port = 23

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
    """Disconnect from mainframe"""
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


def read_screen() -> str:
    """Read current 3270 screen"""
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
    """Get screen data for web terminal"""
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


def exec_emulator_command(command: bytes, timeout: float = 3):
    """Execute emulator command serialized to avoid s3270 desync."""
    em = connection.emulator
    if not em:
        return None
    with connection.command_lock:
        return em.exec_command(command)


def start_screen_poller():
    """Start background screen polling to avoid blocking requests."""
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


def send_terminal_key(key_type: str, value: str = "") -> dict:
    """Send a key to the terminal"""
    global connection

    if not connection.connected or not connection.emulator:
        return {"success": False, "error": "Not connected"}

    try:
        try:
            exec_emulator_command(b'Wait(1,Unlock)')
        except Exception:
            try:
                exec_emulator_command(b'Reset()')
            except Exception:
                pass
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


async def broadcast_screen():
    """Broadcast screen update to all WebSocket clients"""
    if not websocket_clients:
        return

    screen_data = get_cached_screen_data()
    message = json.dumps({"type": "screen_update", "data": screen_data})

    disconnected = set()
    for ws in websocket_clients:
        try:
            await ws.send_text(message)
        except:
            disconnected.add(ws)

    websocket_clients.difference_update(disconnected)


async def process_chat(user_message: str) -> dict:
    """Process a chat message and return response"""
    global conversation_history, OLLAMA_MODEL

    result = {
        "response": "",
        "connected": connection.connected,
        "host": f"{connection.host}:{connection.port}" if connection.connected else "",
        "screen": connection.current_screen if connection.connected else None,
        "model": OLLAMA_MODEL
    }

    # Handle commands
    if user_message.startswith("/"):
        parts = user_message.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/connect":
            if not args:
                result["response"] = "Usage: `/connect host:port`\n\nExample: `/connect localhost:3270`"
            else:
                success, message = connect_mainframe(args)
                result["response"] = message
                result["connected"] = connection.connected
                result["host"] = f"{connection.host}:{connection.port}" if connection.connected else ""
                result["screen"] = connection.current_screen
                # Notify WebSocket clients
                await broadcast_screen()

        elif cmd == "/disconnect":
            result["response"] = disconnect_mainframe()
            result["connected"] = False
            result["screen"] = None
            await broadcast_screen()

        elif cmd == "/screen":
            if connection.connected:
                screen = read_screen()
                result["response"] = f"**Current Screen:**\n```\n{screen}\n```"
                result["screen"] = screen
            else:
                result["response"] = "Not connected. Use `/connect host:port` first."

        elif cmd == "/clear":
            conversation_history = []
            result["response"] = "Conversation cleared."

        elif cmd == "/model":
            if args:
                OLLAMA_MODEL = args
                result["response"] = f"Model changed to: `{args}`"
            else:
                result["response"] = f"Current model: `{OLLAMA_MODEL}`\n\nUsage: `/model llama3.1:8b`"

        elif cmd == "/help":
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
            result["response"] = f"Unknown command: `{cmd}`. Type `/help` for available commands."

        return result

    # Check if Ollama is running
    if not await check_ollama():
        result["response"] = """⚠️ **Ollama is not running!**

Start Ollama with:
```bash
ollama serve
```

Or install it:
```bash
brew install ollama
ollama pull llama3.1:8b
ollama serve
```"""
        return result

    # Regular chat - send to Ollama
    context = ""

    # Query RAG for relevant knowledge
    rag_context = ""
    if RAG_AVAILABLE:
        try:
            engine = get_rag_engine()
            rag_results = await engine.query_simple(user_message, n_results=2)
            if rag_results:
                rag_context = "\n\n[Relevant Knowledge Base Information]\n"
                for r in rag_results:
                    rag_context += f"---\n{r['content']}\n"
        except Exception as e:
            print(f"RAG query error: {e}")

    if connection.connected:
        screen = read_screen()
        result["screen"] = screen
        # Always include screen context when connected
        context = f"\n\n[Current 3270 Screen]\n```\n{screen}\n```"

    full_message = user_message + rag_context + context

    conversation_history.append({
        "role": "user",
        "content": full_message
    })

    # Call Ollama
    assistant_message = await chat_with_ollama(conversation_history)

    conversation_history.append({
        "role": "assistant",
        "content": assistant_message
    })

    result["response"] = assistant_message
    return result


# API Models
class ChatRequest(BaseModel):
    message: str


class TerminalKeyRequest(BaseModel):
    key_type: str
    value: str = ""


# Routes
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse("chat.html", {"request": request, "embed": embed})


@app.get("/connect", response_class=HTMLResponse)
async def connect_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    return templates.TemplateResponse("terminal.html", {"request": request})


@app.get("/scanner", response_class=HTMLResponse)
async def scanner_page(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})


@app.get("/screencaps", response_class=HTMLResponse)
async def screencaps_page(request: Request):
    return templates.TemplateResponse("screencaps.html", {"request": request})


@app.get("/rag", response_class=HTMLResponse)
async def rag_page(request: Request):
    return templates.TemplateResponse("rag.html", {"request": request})

@app.get("/architecture", response_class=HTMLResponse)
async def architecture_page(request: Request):
    return templates.TemplateResponse("architecture.html", {"request": request})


@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    result = await process_chat(request.message)
    return JSONResponse(result)


@app.get("/api/status")
async def api_status():
    ollama_ok = await check_ollama()
    return JSONResponse({
        "connected": connection.connected,
        "host": f"{connection.host}:{connection.port}" if connection.connected else "",
        "screen": connection.current_screen if connection.connected else None,
        "birp_available": BIRP_AVAILABLE,
        "ollama_running": ollama_ok,
        "model": OLLAMA_MODEL
    })


@app.get("/api/screen")
async def api_screen():
    return JSONResponse(get_cached_screen_data())


@app.post("/api/terminal/key")
async def api_terminal_key(request: TerminalKeyRequest):
    result = send_terminal_key(request.key_type, request.value)
    if result.get("success"):
        await broadcast_screen()
    return JSONResponse(result)


@app.post("/api/terminal/connect")
async def api_terminal_connect(request: Request):
    data = await request.json()
    target = data.get("target", "localhost:3270")
    success, message = connect_mainframe(target)
    if success:
        await broadcast_screen()
    return JSONResponse({
        "success": success,
        "message": message,
        "screen_data": get_screen_data() if success else None
    })


@app.post("/api/terminal/disconnect")
async def api_terminal_disconnect():
    message = disconnect_mainframe()
    await broadcast_screen()
    return JSONResponse({"success": True, "message": message})


def parse_scan_targets(target: str, max_hosts: int = 256) -> list[str]:
    """Expand target string into a list of hosts."""
    hosts: list[str] = []
    for token in target.split(","):
        token = token.strip()
        if not token:
            continue
        if token.lower() == "localhost":
            hosts.append("localhost")
            continue
        if "/" in token:
            try:
                network = ipaddress.ip_network(token, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid CIDR target: {token}") from exc
            if network.num_addresses <= 2:
                hosts.append(str(network.network_address))
            else:
                hosts.extend(str(ip) for ip in network.hosts())
        else:
            hosts.append(token)

    deduped = []
    seen = set()
    for host in hosts:
        if host not in seen:
            deduped.append(host)
            seen.add(host)

    if len(deduped) > max_hosts:
        raise ValueError(f"Target expands to {len(deduped)} hosts (max {max_hosts}).")
    return deduped


def parse_scan_ports(ports: str, max_ports: int = 32) -> list[int]:
    """Parse comma-separated port list, allowing ranges like 20-25."""
    if not ports:
        return [23, 3270, 2323]

    parsed: list[int] = []
    for part in ports.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError as exc:
                raise ValueError(f"Invalid port range: {part}") from exc
            if start > end:
                start, end = end, start
            parsed.extend(range(start, end + 1))
        else:
            try:
                parsed.append(int(part))
            except ValueError as exc:
                raise ValueError(f"Invalid port: {part}") from exc

    parsed = [p for p in parsed if 1 <= p <= 65535]
    parsed = sorted(set(parsed))

    if len(parsed) > max_ports:
        raise ValueError(f"Too many ports ({len(parsed)}). Limit to {max_ports}.")
    return parsed


async def check_tcp_port(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()
        return True
    except Exception:
        return False


@app.post("/api/scanner/scan")
async def api_scanner_scan(request: Request):
    data = await request.json()
    target = (data.get("target") or "").strip()
    ports_input = (data.get("ports") or "").strip()

    if not target:
        return JSONResponse({"error": "Target is required"}, status_code=400)

    try:
        targets = parse_scan_targets(target)
        ports = parse_scan_ports(ports_input)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    results = []
    semaphore = asyncio.Semaphore(128)

    async def scan_host_port(host: str, port: int):
        async with semaphore:
            if await check_tcp_port(host, port):
                service = "TN3270" if port in (23, 3270, 2323) else "TCP"
                results.append({
                    "host": host,
                    "port": port,
                    "type": service,
                    "details": "Open port detected"
                })

    tasks = [scan_host_port(host, port) for host in targets for port in ports]
    if tasks:
        await asyncio.gather(*tasks)

    results.sort(key=lambda item: (item["host"], item["port"]))
    return JSONResponse({"results": results})


# Screencap API
@app.post("/api/screencap")
async def api_capture_screen(request: Request):
    """Capture and save current screen"""
    global screencaps

    if not connection.connected:
        return JSONResponse({"success": False, "error": "Not connected"})

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

    return JSONResponse({"success": True, "screencap": cap, "file": filename})


@app.get("/api/screencaps")
async def api_get_screencaps():
    """Get all captured screens"""
    # Also load from files if screencaps list is empty but files exist
    if not screencaps:
        load_screencaps_from_disk()
    return JSONResponse({"captures": screencaps})


@app.get("/api/screencap/{cap_id}")
async def api_get_screencap(cap_id: str):
    """Get a specific screencap"""
    for cap in screencaps:
        if cap["id"] == cap_id:
            return JSONResponse(cap)
    return JSONResponse({"error": "Screencap not found"}, status_code=404)


@app.delete("/api/screencap/{cap_id}")
async def api_delete_screencap(cap_id: str):
    """Delete a screencap"""
    global screencaps
    for i, cap in enumerate(screencaps):
        if cap["id"] == cap_id:
            screencaps.pop(i)
            # Also delete file
            filename = f"screencap_{cap_id}.txt"
            filepath = os.path.join(SCREENCAPS_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            return JSONResponse({"success": True})
    return JSONResponse({"error": "Screencap not found"}, status_code=404)


def load_screencaps_from_disk():
    """Load screencaps from saved files"""
    global screencaps
    if not os.path.exists(SCREENCAPS_DIR):
        return

    for filename in os.listdir(SCREENCAPS_DIR):
        if filename.startswith("screencap_") and filename.endswith(".txt"):
            filepath = os.path.join(SCREENCAPS_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    lines = f.readlines()
                    host = lines[0].replace("Host: ", "").strip() if lines else "unknown"
                    time_str = lines[1].replace("Time: ", "").strip() if len(lines) > 1 else ""
                    screen = "".join(lines[3:]) if len(lines) > 3 else ""

                    cap_id = filename.replace("screencap_", "").replace(".txt", "")

                    # Parse time to epoch
                    try:
                        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        epoch = int(dt.timestamp())
                    except:
                        epoch = int(os.path.getmtime(filepath))

                    cap = {
                        "id": cap_id,
                        "screen": screen,
                        "host": host,
                        "timestamp": epoch,
                        "time": time_str
                    }
                    screencaps.append(cap)
            except Exception as e:
                print(f"Error loading screencap {filename}: {e}")


# RAG API Endpoints
@app.get("/api/rag/stats")
async def api_rag_stats():
    """Get RAG system statistics"""
    if not RAG_AVAILABLE:
        return JSONResponse({"error": "RAG not available", "documents": 0, "chunks": 0})
    engine = get_rag_engine()
    return JSONResponse(engine.get_stats())


@app.get("/api/rag/documents")
async def api_rag_documents():
    """Get list of indexed documents"""
    if not RAG_AVAILABLE:
        return JSONResponse({"documents": []})
    engine = get_rag_engine()
    return JSONResponse({"documents": engine.get_documents()})


@app.post("/api/rag/init")
async def api_rag_init():
    """Initialize built-in knowledge"""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})
    result = await initialize_builtin_knowledge()
    return JSONResponse(result)


@app.post("/api/rag/upload")
async def api_rag_upload(file: UploadFile = File(...)):
    """Upload and index a document"""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})

    engine = get_rag_engine()

    # Save file temporarily
    temp_path = os.path.join(BASE_DIR, "rag_data", "documents", file.filename)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    # Process based on file type
    if file.filename.lower().endswith(".pdf"):
        result = await engine.add_pdf(temp_path, file.filename)
    else:
        result = await engine.add_text_file(temp_path, file.filename)

    return JSONResponse(result)


@app.delete("/api/rag/document/{doc_id}")
async def api_rag_delete(doc_id: str):
    """Delete a document from RAG"""
    if not RAG_AVAILABLE:
        return JSONResponse({"success": False, "error": "RAG not available"})
    engine = get_rag_engine()
    return JSONResponse(engine.delete_document(doc_id))


@app.post("/api/rag/query")
async def api_rag_query(request: Request):
    """Query the RAG system with enhanced results"""
    if not RAG_AVAILABLE:
        return JSONResponse({"results": [], "query_time_ms": 0, "total_chunks": 0, "cache_hit": False})

    data = await request.json()
    query = data.get("query", "")
    n_results = data.get("n_results", 3)
    include_highlights = data.get("include_highlights", True)

    if not query:
        return JSONResponse({"results": [], "query_time_ms": 0, "total_chunks": 0, "cache_hit": False})

    engine = get_rag_engine()
    response = await engine.query(query, n_results, include_highlights)
    return JSONResponse(response)


@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)

    try:
        # Send initial screen state
        screen_data = get_screen_data()
        await websocket.send_text(json.dumps({
            "type": "screen_update",
            "data": screen_data
        }))

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg["type"] == "key":
                result = send_terminal_key(msg["key_type"], msg.get("value", ""))
                await websocket.send_text(json.dumps({
                    "type": "key_result",
                    "data": result
                }))
                # Broadcast to all clients
                await broadcast_screen()

            elif msg["type"] == "connect":
                success, message = connect_mainframe(msg.get("target", "localhost:3270"))
                await websocket.send_text(json.dumps({
                    "type": "connect_result",
                    "success": success,
                    "message": message
                }))
                await broadcast_screen()

            elif msg["type"] == "disconnect":
                message = disconnect_mainframe()
                await websocket.send_text(json.dumps({
                    "type": "disconnect_result",
                    "message": message
                }))
                await broadcast_screen()

            elif msg["type"] == "refresh":
                screen_data = get_screen_data()
                await websocket.send_text(json.dumps({
                    "type": "screen_update",
                    "data": screen_data
                }))

    except WebSocketDisconnect:
        websocket_clients.discard(websocket)
    except Exception as e:
        websocket_clients.discard(websocket)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Mainframe AI Assistant Web App")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model to use")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    global OLLAMA_MODEL
    OLLAMA_MODEL = args.model

    print(f"""
╔══════════════════════════════════════════════════════════╗
║       Mainframe AI Assistant - LOCAL LLM Edition         ║
╠══════════════════════════════════════════════════════════╣
║  Landing Page:  http://{args.host}:{args.port}/                    ║
║  Chat:          http://{args.host}:{args.port}/chat                ║
╠══════════════════════════════════════════════════════════╣
║  LLM Backend:   Ollama ({OLLAMA_MODEL})             ║
║  BIRP Available: {str(BIRP_AVAILABLE):<39} ║
╠══════════════════════════════════════════════════════════╣
║  No API key required! Runs 100% locally.                 ║
║  Web Terminal: Type in browser, no shell needed!         ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "web_app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
