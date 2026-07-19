"""Write layer for schemes — used by the admin dashboard.

The JSON files in ``data/`` are the source of truth. Saving/deleting a scheme
edits the right JSON file and then rebuilds the SQLite runtime store so the
change is live immediately. Every write is validated against the canonical
schema first, so the admin UI can't persist a malformed scheme.

Note: on an ephemeral host these JSON edits are lost on redeploy — the durable
path for production edits is committing to the repo (git / the sync PR flow).
"""

import json
from pathlib import Path
from typing import Any

from .db import _FILE_STATE, DB_PATH, build_db
from .schema import validate_scheme

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
# state name -> filename (invert _FILE_STATE, dropping the central None entry)
_STATE_FILE = {state: name for name, state in _FILE_STATE.items() if state}
_CENTRAL_FILE = "schemes_central.json"


def _file_for(scheme: dict[str, Any]) -> Path:
    """Which JSON file a scheme belongs in (state file if state-specific)."""
    if scheme.get("state_specific"):
        states = scheme.get("eligibility", {}).get("states") or []
        if isinstance(states, list) and states and states[0] in _STATE_FILE:
            return _DATA_DIR / _STATE_FILE[states[0]]
    return _DATA_DIR / _CENTRAL_FILE


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, data: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _all_ids() -> set[str]:
    ids: set[str] = set()
    for name in _FILE_STATE:
        for s in _load(_DATA_DIR / name):
            ids.add(s["id"])
    return ids


def save_scheme(scheme: dict[str, Any], original_id: str | None = None) -> dict[str, Any]:
    """Create or update a scheme. Returns {"ok": bool, "errors": [...]}.

    ``original_id`` is the id being edited (None for a new scheme); it lets an
    edit change other fields while catching duplicate ids on create/rename.
    """
    errors = validate_scheme(scheme)
    if errors:
        return {"ok": False, "errors": errors}

    sid = scheme["id"]
    existing = _all_ids()
    if sid in existing and sid != original_id:
        return {"ok": False, "errors": [f"A scheme with id '{sid}' already exists"]}

    # If the id/target file changed, remove the old record first.
    if original_id and original_id != sid:
        delete_scheme(original_id, rebuild=False)
    elif original_id:
        # same id — remove old copy (it may have moved files if state changed)
        delete_scheme(original_id, rebuild=False)

    target = _file_for(scheme)
    data = _load(target)
    data = [s for s in data if s["id"] != sid]
    data.append(scheme)
    try:
        _write(target, data)
        build_db(DB_PATH, force=True)
    except OSError:
        # Read-only filesystem (e.g. Vercel) — scheme data can't be edited live.
        return {
            "ok": False,
            "errors": [
                "This host has a read-only filesystem, so scheme edits can't be "
                "saved here. Edit the JSON in the git repo (the source of truth) "
                "and redeploy."
            ],
        }
    return {"ok": True, "errors": []}


def delete_scheme(scheme_id: str, rebuild: bool = True) -> bool:
    """Remove a scheme from whichever file holds it. Returns True if removed."""
    removed = False
    for name in _FILE_STATE:
        path = _DATA_DIR / name
        data = _load(path)
        new = [s for s in data if s["id"] != scheme_id]
        if len(new) != len(data):
            _write(path, new)
            removed = True
    if removed and rebuild:
        build_db(DB_PATH, force=True)
    return removed
