"""Parser for TSO enumeration output."""
import re
from typing import Any

from .base import OutputParser
from .registry import parser_for


@parser_for("auxiliary/scanner/mainframe/tso_enum")
@parser_for("*/tso_enum")
class TSOEnumParser(OutputParser):
    """Parses TSO user enumeration output."""

    # Pattern for valid user lines
    USER_PATTERN = re.compile(r'\[\+\]\s*(?:Valid user found|Found):\s*(\w+)', re.IGNORECASE)

    def parse(self, output: str) -> list[dict[str, Any]]:
        """Extract discovered TSO users from output."""
        entities = []

        for match in self.USER_PATTERN.finditer(output):
            username = match.group(1).upper()
            entities.append({
                "node_type": "user",
                "label": username,
                "properties": {
                    "source": "tso_enum",
                    "username": username
                }
            })

        return entities
