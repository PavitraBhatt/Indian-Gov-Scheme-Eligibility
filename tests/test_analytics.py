"""Tests for the anonymised response store (SQLite backend)."""

import json

import pytest

from scheme_checker import analytics


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(analytics, "EVENTS_DB", tmp_path / "ev.db")
    monkeypatch.setattr(analytics, "_schema_ready", False)
    return analytics


PROFILE = {
    "state": "Bihar",
    "age": 40,
    "gender": "Female",
    "caste": "SC",
    "annual_income": 45000,
    "occupation": "daily_wage",
    "land_acres": None,
    "has_bpl_card": True,
    "is_differently_abled": False,
    "is_widow": True,
}


def test_logs_full_anonymised_answer(fresh_db):
    a = fresh_db
    a.log_response(PROFILE, matched_count=5, annual_cash=12000, scheme_ids=["pm_kisan"])
    a.log_response(
        {**PROFILE, "state": "Kerala", "caste": "OBC", "annual_income": 900000},
        matched_count=2,
        annual_cash=0,
        scheme_ids=["ayushman_bharat"],
    )

    ov = a.overview()
    assert ov["total_checks"] == 2

    # answer dimensions are captured
    caste = a.distribution("caste")
    assert dict(zip(caste["labels"], caste["data"], strict=True)) == {"SC": 1, "OBC": 1}
    assert a.income_bands()["data"] == [1, 0, 0, 1]  # Below 60k, ..., Above 8L
    assert a.age_bands()["labels"][2] == "30-44"
    assert a.checks_by_state() == {"Bihar": 1, "Kerala": 1}
    assert a.top_scheme_ids(5)  # matched ids counted


def test_stores_ip_but_no_name(fresh_db):
    """Responses capture the visitor's IP (for the admin) but never a name."""
    import sqlite3

    a = fresh_db
    a.log_response(PROFILE, 1, 100, ["x"], ip="203.0.113.7", vid="sess1")
    conn = sqlite3.connect(a.EVENTS_DB)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(responses)").fetchall()}
    stored_ip = conn.execute("SELECT ip FROM responses").fetchone()[0]
    conn.close()
    assert "name" not in cols
    assert "ip" in cols
    assert stored_ip == "203.0.113.7"
    assert {"state", "age", "caste", "annual_income", "rid"} <= cols


def test_funnel_and_recent_visitors(fresh_db):
    """Funnel counts people who only visit, who abandon, and who complete."""
    a = fresh_db
    # visitor A: only visits
    a.log_event("A", "visit", ip="10.0.0.1")
    # visitor B: starts then abandons at step 4
    a.log_event("B", "visit", ip="10.0.0.2")
    a.log_event("B", "start", ip="10.0.0.2", last_step=1)
    a.log_event("B", "abandon", ip="10.0.0.2", last_step=4)
    # visitor C: completes
    a.log_event("C", "visit", ip="10.0.0.3")
    a.log_event("C", "start", ip="10.0.0.3", last_step=1)
    a.log_event("C", "complete", ip="10.0.0.3", last_step=10)

    f = a.funnel()
    assert f["visited"] == 3
    assert f["started"] == 2
    assert f["completed"] == 1
    assert f["abandoned"] == 1  # started - completed
    assert f["bounced"] == 1  # visited - started

    visitors = a.recent_visitors(10)
    by_vid = {v["vid"]: v for v in visitors}
    assert by_vid["A"]["stage"] == "Only visited"
    assert by_vid["B"]["stage"] == "Abandoned"
    assert by_vid["B"]["last_step"] == 4
    assert by_vid["C"]["stage"] == "Completed"
    assert by_vid["C"]["ip"] == "10.0.0.3"


def test_invalid_stage_ignored(fresh_db):
    a = fresh_db
    a.log_event("Z", "hovered", ip="10.0.0.9")  # not a real stage
    assert a.funnel()["visited"] == 0


def test_logging_never_raises(fresh_db, monkeypatch):
    # even if the DB path is bad, logging must swallow the error
    monkeypatch.setattr(analytics, "EVENTS_DB", analytics.Path("/nonexistent/\0/bad.db"))
    monkeypatch.setattr(analytics, "_schema_ready", False)
    analytics.log_response(PROFILE, 1, 1, ["x"])  # should not raise


def test_scheme_ids_stored_as_json(fresh_db):
    a = fresh_db
    a.log_response(PROFILE, 3, 5000, ["pm_kisan", "kisan_credit_card"])
    import sqlite3

    conn = sqlite3.connect(a.EVENTS_DB)
    raw = conn.execute("SELECT scheme_ids FROM responses").fetchone()[0]
    conn.close()
    assert json.loads(raw) == ["pm_kisan", "kisan_credit_card"]
