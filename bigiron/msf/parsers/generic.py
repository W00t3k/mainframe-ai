"""Generic fallback parser for unknown modules."""
import re
from typing import Any

from .base import OutputParser


class GenericParser(OutputParser):
    """Fallback parser that extracts common patterns."""

    PATTERNS = [
        # Users
        (re.compile(r'(?:user|username|userid)[:\s]+(\w+)', re.I), "user"),
        # Datasets
        (re.compile(r'([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9]*){2,})', re.I), "dataset"),
        # Jobs
        (re.compile(r'JOB[:\s]*([A-Z0-9]{5,8})', re.I), "job"),
        # Transactions
        (re.compile(r'(?:transaction|tran)[:\s]+(\w{4})', re.I), "transaction"),
        # IPs
        (re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', re.I), "host"),
    ]

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract entities using generic patterns."""
        entities = []
        seen = set()

        for pattern, node_type in self.PATTERNS:
            for match in pattern.finditer(output):
                value = match.group(1)
                key = f"{node_type}:{value}"

                if key in seen:
                    continue
                seen.add(key)

                entities.append({
                    "node_type": node_type,
                    "label": value,
                    "properties": {
                        "source": "generic_parser",
                        "value": value
                    }
                })

        return entities
