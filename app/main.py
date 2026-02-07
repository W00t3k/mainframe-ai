"""
Main Application Factory

Creates and configures the FastAPI application.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.routes import register_routes
from app.websocket.handlers import websocket_terminal, websocket_graph


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan handler - startup and shutdown logic."""
    config = get_config()
    
    # Startup: seed trust graph with demo data if empty
    try:
        from trust_graph import get_trust_graph
        from graph_tools import (
            parse_jcl, parse_sysout,
            update_graph_from_jcl, update_graph_from_sysout, update_graph_from_screen
        )
        
        graph = get_trust_graph()
        if not graph.nodes:
            demo_dir = config.DEMO_DATA_DIR
            for loader, key in [
                (lambda t: update_graph_from_jcl(graph, parse_jcl(t), {"type": "demo", "source": "sample_jcl"}),
                 "sample_jcl.txt"),
                (lambda t: update_graph_from_sysout(graph, parse_sysout(t), {"type": "demo", "source": "sample_sysout"}),
                 "sample_sysout.txt"),
                (lambda t: update_graph_from_screen(graph, t, "demo:3270"),
                 "sample_screen.txt"),
            ]:
                fpath = os.path.join(demo_dir, key)
                if os.path.exists(fpath):
                    with open(fpath, "r") as f:
                        loader(f.read())
            graph.save()
            print("Trust graph seeded with demo data.")
    except ImportError:
        print("Trust graph modules not available - skipping demo data seeding.")
    except Exception as e:
        print(f"Trust graph seed skipped: {e}")
    
    yield  # Application runs here


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()
    
    app = FastAPI(
        title="Mainframe AI Assistant",
        description="AI-powered assistant for z/OS mainframe systems",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
    
    # Register all routes
    register_routes(app)
    
    # Register WebSocket endpoints
    app.websocket("/ws/terminal")(websocket_terminal)
    app.websocket("/ws/graph")(websocket_graph)
    
    return app


# Create the application instance
app = create_app()
