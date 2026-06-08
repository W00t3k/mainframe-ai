"""Base class for output parsers."""
from abc import ABC, abstractmethod
from typing import Any


class OutputParser(ABC):
    """Base class for module output parsers.

    Parsers extract entities from module output and return them
    as dictionaries ready to become graph nodes.
    """

    @abstractmethod
    def parse(self, output: str) -> list[dict[str, Any]]:
        """Parse module output and extract entities.

        Args:
            output: Raw module output text

        Returns:
            List of entity dictionaries with:
            - node_type: The NodeType value (as string)
            - label: Human-readable label
            - properties: Additional properties dict
        """
        pass
