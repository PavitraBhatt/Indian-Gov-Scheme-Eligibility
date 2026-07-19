"""Vercel serverless entrypoint for SchemeSaathi.

Vercel runs this as a Python serverless function; @vercel/python detects the
ASGI ``app`` object and serves the whole FastAPI app from it.

Vercel's filesystem is read-only except for ``/tmp``, so the SQLite scheme
cache (rebuilt from the JSON source each cold start) and any SQLite event-log
fallback live under ``/tmp``. Real analytics persist to Neon via ``DATABASE_URL``.
"""

import os
import sys
from pathlib import Path

# The package lives in ./src — make it importable in the function sandbox.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

# Writable, ephemeral paths (the project fs is read-only on Vercel).
os.environ.setdefault("SCHEME_DB_PATH", "/tmp/schemes.db")
os.environ.setdefault("SCHEME_EVENTS_DB", "/tmp/events.db")

from scheme_checker.api import app  # noqa: E402

__all__ = ["app"]
