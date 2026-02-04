#!/usr/bin/env python3
"""
Mainframe AI Assistant - Web Application
FastAPI backend with chat interface and TN3270 connectivity
Uses LOCAL LLM via Ollama (no API key required!)

Enhanced with:
- Agentic tool-calling loop
- Trust Graph for mainframe relationship mapping
- Real-time graph visualization via WebSocket
"""

import os
import sys
import json
import re
import asyncio
import httpx
import ipaddress
import threading
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from datetime import datetime

from contextlib import asynccontextmanager
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

# Import agent tools (connection management, tool definitions)
try:
    from agent_tools import (
        connection, BIRP_AVAILABLE, TOOL_DEFINITIONS,
        connect_mainframe, disconnect_mainframe, read_screen,
        send_terminal_key, get_screen_data, get_cached_screen_data,
        capture_screen, get_connection_status, execute_tool_async,
        set_screen_update_callback, screencaps, SCREENCAPS_DIR
    )
    AGENT_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"Agent tools import error: {e}")
    AGENT_TOOLS_AVAILABLE = False
    BIRP_AVAILABLE = False

# Import trust graph
try:
    from trust_graph import get_trust_graph, TrustGraph
    from graph_tools import (
        classify_panel, extract_identifiers, parse_jcl, parse_sysout,
        update_graph_from_jcl, update_graph_from_sysout, update_graph_from_screen,
        generate_finding, ScreenMapperAgent, BatchTrustAgent, CICSRelationshipAgent
    )
    GRAPH_AVAILABLE = True
except ImportError as e:
    print(f"Trust graph import error: {e}")
    GRAPH_AVAILABLE = False

# Import recon engine
try:
    from recon_engine import (
        TSOEnumerator, CICSEnumerator, VTAMEnumerator,
        HiddenFieldDetector, ScreenAnalyzer, ApplicationMapper,
        generate_report as generate_recon_report,
    )
    RECON_AVAILABLE = True
except ImportError as e:
    print(f"Recon engine import error: {e}")
    RECON_AVAILABLE = False

# Active enumerator/mapper references for stop support
_active_enumerator = None
_active_mapper = None

@asynccontextmanager
async def lifespan(application):
    """Startup: seed trust graph with demo data if empty."""
    if GRAPH_AVAILABLE:
        try:
            graph = get_trust_graph()
            if not graph.nodes:
                for loader, key in [
                    (lambda t: update_graph_from_jcl(graph, parse_jcl(t), {"type": "demo", "source": "sample_jcl"}),
                     "sample_jcl.txt"),
                    (lambda t: update_graph_from_sysout(graph, parse_sysout(t), {"type": "demo", "source": "sample_sysout"}),
                     "sample_sysout.txt"),
                    (lambda t: update_graph_from_screen(graph, t, "demo:3270"),
                     "sample_screen.txt"),
                ]:
                    fpath = os.path.join(DEMO_DATA_DIR, key)
                    if os.path.exists(fpath):
                        with open(fpath, "r") as f:
                            loader(f.read())
                graph.save()
                print("Trust graph seeded with demo data.")
        except Exception as e:
            print(f"Trust graph seed skipped: {e}")
    yield


# Initialize FastAPI
app = FastAPI(title="Mainframe AI Assistant", lifespan=lifespan)

# Mount static files and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
LAB_DATA_DIR = os.path.join(BASE_DIR, "lab_data")
DEMO_DATA_DIR = os.path.join(BASE_DIR, "docs", "demo")

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


# Global state (connection imported from agent_tools)
conversation_history = []
websocket_clients = set()
graph_websocket_clients = set()  # For real-time graph visualization

# Note: screencaps and SCREENCAPS_DIR imported from agent_tools


def read_json_file(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"Failed to read JSON {path}: {exc}")
        return default


def read_text_file(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r") as handle:
        return handle.read()


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


async def agentic_chat(messages: list, max_iterations: int = 10) -> dict:
    """
    Agentic chat loop using Ollama /api/chat with tool calling.
    The LLM can invoke tools and observe results before responding.

    Returns:
        {
            "response": str,
            "agent_steps": list of {tool, arguments, result},
            "iterations": int
        }
    """
    if not AGENT_TOOLS_AVAILABLE:
        # Fall back to basic chat
        response = await chat_with_ollama(messages)
        return {"response": response, "agent_steps": [], "iterations": 0}

    # Build system message with tools context
    system_message = SYSTEM_PROMPT + """

## Available Tools
You can use these tools to interact with the mainframe:
- connect_mainframe: Connect to a mainframe via TN3270
- disconnect_mainframe: Disconnect from mainframe
- read_screen: Read the current 3270 screen
- send_text: Type text on the terminal
- send_enter: Press Enter key
- send_pf_key: Press a PF key (1-24)
- send_clear: Press Clear key
- send_tab: Press Tab key
- query_knowledge_base: Search the knowledge base
- capture_screen: Save a screen capture
- get_connection_status: Check connection status

When you need information from the mainframe, use the appropriate tool.
After using tools, provide your analysis and recommendations."""

    # Format messages for Ollama /api/chat
    chat_messages = [{"role": "system", "content": system_message}]
    for msg in messages:
        chat_messages.append({"role": msg["role"], "content": msg["content"]})

    agent_steps = []
    iterations = 0

    try:
        async with httpx.AsyncClient() as client:
            while iterations < max_iterations:
                iterations += 1

                # Call Ollama with tools
                response = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": chat_messages,
                        "tools": TOOL_DEFINITIONS,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 2048,
                        }
                    },
                    timeout=120.0
                )

                if response.status_code != 200:
                    return {
                        "response": f"Ollama error: {response.status_code}",
                        "agent_steps": agent_steps,
                        "iterations": iterations
                    }

                data = response.json()
                message = data.get("message", {})

                # Check for tool calls
                tool_calls = message.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls - return the response
                    return {
                        "response": message.get("content", "No response generated."),
                        "agent_steps": agent_steps,
                        "iterations": iterations
                    }

                # Execute tool calls
                chat_messages.append(message)  # Add assistant message with tool calls

                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name", "")
                    tool_args = tool_call.get("function", {}).get("arguments", {})

                    # Execute the tool
                    tool_result = await execute_tool_async(tool_name, tool_args)

                    step = {
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": tool_result
                    }
                    agent_steps.append(step)

                    # Add tool result to messages
                    chat_messages.append({
                        "role": "tool",
                        "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                    })

                    # Broadcast screen updates if terminal state changed
                    if tool_name in ["connect_mainframe", "send_text", "send_enter",
                                     "send_pf_key", "send_clear", "send_tab", "read_screen"]:
                        await broadcast_screen()

            # Max iterations reached
            return {
                "response": "Maximum iterations reached. The agent may need more steps to complete the task.",
                "agent_steps": agent_steps,
                "iterations": iterations
            }

    except httpx.TimeoutException:
        return {
            "response": "Request timed out. The model may be loading - please try again.",
            "agent_steps": agent_steps,
            "iterations": iterations
        }
    except Exception as e:
        return {
            "response": f"Error in agentic chat: {str(e)}",
            "agent_steps": agent_steps,
            "iterations": iterations
        }


# Note: connect_mainframe, disconnect_mainframe, read_screen, send_terminal_key,
# get_screen_data, get_cached_screen_data are all imported from agent_tools.py


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

    # Cap history to prevent unbounded growth during long demo sessions
    MAX_HISTORY = 40
    if len(conversation_history) > MAX_HISTORY:
        conversation_history[:] = conversation_history[-MAX_HISTORY:]

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

@app.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    return templates.TemplateResponse("labs.html", {"request": request})


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


@app.get("/abstract-models", response_class=HTMLResponse)
async def abstract_models_page(request: Request):
    return templates.TemplateResponse("abstract_models.html", {"request": request})


@app.get("/tutor", response_class=HTMLResponse)
async def tutor_page(request: Request):
    """Red Team Tutor - guided mainframe learning"""
    return templates.TemplateResponse("tutor.html", {"request": request})


@app.get("/recon", response_class=HTMLResponse)
async def recon_page(request: Request):
    """Recon & Assessment dashboard"""
    return templates.TemplateResponse("recon.html", {"request": request})


@app.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough_page(request: Request):
    """Autonomous mainframe walkthrough"""
    return templates.TemplateResponse("walkthrough.html", {"request": request})


@app.get("/slides", response_class=HTMLResponse)
async def slides_page(request: Request):
    """Conference slide deck"""
    return templates.TemplateResponse("slides.html", {"request": request})


# ============================================================================
# Red Team Tutor API Endpoints
# ============================================================================

TUTOR_SYSTEM_PROMPT = """You are a senior mainframe mentor guiding modern red teamers through IBM MVS systems.

Your role is to make mainframe systems LEGIBLE to security professionals who did not grow up with them.

When analyzing a screen, structure your response as:
1. CURRENT SCREEN: What we see (plain English summary)
2. WHAT THIS IS: Panel or subsystem identification
3. WHY IT EXISTS: Historical/architectural rationale
4. RED TEAM INSIGHT: Trust boundary or control-plane implication
5. NEXT ACTION: What to do next and why

Key teaching principles:
- Correct Unix/cloud assumptions explicitly
- Explain trust boundaries (interactive vs batch, user vs system)
- Relate to modern concepts (control planes, blast radius, delayed execution)
- Default to READ-ONLY navigation
- Never skip steps for speed - teaching matters more

Environment: MVS 3.8J under Hercules (TK5). No DB2, IMS, or modern z/OS middleware.
Focus on: TN3270, TSO, ISPF, JCL, JES, batch execution, datasets, panels."""

PATH_SYSTEM_PROMPT = """You are a red-team learning path advisor for mainframe security.
Your job is to explain each learning path in plain language to someone new to mainframes.

Requirements:
- Be clear and non-intimidating.
- Explain what the path teaches and why it matters.
- Emphasize defensive outcomes, safe lab practice, and auditability.
- Answer "Is this right for me?" before the user starts.
- Use short paragraphs or bullets.
- Avoid jargon unless the user opts in explicitly.
"""

PATH_SESSION_PROMPT = """You are building a step-by-step learning path for a red-team session.
Return JSON only. No markdown. No prose outside JSON.

Each step must include:
- title
- instruction (what to do in TN3270)
- rationale (why this matters)
- expected (what should appear on screen)
- expected_signature (short strings to match in the screen)
- hints (array of short recovery tips)
"""

TUTOR_PERSONAS = {
    "mentor": {
        "name": "The Mentor",
        "style": "Patient, methodical, and big-picture. Emphasize conceptual models and historical rationale.",
        "focus": "Foundations, systems thinking, and mapping mainframe concepts to modern control planes."
    },
    "operator": {
        "name": "The Operator",
        "style": "Practical and procedural. Give step-by-step guidance and real-world operational cautions.",
        "focus": "Console flow, SOPs, and precise keystrokes or commands."
    },
    "redteam": {
        "name": "The Red Teamer",
        "style": "Direct and threat-focused. Call out abuse paths and misconfig risks.",
        "focus": "Trust gaps, over-privilege, and offensive tradecraft implications."
    },
    "forensics": {
        "name": "The Forensics Lead",
        "style": "Evidence-driven. Highlight audit trails and what artifacts persist.",
        "focus": "Logs, dataset provenance, and incident response traces."
    },
    "architect": {
        "name": "The Architect",
        "style": "Systems-depth. Explain subsystem boundaries and address spaces.",
        "focus": "Long-lived control boundaries, blast radius, and design tradeoffs."
    },
    "policy": {
        "name": "Policy Coach",
        "style": "Guardrail-focused. Emphasize least privilege, auditability, and change control.",
        "focus": "Defensive outcomes, compliance evidence, and safe operational patterns."
    }
}


def build_tutor_prompt(tutor_id: str) -> str:
    persona = TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS["mentor"])
    return f"""{TUTOR_SYSTEM_PROMPT}

Tutor persona: {persona['name']}
Style: {persona['style']}
Focus: {persona['focus']}
"""


async def build_rag_context(query: str, n_results: int = 2) -> str:
    if not RAG_AVAILABLE or not query:
        return ""
    try:
        engine = get_rag_engine()
        rag_results = await engine.query_simple(query, n_results=n_results)
        if rag_results:
            rag_context = "\n\n[Relevant Knowledge Base Information]\n"
            for r in rag_results:
                rag_context += f"---\n{r['content']}\n"
            return rag_context
    except Exception as e:
        print(f"RAG query error: {e}")
    return ""


@app.post("/api/tutor/analyze")
async def api_tutor_analyze(request: Request):
    """Analyze current screen with tutor context"""
    data = await request.json()
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    if not connection.connected:
        return JSONResponse({"error": "Not connected to mainframe"})

    screen_text = read_screen()
    if not screen_text or screen_text == "[Not connected]":
        return JSONResponse({"error": "Could not read screen"})

    # Classify the panel
    panel_info = {}
    if GRAPH_AVAILABLE:
        panel_info = classify_panel(screen_text)
        identifiers = extract_identifiers(screen_text)

        # Update trust graph with screen data
        graph = get_trust_graph()
        update_graph_from_screen(graph, screen_text, f"{connection.host}:{connection.port}")

    # Build prompt for LLM analysis
    goal_context = {
        'session-stack': "Focus on explaining the VTAM→TSO→ISPF session layers.",
        'batch-execution': "Focus on JCL, JES, and batch execution concepts.",
        'dataset-trust': "Focus on dataset access patterns and trust implications.",
        'panel-navigation': "Focus on panel IDs, PF keys, and navigation patterns.",
        'job-tracing': "Focus on job execution chains and program loading.",
        'free-explore': "Provide general mainframe education."
    }.get(goal, "Provide general mainframe education.")

    rag_query = f"{goal_context}\n{panel_info.get('panel_type', 'Unknown')}\n{screen_text[:1200]}"
    rag_context = await build_rag_context(rag_query, n_results=2)

    prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Current learning goal: {goal_context}

Analyze this 3270 screen:
```
{screen_text}
```

Panel classification: {panel_info.get('panel_type', 'Unknown')}
Environment: {panel_info.get('environment', 'Unknown')}

Provide your analysis in the structured format. Be educational and thorough."""

    # Call Ollama
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 1500}
                },
                timeout=120.0
            )

            if response.status_code == 200:
                result = response.json().get("response", "")

                # Parse structured response
                sections = {}
                current_section = None
                current_content = []

                for line in result.split('\n'):
                    line_upper = line.upper().strip()
                    if 'CURRENT SCREEN' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'current_screen'
                        current_content = []
                    elif 'WHAT THIS IS' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'what_this_is'
                        current_content = []
                    elif 'WHY IT EXISTS' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'why_it_exists'
                        current_content = []
                    elif 'RED TEAM INSIGHT' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'red_team_insight'
                        current_content = []
                    elif 'NEXT ACTION' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'next_action'
                        current_content = []
                    elif 'CONFIDENCE' in line_upper:
                        if current_section:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = 'confidence'
                        current_content = []
                    else:
                        current_content.append(line)

                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()

                # If parsing failed, return raw
                if not sections:
                    sections = {'current_screen': result}

                sections['graph_updated'] = GRAPH_AVAILABLE
                sections['panel_type'] = panel_info.get('panel_type', 'Unknown')

                return JSONResponse(sections)
            else:
                return JSONResponse({"error": f"LLM error: {response.status_code}"})

    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/api/tutor/suggest")
async def api_tutor_suggest(request: Request):
    """Suggest next action based on goal and current screen"""
    data = await request.json()
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    if not connection.connected:
        return JSONResponse({"suggestion": "Connect to TK5 (localhost:3270) to begin live navigation."})

    screen_text = read_screen()
    panel_info = classify_panel(screen_text) if GRAPH_AVAILABLE else {}

    rag_query = f"{goal}\n{panel_info.get('panel_type', 'Unknown')}\n{screen_text[:1200]}"
    rag_context = await build_rag_context(rag_query, n_results=2)

    prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Learning goal: {goal}
Current panel: {panel_info.get('panel_type', 'Unknown')}

Screen:
```
{screen_text[:1500]}
```

What should the learner do next to progress toward their goal? Be specific about what to type or which key to press."""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 500}
                },
                timeout=120.0
            )

            if response.status_code == 200:
                suggestion = response.json().get("response", "")
                return JSONResponse({"suggestion": suggestion})
            else:
                return JSONResponse({"suggestion": "Unable to generate suggestion."})

    except Exception as e:
        return JSONResponse({"suggestion": f"Error: {str(e)}"})


