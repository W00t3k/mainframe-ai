"""
Terminal API Routes

Endpoints for TN3270 terminal operations.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.schemas import TerminalKeyRequest

router = APIRouter(tags=["terminal"])

# Import agent_tools functions
try:
    from agent_tools import (
        connect_mainframe, disconnect_mainframe,
        send_terminal_key, get_screen_data, get_cached_screen_data
    )
    AGENT_TOOLS_AVAILABLE = True
except ImportError:
    AGENT_TOOLS_AVAILABLE = False
    connect_mainframe = None
    disconnect_mainframe = None
    send_terminal_key = None
    get_screen_data = lambda: {"connected": False, "screen": "", "screen_html": "", "rows": 24, "cols": 80}
    get_cached_screen_data = lambda: {"connected": False, "screen": "", "screen_html": "", "rows": 24, "cols": 80}


@router.get("/screen")
async def api_screen():
    """Get current screen data with color HTML."""
    data = get_cached_screen_data()
    return JSONResponse(data)


@router.post("/key")
async def api_terminal_key(request: TerminalKeyRequest):
    """Send a key to the terminal."""
    if not AGENT_TOOLS_AVAILABLE:
        return JSONResponse({"success": False, "error": "Agent tools not available"})
    
    result = send_terminal_key(request.key_type, request.value)
    return JSONResponse(result)


@router.post("/connect")
async def api_terminal_connect(request: Request):
    """Connect to a mainframe."""
    if not AGENT_TOOLS_AVAILABLE:
        return JSONResponse({"success": False, "message": "Agent tools not available"})
    
    data = await request.json()
    target = data.get("target", "localhost:3270")
    success, message = connect_mainframe(target)
    
    return JSONResponse({
        "success": success,
        "message": message,
        "screen_data": get_screen_data() if success else None
    })


@router.post("/disconnect")
async def api_terminal_disconnect():
    """Disconnect from the mainframe."""
    if not AGENT_TOOLS_AVAILABLE:
        return JSONResponse({"success": True, "message": "Not connected"})
    
    message = disconnect_mainframe()
    return JSONResponse({"success": True, "message": message})
