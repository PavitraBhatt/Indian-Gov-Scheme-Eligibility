import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .admin import router as admin_router
from .analytics import log_check
from .core import UserProfile, benefit_totals, match_schemes, near_misses
from .schemes import get_scheme_by_id, load_schemes
from .web import router as web_router

app = FastAPI(title="Indian Gov Scheme Eligibility API", version="0.3.0")

# Signed session cookie for the admin login. SESSION_SECRET keeps sessions valid
# across restarts; otherwise a per-process random secret (logs you out on deploy).
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", secrets.token_hex(32)),
    https_only=False,
    same_site="lax",
)

# Server-rendered, indexable pages: /schemes/, /schemes/{slug}, robots, sitemap.
app.include_router(web_router)
# Admin dashboard (password-gated): /admin/*
app.include_router(admin_router)

# CORS — the form is same-origin, but /api is documented for integrations.
# Default to same-origin only; set SCHEME_CORS_ORIGINS (comma-separated) to open up.
_origins = [o for o in os.environ.get("SCHEME_CORS_ORIGINS", "").split(",") if o]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

_FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
_STATIC_DIR = _FRONTEND_DIR / "static"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


class CheckRequest(BaseModel):
    """Validated applicant profile. Bad inputs (negative age, etc.) get a 422."""

    state: str = Field(min_length=1, max_length=60)
    age: int = Field(ge=0, le=120)
    gender: str = Field(min_length=1, max_length=20)
    caste: str = Field(min_length=1, max_length=20)
    annual_income: int = Field(ge=0, le=1_000_000_000)
    occupation: str = Field(min_length=1, max_length=30)
    land_acres: float | None = Field(default=None, ge=0, le=100_000)
    has_bpl_card: bool = False
    is_differently_abled: bool = False
    is_widow: bool = False


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
    # Inject the live origin so canonical/OG URLs are absolute and correct
    # regardless of the deploy host.
    base = str(request.base_url).rstrip("/")
    html = index.read_text(encoding="utf-8").replace("__SITE_URL__", base + "/")
    return HTMLResponse(html)


@app.post("/api/check", response_model=dict[str, Any])
async def check_eligibility(req: CheckRequest):
    profile = UserProfile.from_dict(req.model_dump())
    schemes = load_schemes(states=[req.state])
    matched = match_schemes(profile, schemes)
    totals = benefit_totals(matched)
    # privacy-safe aggregate logging for the admin dashboard (no personal data)
    log_check(req.state, len(matched), totals["annual_cash"], [s["id"] for s in matched])
    return {
        "count": len(matched),
        # honest, type-aware aggregates (the old single total_annual_benefit
        # conflated recurring cash with loan ceilings and insurance cover)
        "annual_cash_benefit": totals["annual_cash"],
        "one_time_benefit": totals["one_time"],
        "loan_access": totals["loan_access"],
        "insurance_cover": totals["insurance_cover"],
        "schemes": matched,
        # schemes the applicant narrowly misses (fail exactly one requirement),
        # each with a 'miss_reason' so they know what would unlock it
        "almost": near_misses(profile, schemes),
    }


@app.get("/api/schemes", response_model=list[dict[str, Any]])
async def list_schemes(state: str | None = None, category: str | None = None):
    states = [state] if state else None
    schemes = load_schemes(states=states)
    if category:
        schemes = [s for s in schemes if s.get("category") == category]
    return schemes


@app.get("/api/schemes/{scheme_id}", response_model=dict[str, Any])
async def get_scheme(scheme_id: str):
    scheme = get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}
