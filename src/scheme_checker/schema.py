"""Canonical definition of a scheme record.

Single source of truth for the scheme shape, shared by the data-integrity tests
and the sync pipeline's normalizer. Keeping it here means the rules a synced
scheme must satisfy are exactly the rules the existing database is held to.
"""

from typing import Any

# field name -> expected python type (bool handled specially against int)
REQUIRED_FIELDS: dict[str, type] = {
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

# Optional metadata, populated by the sync pipeline. Existing hand-written
# schemes may omit these; when present they must have the right type.
OPTIONAL_FIELDS: dict[str, type] = {
    "source_url": str,  # official government page this record was sourced from
    "last_verified": str,  # ISO date (YYYY-MM-DD) the data was last checked
}

VALID_CATEGORIES: set[str] = {
    "agriculture",
    "health",
    "housing",
    "insurance",
    "finance",
    "women_children",
    "education_youth",
    "senior_disability",
    "energy",
}

# keys allowed inside the "eligibility" object (matches core._check_eligibility)
VALID_ELIGIBILITY_KEYS: set[str] = {
    "states",
    "age_min",
    "age_max",
    "gender",
    "caste",
    "income_max",
    "occupation",
    "land_min_acres",
    "requires_bpl",
    "requires_disability",
    "requires_widow",
}


def _type_ok(value: Any, expected: type) -> bool:
    if expected is int:
        # bool is a subclass of int — reject True/False for int fields
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def validate_scheme(scheme: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems with a scheme dict.

    An empty list means the scheme is valid. Used by both the test suite and
    the sync pipeline so synced data meets the same bar as hand-written data.
    """
    errors: list[str] = []
    sid = scheme.get("id", "?")

    for field, expected in REQUIRED_FIELDS.items():
        if field not in scheme:
            errors.append(f"'{sid}': missing required field '{field}'")
        elif not _type_ok(scheme[field], expected):
            errors.append(
                f"'{sid}.{field}': expected {expected.__name__}, got {type(scheme[field]).__name__}"
            )

    for field, expected in OPTIONAL_FIELDS.items():
        if field in scheme and not _type_ok(scheme[field], expected):
            errors.append(
                f"'{sid}.{field}': expected {expected.__name__}, got {type(scheme[field]).__name__}"
            )

    # value-level checks (only if the field is present and the right type)
    if isinstance(scheme.get("category"), str) and scheme["category"] not in VALID_CATEGORIES:
        errors.append(f"'{sid}.category': invalid category '{scheme['category']}'")
    if _type_ok(scheme.get("benefit_amount"), int) and scheme["benefit_amount"] < 0:
        errors.append(f"'{sid}.benefit_amount': must be >= 0")
    if isinstance(scheme.get("apply_link"), str) and not scheme["apply_link"].startswith("http"):
        errors.append(f"'{sid}.apply_link': must be a URL")
    if isinstance(scheme.get("documents"), list) and not scheme["documents"]:
        errors.append(f"'{sid}.documents': must list at least one document")
    if isinstance(scheme.get("steps_en"), list) and not scheme["steps_en"]:
        errors.append(f"'{sid}.steps_en': must list at least one step")
    if isinstance(scheme.get("scam_note"), str) and not scheme["scam_note"].strip():
        errors.append(f"'{sid}.scam_note': must not be empty")

    elig = scheme.get("eligibility")
    if isinstance(elig, dict):
        for key in elig:
            if key not in VALID_ELIGIBILITY_KEYS:
                errors.append(f"'{sid}.eligibility': unknown key '{key}'")
        states = elig.get("states")
        if states is None:
            errors.append(f"'{sid}.eligibility': must have 'states'")
        elif states != "all" and not isinstance(states, list):
            errors.append(f"'{sid}.eligibility.states': must be 'all' or a list")

    return errors
