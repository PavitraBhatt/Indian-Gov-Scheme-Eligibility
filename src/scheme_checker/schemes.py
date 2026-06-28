"""Scheme access layer.

Thin wrapper over the SQLite runtime store in :mod:`scheme_checker.db`. The
JSON files in ``data/`` remain the source of truth; ``db`` builds and serves a
SQLite database from them. These functions keep their original signatures so
callers (core, api, cli) are unaffected by the storage change.
"""

from typing import Any

from .db import get_scheme, query_schemes


def load_schemes(states: list[str] | None = None) -> list[dict[str, Any]]:
    """Load central schemes plus any for the given states."""
    return query_schemes(states=states)


def get_scheme_by_id(scheme_id: str) -> dict[str, Any] | None:
    """Return a single scheme by its id, or None if not found."""
    return get_scheme(scheme_id)
