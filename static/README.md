# Static Assets (`static/`)

Frontend static files served by FastAPI.

## Directory Structure

```
static/
├── css/
│   ├── base.css         # Global styles, variables, components
│   └── pages/           # Page-specific stylesheets
├── js/
│   ├── vendor/          # Third-party libraries (marked.js, etc.)
│   └── *.js             # Custom JavaScript
├── logo.svg             # Application logo
└── favicon.ico          # Browser favicon
```

## CSS Architecture

### `base.css`
- CSS custom properties (colors, spacing)
- Typography settings
- Common component styles (buttons, cards, forms)
- Utility classes

### `pages/*.css`
Page-specific styles:
- `index.css` - Landing page
- `chat.css` - Chat interface
- `terminal.css` - TN3270 terminal
- `tutor.css` - Red Team Tutor
- `walkthrough.css` - Autonomous walkthroughs
- `graph.css` - Trust graph visualization
- etc.

## Design System

Based on IBM Carbon Design with custom mainframe theme:
- Dark background (`#0d0d0d`)
- Blue accent (`#4589ff`)
- Green terminal (`#42be65`)
- Monospace fonts for code/terminal
