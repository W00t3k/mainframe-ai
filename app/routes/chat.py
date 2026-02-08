"""
Chat API Routes

Endpoints for chat functionality and AI interaction.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import ChatRequest
from app.services.chat import get_chat_service
from app.services.ollama import get_ollama_service

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
