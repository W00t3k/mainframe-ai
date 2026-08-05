"""
LLM Provider Routes

Status endpoint for the local Ollama LLM backend.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["llm"])


@router.get("/llm/status")
async def api_llm_status():
    """Get status of the LLM provider (Ollama)."""
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    return JSONResponse(await service.get_status())