@app.post("/api/tutor/ask")
async def api_tutor_ask(request: Request):
    """Answer a question from the learner"""
    data = await request.json()
    question = data.get("question", "")
    goal = data.get("goal", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")

    screen_context = ""
    if connection.connected:
        screen_text = read_screen()
        screen_context = f"\n\nCurrent screen:\n```\n{screen_text[:1000]}\n```"
    else:
        screen_text = ""

    rag_query = f"{question}\n{screen_text[:1200]}" if question else screen_text[:1200]
    rag_context = await build_rag_context(rag_query, n_results=3)

    prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Learning goal: {goal}
{screen_context}

Learner's question: {question}

Answer in an educational, thorough manner. Relate concepts to modern security thinking where relevant."""

    try:
        timeout_s = 120.0
        num_predict = 500
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": num_predict}
                },
                timeout=timeout_s
            )

            if response.status_code == 200:
                answer = response.json().get("response", "")
                return JSONResponse({"answer": answer})
            else:
                return JSONResponse({"answer": "Unable to answer right now."})

    except httpx.ReadTimeout:
        return JSONResponse({"answer": "Error: ReadTimeout: LLM took too long. Try again or ask a shorter question."})
    except Exception as e:
        return JSONResponse({"answer": f"Error: {type(e).__name__}: {str(e)}"})


@app.post("/api/tutor/event")
async def api_tutor_event(request: Request):
    """
    Orchestrated tutor endpoint that handles Ask/Analyze/Next events.
    Performs:
    1. Pull TN3270 snapshot (screenText, cursor, signature)
    2. Call RAG retrieval with query + screenText + module + persona
    3. Call LLM with system prompt + user prompt + terminal snapshot + retrieved context
    Returns structured JSON for UI rendering.
    """
    data = await request.json()
    event_type = data.get("event", "ask")  # ask, analyze, next
    question = data.get("question", "")
    module_id = data.get("module", "free-explore")
    tutor_id = data.get("tutor_id", "mentor")
    step = data.get("step", {})

    result = {
        "messages": [],
        "steps": [],
        "canAdvance": False,
        "diagnostics": {
            "ragUsed": False,
            "k": 0,
            "llmUsed": False,
            "terminalConnected": connection.connected
        }
    }

    # 1. Pull TN3270 snapshot
    screen_text = ""
    screen_signature = ""
    if connection.connected:
        try:
            screen_text = read_screen()
            screen_signature = screen_text[:80] if screen_text else ""
            result["diagnostics"]["terminalConnected"] = True
        except Exception as e:
            result["messages"].append({
                "role": "system",
                "content": f"Warning: Could not read terminal screen: {str(e)}"
            })
    else:
        result["diagnostics"]["terminalConnected"] = False

    # 2. RAG retrieval
    rag_context = ""
    rag_warning = ""
    try:
        module_info = pathCatalog.get(module_id, {})
        rag_query = f"{question}\n{module_info.get('description', '')}\n{screen_text[:1200]}"
        rag_context = await build_rag_context(rag_query, n_results=4)
        if rag_context:
            result["diagnostics"]["ragUsed"] = True
            result["diagnostics"]["k"] = 4
    except Exception as e:
        rag_warning = f"RAG unavailable: {str(e)}"
        result["messages"].append({
            "role": "system",
            "content": f"Warning: {rag_warning}"
        })

    # 3. Build prompt based on event type
    if event_type == "ask":
        prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Module: {module_id}
Current screen:
```
{screen_text[:1500]}
```

User question: {question}

Answer thoroughly and educationally. If the question relates to the current screen, explain what they're seeing."""

    elif event_type == "analyze":
        prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Module: {module_id}
Analyze this TN3270 screen:
```
{screen_text}
```

Provide your analysis following the structured format:
1. CURRENT SCREEN: Plain English summary
2. WHAT THIS IS: Panel/subsystem identification
3. WHY IT EXISTS: Historical/architectural rationale
4. RED TEAM INSIGHT: Trust boundary or control-plane implication
5. NEXT ACTION: What to do next"""

    elif event_type == "next":
        step_context = f"Current step: {step.get('title', '')}\nInstruction: {step.get('instruction', '')}" if step else ""
        prompt = f"""{build_tutor_prompt(tutor_id)}{rag_context}

Module: {module_id}
{step_context}
Current screen:
```
{screen_text[:1500]}
```

What should the learner do next to progress? Be specific about keystrokes or text to type."""

    else:
        prompt = f"{build_tutor_prompt(tutor_id)}\n\n{question}"

    # 4. Call LLM
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 1200}
                },
                timeout=120.0
            )

            if response.status_code == 200:
                llm_response = response.json().get("response", "")
                result["diagnostics"]["llmUsed"] = True
                result["messages"].append({
                    "role": "assistant",
                    "content": llm_response
                })
            else:
                result["messages"].append({
                    "role": "error",
                    "content": f"LLM returned status {response.status_code}"
                })

    except httpx.TimeoutException:
        result["messages"].append({
            "role": "error",
            "content": "LLM request timed out. The model may be loading - please try again."
        })
    except Exception as e:
        result["messages"].append({
            "role": "error",
            "content": f"LLM error: {str(e)}"
        })

    return JSONResponse(result)


# Module catalog used by /api/tutor/event
pathCatalog = {
    'session-stack': {
        'id': 'session-stack',
        'title': 'Session Stack',
        'description': 'Connect VTAM→TSO→ISPF and learn navigation, PF keys, panels, and command flow.',
        'defender_outcome': 'Understand where authentication, authorization, and auditing occur in the session stack.'
    },
    'batch-execution': {
        'id': 'batch-execution',
        'title': 'Batch Execution',
        'description': 'Create and submit JCL, interpret JES output, and trace job logs and return codes.',
        'defender_outcome': 'Know where jobs are queued, scheduled, and logged so you can trace execution safely.'
    },
    'dataset-trust': {
        'id': 'dataset-trust',
        'title': 'Dataset Trust',
        'description': 'Understand RACF/Dataset profiles, access checks, and common misconfig trust breaks.',
        'defender_outcome': 'Map dataset access patterns to least-privilege controls and audit evidence.'
    },
    'free-explore': {
        'id': 'free-explore',
        'title': 'Free Explore',
        'description': 'Explore with guardrails—ask questions and get contextual help on the current screen.',
        'defender_outcome': 'Practice safe exploration while maintaining system integrity.'
    }
}


@app.post("/api/tutor/path_explain")
async def api_tutor_path_explain(request: Request):
    data = await request.json()
    path = data.get("path", {})
    tutor_id = data.get("tutor_id", "mentor")
    question = data.get("question", "")

    meta = "\n".join([
        f"Title: {path.get('title', '')}",
        f"Objective: {path.get('objective', '')}",
        f"Level: {path.get('level', '')}",
        f"Time: {path.get('time', '')}",
        f"Domain: {path.get('domain', '')}",
        f"Intent: {path.get('intent', '')}",
        f"Summary: {path.get('summary', '')}",
        f"Defender Outcome: {path.get('defender_outcome', '')}",
    ])

    rag_context = await build_rag_context(meta, n_results=2)
    prompt = f"""{PATH_SYSTEM_PROMPT}{rag_context}
Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}

Path metadata:
{meta}

User question (optional): {question or "N/A"}

Respond with:
1) What this path teaches (1-2 sentences)
2) Why it matters (1-2 sentences)
3) Is this right for me? (1-2 sentences)
4) Suggested next step: Start / Preview / Ask (1 short sentence)
"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.6, "num_predict": 400}
                },
                timeout=120.0
            )
            if response.status_code == 200:
                explanation = response.json().get("response", "")
                return JSONResponse({"explanation": explanation})
            return JSONResponse({"explanation": "Unable to generate explanation."})
    except Exception as e:
        return JSONResponse({"explanation": f"Error: {str(e)}"})


@app.post("/api/tutor/path_hint")
async def api_tutor_path_hint(request: Request):
    data = await request.json()
    path = data.get("path", {})
    tutor_id = data.get("tutor_id", "mentor")

    meta = "\n".join([
        f"Title: {path.get('title', '')}",
        f"Objective: {path.get('objective', '')}",
        f"Level: {path.get('level', '')}",
        f"Time: {path.get('time', '')}",
        f"Domain: {path.get('domain', '')}",
        f"Intent: {path.get('intent', '')}",
    ])

    rag_context = await build_rag_context(meta, n_results=1)
    prompt = f"""{PATH_SYSTEM_PROMPT}{rag_context}
Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}

Path metadata:
{meta}

Provide a single-sentence hint that helps a beginner decide if this path is for them.
"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.6, "num_predict": 120}
                },
                timeout=60.0
            )
            if response.status_code == 200:
                hint = response.json().get("response", "")
                return JSONResponse({"hint": hint})
            return JSONResponse({"hint": ""})
    except Exception as e:
        return JSONResponse({"hint": ""})


@app.post("/api/tutor/persona_hint")
async def api_tutor_persona_hint(request: Request):
    data = await request.json()
    tutor_id = data.get("tutor_id", "mentor")
    persona = TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS["mentor"])

    prompt = f"""You are the tutor persona speaking in first person.
