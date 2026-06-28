"""Diff normalized schemes against the current database.

Classifies each incoming scheme as NEW (id not in the DB), CHANGED (id present
but content differs), or UNCHANGED. ``last_verified`` is ignored when comparing
content, so a re-sync that only refreshes the verification date doesn't show up
as a change.
"""

from typing import Any

NEW = "new"
CHANGED = "changed"
UNCHANGED = "unchanged"

# Fields that don't affect the scheme's meaning — excluded from change detection.
_IGNORED_ON_COMPARE = {"last_verified"}


def _comparable(scheme: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in scheme.items() if k not in _IGNORED_ON_COMPARE}


def classify(incoming: dict[str, Any], current_by_id: dict[str, dict]) -> str:
    existing = current_by_id.get(incoming["id"])
    if existing is None:
        return NEW
    if _comparable(existing) == _comparable(incoming):
        return UNCHANGED
    return CHANGED


def diff_schemes(
    incoming: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Bucket incoming schemes into new / changed / unchanged.

    Returns a dict with keys 'new', 'changed', 'unchanged', each a list of
    schemes. 'changed' entries carry an extra '_previous' key with the old
    record so a reviewer can see exactly what moved.
    """
    current_by_id = {s["id"]: s for s in current}
    buckets: dict[str, list[dict[str, Any]]] = {NEW: [], CHANGED: [], UNCHANGED: []}

    for scheme in incoming:
        kind = classify(scheme, current_by_id)
        if kind == CHANGED:
            entry = dict(scheme)
            entry["_previous"] = current_by_id[scheme["id"]]
            buckets[CHANGED].append(entry)
        else:
            buckets[kind].append(scheme)

    return buckets


def summarize(buckets: dict[str, list[dict[str, Any]]]) -> str:
    """A short human-readable summary for PR titles / logs."""
    return (
        f"{len(buckets[NEW])} new, "
        f"{len(buckets[CHANGED])} changed, "
        f"{len(buckets[UNCHANGED])} unchanged"
    )
