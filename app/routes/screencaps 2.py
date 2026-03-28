"""
Screen Capture API Routes

Endpoints for capturing and managing terminal screenshots.
"""

import os
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_config

router = APIRouter(tags=["screencaps"])
config = get_config()

# In-memory screencap store
screencaps = []

# Import agent_tools functions
try:
    from agent_tools import connection, read_screen
    AGENT_TOOLS_AVAILABLE = True
except ImportError:
    AGENT_TOOLS_AVAILABLE = False
    connection = None
    read_screen = lambda: "[Not connected]"


def load_screencaps_from_disk():
    """Load screencaps from saved files."""
    global screencaps
    if not os.path.exists(config.SCREENCAPS_DIR):
        return

    for filename in os.listdir(config.SCREENCAPS_DIR):
        if filename.startswith("screencap_") and filename.endswith(".txt"):
            filepath = os.path.join(config.SCREENCAPS_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    lines = f.readlines()
                    host = lines[0].replace("Host: ", "").strip() if lines else "unknown"
                    time_str = lines[1].replace("Time: ", "").strip() if len(lines) > 1 else ""
                    screen = "".join(lines[3:]) if len(lines) > 3 else ""

                    cap_id = filename.replace("screencap_", "").replace(".txt", "")

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


@router.post("/screencap")
async def api_capture_screen(request: Request):
    """Capture and save current screen."""
    global screencaps

    if not AGENT_TOOLS_AVAILABLE or not connection or not connection.connected:
        return JSONResponse({"success": False, "error": "Not connected"})

    import time
    screen = read_screen()
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
    filepath = os.path.join(config.SCREENCAPS_DIR, filename)
    with open(filepath, "w") as f:
        f.write(f"Host: {host}\n")
        f.write(f"Time: {cap['time']}\n")
        f.write("=" * 80 + "\n")
        f.write(screen)

    return JSONResponse({"success": True, "screencap": cap, "file": filename})


@router.get("/screencaps")
async def api_get_screencaps():
    """Get all captured screens."""
    if not screencaps:
        load_screencaps_from_disk()
    return JSONResponse({"captures": screencaps})


@router.get("/screencap/{cap_id}")
async def api_get_screencap(cap_id: str):
    """Get a specific screencap."""
    for cap in screencaps:
        if cap["id"] == cap_id:
            return JSONResponse(cap)
    return JSONResponse({"error": "Screencap not found"}, status_code=404)


@router.delete("/screencap/{cap_id}")
async def api_delete_screencap(cap_id: str):
    """Delete a screencap."""
    global screencaps
    for i, cap in enumerate(screencaps):
        if cap["id"] == cap_id:
            screencaps.pop(i)
            filename = f"screencap_{cap_id}.txt"
            filepath = os.path.join(config.SCREENCAPS_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            return JSONResponse({"success": True})
    return JSONResponse({"error": "Screencap not found"}, status_code=404)