Provide a single, calm sentence that explains how you guide the learner.
Keep it short and non-intimidating.

Persona: {persona['name']}
Style: {persona['style']}
Focus: {persona['focus']}
"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.5, "num_predict": 80}
                },
                timeout=60.0
            )
            if response.status_code == 200:
                hint = response.json().get("response", "")
                return JSONResponse({"hint": hint})
            return JSONResponse({"hint": ""})
    except Exception as e:
        return JSONResponse({"hint": ""})


def _extract_json_block(text: str) -> dict:
    import json
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


@app.post("/api/tutor/path_start")
async def api_tutor_path_start(request: Request):
    data = await request.json()
    path = data.get("path", {})
    tutor_id = data.get("tutor_id", "mentor")
    screen = data.get("screen", "")

    meta = "\n".join([
        f"Title: {path.get('title', '')}",
        f"Objective: {path.get('objective', '')}",
        f"Level: {path.get('level', '')}",
        f"Time: {path.get('time', '')}",
        f"Domain: {path.get('domain', '')}",
        f"Intent: {path.get('intent', '')}",
        f"Summary: {path.get('summary', '')}",
    ])

    rag_context = await build_rag_context(meta + "\n" + screen, n_results=2)
    prompt = f"""{PATH_SESSION_PROMPT}
Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}

Path metadata:
{meta}

Current screen:
{screen[:1500]}

Return JSON in this shape:
{{
  "session": {{
    "path_id": "{path.get('id', '')}",
    "steps": [
      {{
        "title": "Step 1 title",
        "instruction": "Exact action to perform",
        "rationale": "Why this matters",
        "expected": "What should appear on screen",
        "expected_signature": ["LOGON", "ISPF"],
        "hints": ["Tip 1", "Tip 2"]
      }}
    ]
  }}
}}
{rag_context}
"""

    fallback_steps = {
            "session-stack": [
                {
                    "title": "Find the LOGON prompt",
                    "instruction": "Look for the LOGON ===> prompt on the terminal. If you don't see it, press Enter once.",
                    "rationale": "VTAM/TN3270 sessions typically start at the LOGON prompt before TSO.",
                    "expected": "A screen with LOGON ===> or similar prompt.",
                    "expected_signature": ["LOGON", "LOGON ===>"],
                    "hints": ["Press Enter once", "If you see a blank screen, press Clear"]
                },
                {
                    "title": "Enter TSO",
                    "instruction": "Type TSO and press Enter.",
                    "rationale": "TSO is the interactive shell used to access ISPF and datasets.",
                    "expected": "A TSO/E logon panel or READY prompt.",
                    "expected_signature": ["TSO", "READY", "IKJ"],
                    "hints": ["If you see IKJ, you are in TSO", "If denied, verify your user ID"]
                },
                {
                    "title": "Launch ISPF",
                    "instruction": "At the TSO READY prompt, type ISPF and press Enter.",
                    "rationale": "ISPF is the menu-driven interface for dataset and panel navigation.",
                    "expected": "ISPF Primary Option Menu.",
                    "expected_signature": ["ISPF", "Primary Option Menu"],
                    "hints": ["If you see option menu, you’re in ISPF"]
                }
            ],
            "batch-execution": [
                {
                    "title": "Locate a JCL member",
                    "instruction": "In ISPF, go to option 3.4 and locate a dataset with JCL members.",
                    "rationale": "Batch execution starts with JCL source members.",
                    "expected": "ISPF Dataset List panel.",
                    "expected_signature": ["DATA SET LIST", "DSLIST", "3.4"],
                    "hints": ["If not in ISPF, launch it first", "Use wildcards like HLQ.*"]
                },
                {
                    "title": "Submit a job",
                    "instruction": "Select a JCL member and submit it (SUB or JCL submit action).",
                    "rationale": "Submitting a job sends it to JES for execution.",
                    "expected": "A message that the job was submitted.",
                    "expected_signature": ["SUBMITTED", "JOB", "JES"],
                    "hints": ["Look for a confirmation line", "If you see error, review the JOB card"]
                },
                {
                    "title": "View job output",
                    "instruction": "Go to SDSF or JES output panel and find your job output.",
                    "rationale": "Output verification confirms batch execution.",
                    "expected": "Job output listing or SDSF panel.",
                    "expected_signature": ["SDSF", "OUTPUT", "JOBNAME"],
                    "hints": ["If SDSF unavailable, use JES panels"]
                }
            ],
            "dataset-trust": [
                {
                    "title": "Open dataset list",
                    "instruction": "In ISPF, open option 3.4 and list datasets under your HLQ.",
                    "rationale": "Dataset access is central to mainframe trust boundaries.",
                    "expected": "ISPF Dataset List panel.",
                    "expected_signature": ["DATA SET LIST", "DSLIST", "3.4"],
                    "hints": ["Use HLQ.* to filter"]
                },
                {
                    "title": "Inspect dataset attributes",
                    "instruction": "Select a dataset and view its attributes (DSORG, LRECL, BLKSIZE).",
                    "rationale": "Attributes affect how data is stored and protected.",
                    "expected": "Dataset attributes panel.",
                    "expected_signature": ["DSORG", "LRECL", "BLKSIZE"],
                    "hints": ["Use the info/attributes action from the list"]
                },
                {
                    "title": "Understand DISP",
                    "instruction": "Open a JCL member and locate DISP parameters.",
                    "rationale": "DISP controls dataset disposition and access behavior.",
                    "expected": "JCL member view with DISP=...",
                    "expected_signature": ["DISP="],
                    "hints": ["Search for DISP in the JCL"]
                }
            ],
            "free-explore": [
                {
                    "title": "Take a look around",
                    "instruction": "Use the menu or panels available and describe what you see.",
                    "rationale": "Exploration builds familiarity and context.",
                    "expected": "Any stable panel to discuss.",
                    "expected_signature": ["MENU", "OPTION", "TSO", "ISPF"],
                    "hints": ["Ask the tutor what the current panel is"]
                }
            ]
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.4, "num_predict": 700}
                },
                timeout=120.0
            )
            if response.status_code == 200:
                raw = response.json().get("response", "")
                payload = _extract_json_block(raw)
                if payload and payload.get("session", {}).get("steps"):
                    return JSONResponse(payload)
                # Fall back to local steps if LLM didn't return anything useful
                raise ValueError("LLM returned no steps")
            raise ValueError("LLM request failed")
    except httpx.ReadTimeout:
        steps = fallback_steps.get(path.get("id", ""), fallback_steps["free-explore"])
        return JSONResponse({"session": {"path_id": path.get("id", ""), "steps": steps}})
    except Exception:
        steps = fallback_steps.get(path.get("id", ""), fallback_steps["free-explore"])
        return JSONResponse({"session": {"path_id": path.get("id", ""), "steps": steps}})


@app.post("/api/tutor/path_verify")
async def api_tutor_path_verify(request: Request):
    data = await request.json()
    step = data.get("step", {})
    screen = data.get("screen", "")
    tutor_id = data.get("tutor_id", "mentor")
    expected_signatures = step.get("expected_signature", [])
    if isinstance(expected_signatures, str):
        expected_signatures = [expected_signatures]

    # Fast local match
    if expected_signatures and screen:
        hit = any(sig.lower() in screen.lower() for sig in expected_signatures if sig)
        if hit:
            return JSONResponse({"verified": True})

    prompt = f"""You are validating a TN3270 screen against an expected step.
Answer with JSON only: {{"verified": true/false, "feedback": "short guidance"}}

Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}
Expected: {step.get('expected', '')}
Expected signature: {expected_signatures}

Screen:
{screen[:1500]}
"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 200}
                },
                timeout=120.0
            )
            if response.status_code == 200:
                raw = response.json().get("response", "")
                payload = _extract_json_block(raw)
                if "verified" in payload:
                    return JSONResponse(payload)
            return JSONResponse({"verified": False, "feedback": "Screen does not match expected state."})
    except Exception as e:
        return JSONResponse({"verified": False, "feedback": "Unable to verify screen."})


@app.post("/api/tutor/path_help")
async def api_tutor_path_help(request: Request):
    data = await request.json()
    step = data.get("step", {})
    screen = data.get("screen", "")
    tutor_id = data.get("tutor_id", "mentor")

    prompt = f"""You are a red-team tutor helping a learner who is stuck.
Provide 2-3 short bullets with recovery steps.

Tutor persona: {TUTOR_PERSONAS.get(tutor_id, TUTOR_PERSONAS['mentor'])['name']}
Step instruction: {step.get('instruction', '')}
Expected: {step.get('expected', '')}

Screen:
{screen[:1500]}
"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.5, "num_predict": 250}
                },
                timeout=120.0
            )
            if response.status_code == 200:
                help_text = response.json().get("response", "")
                return JSONResponse({"help": help_text})
            return JSONResponse({"help": "Try returning to the previous screen and re-entering the command."})
    except Exception as e:
        return JSONResponse({"help": "Unable to provide help right now."})


@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    result = await process_chat(request.message)
    return JSONResponse(result)


@app.get("/api/labs")
async def api_labs_index():
    index_path = os.path.join(LAB_DATA_DIR, "index.json")
    data = read_json_file(index_path, {"labs": []})
    return JSONResponse(data)


@app.get("/api/labs/{lab_id}")
async def api_labs_detail(lab_id: str):
    lab_path = os.path.join(LAB_DATA_DIR, f"{lab_id}.json")
    if not os.path.exists(lab_path):
        return JSONResponse({"error": "Lab not found"}, status_code=404)
    data = read_json_file(lab_path, {})
    if not data:
        return JSONResponse({"error": "Lab not available"}, status_code=404)
    return JSONResponse(data)


@app.post("/api/demo/load")
async def api_demo_load(request: Request):
    if not GRAPH_AVAILABLE:
        return JSONResponse({"success": False, "error": "Trust graph not available"}, status_code=400)

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    load_type = payload.get("type", "all")
    graph = get_trust_graph()
    results = {}

    try:
        if load_type in ("jcl", "all"):
            jcl_text = read_text_file(os.path.join(DEMO_DATA_DIR, "sample_jcl.txt"))
            parsed_jcl = parse_jcl(jcl_text)
            results["jcl"] = update_graph_from_jcl(
                graph, parsed_jcl, {"type": "demo", "source": "sample_jcl"}
            )

        if load_type in ("sysout", "all"):
            sysout_text = read_text_file(os.path.join(DEMO_DATA_DIR, "sample_sysout.txt"))
            parsed_sysout = parse_sysout(sysout_text)
            if not parsed_sysout.get("jobname"):
                parsed_sysout["jobname"] = "DEMOJOB"
            if not parsed_sysout.get("jobid"):
                parsed_sysout["jobid"] = "JOB00012"
            results["sysout"] = update_graph_from_sysout(
                graph, parsed_sysout, {"type": "demo", "source": "sample_sysout"}
            )

        if load_type in ("screen", "all"):
            screen_text = read_text_file(os.path.join(DEMO_DATA_DIR, "sample_screen.txt"))
            results["screen"] = update_graph_from_screen(graph, screen_text, "demo:3270")

        graph.save()
        await broadcast_graph_update("demo_loaded", results)
        return JSONResponse({"success": True, "results": results})
    except FileNotFoundError as exc:
        return JSONResponse({"success": False, "error": f"Missing demo file: {exc}"}, status_code=404)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


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


# ============================================================================
# Recon & Assessment API Endpoints
# ============================================================================

@app.post("/api/recon/enumerate")
async def api_recon_enumerate(request: Request):
    """Run TSO/CICS/VTAM enumeration."""
    global _active_enumerator

    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection.connected:
        return JSONResponse({"error": "Not connected to a mainframe"}, status_code=400)

    data = await request.json()
    module = data.get("module", "tso")
    wordlist = data.get("wordlist")  # list of strings or None
    command_sequence = data.get("command_sequence")  # list of strings or None

    try:
        if module == "tso":
            enumerator = TSOEnumerator(userids=wordlist, command_sequence=command_sequence)
        elif module == "cics":
            enumerator = CICSEnumerator(transactions=wordlist)
        elif module == "vtam":
            enumerator = VTAMEnumerator(applids=wordlist)
        else:
            return JSONResponse({"error": f"Unknown module: {module}"}, status_code=400)

        _active_enumerator = enumerator

        # Run enumeration in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, enumerator.enumerate)

        _active_enumerator = None
        return JSONResponse({"results": results})

    except Exception as e:
        _active_enumerator = None
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/recon/enumerate/stop")
async def api_recon_enumerate_stop():
    """Stop a running enumeration."""
    global _active_enumerator
    if _active_enumerator:
        _active_enumerator.stop()
        _active_enumerator = None
    return JSONResponse({"success": True})


