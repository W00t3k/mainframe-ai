"""
Labs API Routes

Endpoints for lab exercises and guided learning.
"""

import os
import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_config

router = APIRouter(tags=["labs"])
config = get_config()


def read_json_file(path: str, default: dict) -> dict:
    """Read a JSON file with fallback to default."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"Failed to read JSON {path}: {exc}")
        return default


@router.get("")
async def api_labs_index():
    """Get labs index - merges static labs with agentic labs."""
    from app.constants.agentic_labs import AGENTIC_LABS

    # Start with agentic labs (these are the primary ones)
    labs = []
    for lab_id, lab in AGENTIC_LABS.items():
        if lab.get("disabled"):
            continue
        labs.append({
            "id": lab_id,
            "title": lab.get("title", lab_id),
            "description": lab.get("description", ""),
            "category": "fundamentals",
            "difficulty": "beginner",
            "status": "working",
            "walkthrough": True,
            "agentic": True,
            "steps": len(lab["steps"]),
        })

    # Add any static labs not in agentic labs
    index_path = os.path.join(config.LAB_DATA_DIR, "index.json")
    static_data = read_json_file(index_path, {"labs": []})
    agentic_ids = set(AGENTIC_LABS.keys())
    for lab in static_data.get("labs", []):
        if lab.get("id") not in agentic_ids:
            labs.append(lab)

    return JSONResponse({"labs": labs})


@router.get("/{lab_id}")
async def api_labs_detail(lab_id: str):
    """Get lab details."""
    lab_path = os.path.join(config.LAB_DATA_DIR, f"{lab_id}.json")
    if not os.path.exists(lab_path):
        return JSONResponse({"error": "Lab not found"}, status_code=404)
    
    data = read_json_file(lab_path, {})
    if not data:
        return JSONResponse({"error": "Lab not available"}, status_code=404)
    
    return JSONResponse(data)
