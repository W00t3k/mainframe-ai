"""Auto-generate eval cases from feedback."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.services.seed_index.fuzzy import normalize


class EvalGenerator:
    """Generate eval cases from user feedback."""

    def __init__(self, feedback_path: Path):
        self.feedback_path = feedback_path

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load feedback entries."""
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

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Extract significant keywords from text."""
        # Simple extraction: words longer than 3 chars, not common
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "been", "will", "more", "when", "what", "this",
            "that", "with", "from", "they", "which", "about", "into",
        }

        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        keywords = [w for w in words if w not in stop_words]

        # Dedupe while preserving order
        seen = set()
        unique = []
        for w in keywords:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        return unique[:max_keywords]

    def _is_duplicate(
        self,
        question: str,
        existing: list[dict[str, Any]],
        threshold: float = 0.85,
    ) -> bool:
        """Check if question is too similar to existing."""
        normalized = normalize(question)
        for e in existing:
            existing_normalized = normalize(e.get("question", ""))
            ratio = SequenceMatcher(None, normalized, existing_normalized).ratio()
            if ratio >= threshold:
                return True
        return False

    def generate(self) -> list[dict[str, Any]]:
        """Generate eval cases from feedback."""
        feedback = self._load_feedback()
        evals = []
        id_counter = 1

        for entry in feedback:
            question = entry.get("question", "")
            rating = entry.get("rating", "")

            if not question:
                continue

            # Skip duplicates
            if self._is_duplicate(question, evals):
                continue

            if rating == "right":
                # Use answer keywords for expected output
                answer = entry.get("answer", "")
                keywords = self._extract_keywords(answer)
                if keywords:
                    evals.append({
                        "id": f"auto-{id_counter:03d}",
                        "question": question,
                        "ideal_keywords": keywords,
                        "source": "feedback_right",
                    })
                    id_counter += 1

            elif rating == "wrong" and entry.get("correction"):
                # Use correction keywords for expected output
                correction = entry.get("correction", "")
                keywords = self._extract_keywords(correction)
                if keywords:
                    evals.append({
                        "id": f"auto-{id_counter:03d}",
                        "question": question,
                        "ideal_keywords": keywords,
                        "source": "feedback_wrong",
                    })
                    id_counter += 1

        return evals

    def write_evals(self, output_path: Path) -> dict[str, Any]:
        """Generate and write evals to JSONL file."""
        evals = self.generate()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for e in evals:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

        return {
            "path": str(output_path),
            "count": len(evals),
        }
