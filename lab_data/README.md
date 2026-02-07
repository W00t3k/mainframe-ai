# Lab Data (`lab_data/`)

Security lab exercise definitions in JSON format.

## Structure

### `index.json`
Lab index with metadata:
```json
{
  "labs": [
    {"id": "lab-id", "title": "Lab Title", "steps": 5}
  ]
}
```

### Individual Lab Files
Each lab is a JSON file (e.g., `batch-basics.json`) containing:
- `title` - Lab display name
- `description` - Lab overview
- `steps` - Array of step objects with instructions

## Adding New Labs

1. Create a new JSON file in this directory
2. Add entry to `index.json`
3. Define steps with `title`, `instruction`, `expected`, and `hint` fields

## Available Labs

- `batch-basics.json` - JCL and batch job execution
- `session-stack.json` - VTAM → TSO → ISPF navigation
