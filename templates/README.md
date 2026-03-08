# `templates/` — Jinja2 HTML Pages

24 Jinja2 templates rendering the full web interface. All extend `base.html`.

## Base Template

`base.html` provides: HTML head (meta, IBM Plex fonts, base CSS), toast notification container, and four override blocks:

```jinja2
{% block title %}       — Page title
{% block page_styles %} — Per-page CSS <link>
{% block body %}        — Main content
{% block page_scripts %} — Per-page <script>
```

## Pages

| Template | Route | Feature |
|----------|-------|---------|
| `index.html` | `/` | CRT hero + live terminal overlay + matrix boot sequence |
| `terminal.html` | `/terminal` | Full-screen TN3270 with color rendering |
| `walkthrough.html` | `/walkthrough` | 13 autonomous walkthroughs with narration |
| `tutor.html` | `/tutor` | Red Team Tutor — labs, chat, terminal side-by-side |
| `tutorials.html` | `/tutorials` | Step-by-step tutorial library |
| `chat.html` | `/chat`, `/connect` | AI chat with tool-calling |
| `graph.html` | `/graph` | D3.js trust graph visualization |
| `recon.html` | `/recon` | Test & Report — enumeration + findings |
| `labs.html` | `/labs` | Security lab exercises |
| `scanner.html` | `/scanner` | TN3270 network discovery + EBCDIC tools |
| `rag.html` | `/rag` | Knowledge base upload + query |
| `abstract_models.html` | `/abstract-models` | Interactive mental model explorer |
| `abstract.html` | `/abstract` | Conference abstract |
| `architecture.html` | `/architecture` | System architecture diagram |
| `ftp.html` | `/ftp` | MVS FTP client |
| `uss_editor.html` | `/uss-editor` | USS logon screen editor |
| `slides.html` | `/slides` | Presentation slide viewer |
| `presentation.html` | `/presentation` | Teaching presentation deck |
| `video.html` | `/video` | IBM-AI demo video player |
| `docs.html` | `/docs` | API documentation |
| `screencaps.html` | — | Legacy (redirects to `/recon`) |

## Partials

`partials/site_header.html` — reusable page header with back button and IBM logo.
