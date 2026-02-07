# API Routes (`app/routes/`)

This directory contains all FastAPI route handlers organized by feature.

## Route Modules

| File | Prefix | Description |
|------|--------|-------------|
| `chat.py` | `/api/chat` | Chat message handling |
| `graph.py` | `/api/graph` | Trust graph operations |
| `labs.py` | `/api/labs` | Security lab exercises |
| `pages.py` | `/` | HTML page rendering |
| `rag.py` | `/api/rag` | RAG document management |
| `recon.py` | `/api/recon` | TN3270 enumeration/recon |
| `scanner.py` | `/api/scanner` | Network scanning |
| `screencaps.py` | `/api/screencaps` | Screen capture management |
| `system.py` | `/api/system` | System/mainframe control |
| `terminal.py` | `/api/terminal` | TN3270 terminal I/O |
| `tutor.py` | `/api/tutor` | Red Team Tutor API |
| `walkthrough.py` | `/api/walkthrough` | Autonomous walkthroughs |

## Route Registration

Routes are registered in `__init__.py` via the `register_routes(app)` function which includes each router with its prefix.

## Adding New Routes

1. Create a new file (e.g., `myfeature.py`)
2. Define a router: `router = APIRouter(tags=["myfeature"])`
3. Add routes using `@router.get()`, `@router.post()`, etc.
4. Register in `__init__.py`
