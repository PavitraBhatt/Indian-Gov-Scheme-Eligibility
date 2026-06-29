"""Tests for the Claude-assisted normalizer (completer is injected — no API call)."""

from scheme_checker.sync.normalize import normalize_scheme, slug_to_id


def _good_content():
    """A well-formed Claude response for a farmer income-support scheme."""
    return {
        "name_en": "PM Sample Yojana",
        "name_hi": "पीएम सैंपल योजना",
        "name_gu": "પીએમ સેમ્પલ યોજના",
        "ministry": "Ministry of Agriculture",
        "category": "agriculture",
        "benefit_en": "Rs 6,000 per year income support",
        "benefit_amount": 6000,
        "benefit_type": "cash_yearly",
        "apply_link": "https://example.gov.in",
        "eligibility": {"states": "all", "occupation": ["farmer"]},
        "documents": ["Aadhaar card", "Bank passbook"],
        "steps_en": ["Visit the portal", "Submit Aadhaar", "Get benefit"],
        "rejection_reasons": ["Income too high"],
        "scam_note": "This scheme is free. Report fraud to 155261.",
        "processing_days": "30-60",
        "tags": ["agriculture", "income_support"],
    }


def _raw(**overrides):
    base = {
        "source_id": "pm-sample-yojana",
        "name_en": "PM Sample Yojana",
        "source_url": "https://www.myscheme.gov.in/schemes/pm-sample-yojana",
        "text": "An income support scheme for farmers worth Rs 6,000 a year.",
    }
    base.update(overrides)
    return base


def test_slug_to_id():
    assert slug_to_id("pm-kisan-samman") == "pm_kisan_samman"
    assert slug_to_id("PM Kisan 2.0") == "pm_kisan_2_0"
    assert slug_to_id("") == "scheme"


def test_normalize_valid_scheme():
    scheme, errors = normalize_scheme(
        _raw(), last_verified="2026-06-28", completer=lambda s, u, sch: _good_content()
    )
    assert errors == []
    assert scheme["id"] == "pm_sample_yojana"
    assert scheme["source_url"].endswith("pm-sample-yojana")
    assert scheme["last_verified"] == "2026-06-28"
    assert scheme["state_specific"] is False


def test_normalize_fills_identity_fields_not_from_model():
    """id/source_url/last_verified/state_specific come from code, not the model."""
    content = _good_content()
    content["id"] = "HACKED"  # model tries to set id — must be ignored
    scheme, _ = normalize_scheme(
        _raw(), last_verified="2026-06-28", completer=lambda s, u, sch: _good_content()
    )
    assert scheme["id"] == "pm_sample_yojana"


def test_normalize_defaults_states_to_all():
    content = _good_content()
    content["eligibility"] = {"occupation": ["farmer"]}  # model omitted states
    scheme, errors = normalize_scheme(
        _raw(), last_verified="2026-06-28", completer=lambda s, u, sch: content
    )
    assert scheme["eligibility"]["states"] == "all"
    assert errors == []


def test_normalize_invalid_scheme_reports_errors():
    bad = _good_content()
    bad["category"] = "not_a_category"
    bad["scam_note"] = ""  # empty scam note is invalid
    scheme, errors = normalize_scheme(
        _raw(), last_verified="2026-06-28", completer=lambda s, u, sch: bad
    )
    assert errors  # must be flagged, not published
    assert any("category" in e for e in errors)
    assert any("scam_note" in e for e in errors)


def test_completer_receives_schema_and_prompt():
    seen = {}

    def spy(system, user, schema):
        seen["system"] = system
        seen["user"] = user
        seen["schema"] = schema
        return _good_content()

    normalize_scheme(_raw(), last_verified="2026-06-28", completer=spy)
    assert "category" in seen["schema"]["properties"]
    assert "PM Sample Yojana" in seen["user"]
    assert "Gujarati" in seen["system"]
