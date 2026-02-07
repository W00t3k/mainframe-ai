# WebSocket Handlers (`app/websocket/`)

Real-time communication handlers for terminal and graph updates.

## Handlers

### `handlers.py`

**Terminal WebSocket** (`/ws/terminal`)
- Real-time screen updates from TN3270 emulator
- Keyboard input forwarding
- Connection state management

**Graph WebSocket** (`/ws/graph`)
- Trust graph live updates
- Node/edge addition notifications
- Query result streaming

## Client Management

The module maintains sets of connected clients:
- `terminal_clients` - WebSocket connections for terminal
- `graph_clients` - WebSocket connections for graph visualization

## Broadcast Functions

- `broadcast_screen_update()` - Send screen data to all terminal clients
- `broadcast_graph_update()` - Send graph changes to all graph clients
