"""
Chat API Routes

Endpoints for chat functionality and AI interaction.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import json
import asyncio

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


@router.post("/models/pull")
async def api_pull_model(request: Request):
    """Pull (download) a model from Ollama. Streams progress as SSE."""
    data = await request.json()
    model = data.get("model", "").strip()
    if not model:
        return JSONResponse({"success": False, "error": "No model specified"})

    config = get_config()

    async def stream_pull():
        import time
        prev_completed = 0
        prev_time = time.time()
        buf = b""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{config.OLLAMA_URL}/api/pull",
                    json={"name": model, "stream": True},
                ) as resp:
                    async for raw in resp.aiter_bytes():
                        buf += raw
                        while b"\n" in buf:
                            line_bytes, buf = buf.split(b"\n", 1)
                            line = line_bytes.decode("utf-8", errors="replace").strip()
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                status = chunk.get("status", "")
                                total = chunk.get("total", 0)
                                completed = chunk.get("completed", 0)
                                pct = int(completed / total * 100) if total else 0

                                now = time.time()
                                dt = now - prev_time
                                speed_bps = 0
                                if dt > 0.1 and completed > prev_completed:
                                    speed_bps = (completed - prev_completed) / dt
                                    prev_completed = completed
                                    prev_time = now

                                evt = json.dumps({
                                    "status": status, "pct": pct,
                                    "total": total, "completed": completed,
                                    "speed": speed_bps,
                                })
                                yield f"data: {evt}\n\n"
                            except Exception:
                                yield f"data: {json.dumps({'status': line})}\n\n"
            yield f"data: {json.dumps({'status': 'done', 'pct': 100, 'model': model})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
