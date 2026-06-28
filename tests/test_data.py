"""Validates the integrity of every scheme in the JSON database.

These tests are the safety net that stops a malformed scheme entry from
reaching production. They run in CI, so a missing field or wrong type
fails the build before merge.
"""
import json
from pathlib import Path

import pytest

_DATA_DIR = Path(__file__).parent.parent / "data"

# field name -> expected python type
REQUIRED_FIELDS = {
    "id": str,
    "name_en": str,
    "name_hi": str,
    "name_gu": str,
    "ministry": str,
    "category": str,
    "benefit_en": str,
    "benefit_amount": int,
    "apply_link": str,
    "eligibility": dict,
    "documents": list,
    "steps_en": list,
    "rejection_reasons": list,
    "scam_note": str,
    "processing_days": str,
    "tags": list,
    "state_specific": bool,
}

VALID_CATEGORIES = {
    "agriculture", "health", "housing", "insurance", "finance",
    "women_children", "education_youth", "senior_disability", "energy",
}

# keys allowed inside the "eligibility" object (matches core._check_eligibility)
VALID_ELIGIBILITY_KEYS = {
    "states", "age_min", "age_max", "gender", "caste", "income_max",
    "occupation", "land_min_acres", "requires_bpl", "requires_disability",
    "requires_widow",
}


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


@pytest.mark.parametrize("filename,scheme", _all_schemes(),
                         ids=[f"{f}:{s.get('id','?')}" for f, s in _all_schemes()])
def test_scheme_has_all_required_fields(filename, scheme):
    for field, expected_type in REQUIRED_FIELDS.items():
        assert field in scheme, f"{filename}: scheme '{scheme.get('id','?')}' missing field '{field}'"
        value = scheme[field]
        # bool is a subclass of int — guard benefit_amount against True/False
        if expected_type is int:
            assert isinstance(value, int) and not isinstance(value, bool), \
                f"{filename}: '{scheme['id']}.{field}' must be int, got {type(value).__name__}"
        else:
            assert isinstance(value, expected_type), \
                f"{filename}: '{scheme['id']}.{field}' must be {expected_type.__name__}, got {type(value).__name__}"


@pytest.mark.parametrize("filename,scheme", _all_schemes(),
                         ids=[f"{f}:{s.get('id','?')}" for f, s in _all_schemes()])
def test_scheme_field_values_are_sane(filename, scheme):
    sid = scheme.get("id", "?")
    assert scheme["category"] in VALID_CATEGORIES, \
        f"{filename}: '{sid}' has invalid category '{scheme['category']}'"
    assert scheme["benefit_amount"] >= 0, f"{filename}: '{sid}' benefit_amount must be >= 0"
    assert scheme["apply_link"].startswith("http"), \
        f"{filename}: '{sid}' apply_link must be a URL"
    assert scheme["documents"], f"{filename}: '{sid}' must list at least one document"
    assert scheme["steps_en"], f"{filename}: '{sid}' must list at least one step"
    assert scheme["scam_note"].strip(), f"{filename}: '{sid}' scam_note must not be empty"


@pytest.mark.parametrize("filename,scheme", _all_schemes(),
                         ids=[f"{f}:{s.get('id','?')}" for f, s in _all_schemes()])
def test_eligibility_keys_are_known(filename, scheme):
    for key in scheme["eligibility"]:
        assert key in VALID_ELIGIBILITY_KEYS, \
            f"{filename}: '{scheme['id']}' has unknown eligibility key '{key}'"


@pytest.mark.parametrize("filename,scheme", _all_schemes(),
                         ids=[f"{f}:{s.get('id','?')}" for f, s in _all_schemes()])
def test_eligibility_states_field(filename, scheme):
    states = scheme["eligibility"].get("states")
    assert states is not None, f"{filename}: '{scheme['id']}' eligibility must have 'states'"
    assert states == "all" or isinstance(states, list), \
        f"{filename}: '{scheme['id']}' states must be 'all' or a list"


def test_no_duplicate_ids_across_all_files():
    ids = [s["id"] for _, s in _all_schemes()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"Duplicate scheme IDs found: {dupes}"


def test_state_specific_schemes_not_in_central():
    central = _load(_DATA_DIR / "schemes_central.json")
    for scheme in central:
        assert scheme["eligibility"].get("states") == "all", \
            f"Central scheme '{scheme['id']}' should apply to all states"
        assert scheme["state_specific"] is False, \
            f"Central scheme '{scheme['id']}' should have state_specific=False"
