from fastapi.testclient import TestClient

from scheme_checker.api import app

client = TestClient(app)


def _payload(**overrides):
    base = {
        "state": "Gujarat",
        "age": 35,
        "gender": "Male",
        "caste": "OBC",
        "annual_income": 120000,
        "occupation": "farmer",
        "land_acres": 2.0,
        "has_bpl_card": False,
        "is_differently_abled": False,
        "is_widow": False,
    }
    base.update(overrides)
    return base


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_check_returns_schemes():
    r = client.post("/api/check", json=_payload())
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "schemes" in data
    assert data["count"] == len(data["schemes"])


def test_check_returns_type_aware_totals():
    """Honest aggregates: loans/insurance must not be summed as cash."""
    data = client.post("/api/check", json=_payload()).json()
    for key in ("annual_cash_benefit", "one_time_benefit", "loan_access", "insurance_cover"):
        assert key in data
    assert "total_annual_benefit" not in data  # the old misleading field is gone

    # annual_cash must only reflect cash_yearly schemes, never loans/insurance
    cash = sum(s["benefit_amount"] for s in data["schemes"] if s["benefit_type"] == "cash_yearly")
    assert data["annual_cash_benefit"] == cash
    loans = sum(s["benefit_amount"] for s in data["schemes"] if s["benefit_type"] == "loan")
    assert data["loan_access"] == loans


def test_check_farmer_gets_kisan():
    r = client.post("/api/check", json=_payload())
    ids = {s["id"] for s in r.json()["schemes"]}
    assert "pm_kisan" in ids


def test_check_bpl_unlocks_ayushman():
    r_no = client.post("/api/check", json=_payload(has_bpl_card=False))
    r_yes = client.post("/api/check", json=_payload(has_bpl_card=True))
    ids_no = {s["id"] for s in r_no.json()["schemes"]}
    ids_yes = {s["id"] for s in r_yes.json()["schemes"]}
    assert "ayushman_bharat" not in ids_no
    assert "ayushman_bharat" in ids_yes


def test_list_schemes():
    r = client.get("/api/schemes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_list_schemes_by_state():
    r = client.get("/api/schemes?state=Gujarat")
    ids = {s["id"] for s in r.json()}
    assert "gu_ikhedut" in ids


def test_list_schemes_by_category():
    r = client.get("/api/schemes?category=agriculture")
    for s in r.json():
        assert s["category"] == "agriculture"


def test_get_scheme_by_id():
    r = client.get("/api/schemes/pm_kisan")
    assert r.status_code == 200
    assert r.json()["id"] == "pm_kisan"


def test_get_scheme_not_found():
    r = client.get("/api/schemes/nonexistent_scheme")
    assert r.status_code == 404


def test_frontend_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "scheme" in r.text.lower()
