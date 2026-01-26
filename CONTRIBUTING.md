# Contributing to Mainframe AI Assistant

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.10+
- x3270 (for TN3270 emulation)
- Anthropic API key (for AI features)
- Access to a mainframe for integration testing (optional)

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd mainframe_ai_assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest ruff mypy

# Set up environment
export ANTHROPIC_API_KEY="your-key-here"
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- Line length: 100 characters
- Use tabs for indentation in BIRP modules (legacy)
- Use spaces (4) for new code
- Use type hints for public APIs

### Formatting

```bash
# Check code style
ruff check .

# Auto-format
ruff format .

# Type checking
mypy src/
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
mainframe_ai_assistant/
├── mainframe_assistant.py   # CLI entry point
├── web_app.py               # Web interface
├── rag_engine.py            # RAG implementation
├── birpv2_modules/          # BIRP v2 toolkit
│   ├── core/                # Data models
│   ├── emulator/            # TN3270 wrapper
│   ├── security/            # Security tools
│   ├── io/                  # Export functions
│   ├── zos/                 # z/OS helpers
│   └── utils/               # Utilities
├── templates/               # Web templates
├── static/                  # Static assets
├── docs/                    # Documentation
└── tests/                   # Test suite
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
pytest --cov=birpv2_modules

# Run only unit tests (no mainframe required)
pytest -m "not integration"
```

### Writing Tests

```python
# tests/test_models.py
import pytest
from birpv2_modules.core.models import Screen, Field

def test_field_creation():
    field = Field("TEST", 0, 0, "SF(c0=c8)")
    assert field.contents == "TEST"
    assert field.row == 0
    assert field.col == 0

def test_screen_fields():
    # Create mock buffer
    buffer = ["00 00 SF(c0=c8) 54 45 53 54"]  # "TEST"
    screen = Screen(buffer)
    assert len(screen.fields) > 0

@pytest.mark.integration
def test_emulator_connect():
    """Requires running mainframe"""
    from birpv2_modules.emulator.wrapper import WrappedEmulator
    em = WrappedEmulator(visible=False)
    em.connect('localhost:3270')
    assert em.is_connected()
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

### New z/OS Parser

1. Create `birpv2_modules/zos/new_helper.py`:

```python
#!/usr/bin/env python3
"""
New Subsystem Helper for z/OS
"""

class NewHelper:
    def __init__(self):
        pass

    def detect_screen(self, screen_text: str) -> bool:
        """Detect if screen is from this subsystem"""
        indicators = ['INDICATOR1', 'INDICATOR2']
        return any(i in screen_text.upper() for i in indicators)

    def parse_output(self, screen_text: str) -> dict:
        """Parse subsystem output"""
        result = {}
        # Implementation
        return result
```

2. Update `birpv2_modules/zos/__init__.py`:

```python
from .new_helper import NewHelper
```

3. Add tests in `tests/test_new_helper.py`
4. Document in `birpv2_modules/zos/README.md`

### New Security Check

1. Add pattern to `SecurityScanner.patterns`:

```python
self.patterns['new_pattern'] = [
    r'regex_pattern_1',
    r'regex_pattern_2',
]
```

2. Update `scan_screen()` if needed
3. Add test case
4. Update documentation

### New Export Format

1. Add function to `birpv2_modules/io/exporters.py`:

```python
def export_to_new_format(history, filename):
    """Export to new format"""
    # Implementation
    return True
```

2. Update `auto_export()`:

```python
elif filename_lower.endswith('.new'):
    return export_to_new_format(history, filename)
```

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
