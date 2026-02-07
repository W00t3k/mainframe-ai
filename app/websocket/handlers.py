"""
WebSocket Handlers

Handles real-time WebSocket connections for terminal and graph visualization.
"""

import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

# WebSocket client sets
websocket_clients = set()
graph_websocket_clients = set()

# Import agent_tools
try:
    from agent_tools import (
        connection, connect_mainframe, disconnect_mainframe,
        send_terminal_key, get_screen_data, get_cached_screen_data
    )
    AGENT_TOOLS_AVAILABLE = True
except ImportError:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    get_screen_data = lambda: {"connected": False, "screen": "", "screen_html": "", "rows": 24, "cols": 80}
    get_cached_screen_data = lambda: {"connected": False, "screen": "", "screen_html": "", "rows": 24, "cols": 80}
    connect_mainframe = lambda t: (False, "Agent tools not available")
    disconnect_mainframe = lambda: "Not connected"
    send_terminal_key = lambda *args: {"success": False, "error": "Agent tools not available"}

# Import graph modules
try:
    from trust_graph import get_trust_graph
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    get_trust_graph = None


async def broadcast_screen():
    """Broadcast screen update to all WebSocket clients."""
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


async def broadcast_graph_update(event_type: str, data: dict):
    """Broadcast graph update to all graph WebSocket clients."""
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


async def websocket_terminal(websocket: WebSocket):
    """WebSocket handler for terminal communication."""
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
    except Exception:
        websocket_clients.discard(websocket)


async def websocket_graph(websocket: WebSocket):
    """WebSocket handler for real-time graph visualization updates."""
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
    except Exception:
        graph_websocket_clients.discard(websocket)
