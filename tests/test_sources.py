"""Tests for the scheme source adapters (no network — http_get is injected)."""

from scheme_checker.sync.sources import MyySchemeSource, _extract_items, _to_raw


def _hit(slug, name, desc=""):
    return {"fields": {"slug": slug, "schemeName": name, "briefDescription": desc}}


def _page(items):
    return {"data": {"hits": {"items": items}}}


def test_extract_items_nested_shape():
    payload = _page([_hit("a", "A"), _hit("b", "B")])
    assert len(_extract_items(payload)) == 2


def test_extract_items_flat_shape():
    assert _extract_items({"data": [{"x": 1}]}) == [{"x": 1}]


def test_extract_items_missing_degrades_to_empty():
    assert _extract_items({}) == []
    assert _extract_items({"data": {"hits": {}}}) == []


def test_to_raw_maps_fields():
    raw = _to_raw(_hit("pm-kisan", "PM Kisan", "Income support"))
    assert raw["source_id"] == "pm-kisan"
    assert raw["name_en"] == "PM Kisan"
    assert raw["source_url"] == "https://www.myscheme.gov.in/schemes/pm-kisan"
    assert "Income support" in raw["text"]


def test_fetch_paginates_until_short_page():
    # 3 items per page, page_size 3 -> second (short) page ends pagination
    pages = {
        0: _page([_hit("a", "A"), _hit("b", "B"), _hit("c", "C")]),
        3: _page([_hit("d", "D")]),
    }
    calls = []

    def fake_get(url, params, headers):
        calls.append(params["from"])
        return pages.get(params["from"], _page([]))

    src = MyySchemeSource(page_size=3, http_get=fake_get)
    raw = src.fetch()
    assert [r["source_id"] for r in raw] == ["a", "b", "c", "d"]
    assert calls == [0, 3]


def test_fetch_respects_max_schemes():
    page = _page([_hit(str(i), f"S{i}") for i in range(10)])
    src = MyySchemeSource(page_size=10, max_schemes=4, http_get=lambda u, p, h: page)
    assert len(src.fetch()) == 4


def test_api_key_added_to_headers():
    src = MyySchemeSource(api_key="secret123", http_get=lambda u, p, h: _page([]))
    assert src._headers()["x-api-key"] == "secret123"


def test_no_api_key_omits_header():
    src = MyySchemeSource(api_key="", http_get=lambda u, p, h: _page([]))
    assert "x-api-key" not in src._headers()
