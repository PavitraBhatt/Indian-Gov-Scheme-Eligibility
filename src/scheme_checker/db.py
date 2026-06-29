"""SQLite runtime store for schemes.

The JSON files in ``data/`` remain the source of truth — human-editable,
reviewed in pull requests, and validated by ``tests/test_data.py``. This module
builds a SQLite database from those JSON files and serves indexed queries from
it. The DB is rebuilt automatically whenever a JSON file changes, so the JSON
and the runtime store never drift.

Set the ``SCHEME_DB_PATH`` env var to override where the DB file lives (useful
for read-only deploys that need it on a writable volume).
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = Path(os.environ.get("SCHEME_DB_PATH", _DATA_DIR / "schemes.db"))

# Which state a given scheme file belongs to. Central schemes have no state.
_FILE_STATE = {
    "schemes_central.json": None,
    "schemes_gujarat.json": "Gujarat",
    "schemes_maharashtra.json": "Maharashtra",
    "schemes_rajasthan.json": "Rajasthan",
    "schemes_uttar_pradesh.json": "Uttar Pradesh",
}

# Scalar columns stored natively; everything else is JSON-encoded text.
_JSON_FIELDS = ("eligibility", "documents", "steps_en", "rejection_reasons", "tags")
_SCALAR_FIELDS = (
    "id",
    "name_en",
    "name_hi",
    "name_gu",
    "ministry",
    "category",
    "benefit_en",
    "benefit_amount",
    "benefit_type",
    "apply_link",
    "scam_note",
    "processing_days",
    "state_specific",
)


def _scheme_files() -> list[Path]:
    return [_DATA_DIR / name for name in _FILE_STATE if (_DATA_DIR / name).exists()]


def _needs_rebuild(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    db_mtime = db_path.stat().st_mtime
    return any(f.stat().st_mtime > db_mtime for f in _scheme_files())


def build_db(db_path: Path = DB_PATH, force: bool = False) -> int:
    """(Re)build the SQLite DB from the JSON files. Returns the row count."""
    if not force and not _needs_rebuild(db_path):
        return _count(db_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE schemes (
                id            TEXT PRIMARY KEY,
                name_en       TEXT NOT NULL,
                name_hi       TEXT NOT NULL,
                name_gu       TEXT NOT NULL,
                ministry      TEXT NOT NULL,
                category      TEXT NOT NULL,
                benefit_en    TEXT NOT NULL,
                benefit_amount INTEGER NOT NULL,
                benefit_type  TEXT NOT NULL,
                apply_link    TEXT NOT NULL,
                scam_note     TEXT NOT NULL,
                processing_days TEXT NOT NULL,
                state_specific INTEGER NOT NULL,
                source_state  TEXT,            -- NULL for central schemes
                eligibility   TEXT NOT NULL,   -- JSON
                documents     TEXT NOT NULL,   -- JSON
                steps_en      TEXT NOT NULL,   -- JSON
                rejection_reasons TEXT NOT NULL, -- JSON
                tags          TEXT NOT NULL    -- JSON
            )
            """
        )
        conn.execute("CREATE INDEX idx_source_state ON schemes(source_state)")
        conn.execute("CREATE INDEX idx_category ON schemes(category)")

        rows = []
        for name, state in _FILE_STATE.items():
            path = _DATA_DIR / name
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as f:
                for s in json.load(f):
                    rows.append(
                        (
                            s["id"],
                            s["name_en"],
                            s["name_hi"],
                            s["name_gu"],
                            s["ministry"],
                            s["category"],
                            s["benefit_en"],
                            s["benefit_amount"],
                            s["benefit_type"],
                            s["apply_link"],
                            s["scam_note"],
                            s["processing_days"],
                            int(s["state_specific"]),
                            state,
                            json.dumps(s["eligibility"], ensure_ascii=False),
                            json.dumps(s["documents"], ensure_ascii=False),
                            json.dumps(s["steps_en"], ensure_ascii=False),
                            json.dumps(s["rejection_reasons"], ensure_ascii=False),
                            json.dumps(s["tags"], ensure_ascii=False),
                        )
                    )
        conn.executemany(
            """
            INSERT INTO schemes (
                id, name_en, name_hi, name_gu, ministry, category, benefit_en,
                benefit_amount, benefit_type, apply_link, scam_note, processing_days,
                state_specific, source_state, eligibility, documents, steps_en,
                rejection_reasons, tags
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def _count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM schemes").fetchone()[0]
    finally:
        conn.close()


def _row_to_scheme(row: sqlite3.Row) -> dict[str, Any]:
    """Reconstruct the original scheme dict shape from a DB row."""
    scheme: dict[str, Any] = {}
    for field in _SCALAR_FIELDS:
        scheme[field] = row[field]
    scheme["state_specific"] = bool(row["state_specific"])
    for field in _JSON_FIELDS:
        scheme[field] = json.loads(row[field])
    return scheme


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    build_db(db_path)  # ensure built / fresh
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def query_schemes(
    states: list[str] | None = None,
    category: str | None = None,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    """Return central schemes plus any matching the given states.

    Mirrors the previous JSON loader's behaviour and return shape.
    """
    clauses = ["source_state IS NULL"]
    params: list[Any] = []
    if states:
        placeholders = ",".join("?" for _ in states)
        clauses.append(f"source_state IN ({placeholders})")
        params.extend(states)
    where = " OR ".join(clauses)

    sql = f"SELECT * FROM schemes WHERE ({where})"
    if category:
        sql += " AND category = ?"
        params.append(category)

    conn = _connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row_to_scheme(r) for r in rows]


def get_scheme(scheme_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_scheme(row) if row else None
