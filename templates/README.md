# Templates (`templates/`)

Jinja2 HTML templates for the web interface.

## Base Template

### `base.html`
Master template with:
- HTML head (meta, fonts, base CSS)
- Toast notification container
- Block definitions for child templates

## Page Templates

| Template | Route | Description |
|----------|-------|-------------|
| `index.html` | `/` | Landing page with feature cards |
| `chat.html` | `/chat` | AI chat interface |
| `terminal.html` | `/terminal` | TN3270 terminal emulator |
| `tutor.html` | `/tutor` | Red Team Tutor |
| `walkthrough.html` | `/walkthrough` | Autonomous demonstrations |
| `graph.html` | `/graph` | Trust graph visualization |
| `recon.html` | `/recon` | Reconnaissance tools |
| `labs.html` | `/labs` | Security lab exercises |
| `scanner.html` | `/scanner` | Network scanner |
| `rag.html` | `/rag` | Knowledge base management |
| `architecture.html` | `/architecture` | System architecture |
| `docs.html` | `/docs` | API documentation |
| `abstract-models.html` | `/abstract-models` | Mental models |
| `screencaps.html` | `/screencaps` | Screen captures |

## Partials

### `partials/`
Reusable template fragments:
- `site_header.html` - Standard page header with back button

## Template Blocks

Templates extend `base.html` and override blocks:
- `{% block title %}` - Page title
- `{% block page_styles %}` - Page-specific CSS
- `{% block body %}` - Main content
- `{% block page_scripts %}` - Page-specific JavaScript
