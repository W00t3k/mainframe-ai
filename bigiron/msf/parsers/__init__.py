"""Output parsers for extracting entities from module output."""
from .base import OutputParser
from .registry import parser_for, get_parser
from .tso import TSOEnumParser
from .jcl import JCLOutputParser
from .generic import GenericParser

__all__ = [
    "OutputParser",
    "parser_for",
    "get_parser",
    "TSOEnumParser",
    "JCLOutputParser",
    "GenericParser",
]
