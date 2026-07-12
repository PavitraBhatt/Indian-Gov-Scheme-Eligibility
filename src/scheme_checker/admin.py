"""Admin dashboard — single-password gated management UI at /admin.

Auth is a single shared password from the ADMIN_PASSWORD env var, kept in a
signed session cookie. If ADMIN_PASSWORD is unset the dashboard is disabled
(login always fails) — so there is no default-password hole in production.
"""

import hmac
import json
import os
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import analytics
from .schema import VALID_BENEFIT_TYPES, VALID_CATEGORIES
from .schemes import get_scheme_by_id, load_schemes
from .store import delete_scheme, save_scheme
from .web import CATEGORY_LABELS, STATES, slug_for

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/admin")


def _admin_password() -> str | None:
    """Read the shared admin password at call time (env can change per deploy)."""
    return os.environ.get("ADMIN_PASSWORD")


def _is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def _all_schemes() -> list[dict]:
    return load_schemes(states=STATES)


def _ctx(request: Request, **extra):
    base = {"request": request, "site_name": "SchemeSaathi", "nav": extra.pop("nav", "")}
    base.update(extra)
    return base


# ── auth ───────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str = ""):
    if _is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "admin/login.html", _ctx(request, error=error))


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    admin_password = _admin_password()
    if not admin_password:
        err = "Admin is disabled. Set the ADMIN_PASSWORD environment variable."
    elif hmac.compare_digest(password, admin_password):
        request.session["admin"] = True
        return RedirectResponse("/admin", status_code=303)
    else:
        err = "Incorrect password."
    return RedirectResponse(f"/admin/login?error={err}", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


# ── overview ───────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def overview(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    schemes = _all_schemes()
    stats = analytics.overview()
    id_to_name = {s["id"]: s["name_en"] for s in schemes}
    recent = analytics.recent_checks(10)
    top = [
        {"name": id_to_name.get(sid, sid), "slug": slug_for(sid), "count": c}
        for sid, c in analytics.top_scheme_ids(6)
    ]
    return templates.TemplateResponse(
        request,
        "admin/overview.html",
        _ctx(
            request,
            nav="overview",
            stats=stats,
            scheme_count=len(schemes),
            category_count=len({s["category"] for s in schemes}),
            state_count=len(STATES),
            recent=recent,
            top=top,
        ),
    )


# ── analytics ──────────────────────────────────────────────
@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    schemes = _all_schemes()
    id_to = {s["id"]: s for s in schemes}
    per_day = analytics.checks_per_day(14)
    states = analytics.top_states(8)
    top_ids = analytics.top_scheme_ids(10)
    top_schemes = {
        "labels": [id_to.get(i, {}).get("name_en", i) for i, _ in top_ids],
        "data": [c for _, c in top_ids],
    }
    # category mix of the catalogue
    cat_counts: dict[str, int] = {}
    for s in schemes:
        cat_counts[s["category"]] = cat_counts.get(s["category"], 0) + 1
    catalogue = {
        "labels": [CATEGORY_LABELS.get(k, k) for k in cat_counts],
        "data": list(cat_counts.values()),
    }
    charts = {
        "per_day": per_day,
        "states": states,
        "top_schemes": top_schemes,
        "catalogue": catalogue,
    }
    return templates.TemplateResponse(
        request,
        "admin/analytics.html",
        _ctx(request, nav="analytics", charts_json=json.dumps(charts), stats=analytics.overview()),
    )


# ── scheme manager ─────────────────────────────────────────
@router.get("/schemes", response_class=HTMLResponse)
async def schemes_admin(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    schemes = sorted(_all_schemes(), key=lambda s: s["name_en"])
    rows = [
        {
            "id": s["id"],
            "name": s["name_en"],
            "category": CATEGORY_LABELS.get(s["category"], s["category"]),
            "scope": (s["eligibility"].get("states") or ["All India"])[0]
            if s["state_specific"]
            else "All India",
            "amount": s["benefit_amount"],
            "type": s["benefit_type"],
        }
        for s in schemes
    ]
    return templates.TemplateResponse(
        request,
        "admin/schemes.html",
        _ctx(request, nav="schemes", rows=rows, rows_json=json.dumps(rows)),
    )


def _blank_scheme() -> dict:
    return {
        "id": "",
        "name_en": "",
        "name_hi": "",
        "name_gu": "",
        "ministry": "",
        "category": "finance",
        "benefit_en": "",
        "benefit_amount": 0,
        "benefit_type": "cash_yearly",
        "apply_link": "https://",
        "eligibility": {"states": "all"},
        "documents": [],
        "steps_en": [],
        "rejection_reasons": [],
        "scam_note": "",
        "processing_days": "",
        "tags": [],
        "state_specific": False,
    }


def _render_form(request: Request, scheme: dict, original_id: str, errors=None):
    return templates.TemplateResponse(
        request,
        "admin/scheme_form.html",
        _ctx(
            request,
            nav="schemes",
            scheme=scheme,
            original_id=original_id,
            errors=errors or [],
            categories=sorted(VALID_CATEGORIES),
            benefit_types=sorted(VALID_BENEFIT_TYPES),
            eligibility_json=json.dumps(
                scheme.get("eligibility", {}), indent=2, ensure_ascii=False
            ),
        ),
    )


@router.get("/schemes/new", response_class=HTMLResponse)
async def scheme_new(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _render_form(request, _blank_scheme(), "")


@router.get("/schemes/{scheme_id}/edit", response_class=HTMLResponse)
async def scheme_edit(request: Request, scheme_id: str):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    scheme = get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return _render_form(request, scheme, scheme_id)


@router.post("/schemes/save")
async def scheme_save(
    request: Request,
    original_id: str = Form(""),
    id: str = Form(...),
    name_en: str = Form(...),
    name_hi: str = Form(""),
    name_gu: str = Form(""),
    ministry: str = Form(""),
    category: str = Form(...),
    benefit_en: str = Form(""),
    benefit_amount: int = Form(0),
    benefit_type: str = Form(...),
    apply_link: str = Form(...),
    processing_days: str = Form(""),
    scam_note: str = Form(""),
    state_specific: str = Form(""),
    eligibility: str = Form("{}"),
    documents: str = Form(""),
    steps_en: str = Form(""),
    rejection_reasons: str = Form(""),
    tags: str = Form(""),
):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)

    def lines(text: str) -> list[str]:
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    try:
        elig = json.loads(eligibility or "{}")
    except json.JSONDecodeError as e:
        elig = None
        elig_err = f"Eligibility is not valid JSON: {e}"

    scheme = {
        "id": id.strip(),
        "name_en": name_en.strip(),
        "name_hi": name_hi.strip(),
        "name_gu": name_gu.strip(),
        "ministry": ministry.strip(),
        "category": category,
        "benefit_en": benefit_en.strip(),
        "benefit_amount": int(benefit_amount),
        "benefit_type": benefit_type,
        "apply_link": apply_link.strip(),
        "eligibility": elig if elig is not None else {},
        "documents": lines(documents),
        "steps_en": lines(steps_en),
        "rejection_reasons": lines(rejection_reasons),
        "scam_note": scam_note.strip(),
        "processing_days": processing_days.strip(),
        "tags": lines(tags),
        "state_specific": state_specific == "on",
    }

    if elig is None:
        return _render_form(request, scheme, original_id, [elig_err])

    result = save_scheme(scheme, original_id=original_id or None)
    if not result["ok"]:
        return _render_form(request, scheme, original_id, result["errors"])
    return RedirectResponse("/admin/schemes", status_code=303)


@router.post("/schemes/{scheme_id}/delete")
async def scheme_delete(request: Request, scheme_id: str):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    delete_scheme(scheme_id)
    return RedirectResponse("/admin/schemes", status_code=303)
