#!/usr/bin/env python3
"""
Integrate External Mainframe Datasets into BigIron-AI Training

Available public datasets:
- MainframeBench (Fsoft-AIC): 7,052 samples (Q&A, MCQ, COBOL summarization)
- IBM CodeNet: COBOL code samples (requires separate download)

Not publicly available:
- XMainframe Instruct: 41,667 training samples (private)
- XMainframe Training: 236M tokens raw data (private)
"""

import json
import re
from pathlib import Path
from typing import Generator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
EXAMPLES_DIR = PROJECT_ROOT / "data" / "training" / "examples"


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def convert_mainframebench_qa() -> Generator[dict, None, None]:
    """Convert MainframeBench Q&A to chat format."""
    qa_file = EXTERNAL_DIR / "mainframebench" / "question_answering_train.jsonl"
    if not qa_file.exists():
        print(f"  Skipping: {qa_file} not found")
        return

    with open(qa_file) as f:
        for line in f:
            item = json.loads(line)
            question = clean_text(item.get("question", ""))
            answer = clean_text(item.get("answer", ""))

            if question and answer:
                yield {
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer}
                    ]
                }


def convert_mainframebench_mcq() -> Generator[dict, None, None]:
    """Convert MainframeBench MCQ to Q&A format."""
    mcq_file = EXTERNAL_DIR / "mainframebench" / "multiple_choice_question_train.jsonl"
    if not mcq_file.exists():
        print(f"  Skipping: {mcq_file} not found")
        return

    with open(mcq_file) as f:
        for line in f:
            item = json.loads(line)
            question = clean_text(item.get("question", ""))
            choices = item.get("choices", [])
            answer_idx = item.get("answer", 0)

            if question and choices and 0 <= answer_idx < len(choices):
                # Format as Q&A with explanation
                answer = choices[answer_idx]
                yield {
                    "messages": [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer}
                    ]
                }


def convert_mainframebench_summarization() -> Generator[dict, None, None]:
    """Convert COBOL summarization to instruction format."""
    sum_file = EXTERNAL_DIR / "mainframebench" / "COBOL_code_summarization_train.jsonl"
    if not sum_file.exists():
        print(f"  Skipping: {sum_file} not found")
        return

    with open(sum_file) as f:
        for line in f:
            item = json.loads(line)
            code = item.get("code", "")
            summary = clean_text(item.get("summary", ""))

            if code and summary:
                yield {
                    "messages": [
                        {"role": "user", "content": f"Explain what this COBOL code does:\n\n```cobol\n{code}\n```"},
                        {"role": "assistant", "content": summary}
                    ]
                }


def main():
    print("=" * 60)
    print("Integrating External Mainframe Datasets")
    print("=" * 60)

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # Track totals
    total_samples = 0

    # Convert MainframeBench Q&A
    print("\n[1/3] MainframeBench Q&A...")
    qa_samples = list(convert_mainframebench_qa())
    if qa_samples:
        out_file = EXAMPLES_DIR / "mainframebench_qa.jsonl"
        with open(out_file, 'w') as f:
            for sample in qa_samples:
                f.write(json.dumps(sample) + '\n')
        print(f"  Saved {len(qa_samples)} samples to {out_file.name}")
        total_samples += len(qa_samples)

    # Convert MainframeBench MCQ
    print("\n[2/3] MainframeBench MCQ...")
    mcq_samples = list(convert_mainframebench_mcq())
    if mcq_samples:
        out_file = EXAMPLES_DIR / "mainframebench_mcq.jsonl"
        with open(out_file, 'w') as f:
            for sample in mcq_samples:
                f.write(json.dumps(sample) + '\n')
        print(f"  Saved {len(mcq_samples)} samples to {out_file.name}")
        total_samples += len(mcq_samples)

    # Convert COBOL Summarization
    print("\n[3/3] MainframeBench COBOL Summarization...")
    sum_samples = list(convert_mainframebench_summarization())
    if sum_samples:
        out_file = EXAMPLES_DIR / "mainframebench_cobol_summary.jsonl"
        with open(out_file, 'w') as f:
            for sample in sum_samples:
                f.write(json.dumps(sample) + '\n')
        print(f"  Saved {len(sum_samples)} samples to {out_file.name}")
        total_samples += len(sum_samples)

    print("\n" + "=" * 60)
    print(f"Total external samples integrated: {total_samples}")
    print("=" * 60)

    # Show current training data totals
    print("\nCurrent training data:")
    total_existing = 0
    for f in EXAMPLES_DIR.glob("*.jsonl"):
        count = sum(1 for _ in open(f))
        print(f"  {f.name}: {count}")
        total_existing += count
    print(f"\nTotal training examples: {total_existing}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
