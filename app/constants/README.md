# `app/constants/` — Prompts, Walkthroughs, Learning Paths

All static content that drives the AI tutor, autonomous walkthroughs, and assessment methodology.

## Files

### `prompts.py`
LLM system prompts for every interaction mode:
- **SYSTEM_PROMPT** — General AI assistant capabilities
- **TUTOR_SYSTEM_PROMPT** — Red team operator persona, 6 control planes, engagement rules
- **WALKTHROUGH_PROMPTS** — Per-module prompts (13 walkthroughs including PR/SM HMC simulator)
- **RECON_AI_PROMPT** — Findings-based analysis (F1–F5 framework)
- **EXPLAIN_SCREEN_PROMPT** — Click-to-analyze screen explanation
- **SLIDES_PROMPT** — Presentation narration
- **TUTOR_PERSONAS** — 6 personas (Mentor, Operator, Red Teamer, Forensics, Architect, Policy)

### `walkthrough_scripts.py`
13 autonomous walkthrough definitions with per-step:
- Terminal actions (connect, login, keystrokes, waits)
- Control plane annotations (tso, jes, racf, vtam, prsm)
- Markdown narration with security context
- Expected screen signatures

### `paths.py`
9 guided learning paths:
- **PATH_CATALOG** — Path metadata (title, description, defender outcome)
- **FALLBACK_STEPS** — Static step definitions when LLM is unavailable

## Usage

```python
from app.constants.prompts import SYSTEM_PROMPT, TUTOR_SYSTEM_PROMPT, WALKTHROUGH_PROMPTS
from app.constants.paths import PATH_CATALOG, FALLBACK_STEPS
from app.constants.walkthrough_scripts import WALKTHROUGH_SCRIPTS
```
