"""
Agentic Lab API Routes

Endpoints for the goal-based agentic lab runner.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["agentic"])


@router.get("/labs")
async def list_agentic_labs():
    """List available agentic labs."""
    from app.constants.agentic_labs import AGENTIC_LABS

    labs = []
    for lab_id, lab in AGENTIC_LABS.items():
        # Skip disabled labs
        if lab.get("disabled"):
            continue
        labs.append({
            "id": lab_id,
            "title": lab["title"],
            "description": lab.get("description", ""),
            "steps": len(lab["steps"]),
            "agentic": True,
        })

    return JSONResponse({"labs": labs})


@router.post("/start")
async def start_agentic_lab(request: Request):
    """Start an agentic lab."""
    from app.services.agentic_runner import get_agentic_runner

    data = await request.json()
    lab_name = data.get("name")
    target = data.get("target", "localhost:3270")
    explain_mode = bool(data.get("explain_mode", False))

    if not lab_name:
        return JSONResponse({"success": False, "error": "Missing lab name"})

    runner = get_agentic_runner()
    runner.start(lab_name, target, explain_mode=explain_mode)

    return JSONResponse({"success": True, "lab": lab_name})


@router.post("/stop")
async def stop_agentic_lab():
    """Stop the running agentic lab."""
    from app.services.agentic_runner import get_agentic_runner

    runner = get_agentic_runner()
    runner.stop()

    return JSONResponse({"success": True})


@router.post("/pause")
async def pause_agentic_lab():
    """Pause/resume the agentic lab."""
    from app.services.agentic_runner import get_agentic_runner

    runner = get_agentic_runner()
    if runner.paused:
        runner.resume()
        return JSONResponse({"success": True, "paused": False})
    else:
        runner.pause()
        return JSONResponse({"success": True, "paused": True})


@router.post("/explain_mode")
async def toggle_explain_mode(request: Request):
    """Enable/disable auto-pause-on-data-screens mid-run."""
    from app.services.agentic_runner import get_agentic_runner

    data = await request.json()
    enabled = bool(data.get("enabled", False))
    runner = get_agentic_runner()
    runner.set_explain_mode(enabled)
    return JSONResponse({"success": True, "explain_mode": enabled})


@router.get("/status")
async def agentic_lab_status():
    """Get current status of the agentic lab."""
    from app.services.agentic_runner import get_agentic_runner

    runner = get_agentic_runner()
    status = runner.get_status()

    return JSONResponse(status)
