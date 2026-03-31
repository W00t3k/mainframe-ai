"""
API Routes

All FastAPI route modules for the application.
"""

from fastapi import APIRouter

from .pages import router as pages_router
from .chat import router as chat_router
from .terminal import router as terminal_router
from .labs import router as labs_router
from .scanner import router as scanner_router
from .screencaps import router as screencaps_router
from .rag import router as rag_router
from .graph import router as graph_router
from .recon import router as recon_router
from .tutor import router as tutor_router
from .walkthrough import router as walkthrough_router
from .system import router as system_router
from .methodology import router as methodology_router
from .kicks import router as kicks_router
from .llm import router as llm_router
from .ftp import router as ftp_router


def register_routes(app):
    """Register all route modules with the FastAPI application."""
    app.include_router(pages_router)
    app.include_router(chat_router, prefix="/api")
    app.include_router(terminal_router, prefix="/api/terminal")
    app.include_router(labs_router, prefix="/api/labs")
    app.include_router(scanner_router, prefix="/api/scanner")
    app.include_router(screencaps_router, prefix="/api")
    app.include_router(rag_router, prefix="/api/rag")
    app.include_router(graph_router, prefix="/api/graph")
    app.include_router(recon_router, prefix="/api/recon")
    app.include_router(tutor_router, prefix="/api/tutor")
    app.include_router(walkthrough_router, prefix="/api/walkthrough")
    app.include_router(system_router, prefix="/api/system")
    app.include_router(methodology_router)
    app.include_router(kicks_router, prefix="/api")
    app.include_router(llm_router, prefix="/api")
    app.include_router(ftp_router, prefix="/api")
