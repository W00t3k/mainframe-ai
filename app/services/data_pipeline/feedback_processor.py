"""Process feedback JSONL to extract corrections."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.seed_index.fuzzy import normalize


class FeedbackProcessor:
    """Process user feedback to extract and approve corrections."""

    def __init__(
        self,
        feedback_path: Path,
        output_dir: Path,
        threshold: int = 3,
    ):
        self.feedback_path = feedback_path
        self.output_dir = output_dir
        self.threshold = threshold
        self.approved_dir = output_dir / "approved"
        self.pending_dir = output_dir / "pending"

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load feedback entries from JSONL."""
        if not self.feedback_path.exists():
            return []

        entries = []
        for line in self.feedback_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def process(self) -> dict[str, Any]:
        """Process feedback and generate correction files."""
        entries = self._load_feedback()

        # Extract corrections (rating=wrong with correction text)
        corrections: list[dict[str, str]] = []
        for entry in entries:
            if entry.get("rating") == "wrong" and entry.get("correction"):
                corrections.append({
                    "question": entry.get("question", ""),
                    "correction": entry["correction"],
                })

        if not corrections:
            return {
                "corrections_found": 0,
                "auto_approved": 0,
                "pending": 0,
            }

        # Group by normalized question + correction
        grouped: dict[str, list[dict]] = {}
        for c in corrections:
            key = normalize(c["question"]) + "||" + normalize(c["correction"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(c)

        # Separate into auto-approved and pending
        auto_approved = []
        pending = []

        for key, items in grouped.items():
            if len(items) >= self.threshold:
                auto_approved.append(items[0])
            else:
                pending.append(items[0])

        # Write approved corrections
        if auto_approved:
            self.approved_dir.mkdir(parents=True, exist_ok=True)
            approved_file = self.approved_dir / "corrections.md"
            lines = self._format_corrections(auto_approved, "Auto-Approved")
            self._append_to_file(approved_file, lines)

        # Write pending corrections
        if pending:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            pending_file = self.pending_dir / "corrections.md"
            lines = self._format_corrections(pending, "Pending Review")
            self._append_to_file(pending_file, lines)

        return {
            "corrections_found": len(corrections),
            "auto_approved": len(auto_approved),
            "pending": len(pending),
        }

    def _format_corrections(
        self,
        corrections: list[dict[str, str]],
        section_title: str,
    ) -> str:
        """Format corrections as markdown."""
        lines = [
            f"# {section_title} Corrections",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        for c in corrections:
            question = c.get("question", "Unknown")
            correction = c.get("correction", "")
            lines.append(f"### {question}")
            lines.append(f"Definition: {correction}")
            lines.append("")

        return "\n".join(lines)

    def _append_to_file(self, path: Path, content: str) -> None:
        """Append content to file, creating if needed."""
        mode = "a" if path.exists() else "w"
        with path.open(mode, encoding="utf-8") as f:
            f.write(content + "\n")
