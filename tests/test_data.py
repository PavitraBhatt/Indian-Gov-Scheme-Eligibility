"""Validates the integrity of every scheme in the JSON database.

The per-scheme rules live in :mod:`scheme_checker.schema` so the sync pipeline
holds synced data to the exact same bar. These tests run in CI, so a missing
field or wrong type fails the build before merge.
"""

import json
from pathlib import Path

import pytest

from scheme_checker.schema import validate_scheme

_DATA_DIR = Path(__file__).parent.parent / "data"


def _all_scheme_files():
    return sorted(_DATA_DIR.glob("schemes_*.json"))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _all_schemes():
    schemes = []
    for path in _all_scheme_files():
        for scheme in _load(path):
            schemes.append((path.name, scheme))
    return schemes


def test_data_dir_has_files():
    assert _all_scheme_files(), "No schemes_*.json files found in data/"


def test_each_file_is_a_json_list():
    for path in _all_scheme_files():
        data = _load(path)
        assert isinstance(data, list), f"{path.name} must be a JSON array"
        assert len(data) > 0, f"{path.name} is empty"


@pytest.mark.parametrize(
    "filename,scheme", _all_schemes(), ids=[f"{f}:{s.get('id', '?')}" for f, s in _all_schemes()]
)
def test_scheme_is_valid(filename, scheme):
    errors = validate_scheme(scheme)
    assert not errors, f"{filename}: " + "; ".join(errors)


def test_no_duplicate_ids_across_all_files():
    ids = [s["id"] for _, s in _all_schemes()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"Duplicate scheme IDs found: {dupes}"


def test_state_specific_schemes_not_in_central():
    central = _load(_DATA_DIR / "schemes_central.json")
    for scheme in central:
        assert scheme["eligibility"].get("states") == "all", (
            f"Central scheme '{scheme['id']}' should apply to all states"
        )
        assert scheme["state_specific"] is False, (
            f"Central scheme '{scheme['id']}' should have state_specific=False"
        )
