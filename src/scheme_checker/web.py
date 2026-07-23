"""Server-side-rendered, indexable pages for schemes.

The interactive checker (frontend/index.html) stays client-rendered — it is
personalised and not meant to be indexed. These routes instead render *plain,
crawlable HTML* for every scheme and for category/state index pages, so search
engines and AI answer engines (which don't run JS) can read the full content.

Pages are intentionally lightweight: small inline CSS, no Tailwind CDN, no
checker JS — good for Core Web Vitals and for non-JS crawlers.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from .schemes import get_scheme_by_id, load_schemes

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()

SITE_NAME = "SchemeSaathi"

CATEGORY_LABELS = {
    "agriculture": "Agriculture & Farmers",
    "health": "Health & Insurance",
    "housing": "Housing",
    "insurance": "Insurance",
    "finance": "Finance & Livelihood",
    "women_children": "Women & Children",
    "education_youth": "Education & Youth",
    "senior_disability": "Senior Citizens & Disability",
    "energy": "Energy & Electricity",
}

STATES = ["Gujarat", "Maharashtra", "Rajasthan", "Uttar Pradesh"]


# ── helpers ────────────────────────────────────────────────
def slug_for(scheme_id: str) -> str:
    """URL slug for a scheme id (ids use underscores; slugs use hyphens)."""
    return scheme_id.replace("_", "-")


def id_for(slug: str) -> str:
    return slug.replace("-", "_")


def _all_schemes() -> list[dict]:
    return load_schemes(states=STATES)


def scheme_summary(s: dict) -> str:
    cat = CATEGORY_LABELS.get(s["category"], s["category"].replace("_", " "))
    return f"{s['name_en']} is a {cat.lower()} scheme by {s['ministry']}. {s['benefit_en']}."


def eligibility_prose(s: dict) -> list[str]:
    """Turn the machine eligibility rules into human-readable requirement lines."""
    e = s.get("eligibility", {})
    out: list[str] = []
    states = e.get("states")
    if states == "all":
        out.append("Available across all states and union territories of India")
    elif isinstance(states, list):
        out.append("Available in: " + ", ".join(states))
    amin, amax = e.get("age_min"), e.get("age_max")
    if amin and amax:
        out.append(f"Age between {amin} and {amax} years")
    elif amin:
        out.append(f"Age {amin} years or above")
    elif amax:
        out.append(f"Age up to {amax} years")
    if e.get("gender"):
        out.append("For " + ", ".join(g.lower() for g in e["gender"]) + " applicants")
    if e.get("caste"):
        out.append("Category: " + ", ".join(e["caste"]))
    if e.get("income_max") is not None:
        out.append(f"Annual household income up to Rs {e['income_max']:,}")
    if e.get("occupation"):
        out.append("Occupation: " + ", ".join(o.replace("_", " ") for o in e["occupation"]))
    if e.get("land_min_acres") is not None:
        out.append(f"Owns at least {e['land_min_acres']} acres of agricultural land")
    if e.get("requires_bpl"):
        out.append("Must hold a BPL (Below Poverty Line) ration card")
    if e.get("requires_disability"):
        out.append("For persons with 40% or more disability")
    if e.get("requires_widow"):
        out.append("For widows")
    if not out:
        out.append("Open to all eligible citizens")
    return out


def last_verified(s: dict) -> str:
    return s.get("last_verified") or "2026"


def iso_date(s: dict) -> str:
    """A schema.org-valid ISO date for dateModified/datePublished.

    Data currently carries only a year (or nothing); normalise a bare year to
    Jan 1 so the value is valid ISO 8601 rather than a stray ``"2026"``.
    """
    v = str(last_verified(s))
    return f"{v}-01-01" if v.isdigit() and len(v) == 4 else v


def scheme_faqs(s: dict) -> list[tuple[str, str]]:
    """Human FAQ (question, answer) pairs built from a scheme's own data.

    These target the exact long-tail queries people search — "who is eligible
    for X", "what documents for X", "how to apply for X" — and feed both the
    on-page FAQ and the FAQPage structured data (rich results + AI citations).
    """
    name = s["name_en"]
    faqs: list[tuple[str, str]] = []

    faqs.append((f"Who is eligible for {name}?", "; ".join(eligibility_prose(s)) + "."))

    if s.get("benefit_en"):
        faqs.append((f"What is the benefit of {name}?", s["benefit_en"] + "."))

    if s.get("documents"):
        faqs.append(
            (
                f"What documents are required for {name}?",
                "You typically need: " + ", ".join(s["documents"]) + ".",
            )
        )

    steps = s.get("steps_en") or []
    if steps:
        apply = " ".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
        if s.get("apply_link"):
            apply += f" Apply on the official portal: {s['apply_link']}."
        faqs.append((f"How do I apply for {name}?", apply))

    if s.get("processing_days"):
        faqs.append(
            (
                f"How long does {name} take to process?",
                f"Applications are typically processed in about {s['processing_days']}.",
            )
        )

    faqs.append(
        (
            f"Is {name} free to apply for?",
            "Yes. It is completely free to apply. Never pay an agent or middleman — "
            "if anyone asks for money, report it by calling 1930.",
        )
    )
    return faqs


def _faq_jsonld(faqs: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }


def _org_jsonld(base: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": SITE_NAME,
        "url": base,
        "description": (
            "Free public-service tool to help Indian citizens find central and state "
            "government welfare schemes they qualify for."
        ),
    }


# ── routes ─────────────────────────────────────────────────
@router.get("/schemes/", response_class=HTMLResponse)
async def schemes_index(request: Request):
    base = str(request.base_url).rstrip("/")
    schemes = _all_schemes()
    by_cat: dict[str, list[dict]] = {}
    for s in schemes:
        by_cat.setdefault(s["category"], []).append(s)
    groups = [
        {
            "key": k,
            "label": CATEGORY_LABELS.get(k, k),
            "schemes": sorted(v, key=lambda x: x["name_en"]),
        }
        for k, v in sorted(by_cat.items(), key=lambda kv: CATEGORY_LABELS.get(kv[0], kv[0]))
    ]
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "request": request,
            "site_name": SITE_NAME,
            "base": base,
            "page_title": f"All Government Schemes ({len(schemes)}) — Eligibility & Benefits | {SITE_NAME}",
            "meta_description": (
                f"Browse {len(schemes)} Indian central and state government welfare schemes — "
                "eligibility, benefits, documents and how to apply. Free to check."
            ),
            "canonical": f"{base}/schemes/",
            "h1": "All Government Schemes",
            "intro": (
                f"Explore {len(schemes)} central and state welfare schemes by category. "
                "Each page explains who is eligible, the benefits, documents needed and how to apply."
            ),
            "groups": groups,
            "states": STATES,
            "slug_for": slug_for,
            "summary_for": scheme_summary,
            "breadcrumbs": [("Home", base + "/"), ("Schemes", base + "/schemes/")],
            "jsonld_blocks": [_org_jsonld(base)],
        },
    )


@router.get("/schemes/category/{category}", response_class=HTMLResponse)
async def schemes_by_category(request: Request, category: str):
    base = str(request.base_url).rstrip("/")
    if category not in CATEGORY_LABELS:
        raise HTTPException(status_code=404, detail="Category not found")
    schemes = sorted(
        (s for s in _all_schemes() if s["category"] == category), key=lambda x: x["name_en"]
    )
    label = CATEGORY_LABELS[category]
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "request": request,
            "site_name": SITE_NAME,
            "base": base,
            "page_title": f"{label} Schemes — Eligibility & Benefits | {SITE_NAME}",
            "meta_description": f"{label} government schemes in India: eligibility, benefits and how to apply.",
            "canonical": f"{base}/schemes/category/{category}",
            "h1": f"{label} Schemes",
            "intro": f"Government welfare schemes for {label.lower()}.",
            "groups": [{"key": category, "label": label, "schemes": schemes}],
            "states": STATES,
            "slug_for": slug_for,
            "summary_for": scheme_summary,
            "breadcrumbs": [
                ("Home", base + "/"),
                ("Schemes", base + "/schemes/"),
                (label, f"{base}/schemes/category/{category}"),
            ],
            "jsonld_blocks": [_org_jsonld(base)],
        },
    )


@router.get("/schemes/state/{state}", response_class=HTMLResponse)
async def schemes_by_state(request: Request, state: str):
    base = str(request.base_url).rstrip("/")
    match = next((s for s in STATES if s.lower().replace(" ", "-") == state.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail="State not found")
    schemes = sorted(load_schemes(states=[match]), key=lambda x: x["name_en"])
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "request": request,
            "site_name": SITE_NAME,
            "base": base,
            "page_title": f"Government Schemes in {match} — Eligibility & Benefits | {SITE_NAME}",
            "meta_description": f"Central and {match} state government schemes: eligibility, benefits and how to apply.",
            "canonical": f"{base}/schemes/state/{state.lower()}",
            "h1": f"Government Schemes in {match}",
            "intro": f"Central schemes plus schemes specific to {match}.",
            "groups": [{"key": match, "label": match, "schemes": schemes}],
            "states": STATES,
            "slug_for": slug_for,
            "summary_for": scheme_summary,
            "breadcrumbs": [
                ("Home", base + "/"),
                ("Schemes", base + "/schemes/"),
                (match, f"{base}/schemes/state/{state.lower()}"),
            ],
            "jsonld_blocks": [_org_jsonld(base)],
        },
    )


@router.get("/schemes/{slug}", response_class=HTMLResponse)
async def scheme_page(request: Request, slug: str):
    base = str(request.base_url).rstrip("/")
    s = get_scheme_by_id(id_for(slug))
    if not s:
        raise HTTPException(status_code=404, detail="Scheme not found")

    label = CATEGORY_LABELS.get(s["category"], s["category"])
    canonical = f"{base}/schemes/{slug}"
    summary = scheme_summary(s)

    service_ld = {
        "@context": "https://schema.org",
        "@type": "GovernmentService",
        "name": s["name_en"],
        "description": summary,
        "serviceType": label,
        "provider": {
            "@type": "GovernmentOrganization",
            "name": s["ministry"],
            "url": s["apply_link"],
        },
        "areaServed": {"@type": "Country", "name": "India"},
        "audience": {"@type": "Audience", "audienceType": "; ".join(eligibility_prose(s))},
        "url": canonical,
        "dateModified": iso_date(s),
    }
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": "Schemes", "item": base + "/schemes/"},
            {"@type": "ListItem", "position": 3, "name": s["name_en"], "item": canonical},
        ],
    }

    faqs = scheme_faqs(s)

    return templates.TemplateResponse(
        request,
        "scheme.html",
        {
            "request": request,
            "site_name": SITE_NAME,
            "base": base,
            "scheme": s,
            "slug": slug,
            "category_label": label,
            "page_title": f"{s['name_en']} — Eligibility, Benefits & How to Apply | {SITE_NAME}",
            "meta_description": summary[:157] + ("…" if len(summary) > 157 else ""),
            "canonical": canonical,
            "summary": summary,
            "eligibility": eligibility_prose(s),
            "last_verified": last_verified(s),
            "faqs": faqs,
            "breadcrumbs": [
                ("Home", base + "/"),
                ("Schemes", base + "/schemes/"),
                (s["name_en"], canonical),
            ],
            "jsonld_blocks": [_org_jsonld(base), service_ld, breadcrumb_ld, _faq_jsonld(faqs)],
        },
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    base = str(request.base_url).rstrip("/")
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "request": request,
            "site_name": SITE_NAME,
            "base": base,
            "page_title": f"Privacy Policy | {SITE_NAME}",
            "meta_description": f"How {SITE_NAME} handles your information.",
            "canonical": f"{base}/privacy",
            "breadcrumbs": [("Home", base + "/"), ("Privacy", base + "/privacy")],
            "jsonld_blocks": [_org_jsonld(base)],
        },
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots(request: Request):
    base = str(request.base_url).rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\nAllow: /\n\n"
        "User-agent: ClaudeBot\nAllow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /\n\n"
        "User-agent: Google-Extended\nAllow: /\n\n"
        "Disallow: /api/\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
async def sitemap(request: Request):
    base = str(request.base_url).rstrip("/")
    urls: list[tuple[str, str | None]] = [(base + "/", None), (base + "/schemes/", None)]
    for cat in CATEGORY_LABELS:
        urls.append((f"{base}/schemes/category/{cat}", None))
    for st in STATES:
        urls.append((f"{base}/schemes/state/{st.lower().replace(' ', '-')}", None))
    for s in _all_schemes():
        urls.append((f"{base}/schemes/{slug_for(s['id'])}", iso_date(s)))

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return Response("\n".join(parts), media_type="application/xml")


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(request: Request):
    base = str(request.base_url).rstrip("/")
    lines = [
        f"# {SITE_NAME}",
        "",
        "> Free tool to help Indian citizens find central and state government welfare "
        "schemes they qualify for — with eligibility, benefits, documents and how to apply.",
        "",
        "## Scheme categories",
    ]
    for cat, label in CATEGORY_LABELS.items():
        lines.append(f"- [{label}]({base}/schemes/category/{cat})")
    lines += [
        "",
        "## Key pages",
        f"- [All schemes]({base}/schemes/)",
        f"- [Eligibility checker]({base}/)",
    ]
    return "\n".join(lines) + "\n"
