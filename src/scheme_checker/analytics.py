"""Privacy-safe usage analytics for the admin dashboard.

Every eligibility check logs an aggregate row — state, how many schemes matched,
the cash unlocked, and the matched scheme ids. It deliberately stores **no
personal data** (no age, income, gender, caste, etc.).

Events live in their own SQLite file, separate from schemes.db: build_db()
deletes and rebuilds schemes.db from JSON, so co-locating events there would
wipe them. Logging never raises — a failed insert must not break a user's check.

Note: on an ephemeral host (e.g. Render free tier) this file resets on redeploy;
set SCHEME_EVENTS_DB to a persistent path/volume for durable analytics.
"""

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
EVENTS_DB = Path(os.environ.get("SCHEME_EVENTS_DB", _DATA_DIR / "events.db"))


def _connect() -> sqlite3.Connection:
    EVENTS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(EVENTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT NOT NULL,
            state         TEXT,
            matched_count INTEGER NOT NULL,
            annual_cash   INTEGER NOT NULL,
            scheme_ids    TEXT NOT NULL   -- JSON array
        )
        """
    )
    return conn


def log_check(state: str, matched_count: int, annual_cash: int, scheme_ids: list[str]) -> None:
    """Record one eligibility check. Silently ignores any failure."""
    try:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO checks (ts, state, matched_count, annual_cash, scheme_ids) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    state,
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


def _all_rows() -> list[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute("SELECT * FROM checks").fetchall()
    finally:
        conn.close()


def overview() -> dict[str, Any]:
    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
        today = datetime.now(timezone.utc).date().isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) FROM checks WHERE substr(ts,1,10)=?", (today,)
        ).fetchone()[0]
        avg_matched = conn.execute("SELECT AVG(matched_count) FROM checks").fetchone()[0] or 0
        avg_cash = conn.execute("SELECT AVG(annual_cash) FROM checks").fetchone()[0] or 0
    finally:
        conn.close()
    return {
        "total_checks": total,
        "checks_today": today_count,
        "avg_matched": round(avg_matched, 1),
        "avg_cash": int(avg_cash),
    }


def checks_per_day(days: int = 14) -> dict[str, list]:
    """Return {labels: [dates], data: [counts]} for the last `days` days."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT substr(ts,1,10) d, COUNT(*) c FROM checks GROUP BY d"
        ).fetchall()
    finally:
        conn.close()
    counts = {r["d"]: r["c"] for r in rows}
    today = datetime.now(timezone.utc).date()
    labels, data = [], []
    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        labels.append(day)
        data.append(counts.get(day, 0))
    return {"labels": labels, "data": data}


def top_states(limit: int = 8) -> dict[str, list]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT COALESCE(state,'Unknown') s, COUNT(*) c FROM checks "
            "GROUP BY s ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return {"labels": [r["s"] for r in rows], "data": [r["c"] for r in rows]}


def checks_by_state() -> dict[str, int]:
    """All states with their check counts, for the choropleth footfall map."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT state, COUNT(*) c FROM checks WHERE state IS NOT NULL GROUP BY state"
        ).fetchall()
    finally:
        conn.close()
    return {r["state"]: r["c"] for r in rows}


def top_scheme_ids(limit: int = 10) -> list[tuple[str, int]]:
    """Most-frequently-matched scheme ids across all checks."""
    counter: Counter[str] = Counter()
    for row in _all_rows():
        try:
            counter.update(json.loads(row["scheme_ids"]))
        except Exception:
            continue
    return counter.most_common(limit)


def recent_checks(limit: int = 12) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT ts, state, matched_count, annual_cash FROM checks ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
