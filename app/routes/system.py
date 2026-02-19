"""
System Routes

Provides system-level operations like restart and mainframe control.
"""

import os
import sys
import signal
import subprocess
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import get_config, get_gpu_status, update_model

router = APIRouter()

# TK5 mainframe paths
TK5_DIR = Path(__file__).parent.parent.parent / "tk5" / "mvs-tk5"


# ============ GPU Status ============

@router.get("/gpu/status")
async def gpu_status():
    """
    Get GPU detection results, current tier, and model recommendations.
    Returns VRAM, driver info, recommended models, and Ollama options.
    """
    config = get_config()
    status = get_gpu_status()
    status["current_model"] = config.OLLAMA_MODEL
    status["gpu_enabled"] = config.GPU_ENABLED
    return status


@router.post("/gpu/switch-model")
async def switch_model(model: str):
    """
    Switch the active Ollama model.
    Use /api/gpu/status to see recommended models for your GPU.
    """
    if not model or not model.strip():
        return JSONResponse(
            content={"error": "Model name required"},
            status_code=400
        )
    config = get_config()
    old_model = config.OLLAMA_MODEL
    update_model(model.strip())
    return {
        "status": "switched",
        "old_model": old_model,
        "new_model": model.strip(),
        "gpu_enabled": config.GPU_ENABLED,
        "gpu_tier": config.GPU_TIER,
    }

TK5_START = TK5_DIR / "start_tk5.sh"
TK5_STOP = TK5_DIR / "stop_tk5.sh"


@router.post("/restart")
async def restart_application():
    """
    Signal that the application should be restarted.
    The frontend will reload the page - actual restart requires manual server restart.
    """
    # Clear any cached state
    try:
        from agent_tools import disconnect_mainframe
        disconnect_mainframe()
    except Exception:
        pass
    
    return JSONResponse(
        content={
            "status": "ready", 
            "message": "Connections cleared. Reload the page to continue.",
            "action": "reload"
        },
        status_code=200
    )


@router.post("/shutdown")
async def shutdown_application(background_tasks: BackgroundTasks):
    """
    Shutdown the application gracefully.
    """
    def _shutdown():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    
    background_tasks.add_task(_shutdown)
    return JSONResponse(
        content={"status": "shutting_down", "message": "Application is shutting down..."},
        status_code=202
    )


# ============ Mainframe Control ============

def _check_hercules_running() -> bool:
    """Check if Hercules (TK5) is running."""
    try:
        result = subprocess.run(["pgrep", "-x", "hercules"], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


@router.get("/mainframe/status")
async def mainframe_status():
    """Check if TK5 mainframe is running."""
    running = _check_hercules_running()
    return {
        "running": running,
        "status": "online" if running else "offline",
        "tk5_available": TK5_START.exists()
    }


@router.post("/mainframe/start")
async def start_mainframe(background_tasks: BackgroundTasks):
    """Start the TK5 mainframe."""
    if not TK5_START.exists():
        return JSONResponse(
            content={"error": "TK5 start script not found", "path": str(TK5_START)},
            status_code=404
        )
    
    if _check_hercules_running():
        return JSONResponse(
            content={"status": "already_running", "message": "Mainframe is already running"},
            status_code=200
        )
    
    def _start():
        subprocess.run(["bash", str(TK5_START)], cwd=str(TK5_DIR))
    
    background_tasks.add_task(_start)
    return JSONResponse(
        content={"status": "starting", "message": "Mainframe is starting... Wait ~30 seconds for full initialization."},
        status_code=202
    )


@router.post("/mainframe/stop")
async def stop_mainframe(background_tasks: BackgroundTasks):
    """Stop the TK5 mainframe."""
    if not TK5_STOP.exists():
        return JSONResponse(
            content={"error": "TK5 stop script not found", "path": str(TK5_STOP)},
            status_code=404
        )
    
    if not _check_hercules_running():
        return JSONResponse(
            content={"status": "already_stopped", "message": "Mainframe is not running"},
            status_code=200
        )
    
    def _stop():
        subprocess.run(["bash", str(TK5_STOP)], cwd=str(TK5_DIR))
    
    background_tasks.add_task(_stop)
    return JSONResponse(
        content={"status": "stopping", "message": "Mainframe is shutting down..."},
        status_code=202
    )


@router.post("/mainframe/restart")
async def restart_mainframe(background_tasks: BackgroundTasks):
    """Restart the TK5 mainframe."""
    if not TK5_START.exists() or not TK5_STOP.exists():
        return JSONResponse(
            content={"error": "TK5 scripts not found"},
            status_code=404
        )
    
    def _restart():
        import time
        # Stop if running
        if _check_hercules_running():
            subprocess.run(["bash", str(TK5_STOP)], cwd=str(TK5_DIR))
            time.sleep(3)
        # Start
        subprocess.run(["bash", str(TK5_START)], cwd=str(TK5_DIR))
    
    background_tasks.add_task(_restart)
    return JSONResponse(
        content={"status": "restarting", "message": "Mainframe is restarting... Wait ~30 seconds for full initialization."},
        status_code=202
    )


@router.post("/mainframe/prepare-demo")
async def prepare_demo(background_tasks: BackgroundTasks):
    """
    Elegantly restart the mainframe for a clean demo.
    - Disconnect any active terminal sessions
    - Shut down Hercules cleanly
    - Clear console logs
    - Fresh IPL — no history, no previous commands
    """
    if not TK5_START.exists() or not TK5_STOP.exists():
        return JSONResponse(
            content={"error": "TK5 scripts not found"},
            status_code=404
        )

    def _prepare():
        import time
        import glob

        # 1. Disconnect any active terminal session
        try:
            from agent_tools import disconnect_mainframe
            disconnect_mainframe()
        except Exception:
            pass

        # 2. Shut down Hercules cleanly
        if _check_hercules_running():
            subprocess.run(["bash", str(TK5_STOP)], cwd=str(TK5_DIR))
            time.sleep(4)

        # Force kill if still hanging
        if _check_hercules_running():
            subprocess.run(["pkill", "-9", "hercules"], capture_output=True)
            time.sleep(2)

        # 3. Clear console logs for a pristine start
        log_dir = TK5_DIR / "log"
        if log_dir.exists():
            for logfile in log_dir.glob("*.log"):
                try:
                    logfile.write_text("")
                except Exception:
                    pass

        # 4. Fresh IPL
        subprocess.run(["bash", str(TK5_START)], cwd=str(TK5_DIR))

    background_tasks.add_task(_prepare)
    return JSONResponse(
        content={
            "status": "preparing",
            "message": "Preparing clean demo environment — full IPL in progress. Ready in ~40 seconds."
        },
        status_code=202
    )
