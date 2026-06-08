"""Metasploit integration layer."""
from .client import MsfClient
from .models import (
    ModuleSummary,
    ModuleDetail,
    ModuleOption,
    ExecutionPreview,
    ExecutionResult,
)
from .catalog import CatalogService
from .executor import ExecutorService
from .authorization import Authorization, AuthorizationGate
from .parsers import get_parser, parser_for, OutputParser

__all__ = [
    "MsfClient",
    "ModuleSummary",
    "ModuleDetail",
    "ModuleOption",
    "ExecutionPreview",
    "ExecutionResult",
    "CatalogService",
    "ExecutorService",
    "Authorization",
    "AuthorizationGate",
    "get_parser",
    "parser_for",
    "OutputParser",
]
