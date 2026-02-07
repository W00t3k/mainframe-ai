# Application Core (`app/`)

This directory contains the modular FastAPI application structure for the Mainframe AI Assistant.

## Directory Structure

```
app/
├── __init__.py          # Package init
├── config.py            # Application configuration (Ollama, paths, etc.)
├── main.py              # FastAPI app factory and lifespan
├── constants/           # Static configuration and prompts
├── models/              # Pydantic schemas and data models
├── routes/              # API route handlers
├── services/            # Business logic services
└── websocket/           # WebSocket handlers
```

## Key Files

### `main.py`
The FastAPI application factory. Creates and configures the app instance with:
- Static file mounting
- Template configuration
- Route registration
- Lifespan events (startup/shutdown)

### `config.py`
Centralized configuration management:
- Ollama model settings
- File paths
- Feature flags

## Entry Point

The application is started via `run.py` in the project root:
```bash
python run.py --host 127.0.0.1 --port 8080 --model llama3.1:8b
```

## Dependencies

- FastAPI for the web framework
- Jinja2 for HTML templates
- Ollama for local LLM inference
- Various custom modules (trust_graph, rag_engine, recon_engine)
