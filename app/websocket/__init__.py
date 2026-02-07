"""
WebSocket Handlers

Real-time communication for terminal and graph updates.
"""

from .handlers import (
    websocket_terminal,
    websocket_graph,
    broadcast_screen,
    broadcast_graph_update,
    websocket_clients,
    graph_websocket_clients,
)
