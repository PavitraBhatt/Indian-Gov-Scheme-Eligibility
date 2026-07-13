"""Usage analytics store for the admin dashboard.

Persists one row per eligibility check for later analysis. It stores the full
questionnaire answers (state, age, gender, caste, income, occupation, land,
BPL, disability, widow) and the results — but under a random id, with **no
name and no IP address**, so the data set stays useful for analysis without
becoming a re-identifiable dossier on individuals.

Backend is chosen at runtime:
- ``DATABASE_URL`` set  -> PostgreSQL (e.g. Neon) — durable, survives redeploys.
- otherwise             -> local SQLite file (``SCHEME_EVENTS_DB``), zero-config.

Logging never raises — a failed write must not break a user's check.
"""

import json
import os
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
EVENTS_DB = Path(os.environ.get("SCHEME_EVENTS_DB", _DATA_DIR / "events.db"))

_schema_ready = False


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _open() -> tuple[Any, str]:
    """Return (connection, placeholder). Placeholder is '%s' for PG, '?' for SQLite."""
    if _database_url():
        import psycopg  # imported only when Postgres is configured

        conn = psycopg.connect(_database_url())
        ph = "%s"
    else:
        EVENTS_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(EVENTS_DB)
        ph = "?"
    _ensure_schema(conn, ph)
    return conn, ph