@app.post("/api/recon/hidden-fields")
async def api_recon_hidden_fields():
    """Detect hidden fields on current screen."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    try:
        detector = HiddenFieldDetector()
        loop = asyncio.get_event_loop()
        fields = await loop.run_in_executor(None, detector.detect)
        return JSONResponse({"fields": fields})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/recon/analyze-screen")
async def api_recon_analyze_screen():
    """Analyze current screen for security patterns."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    try:
        analyzer = ScreenAnalyzer()
        loop = asyncio.get_event_loop()
        findings = await loop.run_in_executor(None, analyzer.analyze_current_screen)
        return JSONResponse({"findings": findings})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/recon/map")
async def api_recon_map(request: Request):
    """Run application mapper from current screen."""
    global _active_mapper

    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)
    if not connection.connected:
        return JSONResponse({"error": "Not connected"}, status_code=400)

    data = await request.json()
    max_depth = min(int(data.get("max_depth", 3)), 5)

    try:
        mapper = ApplicationMapper(max_depth=max_depth)
        _active_mapper = mapper

        loop = asyncio.get_event_loop()
        tree = await loop.run_in_executor(None, mapper.map)

        stats = mapper.stats
        _active_mapper = None
        return JSONResponse({"tree": tree, "stats": stats})

    except Exception as e:
        _active_mapper = None
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/recon/map/stop")
async def api_recon_map_stop():
    """Stop a running mapper."""
    global _active_mapper
    if _active_mapper:
        _active_mapper.stop()
        _active_mapper = None
    return JSONResponse({"success": True})


@app.post("/api/recon/report")
async def api_recon_report(request: Request):
    """Generate assessment report."""
    if not RECON_AVAILABLE:
        return JSONResponse({"error": "Recon engine not available"}, status_code=400)

    data = await request.json()
    fmt = data.get("format", "json")
    enumerate_results = data.get("enumerate_results", [])
    hidden_fields_data = data.get("hidden_fields", [])
    screen_findings_data = data.get("screen_findings", [])
    map_tree_data = data.get("map_tree", [])

    try:
        report = generate_recon_report(
            enumerate_results=enumerate_results,
            hidden_fields=hidden_fields_data,
            screen_findings=screen_findings_data,
            map_tree=map_tree_data,
            fmt=fmt,
        )
        return JSONResponse({"report": report})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


RECON_AI_PROMPT = """You are a mainframe security analyst using the control-plane assessment methodology.

z/OS is a federation of subsystems, not a monolithic host. Security decisions occur outside the kernel.
Your analysis must address the 5 assessment questions:

1. Where is identity bound?
2. When is authority evaluated?
3. What executes later than expected?
4. Which subsystem enforces policy?
5. What assumptions are being imported incorrectly?

Frame all findings in terms of the 5 control planes:
- **TSO/ISPF** (human interaction plane)
- **JES** (deferred execution plane)
- **RACF** (authorization plane)
- **CICS** (transaction execution plane)
- **VTAM** (session fabric plane)

For each finding, identify:
- Which control plane it belongs to
- Which assessment question it answers
- What broken assumption it reveals (e.g. "there is a root user", "processes are short-lived",
  "ports define exposure", "authentication = authorization", "work executes immediately")

Structure your response as:
1. **Control Plane Summary** - Which planes were assessed and their exposure level
2. **Key Findings by Control Plane** - Findings grouped by TSO, JES, RACF, CICS, VTAM
3. **Broken Assumptions** - Which modern OS assumptions were disproved by the evidence
4. **Assessment Questions Answered** - Map findings to the 5 questions above
5. **Recommendations** - Concrete defensive actions grounded in the methodology

Use markdown formatting. Be specific to IBM z/OS subsystem boundaries."""


