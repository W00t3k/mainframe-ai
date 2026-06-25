#!/usr/bin/env python3
"""Validate BigIron.ai training and eval JSONL files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


VALID_ROLES = {"system", "user", "assistant"}


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_training_record(record: Any, line_no: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"line {line_no}: record must be a JSON object"]

    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        return [f"line {line_no}: messages must be a non-empty array"]

    has_user = False
    has_assistant = False
    for idx, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            errors.append(f"line {line_no}: messages[{idx}] must be an object")
            continue

        role = message.get("role")
        content = message.get("content")
        if role not in VALID_ROLES:
            errors.append(
                f"line {line_no}: messages[{idx}].role must be one of "
                f"{', '.join(sorted(VALID_ROLES))}"
            )
        if not non_empty_string(content):
            errors.append(f"line {line_no}: messages[{idx}].content must be a non-empty string")

        has_user = has_user or role == "user"
        has_assistant = has_assistant or role == "assistant"

    if not has_user:
        errors.append(f"line {line_no}: at least one user message is required")
    if not has_assistant:
        errors.append(f"line {line_no}: at least one assistant message is required")

    return errors


def validate_eval_record(record: Any, line_no: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"line {line_no}: record must be a JSON object"]

    if not non_empty_string(record.get("id")):
        errors.append(f"line {line_no}: id must be a non-empty string")
    if not non_empty_string(record.get("question")):
        errors.append(f"line {line_no}: question must be a non-empty string")

    ideal_keywords = record.get("ideal_keywords")
    if not isinstance(ideal_keywords, list) or not ideal_keywords:
        errors.append(f"line {line_no}: ideal_keywords must be a non-empty list")
    else:
        for idx, keyword in enumerate(ideal_keywords, start=1):
            if not non_empty_string(keyword):
                errors.append(
                    f"line {line_no}: ideal_keywords[{idx}] must be a non-empty string"
                )

    return errors


def validate_file(path: Path, mode: str) -> list[str]:
    errors: list[str] = []
    validator = validate_training_record if mode == "training" else validate_eval_record

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [f"{path}: unable to read file: {exc}"]

    if not lines:
        return [f"{path}: file is empty"]

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"line {line_no}: blank lines are not valid JSONL records")
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: invalid JSON: {exc.msg}")
            continue

        errors.extend(validator(record, line_no))

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BigIron.ai JSONL files.")
    parser.add_argument("--mode", choices=("training", "eval"), required=True)
    parser.add_argument("path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_file(args.path, args.mode)
    if errors:
        print(f"FAIL {args.path} ({args.mode})")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK {args.path} ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
