# `app/websocket/` — Real-Time Communication

WebSocket handlers for live terminal and graph updates.

## Endpoints

| Path | Purpose |
|------|---------|
| `/ws/terminal` | Screen updates pushed to all connected browsers |
| `/ws/graph` | Trust graph node/edge changes broadcast live |

## How It Works

- `handlers.py` maintains client sets (`terminal_clients`, `graph_clients`)
- `broadcast_screen_update()` — pushes screen HTML to all terminal watchers
- `broadcast_graph_update()` — pushes graph diffs to all graph viewers
- Clients auto-reconnect on disconnect