def _ensure_schema(conn: Any, ph: str) -> None:
    global _schema_ready
    if _schema_ready:
        return
    id_col = "SERIAL PRIMARY KEY" if ph == "%s" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS responses (
            id             {id_col},
            rid            TEXT NOT NULL,
            ts             TEXT NOT NULL,
            state          TEXT,
            age            INTEGER,
            gender         TEXT,
            caste          TEXT,
            annual_income  BIGINT,
            occupation     TEXT,
            land_acres     REAL,
            has_bpl        INTEGER,
            is_disabled    INTEGER,
            is_widow       INTEGER,
            matched_count  INTEGER NOT NULL,
            annual_cash    BIGINT NOT NULL,
            scheme_ids     TEXT NOT NULL
        )
        """
    )
    conn.commit()
    _schema_ready = True


def _sql(query: str, ph: str) -> str:
    return query.replace("?", "%s") if ph == "%s" else query


def _q(conn: Any, ph: str, query: str, params: tuple = ()) -> list[tuple]:
    return conn.execute(_sql(query, ph), params).fetchall()


def log_response(
    profile: dict[str, Any], matched_count: int, annual_cash: int, scheme_ids: list[str]
) -> None:
    """Record one check (anonymised full response). Silently ignores failures."""
    try:
        conn, ph = _open()
        try:
            conn.execute(
                _sql(
                    "INSERT INTO responses (rid, ts, state, age, gender, caste, "
                    "annual_income, occupation, land_acres, has_bpl, is_disabled, "
                    "is_widow, matched_count, annual_cash, scheme_ids) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ph,
                ),
                (
                    uuid.uuid4().hex,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    profile.get("state"),
                    profile.get("age"),
                    profile.get("gender"),
                    profile.get("caste"),
                    profile.get("annual_income"),
                    profile.get("occupation"),
                    profile.get("land_acres"),
                    int(bool(profile.get("has_bpl_card"))),
                    int(bool(profile.get("is_differently_abled"))),
                    int(bool(profile.get("is_widow"))),
                    int(matched_count),
                    int(annual_cash),
                    json.dumps(scheme_ids),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


# ── queries ────────────────────────────────────────────────
def overview() -> dict[str, Any]:
    conn, ph = _open()
    try:
        total = _q(conn, ph, "SELECT COUNT(*) FROM responses")[0][0]
        today = datetime.now(timezone.utc).date().isoformat()
        today_count = _q(
            conn, ph, "SELECT COUNT(*) FROM responses WHERE substr(ts,1,10)=?", (today,)
        )[0][0]
        avg_matched = _q(conn, ph, "SELECT AVG(matched_count) FROM responses")[0][0] or 0
        avg_cash = _q(conn, ph, "SELECT AVG(annual_cash) FROM responses")[0][0] or 0
    finally:
        conn.close()
    return {
        "total_checks": total,
        "checks_today": today_count,
        "avg_matched": round(float(avg_matched), 1),
        "avg_cash": int(avg_cash),
    }


def checks_per_day(days: int = 14) -> dict[str, list]:
    conn, ph = _open()
    try:
        rows = _q(
            conn, ph, "SELECT substr(ts,1,10) d, COUNT(*) c FROM responses GROUP BY substr(ts,1,10)"
        )
    finally:
        conn.close()
    counts = {r[0]: r[1] for r in rows}
    today = datetime.now(timezone.utc).date()
    labels, data = [], []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        labels.append(day)
        data.append(counts.get(day, 0))
    return {"labels": labels, "data": data}


def top_states(limit: int = 8) -> dict[str, list]:
    conn, ph = _open()
    try:
        rows = _q(
            conn,
            ph,
            "SELECT COALESCE(state,'Unknown') s, COUNT(*) c FROM responses "
            "GROUP BY state ORDER BY c DESC LIMIT ?",
            (limit,),
        )
    finally:
        conn.close()
    return {"labels": [r[0] for r in rows], "data": [r[1] for r in rows]}


def checks_by_state() -> dict[str, int]:
    conn, ph = _open()
    try:
        rows = _q(
            conn,
            ph,
            "SELECT state, COUNT(*) c FROM responses WHERE state IS NOT NULL GROUP BY state",
        )
    finally:
        conn.close()
    return {r[0]: r[1] for r in rows}


_DIM_COLUMNS = {"gender", "caste", "occupation", "state"}


def distribution(field: str) -> dict[str, list]:
    """Count of responses grouped by an answer column (whitelisted)."""
    if field not in _DIM_COLUMNS:
        return {"labels": [], "data": []}
    conn, ph = _open()
    try:
        rows = _q(
            conn,
            ph,
            f"SELECT COALESCE({field},'Unknown') k, COUNT(*) c FROM responses "
            "GROUP BY k ORDER BY c DESC",
        )
    finally:
        conn.close()
    return {"labels": [str(r[0]).replace("_", " ") for r in rows], "data": [r[1] for r in rows]}


def income_bands() -> dict[str, list]:
    case = (
        "CASE WHEN annual_income < 60000 THEN 'Below 60k' "
        "WHEN annual_income < 250000 THEN '60k-2.5L' "
        "WHEN annual_income < 800000 THEN '2.5L-8L' ELSE 'Above 8L' END"
    )
    conn, ph = _open()
    try:
        rows = _q(conn, ph, f"SELECT {case} b, COUNT(*) c FROM responses GROUP BY {case}")
    finally:
        conn.close()
    order = ["Below 60k", "60k-2.5L", "2.5L-8L", "Above 8L"]
    counts = {r[0]: r[1] for r in rows}
    return {"labels": order, "data": [counts.get(b, 0) for b in order]}


def age_bands() -> dict[str, list]:
    case = (
        "CASE WHEN age < 18 THEN 'Under 18' WHEN age < 30 THEN '18-29' "
        "WHEN age < 45 THEN '30-44' WHEN age < 60 THEN '45-59' ELSE '60+' END"
    )
    conn, ph = _open()
    try:
        rows = _q(conn, ph, f"SELECT {case} b, COUNT(*) c FROM responses GROUP BY {case}")
    finally:
        conn.close()
    order = ["Under 18", "18-29", "30-44", "45-59", "60+"]
    counts = {r[0]: r[1] for r in rows}
    return {"labels": order, "data": [counts.get(b, 0) for b in order]}


def top_scheme_ids(limit: int = 10) -> list[tuple[str, int]]:
    conn, ph = _open()
    try:
        rows = _q(conn, ph, "SELECT scheme_ids FROM responses")
    finally:
        conn.close()
    counter: Counter[str] = Counter()
    for (raw,) in rows:
        try:
            counter.update(json.loads(raw))
        except Exception:
            continue
    return counter.most_common(limit)


def recent_checks(limit: int = 12) -> list[dict[str, Any]]:
    conn, ph = _open()
    try:
        rows = _q(
            conn,
            ph,
            "SELECT ts, state, matched_count, annual_cash FROM responses ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    finally:
        conn.close()
    return [{"ts": r[0], "state": r[1], "matched_count": r[2], "annual_cash": r[3]} for r in rows]
