# Application Core (`app/`)

This directory contains the modular FastAPI application structure for the Mainframe AI Assistant.

## Directory Structure

```
app/
├── __init__.py          # Package init
├── config.py            # Application configuration (Ollama, paths, etc.)
├── main.py              # FastAPI app factory and lifespan
├── constants/           # Static configuration, prompts, walkthrough scripts
├── models/              # Pydantic schemas and data models
├── routes/              # API route handlers (14 modules)
└── services/            # Business logic services
```

## Key Files

### `main.py`
The FastAPI application factory. Creates and configures the app instance with:
- Static file mounting (CSS, JS, fonts, images)
- Jinja2 template configuration (16 HTML pages)
- Route registration (14 route modules)
- Lifespan events (startup/shutdown)

### `config.py`
Centralized configuration management:
- Ollama model settings (`OLLAMA_URL`, `OLLAMA_MODEL`)
- File paths
- Feature flags

## Routes

The `routes/` directory contains 14 API route modules covering:
- Terminal connection and screen management
- AI chat and tutor interactions
- Walkthrough automation
- Trust graph operations
- Test & Report (enumeration and findings)
- RAG knowledge base
- Network scanner
- System status and configuration
- Abstract models
- Architecture and documentation pages

## Entry Point

The application is started via `run.py` in the project root:
```bash
python run.py --host 127.0.0.1 --port 8080 --model llama3.1:8b
```

## Dependencies

- FastAPI for the web framework
- Jinja2 for HTML templates
- Ollama for local LLM inference
- Custom modules: trust_graph, rag_engine, recon_engine, methodology_engine, graph_tools
