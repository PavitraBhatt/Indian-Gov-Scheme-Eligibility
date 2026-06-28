"""Tests for the SQLite runtime store (built from data/*.json)."""

import json

import pytest

from scheme_checker import db


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test_schemes.db"


def test_build_db_populates_rows(tmp_db):
    n = db.build_db(tmp_db, force=True)
    assert n == db._count(tmp_db)
    assert n > 50  # 49 central + state schemes


def test_query_central_excludes_state_specific(tmp_db):
    db.build_db(tmp_db, force=True)
    schemes = db.query_schemes(db_path=tmp_db)
    ids = {s["id"] for s in schemes}
    assert "pm_kisan" in ids
    assert "gu_ikhedut" not in ids  # state-specific must not leak into central


def test_query_includes_requested_state(tmp_db):
    db.build_db(tmp_db, force=True)
    ids = {s["id"] for s in db.query_schemes(states=["Gujarat"], db_path=tmp_db)}
    assert "gu_ikhedut" in ids
    assert "pm_kisan" in ids  # central still included


def test_query_category_filter(tmp_db):
    db.build_db(tmp_db, force=True)
    schemes = db.query_schemes(category="agriculture", db_path=tmp_db)
    assert schemes
    assert all(s["category"] == "agriculture" for s in schemes)


def test_get_scheme_by_id(tmp_db):
    db.build_db(tmp_db, force=True)
    scheme = db.get_scheme("pm_kisan", db_path=tmp_db)
    assert scheme is not None
    assert scheme["id"] == "pm_kisan"
    assert db.get_scheme("does_not_exist", db_path=tmp_db) is None


def test_json_fields_round_trip(tmp_db):
    """eligibility/documents/steps/tags must come back as the original types."""
    db.build_db(tmp_db, force=True)
    scheme = db.get_scheme("pm_kisan", db_path=tmp_db)
    assert isinstance(scheme["eligibility"], dict)
    assert isinstance(scheme["documents"], list)
    assert isinstance(scheme["steps_en"], list)
    assert isinstance(scheme["tags"], list)
    assert isinstance(scheme["state_specific"], bool)
    assert isinstance(scheme["benefit_amount"], int)


def test_db_matches_json_source_of_truth(tmp_db):
    """Every scheme in the JSON files must appear in the DB unchanged."""
    db.build_db(tmp_db, force=True)
    json_ids = set()
    for name in db._FILE_STATE:
        path = db._DATA_DIR / name
        if path.exists():
            with open(path, encoding="utf-8") as f:
                json_ids.update(s["id"] for s in json.load(f))
    db_ids = {
        s["id"]
        for s in db.query_schemes(
            states=["Gujarat", "Maharashtra", "Rajasthan", "Uttar Pradesh"], db_path=tmp_db
        )
    }
    assert json_ids == db_ids


def test_rebuild_when_db_missing(tmp_db):
    db.build_db(tmp_db, force=True)
    assert tmp_db.exists()
    tmp_db.unlink()
    # query should transparently rebuild
    schemes = db.query_schemes(db_path=tmp_db)
    assert schemes
    assert tmp_db.exists()
