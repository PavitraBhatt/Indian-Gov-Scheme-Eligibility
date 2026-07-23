"""Tests for the server-rendered, indexable scheme pages (SEO)."""

import json
import re

from fastapi.testclient import TestClient

from scheme_checker.api import app

client = TestClient(app)


def test_scheme_page_renders_full_content_in_raw_html():
    """Acceptance: curl/view-source returns full content, not an empty div."""
    r = client.get("/schemes/pm-kisan")
    assert r.status_code == 200
    html = r.text
    assert "PM Kisan" in html
    assert "Who is eligible" in html
    assert "How to apply" in html
    assert "Documents required" in html
    # a real CTA into the checker
    assert "Check if you qualify" in html or "Check my eligibility" in html


def test_scheme_page_has_seo_head():
    html = client.get("/schemes/pm-kisan").text
    assert '<link rel="canonical"' in html
    assert 'name="description"' in html
    assert 'property="og:title"' in html
    assert "<h1>" in html


def test_scheme_page_jsonld_is_valid():
    html = client.get("/schemes/ayushman-bharat").text
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert blocks, "no JSON-LD found"
    types = set()
    for b in blocks:
        data = json.loads(b)  # must be valid JSON
        types.add(data["@type"])
    assert {"Organization", "GovernmentService", "BreadcrumbList"} <= types


def test_scheme_page_has_faq_and_faqpage_schema():
    """Per-scheme FAQ: visible Q&A plus matching FAQPage structured data."""
    html = client.get("/schemes/pm-kisan").text
    # visible FAQ block
    assert "Frequently asked questions" in html
    assert "Who is eligible for" in html
    # FAQPage JSON-LD present and valid, with at least one question
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    faq = next((json.loads(b) for b in blocks if json.loads(b).get("@type") == "FAQPage"), None)
    assert faq is not None, "no FAQPage JSON-LD"
    assert len(faq["mainEntity"]) >= 3
    assert faq["mainEntity"][0]["acceptedAnswer"]["text"]


def test_scheme_service_schema_has_datemodified():
    html = client.get("/schemes/pm-kisan").text
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    svc = next(json.loads(b) for b in blocks if json.loads(b).get("@type") == "GovernmentService")
    # valid ISO date, not a bare year
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", svc["dateModified"])


def test_sitemap_every_url_has_lastmod():
    body = client.get("/sitemap.xml").text
    # scheme URLs must carry a lastmod for crawl prioritisation
    assert "<lastmod>" in body


def test_slug_uses_hyphens_not_underscores():
    # canonical URL must be the hyphen form
    html = client.get("/schemes/pm-kisan").text
    assert "/schemes/pm-kisan" in html
    assert "/schemes/pm_kisan" not in html


def test_index_and_facets():
    assert client.get("/schemes/").status_code == 200
    assert client.get("/schemes/category/agriculture").status_code == 200
    assert client.get("/schemes/state/gujarat").status_code == 200
    # index links to individual scheme pages (internal linking)
    assert "/schemes/pm-kisan" in client.get("/schemes/").text


def test_unknown_pages_404():
    assert client.get("/schemes/not-a-real-scheme").status_code == 404
    assert client.get("/schemes/category/spaceflight").status_code == 404
    assert client.get("/schemes/state/atlantis").status_code == 404


def test_robots_allows_ai_crawlers_and_points_to_sitemap():
    body = client.get("/robots.txt").text
    for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        assert bot in body
    assert "Disallow: /api/" in body
    assert "Sitemap:" in body and "/sitemap.xml" in body


def test_sitemap_lists_scheme_pages():
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    body = r.text
    assert body.startswith("<?xml")
    assert "/schemes/pm-kisan" in body
    assert "/schemes/category/agriculture" in body


def test_llms_txt():
    body = client.get("/llms.txt").text
    assert body.startswith("# SchemeSaathi")
    assert "/schemes/" in body


def test_privacy_page():
    r = client.get("/privacy")
    assert r.status_code == 200
    html = r.text
    assert "Privacy Policy" in html
    # states the key promises
    assert "not" in html.lower() and "IP address" in html


def test_every_scheme_has_reachable_page():
    """Acceptance: every scheme is reachable by a direct URL with 200."""
    from scheme_checker.schemes import load_schemes
    from scheme_checker.web import STATES, slug_for

    for s in load_schemes(states=STATES):
        r = client.get(f"/schemes/{slug_for(s['id'])}")
        assert r.status_code == 200, s["id"]
        assert s["name_en"] in r.text
