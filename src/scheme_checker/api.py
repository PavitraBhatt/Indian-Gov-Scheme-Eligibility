from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core import UserProfile, match_schemes
from .schemes import get_scheme_by_id, load_schemes

app = FastAPI(title="Indian Gov Scheme Eligibility API", version="0.2.0")

_FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
_STATIC_DIR = _FRONTEND_DIR / "static"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


class CheckRequest(BaseModel):
    state: str
    age: int
    gender: str
    caste: str
    annual_income: int
    occupation: str
    land_acres: Optional[float] = None
    has_bpl_card: bool = False
    is_differently_abled: bool = False
    is_widow: bool = False


class SchemeResult(BaseModel):
    id: str
    name_en: str
    name_hi: str
    name_gu: str
    category: str
    benefit_en: str
    benefit_amount: int
    apply_link: str
    ministry: str
    documents: List[str]
    steps_en: List[str]
    scam_note: str
    processing_days: str
    tags: List[str]
    state_specific: bool


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.post("/api/check", response_model=Dict[str, Any])
async def check_eligibility(req: CheckRequest):
    profile = UserProfile.from_dict(req.model_dump())
    schemes = load_schemes(states=[req.state])
    matched = match_schemes(profile, schemes)
    total_benefit = sum(s.get("benefit_amount", 0) for s in matched)
    return {
        "count": len(matched),
        "total_annual_benefit": total_benefit,
        "schemes": matched,
    }


@app.get("/api/schemes", response_model=List[Dict[str, Any]])
async def list_schemes(state: Optional[str] = None, category: Optional[str] = None):
    states = [state] if state else None
    schemes = load_schemes(states=states)
    if category:
        schemes = [s for s in schemes if s.get("category") == category]
    return schemes


@app.get("/api/schemes/{scheme_id}", response_model=Dict[str, Any])
async def get_scheme(scheme_id: str):
    scheme = get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}
