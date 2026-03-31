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
        connection, connect_mainframe, disconnect_mainframe,
        send_terminal_key, get_screen_data, get_cached_screen_data, read_screen
    )
    AGENT_TOOLS_AVAILABLE = True
except ImportError:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    connect_mainframe = None
    disconnect_mainframe = None
    send_terminal_key = None
    read_screen = lambda: "[Not connected]"
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


@router.post("/reset-session")
async def api_terminal_reset_session():
    """Logoff any TSO session and return to a clean VTAM screen."""
    import time as _rst_time
    if not AGENT_TOOLS_AVAILABLE or not connection or not connection.connected:
        return JSONResponse({"success": False, "error": "Not connected"})

    try:
        # Exit any ISPF panels via PF3
        for _ in range(6):
            screen = read_screen()
            if any(tok in screen for tok in ("READY", "LOGON", "VTAM", "USS")):
                break
            send_terminal_key("pf", "3")
            _rst_time.sleep(1.5)

        screen = read_screen()
        if "READY" in screen:
            send_terminal_key("string", "LOGOFF")
            send_terminal_key("enter")
            _rst_time.sleep(2)
            screen = read_screen()

        if "IKJ56400" in screen or "ENTER LOGON OR LOGOFF" in screen:
            send_terminal_key("home")
            _rst_time.sleep(0.2)
            send_terminal_key("eraseeof")
            _rst_time.sleep(0.2)
            send_terminal_key("string", "LOGOFF")
            send_terminal_key("enter")
            _rst_time.sleep(2)

        reconnect_target = f"{connection.host}:{connection.port}" if connection and connection.host else "localhost:3270"
        disconnect_mainframe()
        _rst_time.sleep(1)
        connect_mainframe(reconnect_target)
        _rst_time.sleep(2)
        screen = read_screen()

        return JSONResponse({"success": True, "message": "Session reset — clean VTAM screen", "screen": screen})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
