"""
LLM Provider Routes

Endpoints for managing LLM providers (Ollama, Groq) and API keys.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["llm"])


@router.get("/llm/status")
async def api_llm_status():
    """Get status of all LLM providers."""
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    return JSONResponse(await service.get_status())


@router.post("/llm/provider/switch")
async def api_llm_provider_switch(request: Request):
    """Switch the active LLM provider."""
    data = await request.json()
    provider = data.get("provider", "").strip().lower()
    if provider not in ("ollama", "grok", "auto"):
        return JSONResponse({"success": False, "error": f"Unknown provider: {provider}"})
    from app.services.llm_provider import get_llm_service
    service = get_llm_service()
    service.configured_provider = provider
    return JSONResponse({"success": True, "provider": provider})


@router.post("/llm/grok/set-key")
async def api_llm_grok_set_key(request: Request):
    """Set the Groq API key and verify it works."""
    data = await request.json()
    key = data.get("key", "").strip()
    if not key:
        return JSONResponse({"success": False, "error": "No key provided"})

    from app.services.grok import get_grok_service
    from app.services.llm_provider import get_llm_service

    grok = get_grok_service()
    grok._api_key = key
    grok.save_key(key)

    ok = await grok.check_available()
    if ok:
        # Auto-switch provider to grok
        get_llm_service().configured_provider = "grok"
        return JSONResponse({"success": True, "message": "Connected to Groq — switched to cloud provider"})
    else:
        return JSONResponse({"success": False, "error": "Key set but Groq API unreachable — check key and network"})


@router.post("/llm/grok/set-model")
@router.post("/llm/grok/switch-model")
async def api_llm_grok_set_model(request: Request):
    """Set the active Groq model (accepts both set-model and switch-model paths)."""
    data = await request.json()
    model = data.get("model", "").strip()
    if not model:
        return JSONResponse({"success": False, "error": "No model specified"})
    from app.services.grok import get_grok_service
    grok = get_grok_service()
    old = grok.model
    grok.model = model
    return JSONResponse({"success": True, "old": old, "new": model})
