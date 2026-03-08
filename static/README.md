# `static/` — Frontend Assets

CSS, JavaScript, fonts, and images served by FastAPI's `StaticFiles`.

## Layout

```
static/
├── css/
│   ├── base.css              # Global variables, reset, typography, components
│   └── pages/                # Per-page stylesheets (index, chat, terminal, tutor, etc.)
├── js/
│   └── vendor/               # Third-party (marked.js for markdown rendering)
├── img/
│   ├── ibm-retro-desk.png    # CRT terminal hero image (home page)
│   ├── ibm-logo-official.svg # IBM logo
│   └── ...                   # Icons, backgrounds
├── fonts/                    # IBM Plex Mono, IBM Plex Sans (self-hosted)
└── favicon.ico
```

## Design System

IBM Carbon-inspired dark theme with mainframe accents:

| Token | Value | Use |
|-------|-------|-----|
| Background | `#0d0d0d` | Page background |
| Blue accent | `#4589ff` | Links, buttons, active states |
| Green terminal | `#42be65` | Terminal text, success indicators |
| Red alert | `#fa4d56` | Errors, red team highlights |
| Monospace | IBM Plex Mono | All terminal and code contexts |
| Sans | IBM Plex Sans | UI labels, body text |
