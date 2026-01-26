"""
Big Iron Recon & Pwnage (BIRP) v2 — bigger, better, and focused on modern offensive research against legacy and mainframe environments.
"""

__version__ = '2.0.0'
__author__ = '@w00tock (based on original by Dominic White @singe at SensePost)'

# Core data models
from .core.models import Field, Screen, Transaction, History

# Export functionality
from .io.exporters import (
    export_to_json,
    export_to_csv,
    export_to_html,
    export_to_xml,
    auto_export
)

# Logging
from .utils.logger import BIRPLogger, create_logger

# Search utilities
from .utils.search import find_all, find_first

__all__ = [
    # Version info
    '__version__',
    '__author__',

    # Core models
    'Field',
    'Screen',
    'Transaction',
    'History',

    # Export functions
    'export_to_json',
    'export_to_csv',
    'export_to_html',
    'export_to_xml',
    'auto_export',

    # Logging
    'BIRPLogger',
    'create_logger',

    # Search
    'find_all',
    'find_first',
]
