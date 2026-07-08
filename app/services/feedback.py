"""Local chat feedback capture for eval and training data preparation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_config

VALID_RATINGS = {"right", "wrong", "partial"}


def _feedback_path() -> Path:
    path = Path(get_config().BASE_DIR) / "data" / "feedback" / "chat_feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record_chat_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    """Append one local feedback record."""
    question = str(payload.get("question", "")).strip()
    answer = str(payload.get("answer", "")).strip()
    rating = str(payload.get("rating", "")).strip().lower()

    if not question:
        return {"success": False, "error": "question is required"}
    if not answer:
        return {"success": False, "error": "answer is required"}
    if rating not in VALID_RATINGS:
        return {"success": False, "error": "rating must be right, wrong, or partial"}

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": answer,
        "rating": rating,
        "correction": str(payload.get("correction", "")).strip(),
        "notes": str(payload.get("notes", "")).strip(),
        "model": str(payload.get("model", "")).strip(),
        "context_source": str(payload.get("context_source", "")).strip(),
        "answer_mode": str(payload.get("answer_mode", "")).strip(),
        "rag_used": bool(payload.get("rag_used", False)),
        "rag_chunks": int(payload.get("rag_chunks", 0) or 0),
    }

    with _feedback_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")

    return {"success": True, "path": str(_feedback_path()), "record": record}


def feedback_stats() -> dict[str, Any]:
    """Return local feedback counts."""
    path = _feedback_path()
    stats = {
        "path": str(path),
        "total": 0,
        "right": 0,
        "wrong": 0,
        "partial": 0,
        "with_corrections": 0,
    }
    if not path.exists():
        return stats

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            rating = record.get("rating", "")
            stats["total"] += 1
            if rating in VALID_RATINGS:
                stats[rating] += 1
            if str(record.get("correction", "")).strip():
                stats["with_corrections"] += 1

    return stats
