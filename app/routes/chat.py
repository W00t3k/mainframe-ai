"""
Chat API Routes

Endpoints for chat functionality and AI interaction.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import json
import threading
import time as _time

from app.models.schemas import ChatRequest
from app.services.chat import get_chat_service
from app.services.ollama import get_ollama_service
from app.config import get_config

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def api_chat(request: ChatRequest):
    """Process a chat message."""
    chat_service = get_chat_service()
    result = await chat_service.process_message(request.message)
    return JSONResponse(result)


@router.post("/explain-screen")
async def api_explain_screen(request: ChatRequest):
    """Fast screen explanation - bypasses chat history for speed."""
    ollama_service = get_ollama_service()
    
    if not await ollama_service.check_available():
        return JSONResponse({"response": "AI offline - start Ollama: ollama serve"})
    
    # Extract screen text and context from message
    screen_text = request.message
    context = request.context if hasattr(request, 'context') else ""
    
    response = await ollama_service.quick_explain(screen_text, context)
    return JSONResponse({"response": response})


@router.get("/status")
async def api_status():
    """Get system status."""
    chat_service = get_chat_service()
    ollama_service = get_ollama_service()
    ollama_ok = await ollama_service.check_available()
    
    return JSONResponse({
        "connected": chat_service.is_connected,
        "host": chat_service.connection_host,
        "screen": chat_service.current_screen,
        "ollama_running": ollama_ok,
        "model": chat_service.config.OLLAMA_MODEL
    })


@router.get("/models")
async def api_list_models():
    """List available Ollama models."""
    config = get_config()
    models = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{config.OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    size_gb = m.get("size", 0) / (1024**3)
                    models.append({
                        "name": name,
                        "size": f"{size_gb:.1f}GB",
                        "family": m.get("details", {}).get("family", ""),
                        "params": m.get("details", {}).get("parameter_size", ""),
                        "quant": m.get("details", {}).get("quantization_level", ""),
                    })
    except Exception as e:
        return JSONResponse({"models": [], "current": config.OLLAMA_MODEL, "error": str(e)})
    
    return JSONResponse({"models": models, "current": config.OLLAMA_MODEL})


@router.post("/models/switch")
async def api_switch_model(request: Request):
    """Switch the active Ollama model."""
    data = await request.json()
    model = data.get("model", "").strip()
    if not model:
        return JSONResponse({"success": False, "error": "No model specified"})
    
    config = get_config()
    old_model = config.OLLAMA_MODEL
    config.OLLAMA_MODEL = model
    
    return JSONResponse({"success": True, "old": old_model, "new": model})


@router.post("/models/delete")
async def api_delete_model(request: Request):
    """Delete an Ollama model."""
    data = await request.json()
    model = data.get("model", "").strip()
    if not model:
        return JSONResponse({"success": False, "error": "No model specified"})

    config = get_config()
    # Don't allow deleting the currently active model
    if model == config.OLLAMA_MODEL:
        return JSONResponse({"success": False, "error": "Cannot delete the active model. Switch to another model first."})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.request("DELETE", f"{config.OLLAMA_URL}/api/delete", json={"name": model})
            if r.status_code == 200:
                return JSONResponse({"success": True, "model": model})
            else:
                return JSONResponse({"success": False, "error": f"Ollama returned {r.status_code}"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


_pull_state = {
    "active": False,
    "model": "",
    "status": "",
    "pct": 0,
    "completed": 0,
    "total": 0,
    "speed": 0,
    "error": "",
}


def _pull_worker(model: str, ollama_url: str):
    """Background thread that pulls a model from Ollama and updates _pull_state."""
    import requests
    global _pull_state
    _pull_state.update(active=True, model=model, status="starting", pct=0,
                       completed=0, total=0, speed=0, error="")
    prev_completed = 0
    prev_time = _time.time()
    try:
        resp = requests.post(
            f"{ollama_url}/api/pull",
            json={"name": model, "stream": True},
            stream=True,
            timeout=None,
        )
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
                status = chunk.get("status", "")
                total = chunk.get("total", 0)
                completed = chunk.get("completed", 0)
                pct = int(completed / total * 100) if total else 0

                now = _time.time()
                dt = now - prev_time
                speed_bps = _pull_state["speed"]
                if dt > 0.3 and completed > prev_completed:
                    speed_bps = (completed - prev_completed) / dt
                    prev_completed = completed
                    prev_time = now

                _pull_state.update(
                    status=status, pct=pct, completed=completed,
                    total=total, speed=speed_bps,
                )
            except Exception:
                pass
        _pull_state.update(status="done", pct=100, active=False)
    except Exception as e:
        _pull_state.update(status="error", error=str(e), active=False)


@router.post("/models/pull")
async def api_pull_model(request: Request):
    """Start pulling (downloading) a model from Ollama in the background."""
    data = await request.json()
    model = data.get("model", "").strip()
    if not model:
        return JSONResponse({"success": False, "error": "No model specified"})

    if _pull_state["active"]:
        return JSONResponse({"success": False, "error": f"Already pulling {_pull_state['model']}"})

    config = get_config()
    t = threading.Thread(target=_pull_worker, args=(model, config.OLLAMA_URL), daemon=True)
    t.start()
    return JSONResponse({"success": True, "model": model})


@router.get("/models/pull/status")
async def api_pull_status():
    """Poll the current model pull progress."""
    return JSONResponse(_pull_state)
