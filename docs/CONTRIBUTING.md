# Contributing to Mainframe AI Assistant

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) for local LLM inference
- TK5 MVS 3.8j emulator for integration testing (optional)

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd mainframe-ai

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest ruff mypy

# Start Ollama (for AI features)
ollama serve
ollama pull llama3.1:8b
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- Line length: 100 characters
- Use tabs for indentation in TN3270 modules (legacy)
- Use spaces (4) for new code
- Use type hints for public APIs

### Formatting

```bash
# Check code style
ruff check .

# Auto-format
ruff format .

# Type checking
mypy app/
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `SecurityScanner` |
| Functions | snake_case | `parse_screen()` |
| Constants | UPPER_SNAKE | `MAX_TIMEOUT` |
| Private | _leading_underscore | `_internal_method()` |

## Project Structure

```
mainframe-ai/
├── run.py                   # Application entry point (Uvicorn)
├── app/                     # Modular FastAPI application
│   ├── routes/              # API endpoints (19 modules)
│   ├── services/            # Business logic (chat, LLM, FTP, BOF lab)
│   ├── constants/           # Prompts, 13 walkthroughs, 9 learning paths
│   ├── models/              # Pydantic schemas
│   └── websocket/           # Real-time terminal/graph updates
├── tools/                   # Standalone Python tools and engines
│   ├── agent_tools.py       # TN3270 connection, screen reading, tool defs
│   ├── trust_graph.py       # BloodHound-style graph data model
│   ├── graph_tools.py       # JCL/SYSOUT parsers, screen classifiers
│   ├── rag_engine.py        # Local RAG with file-based vector store
│   ├── recon_engine.py      # TSO/CICS/VTAM enumeration + report gen
│   ├── methodology_engine.py # F1–F5 findings framework, 6 control planes
│   ├── mcp_server.py        # Model Context Protocol server
│   └── ai_bridge.py         # KICKS/CICS ↔ Ollama bridge
├── data/                    # Runtime data (lab_data, rag_data, screencaps, graph)
├── jcl/                     # JCL source files (FTPD, USS, KICKS, etc.)
├── scripts/                 # Shell scripts (install, mvs management)
├── templates/               # Jinja2 HTML templates (24+ pages)
├── static/                  # CSS, JS, fonts, images
├── docs/                    # Documentation
├── slides/                  # Presentation assets and demo video
├── start.sh                 # One-command launcher (Ollama + TK5 + Web App)
└── tk5/                     # TK5 MVS 3.8j emulator + Hercules binaries
```

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring

### Commit Messages

Follow conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `refactor` - Code refactoring
- `test` - Tests
- `chore` - Maintenance

Examples:
```
feat(security): add SQL injection detection patterns
fix(emulator): handle timeout in screen_get()
docs(api): add SecurityScanner documentation
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models.py

# Run with coverage
pytest --cov=app

# Run only unit tests (no mainframe required)
pytest -m "not integration"
```

### Writing Tests

```python
# tests/test_agent_tools.py
import pytest
from agent_tools import connect_mainframe, read_screen, disconnect_mainframe

def test_disconnect_when_not_connected():
    result = disconnect_mainframe()
    assert "Disconnected" in result

def test_read_screen_when_not_connected():
    screen = read_screen()
    assert "Not connected" in screen

@pytest.mark.integration
def test_connect_and_read():
    """Requires running TK5 mainframe on localhost:3270"""
    success, msg = connect_mainframe('localhost:3270')
    assert success
    screen = read_screen()
    assert len(screen) > 0
    disconnect_mainframe()
```

### Test Markers

- `@pytest.mark.integration` - Requires mainframe
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.security` - Security-related tests

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def scan_screen(self, screen: Screen) -> list[dict]:
    """Scan a single screen for security issues.

    Args:
        screen: Screen object to analyze.

    Returns:
        List of finding dictionaries with keys:
        - type: Finding type (e.g., 'hidden_field')
        - severity: 'critical', 'high', 'medium', 'low'
        - location: Field position '[row,col]'
        - message: Description of the finding

    Example:
        >>> scanner = SecurityScanner(em, history)
        >>> findings = scanner.scan_screen(screen)
        >>> for f in findings:
        ...     print(f"{f['severity']}: {f['message']}")
    """
```

### README Files

Each module should have a README.md with:
- Overview
- Quick start example
- Class/function reference
- See Also links

## Adding Features

### New Walkthrough

1. Add step definitions to `app/constants/walkthrough_scripts.py`:

```python
WALKTHROUGH_SCRIPTS["my-walkthrough"] = {
    "title": "My Walkthrough Title",
    "steps": [
        {
            "title": "Step Name",
            "control_plane": "tso",
            "narration": "**What's happening** — explanation here.",
            "actions": [{"type": "connect"}],
            "expect": ["VTAM", "Logon"],
            "display_seconds": 8,
        },
    ],
}
```

2. Add a walkthrough prompt to `app/constants/prompts.py` in `WALKTHROUGH_PROMPTS`
3. Optionally add a learning path in `app/constants/paths.py`
4. The walkthrough appears automatically in the UI

### New Route Module

1. Create `app/routes/myfeature.py`:

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["myfeature"])

@router.get("/api/myfeature/status")
async def status():
    return JSONResponse({"status": "ok"})
```

2. Register in `app/routes/__init__.py`
3. Add tests and documentation

## Pull Request Process

1. **Create branch** from `main`
2. **Make changes** following guidelines
3. **Write tests** for new functionality
4. **Update documentation** as needed
5. **Run checks**:
   ```bash
   ruff check .
   pytest
   ```
6. **Submit PR** with description:
   - What changed
   - Why it changed
   - How to test
   - Related issues

### PR Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No security vulnerabilities introduced
- [ ] Backwards compatible (or documented breaking changes)

## Security Considerations

### Reporting Vulnerabilities

For security issues, please email directly rather than opening a public issue.

### Code Review Focus

- No credential logging
- Input validation
- Safe command execution
- Proper error handling

## Questions?

- Open a GitHub issue for bugs/features
- Check existing documentation first
- Tag issues appropriately

Thank you for contributing!
