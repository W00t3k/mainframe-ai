"""
Legacy entry point — all routes have been migrated to app/routes/.

The active application is now app/main.py (run via run.py).
This module re-exports the app instance for any tooling that still references
tools.web_app:app.
"""

from app.main import app  # noqa: F401
