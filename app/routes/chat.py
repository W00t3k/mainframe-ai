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
