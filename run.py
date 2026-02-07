#!/usr/bin/env python3
"""
Mainframe AI Assistant - Entry Point

Run the web application server.
"""

import argparse
import uvicorn

from app.config import get_config, update_model


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Mainframe AI Assistant Web App")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model to use")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    # Update configuration
    config = get_config()
    config.HOST = args.host
    config.PORT = args.port
    update_model(args.model)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║       Mainframe AI Assistant - LOCAL LLM Edition         ║
╠══════════════════════════════════════════════════════════╣
║  Landing Page:  http://{args.host}:{args.port}/                    ║
║  Chat:          http://{args.host}:{args.port}/chat                ║
╠══════════════════════════════════════════════════════════╣
║  LLM Backend:   Ollama ({config.OLLAMA_MODEL})             ║
╠══════════════════════════════════════════════════════════╣
║  No API key required! Runs 100% locally.                 ║
║  Web Terminal: Type in browser, no shell needed!         ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
