"""Tests for the canonical scheme validator in scheme_checker.schema."""

from scheme_checker.schema import validate_scheme


def _valid_scheme(**overrides):
    base = {
        "id": "test_scheme",
        "name_en": "Test",
        "name_hi": "टेस्ट",
        "name_gu": "ટેસ્ટ",
        "ministry": "Test Ministry",
        "category": "finance",
        "benefit_en": "Some benefit",
        "benefit_amount": 1000,
        "apply_link": "https://example.gov.in",
        "eligibility": {"states": "all"},
        "documents": ["Aadhaar card"],
        "steps_en": ["Step 1"],
        "rejection_reasons": ["Reason"],
        "scam_note": "It is free.",
        "processing_days": "30",
        "tags": ["test"],
        "state_specific": False,
    }
    base.update(overrides)
    return base


def test_valid_scheme_has_no_errors():
    assert validate_scheme(_valid_scheme()) == []


def test_missing_field_reported():
    s = _valid_scheme()
    del s["scam_note"]
    errors = validate_scheme(s)
    assert any("scam_note" in e for e in errors)


def test_wrong_type_reported():
    errors = validate_scheme(_valid_scheme(benefit_amount="lots"))
    assert any("benefit_amount" in e for e in errors)


def test_bool_rejected_for_int_field():
    errors = validate_scheme(_valid_scheme(benefit_amount=True))
    assert any("benefit_amount" in e for e in errors)


def test_invalid_category_reported():
    errors = validate_scheme(_valid_scheme(category="space_travel"))
    assert any("category" in e for e in errors)


def test_non_url_apply_link_reported():
    errors = validate_scheme(_valid_scheme(apply_link="example.gov.in"))
    assert any("apply_link" in e for e in errors)


def test_unknown_eligibility_key_reported():
    errors = validate_scheme(_valid_scheme(eligibility={"states": "all", "zodiac": "leo"}))
    assert any("zodiac" in e for e in errors)


def test_missing_states_reported():
    errors = validate_scheme(_valid_scheme(eligibility={"age_min": 18}))
    assert any("states" in e for e in errors)


def test_optional_metadata_accepted_when_valid():
    assert (
        validate_scheme(
            _valid_scheme(source_url="https://myscheme.gov.in/x", last_verified="2026-06-28")
        )
        == []
    )


def test_optional_metadata_wrong_type_reported():
    errors = validate_scheme(_valid_scheme(last_verified=20260628))
    assert any("last_verified" in e for e in errors)
