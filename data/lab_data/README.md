# `lab_data/` — Security Lab Definitions

JSON files defining hands-on security lab exercises. Each lab is a sequence of guided steps with instructions, expected outcomes, and hints.

## Structure

`index.json` is the lab index — the `/api/labs` endpoint reads it to list available labs in the UI.

Each lab file contains:
```json
{
  "id": "lab-id",
  "title": "Lab Title",
  "category": "security|fundamentals|recon",
  "difficulty": "beginner|intermediate|advanced",
  "description": "What you'll learn",
  "steps": [
    {
      "title": "Step Name",
      "instruction": "What to type or do",
      "expected": "What should appear on screen",
      "hint": "Recovery tip if stuck"
    }
  ]
}
```

## Adding a Lab

1. Create `my-lab.json` following the schema above
2. Add an entry to `index.json`
3. The lab appears automatically in the Labs page and Tutor sidebar
