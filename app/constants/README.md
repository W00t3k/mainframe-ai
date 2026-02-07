# Constants (`app/constants/`)

Static configuration, prompts, and data definitions.

## Files

### `paths.py`
File system paths and directories:
- Base directories
- Data file locations
- Static asset paths

### `prompts.py`
LLM system prompts and templates:
- Chat system prompts
- Tutor persona definitions
- Analysis prompt templates

### `walkthrough_scripts.py`
Autonomous walkthrough definitions:
- Step sequences for each walkthrough
- Expected screens and actions
- Narration content
- Assessment question mappings (Q1-Q5)

## Usage

```python
from app.constants.prompts import SYSTEM_PROMPT
from app.constants.paths import DATA_DIR
from app.constants.walkthrough_scripts import WALKTHROUGH_SCRIPTS
```
