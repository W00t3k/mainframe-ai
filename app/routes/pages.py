"""
Page Routes

HTML page rendering routes for the web interface.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_config

router = APIRouter(tags=["pages"])
config = get_config()
templates = Jinja2Templates(directory=config.TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat interface page."""
    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse("chat.html", {"request": request, "embed": embed})


@router.get("/connect", response_class=HTMLResponse)
async def connect_page(request: Request):
    """Connection page (alias for chat)."""
    return templates.TemplateResponse("chat.html", {"request": request})


@router.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    """Terminal emulator page."""
    return templates.TemplateResponse("terminal.html", {"request": request})


@router.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    """Labs page."""
    return templates.TemplateResponse("labs.html", {"request": request})


@router.get("/scanner", response_class=HTMLResponse)
async def scanner_page(request: Request):
    """Scanner page."""
    return templates.TemplateResponse("scanner.html", {"request": request})


@router.get("/screencaps")
async def screencaps_page():
    """Redirect to recon page (captures tab is now merged there)."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/recon", status_code=302)


@router.get("/rag", response_class=HTMLResponse)
async def rag_page(request: Request):
    """RAG knowledge base page."""
    return templates.TemplateResponse("rag.html", {"request": request})


@router.get("/architecture", response_class=HTMLResponse)
async def architecture_page(request: Request):
    """Architecture documentation page."""
    return templates.TemplateResponse("architecture.html", {"request": request})


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    """Documentation page."""
    return templates.TemplateResponse("docs.html", {"request": request})


@router.get("/abstract-models", response_class=HTMLResponse)
async def abstract_models_page(request: Request):
    """Abstract models documentation page."""
    return templates.TemplateResponse("abstract_models.html", {"request": request})


@router.get("/tutor", response_class=HTMLResponse)
async def tutor_page(request: Request):
    """Red Team Tutor page."""
    return templates.TemplateResponse("tutor.html", {"request": request})


@router.get("/recon", response_class=HTMLResponse)
async def recon_page(request: Request):
    """Recon & Assessment dashboard."""
    return templates.TemplateResponse("recon.html", {"request": request})


@router.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough_page(request: Request):
    """Autonomous walkthrough page."""
    return templates.TemplateResponse("walkthrough.html", {"request": request})


@router.get("/slides", response_class=HTMLResponse)
async def slides_page(request: Request):
    """Conference slide deck."""
    return templates.TemplateResponse("slides.html", {"request": request})


@router.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """Trust Graph visualization page."""
    return templates.TemplateResponse("graph.html", {"request": request})


@router.get("/presentation", response_class=HTMLResponse)
async def presentation_page(request: Request):
    """Teaching presentation slide deck."""
    return templates.TemplateResponse("presentation.html", {"request": request})
