"""Tests for the differ and the end-to-end sync orchestrator (no network/API)."""

import json

from scheme_checker.sync.diff import CHANGED, NEW, UNCHANGED, classify, diff_schemes, summarize
from scheme_checker.sync.run import apply_proposal, run_sync
from scheme_checker.sync.sources import SchemeSource


def _scheme(id_, benefit=6000, scam="It is free."):
    return {
        "id": id_,
        "name_en": "X",
        "name_hi": "ए",
        "name_gu": "એ",
        "ministry": "M",
        "category": "agriculture",
        "benefit_en": "b",
        "benefit_amount": benefit,
        "apply_link": "https://x.gov.in",
        "eligibility": {"states": "all"},
        "documents": ["Aadhaar card"],
        "steps_en": ["Step 1"],
        "rejection_reasons": ["r"],
        "scam_note": scam,
        "processing_days": "30",
        "tags": ["t"],
        "state_specific": False,
    }


# ---- diff ----


def test_classify_new():
    assert classify(_scheme("a"), {}) == NEW


def test_classify_unchanged():
    cur = {"a": _scheme("a")}
    assert classify(_scheme("a"), cur) == UNCHANGED


def test_classify_changed_on_content():
    cur = {"a": _scheme("a", benefit=6000)}
    assert classify(_scheme("a", benefit=9000), cur) == CHANGED


def test_last_verified_change_is_not_a_change():
    old = _scheme("a")
    old["last_verified"] = "2026-01-01"
    new = _scheme("a")
    new["last_verified"] = "2026-06-28"
    assert classify(new, {"a": old}) == UNCHANGED


def test_diff_buckets_and_previous():
    incoming = [_scheme("a", benefit=9000), _scheme("b"), _scheme("c")]
    current = [_scheme("a", benefit=6000), _scheme("c")]
    buckets = diff_schemes(incoming, current)
    assert {s["id"] for s in buckets[NEW]} == {"b"}
    assert {s["id"] for s in buckets[CHANGED]} == {"a"}
    assert {s["id"] for s in buckets[UNCHANGED]} == {"c"}
    assert buckets[CHANGED][0]["_previous"]["benefit_amount"] == 6000


def test_summarize():
    buckets = {NEW: [1, 2], CHANGED: [1], UNCHANGED: []}
    assert summarize(buckets) == "2 new, 1 changed, 0 unchanged"


# ---- orchestrator ----


class _FakeSource(SchemeSource):
    def __init__(self, raws):
        self._raws = raws

    def fetch(self):
        return self._raws


def _content_for(raw):
    """A valid normalized content blob keyed off the raw scheme."""
    return {
        "name_en": raw["name_en"],
        "name_hi": "ए",
        "name_gu": "એ",
        "ministry": "M",
        "category": "agriculture",
        "benefit_en": "b",
        "benefit_amount": 6000,
        "apply_link": "https://x.gov.in",
        "eligibility": {"states": "all"},
        "documents": ["Aadhaar card"],
        "steps_en": ["Step 1"],
        "rejection_reasons": ["r"],
        "scam_note": "It is free.",
        "processing_days": "30",
        "tags": ["t"],
    }


def test_run_sync_classifies_new_scheme():
    source = _FakeSource(
        [{"source_id": "brand-new", "name_en": "Brand New", "source_url": "https://x", "text": "t"}]
    )
    proposal = run_sync(
        source=source,
        completer=lambda s, u, sch: _content_for({"name_en": "Brand New"}),
        last_verified="2026-06-28",
        current=[],
    )
    assert len(proposal["new"]) == 1
    assert proposal["new"][0]["id"] == "brand_new"
    assert "1 new" in proposal["summary"]


def test_run_sync_drops_invalid_scheme():
    bad_content = _content_for({"name_en": "Bad"})
    bad_content["category"] = "invalid_cat"

    source = _FakeSource(
        [{"source_id": "bad", "name_en": "Bad", "source_url": "https://x", "text": "t"}]
    )
    proposal = run_sync(
        source=source,
        completer=lambda s, u, sch: bad_content,
        last_verified="2026-06-28",
        current=[],
    )
    assert proposal["new"] == []
    assert len(proposal["dropped"]) == 1
    assert proposal["dropped"][0]["id"] == "bad"


# ---- apply ----


def test_apply_proposal_adds_and_replaces(tmp_path):
    central = tmp_path / "schemes_central.json"
    central.write_text(json.dumps([_scheme("a", benefit=6000)]), encoding="utf-8")

    changed = _scheme("a", benefit=9000)
    changed["_previous"] = _scheme("a", benefit=6000)
    proposal = {"new": [_scheme("b")], "changed": [changed]}

    applied = apply_proposal(proposal, central_path=central)
    result = json.loads(central.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in result}

    assert applied == 2
    assert by_id["a"]["benefit_amount"] == 9000  # replaced
    assert "_previous" not in by_id["a"]  # diff marker stripped
    assert "b" in by_id  # new appended
