"""Tests for the password-gated admin dashboard."""

import pytest
from fastapi.testclient import TestClient

from scheme_checker.api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    return TestClient(app)


def _login(client):
    return client.post("/admin/login", data={"password": "s3cret"}, follow_redirects=False)


# ── auth ───────────────────────────────────────────────────
def test_admin_requires_login(client):
    for path in ["/admin", "/admin/analytics", "/admin/schemes", "/admin/schemes/new"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303
        assert "/admin/login" in r.headers["location"]


def test_wrong_password_rejected(client):
    r = client.post("/admin/login", data={"password": "nope"}, follow_redirects=False)
    assert r.status_code == 303
    assert "error" in r.headers["location"]
    # still not authed
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_login_and_access(client):
    r = _login(client)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/analytics").status_code == 200
    assert client.get("/admin/schemes").status_code == 200


def test_logout(client):
    _login(client)
    assert client.get("/admin").status_code == 200
    client.get("/admin/logout", follow_redirects=False)
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_disabled_when_no_password(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    c = TestClient(app)
    r = c.post("/admin/login", data={"password": "anything"}, follow_redirects=False)
    assert "error" in r.headers["location"]
    assert c.get("/admin", follow_redirects=False).status_code == 303


def test_admin_pages_are_noindex(client):
    _login(client)
    assert 'name="robots" content="noindex' in client.get("/admin").text


# ── analytics logging ──────────────────────────────────────
def test_check_is_logged_and_shown(client):
    _login(client)
    before = client.get("/admin").text
    client.post(
        "/api/check",
        json={
            "state": "Gujarat",
            "age": 35,
            "gender": "Male",
            "caste": "OBC",
            "annual_income": 50000,
            "occupation": "farmer",
            "land_acres": 1.5,
            "has_bpl_card": True,
            "is_differently_abled": False,
            "is_widow": False,
        },
    )
    assert "Total checks" in before  # KPI present
    # analytics page renders chart JSON without error
    assert client.get("/admin/analytics").status_code == 200


# ── scheme CRUD ────────────────────────────────────────────
def _form(**over):
    base = {
        "original_id": "",
        "id": "zz_pytest",
        "name_en": "ZZ Pytest",
        "name_hi": "x",
        "name_gu": "y",
        "ministry": "Test",
        "category": "finance",
        "benefit_en": "Test benefit",
        "benefit_amount": "5000",
        "benefit_type": "cash_yearly",
        "apply_link": "https://example.gov.in",
        "processing_days": "30 days",
        "scam_note": "It is free.",
        "state_specific": "",
        "eligibility": '{"states": "all"}',
        "documents": "Aadhaar card",
        "steps_en": "Step one",
        "rejection_reasons": "Reason",
        "tags": "test",
    }
    base.update(over)
    return base


def test_scheme_create_edit_delete_roundtrip(client):
    from scheme_checker.schemes import get_scheme_by_id

    _login(client)
    try:
        r = client.post("/admin/schemes/save", data=_form(), follow_redirects=False)
        assert r.status_code == 303
        assert get_scheme_by_id("zz_pytest")["name_en"] == "ZZ Pytest"
        # appears on the public SSR page
        assert client.get("/schemes/zz-pytest").status_code == 200

        # edit
        client.post(
            "/admin/schemes/save", data=_form(original_id="zz_pytest", name_en="ZZ Renamed")
        )
        assert get_scheme_by_id("zz_pytest")["name_en"] == "ZZ Renamed"

        # invalid save re-renders the form (200) instead of redirecting
        r = client.post(
            "/admin/schemes/save", data=_form(original_id="zz_pytest", category="bogus")
        )
        assert r.status_code == 200
        assert "could not save" in r.text.lower()
    finally:
        client.post("/admin/schemes/zz_pytest/delete")
    assert get_scheme_by_id("zz_pytest") is None


def test_invalid_eligibility_json_is_reported(client):
    _login(client)
    r = client.post("/admin/schemes/save", data=_form(id="zz_badjson", eligibility="{not json}"))
    assert r.status_code == 200
    assert "not valid json" in r.text.lower()
