#!/usr/bin/env python3
"""Process feedback corrections into seed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_pipeline.feedback_processor import FeedbackProcessor


def main() -> int:
    parser = argparse.ArgumentParser(description="Process feedback corrections.")
    parser.add_argument(
        "--input",
        default="data/feedback/chat_feedback.jsonl",
        help="Feedback JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag_seed",
        help="Output directory for corrections.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Corrections needed for auto-approval.",
    )
    args = parser.parse_args()

    processor = FeedbackProcessor(
        ROOT / args.input,
        ROOT / args.output_dir,
        threshold=args.threshold,
    )
    result = processor.process()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
