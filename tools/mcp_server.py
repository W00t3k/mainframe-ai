#!/usr/bin/env python3
"""
Mainframe AI Assistant - MCP Server
Model Context Protocol server for Ollama Desktop integration.

Exposes mainframe tools and trust graph as MCP tools and resources.

Usage:
    python mcp_server.py

Ollama Desktop config (~/.config/ollama/ollama_desktop_config.json):
{
    "mcpServers": {
        "mainframe-assistant": {
            "command": "python",
            "args": ["/path/to/mainframe_ai_assistant/mcp_server.py"]
        }
    }
}
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        ResourceContents,
        TextResourceContents,
    )
    MCP_AVAILABLE = True
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    MCP_AVAILABLE = False
    sys.exit(1)

# Import our tools and graph
try:
    from agent_tools import (
        connection, TN3270_AVAILABLE,
        connect_mainframe, disconnect_mainframe, read_screen,
        send_terminal_key, get_cached_screen_data, capture_screen,
        get_connection_status, execute_tool_async
    )
    TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"Agent tools import error: {e}", file=sys.stderr)
    TOOLS_AVAILABLE = False

try:
    from trust_graph import get_trust_graph
    from graph_tools import (
        classify_panel, extract_identifiers, parse_jcl, parse_sysout,
        update_graph_from_jcl, update_graph_from_screen, generate_finding
    )
    GRAPH_AVAILABLE = True
except ImportError as e:
    print(f"Trust graph import error: {e}", file=sys.stderr)
    GRAPH_AVAILABLE = False

try:
    from rag_engine import get_rag_engine
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Create MCP server
server = Server("mainframe-assistant")


# ============================================================================
# MCP Tools
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools."""
    tools = []

    if TOOLS_AVAILABLE:
        tools.extend([
            Tool(
                name="connect_mainframe",
                description="Connect to a mainframe via TN3270 terminal emulation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Host and port (e.g., 'localhost:3270' or 'mainframe.example.com:23')"
                        }
                    },
                    "required": ["target"]
                }
            ),
            Tool(
                name="disconnect_mainframe",
                description="Disconnect from the current mainframe session",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="read_screen",
                description="Read the current 3270 terminal screen content",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="send_text",
                description="Type text on the 3270 terminal",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to type"
                        }
                    },
                    "required": ["text"]
                }
            ),
            Tool(
                name="send_enter",
                description="Press the Enter key on the 3270 terminal",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="send_pf_key",
                description="Press a PF (Program Function) key on the 3270 terminal",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "integer",
                            "description": "PF key number (1-24)",
                            "minimum": 1,
                            "maximum": 24
                        }
                    },
                    "required": ["key"]
                }
            ),
            Tool(
                name="send_clear",
                description="Press the Clear key on the 3270 terminal",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="send_tab",
                description="Press the Tab key to move to the next input field",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="capture_screen",
                description="Capture and save the current screen for later analysis",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "note": {
                            "type": "string",
                            "description": "Optional note about this capture"
                        }
                    }
                }
            ),
            Tool(
                name="get_connection_status",
                description="Check the current mainframe connection status",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ])

    if RAG_AVAILABLE:
        tools.append(
            Tool(
                name="query_knowledge_base",
                description="Search the mainframe knowledge base for relevant information",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query about mainframe concepts, commands, or errors"
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Number of results to return (default: 3)",
                            "default": 3
                        }
                    },
                    "required": ["query"]
                }
            )
        )

    if GRAPH_AVAILABLE:
        tools.extend([
            Tool(
                name="classify_panel",
                description="Classify a 3270 screen into a panel type (ISPF, CICS, TSO, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_text": {
                            "type": "string",
                            "description": "Screen text to classify (optional - uses current screen if not provided)"
                        }
                    }
                }
            ),
            Tool(
                name="extract_identifiers",
                description="Extract mainframe identifiers (datasets, programs, jobs, etc.) from screen text",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "screen_text": {
                            "type": "string",
                            "description": "Screen text to analyze (optional - uses current screen if not provided)"
                        }
                    }
                }
            ),
            Tool(
                name="parse_jcl",
                description="Parse JCL text and extract job structure, programs, and datasets",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jcl_text": {
                            "type": "string",
                            "description": "JCL text to parse"
                        }
                    },
                    "required": ["jcl_text"]
                }
            ),
            Tool(
                name="ingest_to_graph",
                description="Ingest current screen or provided text into the trust graph",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content_type": {
                            "type": "string",
                            "enum": ["screen", "jcl", "sysout"],
                            "description": "Type of content to ingest"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to ingest (optional for screen - uses current screen)"
                        }
                    },
                    "required": ["content_type"]
                }
            ),
            Tool(
                name="query_graph",
                description="Run a named query against the trust graph",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_name": {
                            "type": "string",
                            "enum": [
                                "paths_to_job_submit",
                                "library_load_chain",
                                "shared_datasets",
                                "reachable_transactions",
                                "multi_library_programs",
                                "edit_browse_panels",
                                "dataset_conflicts",
                                "boundary_crossings",
                                "abend_chains",
                                "shortest_to_sensitive"
                            ],
                            "description": "Name of the query to run"
                        }
                    },
                    "required": ["query_name"]
                }
            ),
            Tool(
                name="get_graph_stats",
                description="Get statistics about the trust graph (node/edge counts by type)",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ])

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute an MCP tool."""

    result = None

    # Connection tools
    if name == "connect_mainframe":
        if not TOOLS_AVAILABLE or not TN3270_AVAILABLE:
            result = {"success": False, "error": "TN3270 not available"}
        else:
            success, message = connect_mainframe(arguments.get("target", "localhost:3270"))
            result = {"success": success, "message": message}

    elif name == "disconnect_mainframe":
        if not TOOLS_AVAILABLE:
            result = {"success": False, "error": "Tools not available"}
        else:
            message = disconnect_mainframe()
            result = {"success": True, "message": message}

    elif name == "read_screen":
        if not TOOLS_AVAILABLE:
            result = {"connected": False, "screen": "[Tools not available]"}
        elif not connection.connected:
            result = {"connected": False, "screen": "[Not connected]"}
        else:
            screen = read_screen()
            result = {"connected": True, "screen": screen}

    elif name == "send_text":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            res = send_terminal_key("string", arguments.get("text", ""))
            result = res

    elif name == "send_enter":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            res = send_terminal_key("enter")
            result = res

    elif name == "send_pf_key":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            key = arguments.get("key", 3)
            res = send_terminal_key("pf", str(key))
            result = res

    elif name == "send_clear":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            res = send_terminal_key("clear")
            result = res

    elif name == "send_tab":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            res = send_terminal_key("tab")
            result = res

    elif name == "capture_screen":
        if not TOOLS_AVAILABLE or not connection.connected:
            result = {"success": False, "error": "Not connected"}
        else:
            cap = capture_screen(arguments.get("note", ""))
            result = cap

    elif name == "get_connection_status":
        if not TOOLS_AVAILABLE:
            result = {"connected": False, "tn3270_available": False}
        else:
            result = get_connection_status()

    # RAG tools
    elif name == "query_knowledge_base":
        if not RAG_AVAILABLE:
            result = {"results": [], "error": "RAG not available"}
        else:
            engine = get_rag_engine()
            query = arguments.get("query", "")
            n_results = arguments.get("n_results", 3)
            results = await engine.query_simple(query, n_results)
            result = {"results": results}

    # Graph tools
    elif name == "classify_panel":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available"}
        else:
            screen_text = arguments.get("screen_text")
            if not screen_text and TOOLS_AVAILABLE and connection.connected:
                screen_text = read_screen()
            if screen_text:
                result = classify_panel(screen_text)
            else:
                result = {"error": "No screen text provided and not connected"}

    elif name == "extract_identifiers":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available"}
        else:
            screen_text = arguments.get("screen_text")
            if not screen_text and TOOLS_AVAILABLE and connection.connected:
                screen_text = read_screen()
            if screen_text:
                result = extract_identifiers(screen_text)
            else:
                result = {"error": "No screen text provided and not connected"}

    elif name == "parse_jcl":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available"}
        else:
            jcl_text = arguments.get("jcl_text", "")
            result = parse_jcl(jcl_text)

    elif name == "ingest_to_graph":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available"}
        else:
            graph = get_trust_graph()
            content_type = arguments.get("content_type", "screen")
            content = arguments.get("content")

            if content_type == "screen":
                if not content and TOOLS_AVAILABLE and connection.connected:
                    content = read_screen()
                if content:
                    result = update_graph_from_screen(
                        graph, content,
                        f"{connection.host}:{connection.port}" if connection.connected else "unknown"
                    )
                else:
                    result = {"error": "No screen content"}
            elif content_type == "jcl":
                if content:
                    result = update_graph_from_jcl(graph, content, "mcp_upload")
                else:
                    result = {"error": "No JCL content provided"}
            elif content_type == "sysout":
                if content:
                    from graph_tools import update_graph_from_sysout
                    result = update_graph_from_sysout(graph, content, "mcp_upload")
                else:
                    result = {"error": "No SYSOUT content provided"}

    elif name == "query_graph":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available", "results": []}
        else:
            graph = get_trust_graph()
            query_name = arguments.get("query_name", "")
            try:
                results = graph.query(query_name)
                result = {"query": query_name, "results": results, "count": len(results)}
            except ValueError as e:
                result = {"error": str(e), "results": []}

    elif name == "get_graph_stats":
        if not GRAPH_AVAILABLE:
            result = {"error": "Graph tools not available"}
        else:
            graph = get_trust_graph()
            result = graph.get_stats()

    else:
        result = {"error": f"Unknown tool: {name}"}

    # Return result as TextContent
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str)
    )]


# ============================================================================
# MCP Resources
# ============================================================================

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available MCP resources."""
    resources = []

    if TOOLS_AVAILABLE:
        resources.extend([
            Resource(
                uri="mainframe://screen",
                name="Current 3270 Screen",
                description="The current terminal screen content",
                mimeType="text/plain"
            ),
            Resource(
                uri="mainframe://status",
                name="Connection Status",
                description="Current mainframe connection status",
                mimeType="application/json"
            ),
        ])

    if RAG_AVAILABLE:
        resources.append(
            Resource(
                uri="mainframe://rag/stats",
                name="RAG Statistics",
                description="Knowledge base statistics",
                mimeType="application/json"
            )
        )

    if GRAPH_AVAILABLE:
        resources.extend([
            Resource(
                uri="mainframe://graph/stats",
                name="Trust Graph Statistics",
                description="Trust graph node and edge counts",
                mimeType="application/json"
            ),
            Resource(
                uri="mainframe://graph/export",
                name="Trust Graph Export",
                description="Full trust graph in JSON format",
                mimeType="application/json"
            ),
        ])

    return resources


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read an MCP resource."""

    if uri == "mainframe://screen":
        if TOOLS_AVAILABLE and connection.connected:
            screen = read_screen()
            return screen
        return "[Not connected]"

    elif uri == "mainframe://status":
        if TOOLS_AVAILABLE:
            status = get_connection_status()
            return json.dumps(status, indent=2)
        return json.dumps({"connected": False, "error": "Tools not available"})

    elif uri == "mainframe://rag/stats":
        if RAG_AVAILABLE:
            engine = get_rag_engine()
            stats = engine.get_stats()
            return json.dumps(stats, indent=2)
        return json.dumps({"error": "RAG not available"})

    elif uri == "mainframe://graph/stats":
        if GRAPH_AVAILABLE:
            graph = get_trust_graph()
            stats = graph.get_stats()
            return json.dumps(stats, indent=2)
        return json.dumps({"error": "Graph not available"})

    elif uri == "mainframe://graph/export":
        if GRAPH_AVAILABLE:
            graph = get_trust_graph()
            export = graph.export_json()
            return json.dumps(export, indent=2, default=str)
        return json.dumps({"error": "Graph not available"})

    return f"Unknown resource: {uri}"


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run the MCP server."""
    print("Starting Mainframe AI Assistant MCP Server...", file=sys.stderr)
    print(f"  Tools available: {TOOLS_AVAILABLE}", file=sys.stderr)
    print(f"  TN3270 available: {TN3270_AVAILABLE if TOOLS_AVAILABLE else False}", file=sys.stderr)
    print(f"  RAG available: {RAG_AVAILABLE}", file=sys.stderr)
    print(f"  Graph available: {GRAPH_AVAILABLE}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
