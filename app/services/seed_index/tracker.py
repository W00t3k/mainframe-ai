"""Track query misses for backlog prioritization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QueryMissTracker:
    """Log query misses for backlog generation."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_miss(
        self,
        query: str,
        mode: str,
        suggestions: list[str] | None = None,
    ) -> None:
        """Append a query miss to the log."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "mode": mode,
            "suggestions": suggestions or [],
        }

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_misses(self) -> list[dict[str, Any]]:
        """Read all logged misses."""
        if not self.log_path.exists():
            return []

        misses = []
        for line in self.log_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    misses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return misses

    def clear(self) -> None:
        """Clear the miss log."""
        if self.log_path.exists():
            self.log_path.unlink()
