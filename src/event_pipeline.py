"""
Legacy entrypoint shim.

The active FastAPI application is `api.main:app`.
This file is kept only for backward compatibility with old launch commands.
Legacy implementation moved to:
`archive/legacy_groq/event_pipeline_legacy.py`
"""

from api.main import app

__all__ = ["app"]