@app.post("/api/recon/ai-analyze")
async def api_recon_ai_analyze(request: Request):
    """Send recon results to Ollama for AI-assisted interpretation."""
    data = await request.json()

    # Build context from whatever results exist
    sections = []

    enum_results = data.get("enumerate_results", [])
    if enum_results:
        valid = [r for r in enum_results if r.get("status") in ("valid", "auth_required", "locked", "valid_blank")]
        invalid = [r for r in enum_results if r.get("status") == "invalid"]
        sections.append(f"## Enumeration Results\n- {len(enum_results)} targets tested\n- {len(valid)} valid, {len(invalid)} invalid")
        for r in valid[:20]:
            name = r.get("userid") or r.get("transaction_id") or r.get("applid", "?")
            sections.append(f"  - **{name}**: {r['status']} ({r['message']})")

    hidden = data.get("hidden_fields", [])
    if hidden:
        sections.append(f"\n## Hidden Fields\n- {len(hidden)} hidden fields detected")
        for f in hidden[:10]:
            sections.append(f"  - Row {f['row']}, Col {f['col']}: type={f['field_type']}, content=`{f.get('content', '')[:40]}`")

    findings = data.get("screen_findings", [])
    if findings:
        sections.append(f"\n## Screen Findings\n- {len(findings)} patterns matched")
        for f in findings[:15]:
            sections.append(f"  - [{f['severity'].upper()}] {f['description']}: `{f['match']}`")

    screen_text = data.get("current_screen", "")
    if screen_text:
        sections.append(f"\n## Current Screen\n```\n{screen_text[:1500]}\n```")

    if not sections:
        return JSONResponse({"error": "No recon data provided. Run enumeration or screen analysis first."}, status_code=400)

    context = "\n".join(sections)
    prompt = RECON_AI_PROMPT + "\n\n---\n\n" + context

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 2048,
                    }
                },
                timeout=120.0
            )
            if response.status_code == 200:
                ai_response = response.json().get("response", "No analysis generated.")
                return JSONResponse({"analysis": ai_response})
            else:
                return JSONResponse({"error": f"Ollama error: {response.status_code}"}, status_code=502)
    except httpx.TimeoutException:
        return JSONResponse({"error": "LLM request timed out. Model may still be loading."}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": f"AI analysis failed: {str(e)}"}, status_code=500)


EXPLAIN_SCREEN_PROMPT = """You are a mainframe security analyst using the control-plane assessment methodology.
You are explaining a live TN3270 screen to an assessor who is learning the methodology.

z/OS is a federation of subsystems, not a monolithic host. Security decisions occur outside the kernel.

## The 5 Control Planes
- TSO/ISPF -- Human interaction plane (interactive sessions, ISPF panels)
- JES -- Deferred execution plane (job submission, spool, scheduling)
- RACF -- Authorization plane (profiles, access control, identity)
- CICS -- Transaction execution plane (online transactions, regions)
- VTAM -- Session fabric plane (LU sessions, APPLIDs, network)

## The 5 Broken Assumptions
1. "There is a root user" -- RACF distributes authority across profiles, not a single account
2. "Processes are short-lived" -- Address spaces persist; identity outlives sessions
3. "Ports define exposure" -- VTAM sessions outlive TCP; network != authority
4. "Authentication = Authorization" -- RACF separates these; subsystems ask "may this happen?"
5. "Work executes immediately" -- JES brokers deferred privileged execution

## The 5 Assessment Questions
1. Where is identity bound?
2. When is authority evaluated?
3. What executes later than expected?
4. Which subsystem enforces policy?
5. What assumptions are you importing incorrectly?

Analyze the screen and respond with:
1. **Control Plane**: Which control plane you are currently in and why
2. **What You See**: Plain English summary of the screen content
3. **Authority Implications**: What the screen reveals about identity, authority, or enforcement
4. **Broken Assumption**: Which modern OS assumption this screen disproves (if any)
5. **Assessment Insight**: Which of the 5 assessment questions this screen helps answer
6. **Suggested Action**: What to do next and the methodology rationale for doing it

Be educational. Correct Unix/cloud assumptions explicitly. Use markdown."""


@app.post("/api/recon/explain-screen")
async def api_recon_explain_screen(request: Request):
    """Explain the current screen through the methodology lens for the Walkthrough tab."""
    if not connection.connected:
        return JSONResponse({"error": "Not connected to a mainframe"}, status_code=400)

    screen_text = read_screen()
    if not screen_text or screen_text == "[Not connected]":
        return JSONResponse({"error": "Could not read screen"}, status_code=400)

    data = await request.json()
    walkthrough_context = data.get("walkthrough_context", "")

    # Build prompt with methodology framework
    prompt = EXPLAIN_SCREEN_PROMPT
    if walkthrough_context:
        prompt += f"\n\nWalkthrough context: {walkthrough_context}"

    # Add RAG context if available
    rag_context = await build_rag_context(screen_text[:800], n_results=2)
    if rag_context:
        prompt += rag_context

    prompt += f"\n\n---\n\nCurrent TN3270 Screen:\n```\n{screen_text}\n```"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "num_predict": 1500,
                    }
                },
                timeout=120.0
            )
            if response.status_code == 200:
                explanation = response.json().get("response", "No explanation generated.")
                return JSONResponse({"explanation": explanation, "screen": screen_text})
            else:
                return JSONResponse({"error": f"Ollama error: {response.status_code}"}, status_code=502)
    except httpx.TimeoutException:
        return JSONResponse({"error": "LLM request timed out. Model may still be loading."}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": f"Explain screen failed: {str(e)}"}, status_code=500)


# ============================================================================
# Autonomous Walkthrough System
# ============================================================================

import time as _time

WALKTHROUGH_SCRIPTS = {
    "session-stack": {
        "title": "Session Stack: VTAM \u2192 TSO \u2192 ISPF \u2192 Datasets",
        "steps": [
            {
                "title": "Connect to Mainframe",
                "control_plane": "vtam",
                "narration": "**Control Plane: VTAM (Session Fabric)**\n\nWe begin by establishing a TN3270 connection. This creates a Logical Unit (LU) session in VTAM \u2014 the session fabric that exists independently of TCP/IP.\n\n**Key concept:** The session is managed by VTAM, not the network stack. When we connect, we are assigned an LU session that can outlive the TCP connection itself.",
                "actions": [{"type": "connect"}],
                "expect": [],
                "display_seconds": 5,
            },
            {
                "title": "VTAM Entry Screen",
                "control_plane": "vtam",
                "narration": "**Control Plane: VTAM (Session Fabric)**\n\nYou are at the VTAM entry screen \u2014 the session fabric layer. VTAM manages LU sessions that exist independently of TCP/IP.\n\n**Broken Assumption:** *\"Ports define exposure.\"* In z/OS, the session fabric outlives TCP connections. What you see here is not a \"service on a port\" \u2014 it's the session manager itself.\n\n**Assessment Question Q1:** Identity is not yet bound. You are an anonymous VTAM session. No userid, no authority \u2014 just a session handle.\n\nWe'll type `TSO` to leave the session fabric and enter the human interaction plane.",
                "actions": [{"type": "clear"}, {"type": "wait", "seconds": 2}],
                "expect": ["VTAM", "USS", "LOGON", "NVAS"],
                "display_seconds": 6,
            },
            {
                "title": "TSO Logon — Identity Binding",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO / RACF (Identity Binding & Authentication)**\n\nWe transition from the VTAM session fabric to TSO — the human interaction plane. VTAM routes our session to the TSO APPLID, and we authenticate as HERC01.\n\n**Key concept:** VTAM acts as a session router. `TSO` is an APPLID registered in the session fabric. The transition from VTAM to TSO is a control-plane boundary crossing.\n\n**Broken Assumption:** *\"There is a root user.\"* There is no root. RACF distributes authority across profiles. The userid `HERC01` determines which profile set applies.\n\nPassword verification is handled by RACF, not TSO. Authentication proves identity, but authentication is not authorization — RACF evaluates every resource access separately. Logging in does not grant blanket access.",
                "actions": [{"type": "tso_login"}],
                "expect": ["READY", "ISPF", "IKJ56455I"],
                "display_seconds": 6,
            },
            {
                "title": "Enter ISPF",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/ISPF (Human Interaction Desktop)**\n\nWe type `ISPF` to launch the Interactive System Productivity Facility, then navigate to RFE (Review Front End) \u2014 the primary interactive tool on TK5 for dataset management and development.\n\n**Broken Assumption:** *\"Processes are short-lived.\"* This TSO address space persists. Your identity context survives across panels, utilities, and program invocations. The address space may run for hours or days.\n\n**Assessment Question Q4:** TSO/ISPF enforces panel-level access. But the real enforcement is RACF, which every subsystem queries. ISPF is the interface; RACF is the authority engine.\n\nYou've now traversed: VTAM (session) \u2192 TSO (identity) \u2192 ISPF/RFE (interaction).",
                "actions": [
                    {"type": "string", "value": "ISPF"}, {"type": "enter"}, {"type": "wait", "seconds": 3},
                    {"type": "home"},
                    {"type": "string", "value": "=M"}, {"type": "enter"}, {"type": "wait", "seconds": 2},
                    {"type": "string", "value": "1"}, {"type": "enter"}, {"type": "wait", "seconds": 3},
                ],
                "expect": ["RFE", "OPTION", "UTILITIES", "BROWSE", "EDIT"],
                "display_seconds": 6,
            },
            {
                "title": "Dataset List (3.4)",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (Dataset Navigation)**\n\nOption 3.4 opens the Dataset List utility within RFE. Datasets are the z/OS storage model \u2014 not a filesystem.\n\n**Key concept:** z/OS does not have `/etc`, `/var`, or config files in the Unix sense. Everything is stored in datasets: cataloged, named objects with structure (PDS, sequential, VSAM). Access is controlled by RACF profiles, not filesystem permissions.\n\n**Assessment Question Q5:** If you are importing the assumption that \"there is a filesystem hierarchy,\" stop. z/OS uses a flat catalog namespace with profile-based protection.",
                "actions": [
                    {"type": "string", "value": "3"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "4"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["DSLIST", "DATA SET", "DATASET"],
                "display_seconds": 5,
            },
            {
                "title": "Browse System Datasets",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (System Configuration)**\n\nWe enter `SYS1` as the dataset name level to browse system datasets. `SYS1.PARMLIB`, `SYS1.PROCLIB`, and `SYS1.LINKLIB` are critical system datasets.\n\n**Key concept:** System configuration lives in datasets like `SYS1.PARMLIB` \u2014 not in `/etc`. These datasets define system behavior: started tasks, security policy, IPL parameters. Access to them is controlled by RACF dataset profiles.\n\n**Assessment Question Q4:** RACF enforces access to system datasets. Anyone who can UPDATE `SYS1.PARMLIB` can alter system behavior.",
                "actions": [{"type": "string", "value": "SYS1"}, {"type": "enter"}, {"type": "wait", "seconds": 3}],
                "expect": ["SYS1", "PARMLIB", "PROCLIB", "LINKLIB"],
                "display_seconds": 5,
            },
            {
                "title": "Return to RFE",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE**\n\nPF3 navigates back through the RFE panel stack: dataset list \u2192 Utilities \u2192 RFE main menu. The session persists \u2014 identity is still bound, the address space is still alive. We haven't \"logged out\" by going back.\n\n**Key concept:** Navigation does not destroy sessions. The address space continues. This is fundamentally different from web applications where navigating away may end a session.",
                "actions": [{"type": "pf", "value": "3"}, {"type": "wait", "seconds": 2}, {"type": "pf", "value": "3"}, {"type": "wait", "seconds": 2}, {"type": "pf", "value": "3"}, {"type": "wait", "seconds": 2}],
                "expect": ["RFE", "OPTION", "UTILITIES"],
                "display_seconds": 4,
            },
            {
                "title": "TSO Command Line",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Command Execution)**\n\nWe exit ISPF to reach the TSO READY prompt \u2014 raw command execution under the bound identity.\n\n**Key concept:** Every command you execute here runs under the authority of HERC01. There is no `sudo` \u2014 your authority is determined by your RACF profile, not by how you invoke a command.",
                "actions": [{"type": "pf", "value": "3"}, {"type": "wait", "seconds": 2}, {"type": "pf", "value": "3"}, {"type": "wait", "seconds": 3}],
                "expect": ["READY", "TSO", "COMMAND", "ENTER"],
                "display_seconds": 4,
            },
            {
                "title": "LISTALC \u2014 Identity Context",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Identity in Action)**\n\nThe `LISTALC STATUS` command shows every dataset allocated to this TSO session. These allocations reveal the identity context \u2014 what resources are bound to HERC01's address space.\n\n**Key concept:** Dataset allocations are the footprint of your identity. STEPLIB, ISPLLIB, ISPTLIB \u2014 these control which programs and panels are available. The allocations were established when you logged in, and they persist for the lifetime of your session.\n\n**Assessment Question Q1:** Identity was bound at TSO logon. Here we see the *resource context* of that identity \u2014 which libraries, which datasets, which execution environment.",
                "actions": [{"type": "string", "value": "LISTALC STATUS"}, {"type": "enter"}, {"type": "wait", "seconds": 3}],
                "expect": ["LISTALC", "HERC01", "SYS1", "KEEP", "STEPLIB", "ISPF", "ALLOC"],
                "display_seconds": 6,
            },
            {
                "title": "Logoff \u2014 Return to VTAM",
                "control_plane": "vtam",
                "narration": "**Control Plane: VTAM (Session Unbinding)**\n\nThe `LOGOFF` command unbinds the identity from the session. We return to the anonymous VTAM session fabric.\n\n**Session lifecycle summary:**\n1. **VTAM** \u2014 anonymous session established\n2. **TSO** \u2014 identity bound via logon (HERC01)\n3. **ISPF** \u2014 interactive desktop, dataset navigation\n4. **RACF** \u2014 identity inspection, authority model revealed\n5. **VTAM** \u2014 identity unbound, back to anonymous\n\n**Key takeaway:** Three control planes were traversed. Identity was bound at TSO, enforced by RACF, and the session fabric (VTAM) existed before and after authentication. This layered model is fundamentally different from modern systems where login and session management are unified.",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM", "LOGON"],
                "display_seconds": 8,
            },
        ],
    },
    "deferred-exec": {
        "title": "Deferred Execution: JCL \u2192 JES",
        "steps": [
            {
                "title": "Connect & Login",
                "control_plane": "tso",
                "narration": "**Setup: Establishing Identity**\n\nWe connect and log in to TSO. The deferred execution walkthrough requires an authenticated session because JES associates submitted jobs with the submitter's identity.\n\n**Key concept:** JES is the deferred execution broker. It doesn't execute work directly \u2014 it queues, schedules, and manages output. Every job carries the identity of its submitter.",
                "actions": [
                    {"type": "connect"},
                    {"type": "wait", "seconds": 2},
                    {"type": "tso_login"},
                ],
                "expect": ["READY", "ISPF", "IKJ"],
                "display_seconds": 4,
            },
            {
                "title": "Enter ISPF and Navigate to SDSF",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (Deferred Execution)**\n\nSDSF (System Display and Search Facility) is the window into JES. It shows active jobs, input queues, output queues, and system activity.\n\n**Broken Assumption:** *\"Work executes immediately.\"* On z/OS, work is *declared* via JCL, *queued* by JES, and *scheduled* by the system. The time between submission and execution may be seconds, minutes, hours, or days.\n\n**Assessment Question Q3:** Everything in JES executes later than expected.",
                "actions": [
                    {"type": "string", "value": "ISPF"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "home"},
                    {"type": "string", "value": "=S"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["SDSF", "DISPLAY", "ACTIVE", "PRIMARY"],
                "display_seconds": 5,
            },
            {
                "title": "Display Active Jobs",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (Active Address Spaces)**\n\nThe `DA` (Display Active) command shows all active address spaces. These are long-running processes: started tasks, TSO sessions, batch jobs, and system services.\n\n**Key concept:** These address spaces may have been running for days or months. CICS regions, JES itself, VTAM \u2014 these are persistent. The identity context bound to each one was set at startup and persists for the lifetime of the address space.\n\n**Assessment Question Q2:** Authority was evaluated when each address space started. Changes to RACF profiles after startup may not take effect until restart.",
                "actions": [
                    {"type": "string", "value": "DA"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["ACTIVE", "JOBS", "JOBNAME", "OWNERID"],
                "display_seconds": 6,
            },
            {
                "title": "Display Output Queue",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (Job Output)**\n\nThe output queue shows completed jobs and their spool output. Each entry preserves the identity of the submitter.\n\n**Key concept:** JES output is the audit trail of deferred execution. The job's identity, class, priority, return code, and output are all preserved. This is evidence of who submitted what, and when it ran.\n\n**Assessment Question Q3:** These jobs ran later than they were submitted. The identity bound at submission time governed the execution \u2014 even if the submitter logged off in the meantime.",
                "actions": [
                    {"type": "home"},
                    {"type": "eraseeof"},
                    {"type": "string", "value": "H"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["HELD", "OUTPUT", "QUEUE", "JOBNAME"],
                "display_seconds": 6,
            },
            {
                "title": "Return & Logoff",
                "control_plane": "vtam",
                "narration": "**Summary: Deferred Execution**\n\nJES demonstrates that z/OS separates work *declaration* from work *execution*. This has profound security implications:\n\n1. **Identity persists:** The submitter's identity governs execution, not the current user\n2. **Authority is evaluated at submission:** RACF checks happen when the job is submitted, not when it runs\n3. **Audit trail exists:** Every job's identity, input, and output are preserved in JES\n\nOn z/OS, you must ask: \"What work was declared but hasn't run yet? Under whose authority will it run?\"",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM"],
                "display_seconds": 6,
            },
        ],
    },
    "system-inspection": {
        "title": "System Inspection: Configuration & Procedures",
        "steps": [
            {
                "title": "Connect & Login to TSO",
                "control_plane": "tso",
                "narration": "**Setup: Establishing Identity**\n\nWe connect and log in to TSO. This walkthrough inspects the system configuration model \u2014 how z/OS defines its runtime through datasets, procedures, and catalogs.",
                "actions": [
                    {"type": "connect"},
                    {"type": "wait", "seconds": 2},
                    {"type": "tso_login"},
                ],
                "expect": ["READY", "ISPF", "IKJ"],
                "display_seconds": 4,
            },
            {
                "title": "TSO STATUS \u2014 Active Sessions",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Session Discovery)**\n\nThe `STATUS` command shows all active TSO sessions. Each session represents a bound identity \u2014 an address space with a userid attached.\n\n**Key concept:** Unlike `who` on Unix, TSO STATUS shows persistent address spaces. These sessions may have been active for hours or days. Each one has its own identity context, dataset allocations, and authority scope.\n\n**Assessment Question Q1:** Every active session here has an identity bound to it. The identity was established at logon and persists for the lifetime of the address space.",
                "actions": [
                    {"type": "string", "value": "STATUS"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["STATUS", "HERC", "LOGON", "READY"],
                "display_seconds": 5,
            },
            {
                "title": "TSO TIME \u2014 System Clock",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (System Context)**\n\nThe `TIME` command shows the system clock and your session CPU time. This is a simple command, but it demonstrates an important principle: every command you execute runs under your bound identity.\n\n**Key concept:** There is no `sudo`. When HERC01 types `TIME`, the system executes it as HERC01. When HERC01 types any command, RACF evaluates whether HERC01 has authority. Authority is continuous, not one-time.\n\n**Assessment Question Q2:** Authority is evaluated at every command invocation. The TIME command succeeds because it requires no special authority. Other commands may not.",
                "actions": [
                    {"type": "string", "value": "TIME"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["TIME", "READY"],
                "display_seconds": 5,
            },
            {
                "title": "Enter ISPF",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/ISPF/RFE (Interactive Desktop)**\n\nWe enter ISPF and navigate to RFE (Review Front End) to explore the system configuration. RFE provides structured access to datasets, utilities, and system management tools on TK5.\n\n**Key concept:** RFE is a panel-driven interface. Navigation follows a hierarchical menu structure. But the real enforcement is RACF \u2014 RFE presents options, RACF decides whether you can use them.",
                "actions": [
                    {"type": "string", "value": "ISPF"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "home"},
                    {"type": "string", "value": "=M"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                    {"type": "string", "value": "1"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["RFE", "OPTION", "UTILITIES"],
                "display_seconds": 4,
            },
            {
                "title": "System Procedures (SYS1.PROCLIB)",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (System Configuration)**\n\nWe navigate to the dataset list and examine `SYS1.PROCLIB` \u2014 the library of started task procedures. Every address space on the system (JES, VTAM, TSO, catalogs) is defined by a PROC in this library.\n\n**Broken Assumption:** *\"Services are configured in config files.\"* On z/OS, services are defined as JCL procedures in datasets. The PROC defines what program runs, what datasets it uses, and what authority it needs. There is no `/etc/init.d` or `systemd` \u2014 there are PROCs.\n\n**Assessment Question Q4:** The system's runtime behavior is defined by PROCs in SYS1.PROCLIB. Access to this dataset is controlled by RACF. Anyone who can UPDATE SYS1.PROCLIB can alter what services run at IPL.",
                "actions": [
                    {"type": "string", "value": "3"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "4"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "SYS1.PROCLIB"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["SYS1", "PROCLIB", "MEMBER"],
                "display_seconds": 6,
            },
            {
                "title": "Return to ISPF",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE**\n\nWe return through RFE and ISPF. The session persists \u2014 identity still bound, address space still alive.\n\n**Assessment Question Q5:** If you are importing the assumption that \"browsing means no risk,\" stop. On z/OS, the ability to *read* system datasets reveals the entire system configuration. Knowing which PROCs exist, which programs they invoke, and which datasets they reference is the first step in understanding the system's trust boundaries.",
                "actions": [
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["READY"],
                "display_seconds": 4,
            },
            {
                "title": "Logoff",
                "control_plane": "vtam",
                "narration": "**Summary: System Inspection**\n\n1. **TSO STATUS** revealed active sessions \u2014 each with a bound identity\n2. **Every command** executes under your identity \u2014 no sudo, no elevation\n3. **SYS1.PROCLIB** defines the system's services \u2014 access = control\n4. **RACF enforces** who can read, update, or alter system configuration\n\n**Assessment Questions Answered:**\n- Q1: Identity is bound at TSO logon and persists through all commands\n- Q2: Authority is evaluated at every command and resource access\n- Q4: RACF enforces access to system configuration datasets\n- Q5: \"Config files are in /etc\" is wrong \u2014 configuration lives in PDS members",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM"],
                "display_seconds": 7,
            },
        ],
    },
    "auth-model": {
        "title": "Authorization Model: RACF",
        "steps": [
            {
                "title": "Connect & Login to TSO",
                "control_plane": "tso",
                "narration": "**Setup: Establishing Identity for RACF Demonstration**\n\nWe connect and log in to demonstrate the RACF authorization model. RACF is not a subsystem you \"enter\" \u2014 it is the continuous authorization engine that every other subsystem queries.",
                "actions": [
                    {"type": "connect"},
                    {"type": "wait", "seconds": 2},
                    {"type": "tso_login"},
                ],
                "expect": ["READY", "ISPF", "IKJ"],
                "display_seconds": 4,
            },
            {
                "title": "LISTALC \u2014 Session Resource Context",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Identity in Action)**\n\n`LISTALC STATUS` shows every dataset allocated to this TSO session. These allocations reveal the identity context \u2014 what resources are bound to HERC01's address space.\n\n**Key concept:** Your RACF profile is the source of truth for your identity. Every subsystem \u2014 TSO, CICS, JES, batch \u2014 queries RACF to determine what you may do. The dataset allocations you see here were established at logon based on your RACF profile.\n\n**Assessment Question Q1:** Identity is defined in RACF profiles. The allocations here are the *result* of that identity being bound to this session.",
                "actions": [
                    {"type": "string", "value": "LISTALC STATUS"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["LISTALC", "SYS1", "KEEP", "STEPLIB", "ALLOC"],
                "display_seconds": 6,
            },
            {
                "title": "LISTCAT \u2014 Dataset Catalog Entries",
                "control_plane": "racf",
                "narration": "**Control Plane: RACF (Resource Protection)**\n\n`LISTCAT` shows catalog entries for system datasets. The catalog is the namespace \u2014 but access to the datasets is controlled by RACF profiles, not the catalog itself.\n\n**Broken Assumption:** *\"There is a root user.\"* RACF profiles grant specific access levels (NONE, READ, UPDATE, CONTROL, ALTER) to specific userids and groups. Even the most privileged user is governed by profiles \u2014 authority is distributed, not concentrated.\n\n**Assessment Question Q4:** RACF is the subsystem that enforces policy for datasets. The catalog tells you what exists; RACF tells you who may access it.",
                "actions": [
                    {"type": "string", "value": "LISTCAT ENT('SYS1.PARMLIB')"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["LISTCAT", "SYS1", "PARMLIB", "NONVSAM", "VOLSER"],
                "display_seconds": 6,
            },
            {
                "title": "PROFILE \u2014 TSO Session Profile",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Identity Attributes)**\n\nThe `PROFILE` command shows your TSO session settings: PREFIX (your default HLQ), message class, and other session parameters.\n\n**Key concept:** The PREFIX setting determines your default dataset high-level qualifier. When you reference a dataset without quotes, TSO prepends your PREFIX. This is identity-driven behavior \u2014 your PREFIX is typically your userid.\n\n**Assessment Question Q5:** If you are importing the assumption that \"paths are absolute,\" stop. On z/OS, unqualified dataset names are resolved relative to your identity's PREFIX. The same dataset reference means different things for different users.",
                "actions": [
                    {"type": "string", "value": "PROFILE"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                ],
                "expect": ["PROFILE", "PREFIX", "HERC01", "CHAR"],
                "display_seconds": 6,
            },
            {
                "title": "Logoff",
                "control_plane": "vtam",
                "narration": "**Summary: RACF Authorization Model**\n\n1. **RACF is continuous:** Every resource access triggers a RACF check\n2. **Profiles, not roles:** Access is defined per-resource, not per-role\n3. **Authority is distributed:** No single account has unconditional access\n4. **ICH messages are evidence:** Every authorization decision generates an ICH message in the system log\n\n**Assessment Questions Answered:**\n- Q1: Identity is bound in RACF profiles\n- Q2: Authority is evaluated at every resource access\n- Q4: RACF is the subsystem that enforces policy\n- Q5: \"Roles define access\" and \"there is a root user\" are incorrect assumptions",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM"],
                "display_seconds": 7,
            },
        ],
    },
    "dataset-model": {
        "title": "Dataset Model: PDS, Members & Catalogs",
        "steps": [
            {
                "title": "Connect & Login",
                "control_plane": "tso",
                "narration": "**Setup: Establishing Identity**\n\nWe connect and log in to TSO. This walkthrough explores the z/OS storage model \u2014 datasets, partitioned data sets (PDS), members, and the catalog structure that replaces a traditional filesystem.",
                "actions": [
                    {"type": "connect"},
                    {"type": "wait", "seconds": 2},
                    {"type": "tso_login"},
                ],
                "expect": ["READY", "ISPF", "IKJ"],
                "display_seconds": 4,
            },
            {
                "title": "Enter ISPF",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/ISPF/RFE (Dataset Interface)**\n\nWe enter ISPF and navigate to RFE (Review Front End) for structured access to the dataset model. Unlike a Unix filesystem with directories and files, z/OS uses a flat catalog namespace. Datasets are named objects \u2014 not files in directories.\n\n**Broken Assumption:** *\"There is a filesystem hierarchy.\"* z/OS has no `/home`, `/etc`, `/var`. Instead, datasets are named with dot-separated qualifiers: `SYS1.PARMLIB`, `HERC01.MY.DATA`. The catalog maps names to physical locations on DASD volumes.",
                "actions": [
                    {"type": "string", "value": "ISPF"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "home"},
                    {"type": "string", "value": "=M"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 2},
                    {"type": "string", "value": "1"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["RFE", "OPTION", "UTILITIES"],
                "display_seconds": 5,
            },
            {
                "title": "Dataset List \u2014 User Datasets",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (User Dataset Namespace)**\n\nWe navigate to RFE option 3.4 (DSLIST) and list datasets under our userid prefix `HERC01`. Every user has a dataset namespace rooted at their userid.\n\n**Key concept:** The high-level qualifier (HLQ) is identity-driven. `HERC01.*` datasets belong to this identity. RACF controls who can create, read, update, or delete datasets under each HLQ. This is the storage equivalent of identity binding.",
                "actions": [
                    {"type": "string", "value": "3"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "4"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "HERC01"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["HERC01", "DSLIST", "DATA SET"],
                "display_seconds": 6,
            },
            {
                "title": "System Dataset Namespace",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (System Namespace)**\n\nNow we list `SYS1` datasets \u2014 the system namespace. These datasets define the operating system's behavior: `SYS1.PARMLIB` (configuration), `SYS1.PROCLIB` (service definitions), `SYS1.LINKLIB` (system programs).\n\n**Key concept:** There is no `/etc/init.d` or `systemd`. The entire system configuration model lives in datasets. Access to these datasets is controlled by RACF \u2014 anyone who can UPDATE `SYS1.PARMLIB` can alter system behavior at the next IPL.",
                "actions": [
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 1},
                    {"type": "home"},
                    {"type": "tab"},
                    {"type": "eraseeof"},
                    {"type": "string", "value": "SYS1"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["SYS1", "PARMLIB", "PROCLIB"],
                "display_seconds": 6,
            },
            {
                "title": "Browse PDS Members \u2014 SYS1.PARMLIB",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO/RFE (PDS Structure)**\n\nA Partitioned Data Set (PDS) is like a directory with members. `SYS1.PARMLIB` is a PDS containing system configuration members \u2014 each member is a named configuration object.\n\n**Key concept:** PDS members are the closest analog to \"config files.\" But they are not files in a filesystem \u2014 they are records in a dataset. `IEASYSxx` controls IPL parameters, `SMFPRMxx` controls auditing, `IKJTSOxx` controls TSO behavior. Each member name follows a naming convention that the operating system resolves at IPL time.\n\n**Broken Assumption:** *\"Config files are in /etc.\"* On z/OS, you must know which PDS contains the configuration, which member is active, and which suffix (`xx`) the system is using. This is not discoverable through filesystem traversal.",
                "actions": [
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 1},
                    {"type": "home"},
                    {"type": "tab"},
                    {"type": "eraseeof"},
                    {"type": "string", "value": "SYS1.PARMLIB"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["SYS1.PARMLIB", "MEMBER", "NAME"],
                "display_seconds": 7,
            },
            {
                "title": "Catalog Structure \u2014 LISTCAT",
                "control_plane": "tso",
                "narration": "**Control Plane: TSO (Catalog Discovery)**\n\nWe return to TSO and use `LISTCAT` to examine catalog entries. The catalog is the master index \u2014 it maps dataset names to physical DASD locations.\n\n**Key concept:** The catalog is the namespace authority. Without a catalog entry, a dataset is \"uncataloged\" and can only be accessed by specifying its physical volume. The master catalog (`SYS1.MASTER.CATALOG`) chains to user catalogs, creating a federated namespace.\n\nThis is fundamentally different from a filesystem's inode table. Catalogs can be restructured, datasets can move between volumes, and the same physical data can be cataloged under different names.",
                "actions": [
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 2},
                    {"type": "pf", "value": "3"},
                    {"type": "wait", "seconds": 3},
                    {"type": "string", "value": "LISTCAT ENT('SYS1.LINKLIB')"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["LISTCAT", "SYS1", "LINKLIB", "NONVSAM"],
                "display_seconds": 7,
            },
            {
                "title": "Logoff",
                "control_plane": "vtam",
                "narration": "**Summary: Dataset Model**\n\n1. **No filesystem hierarchy:** z/OS uses a flat catalog namespace with dot-separated qualifiers\n2. **PDS = directory:** Partitioned Data Sets contain named members (config, source, JCL)\n3. **HLQ = identity:** Your high-level qualifier ties datasets to your identity\n4. **Catalogs = namespace:** The catalog maps names to physical volumes\n5. **RACF = access control:** Dataset profiles determine who can read, write, or alter\n\nThe dataset model is the foundation of z/OS storage. Every assessment must understand how data is organized, protected, and accessed \u2014 because there are no files to `find`, no permissions to `ls -la`, and no paths to traverse.",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM"],
                "display_seconds": 8,
            },
        ],
    },
    "address-spaces": {
        "title": "Address Space Anatomy: What's Running",
        "steps": [
            {
                "title": "Connect & Login",
                "control_plane": "tso",
                "narration": "**Setup: Establishing Identity**\n\nWe connect and log in to TSO. This walkthrough examines address spaces \u2014 the z/OS equivalent of processes. Unlike Unix processes, address spaces are persistent, identity-bound, and managed by the system rather than user-initiated fork/exec.",
                "actions": [
                    {"type": "connect"},
                    {"type": "wait", "seconds": 2},
                    {"type": "tso_login"},
                ],
                "expect": ["READY", "ISPF", "IKJ"],
                "display_seconds": 4,
            },
            {
                "title": "ISPF \u2192 SDSF (System Activity)",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (System Display)**\n\nSDSF (System Display and Search Facility) provides visibility into the system's runtime state. We navigate to SDSF to examine what's running.\n\n**Key concept:** SDSF is the operator's window into the system. It shows active address spaces, job queues, system messages, and resource utilization. This is the z/OS equivalent of `ps`, `top`, and `journalctl` combined \u2014 but it shows *address spaces*, not processes.",
                "actions": [
                    {"type": "string", "value": "ISPF"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                    {"type": "home"},
                    {"type": "string", "value": "=S"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["SDSF", "PRIMARY", "DISPLAY"],
                "display_seconds": 5,
            },
            {
                "title": "Display Active \u2014 Running Address Spaces",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (Active Address Spaces)**\n\nThe `DA` (Display Active) panel shows every active address space on the system. Each row represents a long-running entity: JES2, VTAM, TSO sessions, catalog address spaces, and system services.\n\n**Broken Assumption:** *\"Processes are short-lived.\"* These address spaces may have been running since IPL (the last system boot). They are persistent services, not spawned-and-exited processes. Each one has an identity bound at startup time.\n\n**Key concept:** The JOBNAME column shows the address space name. The OWNERID shows the identity. Started tasks (STC) run under system identities. TSO users run under their own userid. Batch jobs carry the submitter's identity.",
                "actions": [
                    {"type": "string", "value": "DA"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["ACTIVE", "JOBNAME", "OWNERID", "STEPNAME"],
                "display_seconds": 7,
            },
            {
                "title": "Display Input Queue \u2014 Pending Work",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (Deferred Execution)**\n\nThe `I` (Input) panel shows jobs waiting to execute. These jobs have been submitted but not yet started.\n\n**Key concept:** This is deferred execution in action. Each job in this queue was declared via JCL and submitted by a user or automated process. The identity of the submitter is preserved \u2014 when the job eventually runs, it runs under that identity.\n\n**Broken Assumption:** *\"Work executes immediately.\"* These jobs may wait for initiators, resources, or scheduling constraints. The gap between submission and execution is a security-relevant window.",
                "actions": [
                    {"type": "home"},
                    {"type": "eraseeof"},
                    {"type": "string", "value": "I"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["INPUT", "QUEUE", "JOBNAME", "JOBID"],
                "display_seconds": 6,
            },
            {
                "title": "System Log \u2014 Operator Messages",
                "control_plane": "jes",
                "narration": "**Control Plane: JES (System Messages)**\n\nThe `LOG` panel shows the system log \u2014 operator messages, IPL messages, and system events. This is the audit trail of system activity.\n\n**Key concept:** The system log records everything: IPL events, device activations, security violations (ICH messages), job completions, and operator commands. This is the primary source of evidence for any assessment. Unlike Unix syslog, the system log is a JES-managed spool dataset that persists across sessions.\n\nLook for ICH messages (RACF security decisions), IEF messages (job lifecycle), and IKJ messages (TSO events).",
                "actions": [
                    {"type": "home"},
                    {"type": "eraseeof"},
                    {"type": "string", "value": "LOG"},
                    {"type": "enter"},
                    {"type": "wait", "seconds": 3},
                ],
                "expect": ["LOG", "SYSLOG", "SYSTEM"],
                "display_seconds": 7,
            },
            {
                "title": "Return & Logoff",
                "control_plane": "vtam",
                "narration": "**Summary: Address Space Anatomy**\n\n1. **Address spaces, not processes:** z/OS runs persistent address spaces that may live for weeks or months\n2. **Identity is bound at startup:** Each address space carries the identity of its creator/submitter\n3. **Deferred execution:** Jobs wait in queues before running \u2014 the submission-execution gap matters\n4. **System log is evidence:** Every security decision, job lifecycle event, and system change is logged\n5. **No `ps` equivalent:** SDSF shows the system's runtime state, but it shows much more than a process list\n\nUnderstanding what's running \u2014 and under whose authority \u2014 is the foundation of any mainframe assessment.",
                "actions": [{"type": "tso_logoff"}],
                "expect": ["LOGOFF", "VTAM"],
                "display_seconds": 8,
            },
        ],
    },
}


# Assessment question mapping per walkthrough step
# Maps walkthrough name → step index → list of Q's addressed
_WT_QUESTIONS: dict[str, dict[int, list[str]]] = {
    "session-stack": {
        1: ["Q1", "Q5"],   # VTAM Entry — identity not bound, ports != exposure
        2: ["Q1", "Q2"],   # TSO Logon — identity binding + authentication
        3: ["Q4", "Q5"],   # Enter ISPF — RACF enforces, processes not short-lived
        4: ["Q5"],          # Dataset List — no filesystem
        5: ["Q4"],          # Browse System Datasets — RACF enforces
        8: ["Q1"],          # LISTALC — identity context
    },
    "deferred-exec": {
        1: ["Q3", "Q5"],    # ISPF→SDSF — work executes later
        2: ["Q2"],          # Display Active — authority at startup
        3: ["Q3"],          # Display Output — deferred execution audit
        4: ["Q3"],          # Return & Logoff — summary
    },
    "system-inspection": {
        1: ["Q1"],          # TSO STATUS — active sessions, bound identities
        2: ["Q2"],          # TSO TIME — authority at every command
        4: ["Q4", "Q5"],    # SYS1.PROCLIB — RACF enforces, not config files
        5: ["Q5"],          # Return — browsing reveals config
        6: ["Q1", "Q2", "Q4", "Q5"],  # Logoff summary
    },
    "auth-model": {
        1: ["Q1"],          # LISTALC — identity context
        2: ["Q4", "Q5"],    # LISTCAT — RACF enforces, not roles
        3: ["Q5"],          # PROFILE — PREFIX, not absolute paths
        4: ["Q1", "Q2", "Q4", "Q5"],  # Logoff summary
    },
    "dataset-model": {
        1: ["Q5"],          # Enter ISPF — no filesystem
        2: ["Q1", "Q5"],    # User datasets — HLQ = identity
        3: ["Q4", "Q5"],    # System datasets — RACF enforces
        4: ["Q5"],          # PDS members — not config files
        5: ["Q5"],          # LISTCAT — catalog structure
        6: ["Q1", "Q4", "Q5"],  # Logoff summary
    },
    "address-spaces": {
        2: ["Q2", "Q5"],    # Display Active — persistent, identity-bound
        3: ["Q3"],          # Input queue — deferred execution
        4: ["Q2"],          # System log — audit trail
        5: ["Q1", "Q2", "Q3", "Q5"],  # Logoff summary
    },
}


class WalkthroughRunner:
    """Server-side autonomous walkthrough executor."""

    def __init__(self):
        self.running = False
        self.paused = False
        self.current_step = 0
        self.total_steps = 0
        self.current_title = ""
        self.current_narration = ""
        self.current_screen = ""
        self.current_control_plane = ""
        self.walkthrough_name = ""
        self.log: list[dict] = []
        self.finished = False
        self.error: str | None = None
        self.display_seconds = 4.0  # default per-step display time
        self.questions_answered: set = set()
        self._thread: threading.Thread | None = None

    def start(self, name: str, target: str, speed: float = 4.0):
        # If the thread died but running flag is stale, reset it
        if self.running and (self._thread is None or not self._thread.is_alive()):
            self.running = False
        if self.running:
            return
        # Wait for any previous thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        # Clean up any leftover TSO session before starting fresh
        try:
            if connection.connected:
                self._tso_logoff()
        except Exception:
            pass
        self.running = True
        self.paused = False
        self.finished = False
        self.error = None
        self.current_step = 0
        self.current_screen = ""
        self.log = []
        self.questions_answered = set()
        self.display_seconds = speed
        self._thread = threading.Thread(
            target=self._run, args=(name, target), daemon=True
        )
        self._thread.start()

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def get_status(self) -> dict:
        # Auto-clear stale running flag if thread is dead
        if self.running and (self._thread is None or not self._thread.is_alive()):
            self.running = False
        return {
            "running": self.running,
            "paused": self.paused,
            "step": self.current_step,
            "total": self.total_steps,
            "title": self.current_title,
            "narration": self.current_narration,
            "screen": self.current_screen,
            "control_plane": self.current_control_plane,
            "walkthrough_name": self.walkthrough_name,
            "finished": self.finished,
            "error": self.error,
            "log": list(self.log),
            "questions_answered": sorted(self.questions_answered),
        }

    # ---- internal ----

    def _run(self, name: str, target: str):
        script = WALKTHROUGH_SCRIPTS.get(name)
        if not script:
            self.error = f"Unknown walkthrough: {name}"
            self.running = False
            return

        self.walkthrough_name = script["title"]
        steps = script["steps"]
        self.total_steps = len(steps)

        step_qs_map = _WT_QUESTIONS.get(name, {})

        for idx, step in enumerate(steps):
            if not self.running:
                break

            # Wait while paused
            while self.paused and self.running:
                _time.sleep(0.25)

            if not self.running:
                break

            self.current_step = idx
            self.current_title = step["title"]
            self.current_control_plane = step.get("control_plane", "")
            self.current_narration = ""  # narration comes after actions

            step_qs = step_qs_map.get(idx, [])

            # Phase 1: Append log entry with header only — narration
            # will be filled after actions complete so it aligns with
            # the settled terminal screen
            log_entry = {
                "step": idx,
                "title": step["title"],
                "control_plane": step.get("control_plane", ""),
                "narration": "",
                "executing": True,
                "questions": step_qs,
            }
            self.log.append(log_entry)

            # Execute actions, reading screen after each one so
            # the terminal view updates live during execution
            try:
                for action in step.get("actions", []):
                    if not self.running:
                        break
                    while self.paused and self.running:
                        _time.sleep(0.25)
                    if not self.running:
                        break
                    self._exec_action(action, target)
                    # Update screen after every screen-changing action
                    if action["type"] not in ("wait",):
                        try:
                            self.current_screen = read_screen()
                        except Exception:
                            self.current_screen = connection.current_screen or ""
            except Exception as e:
                self.error = f"Step {idx + 1} failed: {e}"
                self.running = False
                break

            # Final screen read after all actions settle
            try:
                self.current_screen = read_screen()
            except Exception:
                self.current_screen = connection.current_screen or ""

            # Phase 2: Actions done — set narration aligned with screen
            log_entry["narration"] = step["narration"]
            log_entry["executing"] = False
            self.current_narration = step["narration"]

            # Track assessment questions answered
            for q in step_qs:
                self.questions_answered.add(q)

            # Display pause — user reads narration with settled screen
            step_display = step.get("display_seconds", self.display_seconds)
            wait_end = _time.time() + step_display
            while _time.time() < wait_end and self.running:
                while self.paused and self.running:
                    _time.sleep(0.25)
                _time.sleep(0.2)

        if self.running:
            self.finished = True
        self.running = False

    def _exec_action(self, action: dict, target: str):
        atype = action["type"]
        if atype == "connect":
            if not connection.connected:
                connect_mainframe(target)
                _time.sleep(1)
        elif atype == "string":
            send_terminal_key("string", action["value"])
        elif atype == "enter":
            send_terminal_key("enter")
            _time.sleep(0.5)  # let terminal process the command
        elif atype == "clear":
            send_terminal_key("clear")
            _time.sleep(0.3)
        elif atype == "pf":
            send_terminal_key("pf", str(action["value"]))
            _time.sleep(0.5)
        elif atype == "tab":
            send_terminal_key("tab")
        elif atype == "home":
            send_terminal_key("home")
        elif atype == "eraseeof":
            send_terminal_key("eraseeof")
        elif atype == "wait":
            _time.sleep(action.get("seconds", 1))

        elif atype == "tso_login":
            userid = action.get("userid", "HERC01")
            password = action.get("password", "CUL8TR")
            self._tso_login(userid, password, target)

        elif atype == "tso_logoff":
            self._tso_logoff()

    # ---- TSO login/logoff helpers ----

    def _read_screen_safe(self) -> str:
        """Read current screen, returning empty string on failure."""
        try:
            return read_screen()
        except Exception:
            return connection.current_screen or ""

    def _tso_logoff(self):
        """Clean logoff: exit any ISPF panels, then LOGOFF."""
        # PF3 several times to exit SDSF / ISPF / panels
        for _ in range(6):
            try:
                send_terminal_key("pf", "3")
                _time.sleep(1.5)
            except Exception:
                break
            screen = self._read_screen_safe()
            if "READY" in screen or "LOGON" in screen or "VTAM" in screen:
                break
        _time.sleep(1)
        # Check if at READY prompt or need LOGOFF
        screen = self._read_screen_safe()
        if "LOGON" in screen or "VTAM" in screen or "USS" in screen:
            return  # Already at VTAM, no logoff needed
        send_terminal_key("string", "LOGOFF")
        send_terminal_key("enter")
        _time.sleep(2)

    def _tso_login(self, userid: str, password: str, target: str):
        """Robust TSO login handling USERID-IN-USE and stuck states."""
        max_attempts = 3
        for attempt in range(max_attempts):
            if not self.running:
                return

            # Ensure connected
            if not connection.connected:
                connect_mainframe(target)
                _time.sleep(1)

            # Read current screen to determine state
            screen = self._read_screen_safe()
            self.current_screen = screen

            # If stuck at IKJ error/reenter prompt, clear to reset
            if "IKJ56712" in screen or "IKJ56703" in screen or "REENTER" in screen:
                send_terminal_key("clear")
                _time.sleep(1)
                screen = self._read_screen_safe()
                self.current_screen = screen

            # If stuck at "ENTER LOGON OR LOGOFF", send LOGOFF first
            if "LOGON OR LOGOFF" in screen or "IKJ56400" in screen:
                send_terminal_key("string", "LOGOFF")
                send_terminal_key("enter")
                _time.sleep(2)
                send_terminal_key("clear")
                _time.sleep(1)
                screen = self._read_screen_safe()

            # If already at READY prompt (already logged in), we're done
            if "READY" in screen:
                self.current_screen = screen
                return

            # If at ISPF, we're already logged in — done
            if "ISPF" in screen and "PRIMARY" in screen:
                self.current_screen = screen
                return

            # If at SDSF or other ISPF panel, already logged in
            if "SDSF" in screen or "ISPF" in screen:
                self.current_screen = screen
                return

            # If at TSO logon panel (asking for userid), skip "TSO" command
            if "ENTER USERID" in screen or "IKJ56700" in screen or "LOGON" in screen.upper().split("LOGOFF")[0]:
                send_terminal_key("string", userid)
                send_terminal_key("enter")
                _time.sleep(2)
                screen = self._read_screen_safe()
                self.current_screen = screen
            else:
                # Navigate to TSO from VTAM
                send_terminal_key("clear")
                _time.sleep(1)
                send_terminal_key("string", "TSO")
                send_terminal_key("enter")
                _time.sleep(2)
                screen = self._read_screen_safe()
                self.current_screen = screen

                # Enter userid
                send_terminal_key("string", userid)
                send_terminal_key("enter")
                _time.sleep(2)
                screen = self._read_screen_safe()
                self.current_screen = screen

            # Check for "USERID IN USE"
            if "IN USE" in screen or "IKJ56425" in screen:
                # Try RECONNECT to existing session
                _time.sleep(1)
                # We're stuck at "ENTER LOGON OR LOGOFF" — send LOGON RECONNECT
                send_terminal_key("string", f"LOGON {userid} RECONNECT")
                send_terminal_key("enter")
                _time.sleep(3)
                screen = self._read_screen_safe()
                self.current_screen = screen

                # If RECONNECT asks for password
                if "PASSWORD" in screen or "IKJ56476" in screen:
                    send_terminal_key("string", password)
                    send_terminal_key("enter")
                    _time.sleep(3)
                    screen = self._read_screen_safe()
                    self.current_screen = screen

                # Reconnected — now normalize and logoff cleanly
                self._tso_logoff()
                _time.sleep(1)
                screen = self._read_screen_safe()
                self.current_screen = screen

                # Retry fresh login on next iteration
                continue

            # Check for "LOGON OR LOGOFF" stuck state (different path)
            if "LOGON OR LOGOFF" in screen or "IKJ56400" in screen:
                send_terminal_key("string", "LOGOFF")
                send_terminal_key("enter")
                _time.sleep(2)
                continue

            # Normal flow: enter password
            if "PASSWORD" in screen or "IKJ56476" in screen or "IKJ56700" in screen:
                send_terminal_key("string", password)
                send_terminal_key("enter")
                _time.sleep(3)
                screen = self._read_screen_safe()
                self.current_screen = screen

                # Verify login succeeded
                if "READY" in screen or "ISPF" in screen or "IKJ56455" in screen:
                    return  # Success

                # If still problematic, retry
                if "IN USE" in screen or "LOGON OR LOGOFF" in screen:
                    continue

                # Accept whatever state we're in
                return

            # If we got READY directly (no password prompt on TK5 sometimes)
            if "READY" in screen:
                return

        # All attempts exhausted
        self.error = f"TSO login failed after {max_attempts} attempts"


# Singleton runner
_walkthrough_runner = WalkthroughRunner()


@app.post("/api/walkthrough/start")
async def api_walkthrough_start(request: Request):
    """Start an autonomous walkthrough."""
    global _walkthrough_runner
    data = await request.json()
    name = data.get("name", "session-stack")
    target = data.get("target", "localhost:3270")
    speed = float(data.get("speed", 4.0))

    script = WALKTHROUGH_SCRIPTS.get(name)
    if not script:
        return JSONResponse({"success": False, "error": f"Unknown walkthrough: {name}"})

    # Stop any previous run and clean up before starting
    if _walkthrough_runner.running:
        _walkthrough_runner.stop()

    _walkthrough_runner.start(name, target, speed)
    return JSONResponse({"success": True, "walkthrough": script["title"]})


@app.post("/api/walkthrough/stop")
async def api_walkthrough_stop():
    """Stop the running walkthrough."""
    _walkthrough_runner.stop()
    return JSONResponse({"success": True})


@app.post("/api/walkthrough/pause")
async def api_walkthrough_pause():
    """Toggle pause/resume on the walkthrough."""
    if _walkthrough_runner.paused:
        _walkthrough_runner.resume()
    else:
        _walkthrough_runner.pause()
    return JSONResponse({"success": True, "paused": _walkthrough_runner.paused})


@app.get("/api/walkthrough/status")
async def api_walkthrough_status():
    """Get current walkthrough status (polled by frontend)."""
    return JSONResponse(_walkthrough_runner.get_status())


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


# ============================================================================
# Trust Graph API Endpoints
# ============================================================================

@app.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """Trust Graph visualization page"""
    return templates.TemplateResponse("graph.html", {"request": request})


@app.get("/api/graph/stats")
async def api_graph_stats():
    """Get trust graph statistics"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available", "nodes": 0, "edges": 0})
    graph = get_trust_graph()
    stats = graph.get_stats()
    return JSONResponse(stats)


@app.get("/api/graph/nodes")
async def api_graph_nodes():
    """Get all nodes in the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"nodes": []})
    graph = get_trust_graph()
    nodes = [
        {
            "id": node.id,
            "type": node.node_type,
            "label": node.label,
            "properties": node.properties,
            "first_seen": node.first_seen,
            "last_seen": node.last_seen
        }
        for node in graph.nodes.values()
    ]
    return JSONResponse({"nodes": nodes})


@app.get("/api/graph/edges")
async def api_graph_edges():
    """Get all edges in the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"edges": []})
    graph = get_trust_graph()
    edges = [
        {
            "id": edge.id,
            "type": edge.edge_type,
            "source": edge.source_id,
            "target": edge.target_id,
            "properties": edge.properties,
            "confidence": edge.confidence
        }
        for edge in graph.edges.values()
    ]
    return JSONResponse({"edges": edges})


@app.get("/api/graph/query/{query_name}")
async def api_graph_query(query_name: str, request: Request):
    """Run a named query against the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available", "results": []})

    graph = get_trust_graph()
    params = dict(request.query_params)

    try:
        results = graph.query(query_name, **params)
        return JSONResponse({
            "query": query_name,
            "results": results,
            "count": len(results)
        })
    except ValueError as e:
        return JSONResponse({"error": str(e), "results": []}, status_code=400)


@app.post("/api/graph/ingest-jcl")
async def api_graph_ingest_jcl(request: Request):
    """Ingest JCL text into the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()
    jcl_text = data.get("jcl", "")
    source = data.get("source", "manual_upload")

    if not jcl_text:
        return JSONResponse({"error": "No JCL provided"}, status_code=400)

    # Parse JCL first, then update graph
    jcl_parsed = parse_jcl(jcl_text)
    graph = get_trust_graph()
    result = update_graph_from_jcl(graph, jcl_parsed, {"type": "jcl", "source": source})

    # Broadcast graph update
    await broadcast_graph_update("jcl_ingested", result)

    return JSONResponse(result)


@app.post("/api/graph/ingest-sysout")
async def api_graph_ingest_sysout(request: Request):
    """Ingest SYSOUT text into the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()
    sysout_text = data.get("sysout", "")
    source = data.get("source", "manual_upload")

    if not sysout_text:
        return JSONResponse({"error": "No SYSOUT provided"}, status_code=400)

    # Parse SYSOUT first, then update graph
    sysout_parsed = parse_sysout(sysout_text)
    graph = get_trust_graph()
    result = update_graph_from_sysout(graph, sysout_parsed, {"type": "sysout", "source": source})

    # Broadcast graph update
    await broadcast_graph_update("sysout_ingested", result)

    return JSONResponse(result)


@app.post("/api/graph/ingest-screen")
async def api_graph_ingest_screen(request: Request):
    """Ingest current screen into the trust graph"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    if not connection.connected:
        return JSONResponse({"error": "Not connected to mainframe"}, status_code=400)

    screen_text = read_screen()
    graph = get_trust_graph()
    result = update_graph_from_screen(graph, screen_text, f"{connection.host}:{connection.port}")

    # Broadcast graph update
    await broadcast_graph_update("screen_ingested", result)

    return JSONResponse(result)


@app.get("/api/graph/export/json")
async def api_graph_export_json():
    """Export trust graph as JSON"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    return JSONResponse(graph.export_json())


@app.get("/api/graph/export/dot")
async def api_graph_export_dot():
    """Export trust graph as Graphviz DOT format"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    dot_content = graph.export_dot()
    return JSONResponse({"dot": dot_content})


@app.get("/api/graph/export/d3")
async def api_graph_export_d3():
    """Export trust graph in D3.js-compatible format"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    return JSONResponse(graph.export_d3_json())


@app.post("/api/graph/finding")
async def api_graph_generate_finding(request: Request):
    """Generate a defensive finding from graph analysis"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)

    data = await request.json()
    graph = get_trust_graph()

    finding = generate_finding(
        title=data.get("title", "Untitled Finding"),
        evidence=data.get("evidence", []),
        reasoning=data.get("reasoning", ""),
        confidence=data.get("confidence", "MEDIUM"),
        graph_context=data.get("graph_context", {})
    )

    return JSONResponse(finding)


@app.delete("/api/graph/clear")
async def api_graph_clear():
    """Clear the trust graph (for testing)"""
    if not GRAPH_AVAILABLE:
        return JSONResponse({"error": "Trust graph not available"}, status_code=400)
    graph = get_trust_graph()
    graph.nodes.clear()
    graph.edges.clear()
    graph.save()

    await broadcast_graph_update("graph_cleared", {"nodes": 0, "edges": 0})
    return JSONResponse({"success": True, "message": "Graph cleared"})


# Graph WebSocket for real-time updates
async def broadcast_graph_update(event_type: str, data: dict):
    """Broadcast graph update to all graph WebSocket clients"""
    if not graph_websocket_clients:
        return

    message = json.dumps({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })

    disconnected = set()
    for ws in graph_websocket_clients:
        try:
            await ws.send_text(message)
        except:
            disconnected.add(ws)

    graph_websocket_clients.difference_update(disconnected)


@app.websocket("/ws/graph")
async def websocket_graph(websocket: WebSocket):
    """WebSocket for real-time graph visualization updates"""
    await websocket.accept()
    graph_websocket_clients.add(websocket)

    try:
        # Send initial graph state
        if GRAPH_AVAILABLE:
            graph = get_trust_graph()
            await websocket.send_text(json.dumps({
                "type": "initial_state",
                "data": graph.export_d3_json()
            }))

        while True:
            # Handle client messages (e.g., query requests)
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "query":
                query_name = msg.get("query_name", "")
                params = msg.get("params", {})
                if GRAPH_AVAILABLE:
                    graph = get_trust_graph()
                    try:
                        results = graph.query(query_name, **params)
                        await websocket.send_text(json.dumps({
                            "type": "query_result",
                            "query": query_name,
                            "results": results
                        }))
                    except ValueError as e:
                        await websocket.send_text(json.dumps({
                            "type": "query_error",
                            "error": str(e)
                        }))

            elif msg.get("type") == "refresh":
                if GRAPH_AVAILABLE:
                    graph = get_trust_graph()
                    await websocket.send_text(json.dumps({
                        "type": "refresh",
                        "data": graph.export_d3_json()
                    }))

    except WebSocketDisconnect:
        graph_websocket_clients.discard(websocket)
    except Exception as e:
        graph_websocket_clients.discard(websocket)


# ============================================================================
# Terminal WebSocket
# ============================================================================

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
