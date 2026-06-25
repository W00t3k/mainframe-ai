#!/usr/bin/env python3
"""Export local chat corrections into supervised fine-tuning JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "You are BigIron.ai, a mainframe security assistant. "
    "Use mainframe-native reasoning and avoid Unix/Linux assumptions unless explicitly comparing them."
)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc


def export_feedback(input_path: Path, output_path: Path, include_positive: bool = False) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0

    with output_path.open("w", encoding="utf-8") as out:
        for _, record in iter_jsonl(input_path):
            question = str(record.get("question", "")).strip()
            rating = str(record.get("rating", "")).strip().lower()
            correction = str(record.get("correction", "")).strip()
            answer = str(record.get("answer", "")).strip()

            if not question:
                skipped += 1
                continue

            if correction:
                target = correction
            elif include_positive and rating == "right" and answer:
                target = answer
            else:
                skipped += 1
                continue

            sample = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": target},
                ]
            }
            out.write(json.dumps(sample, ensure_ascii=True) + "\n")
            written += 1

    return {"input": str(input_path), "output": str(output_path), "written": written, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export chat feedback corrections to training JSONL.")
    parser.add_argument(
        "--input",
        default="data/feedback/chat_feedback.jsonl",
        help="Input feedback JSONL path.",
    )
    parser.add_argument(
        "--output",
        default="data/training/generated/feedback_sft.jsonl",
        help="Output training JSONL path.",
    )
    parser.add_argument(
        "--include-positive",
        action="store_true",
        help="Also export rating=right records when no correction is provided.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input feedback file does not exist: {input_path}")

    result = export_feedback(input_path, Path(args.output), args.include_positive)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
