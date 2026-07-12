# SchemeSaathi — Government Scheme Eligibility Checker

**SchemeSaathi** (योजना साथी — "your scheme companion") is a FastAPI + Tailwind web app that helps Indian citizens discover every government scheme they qualify for — in English, Hindi, and Gujarati.

**10-question form → personalised scheme list → step-by-step application guide + scam alerts**

## Features

- 64 schemes — 49 central + 15 state (Gujarat, Maharashtra, Rajasthan, Uttar Pradesh), spanning agriculture, health, housing, finance, women & children, education, disability, energy, and social security
- Eligibility matching by: state, age, gender, caste, income, occupation, land ownership, BPL card, disability, widow status
- **Honest benefit totals** — recurring cash, one-time grants, loan *access*, and insurance *cover* are reported separately (a loan ceiling is never presented as yearly income)
- **"Almost eligible" guidance** — schemes you miss by one rule, with the exact requirement that would unlock each
- Multilingual UI: **English / Hindi / Gujarati** (UI strings + scheme names). Note: per-scheme *content* (benefit text, steps, documents, scam note) is currently English-only — translating that content is on the roadmap.
- Per-scheme: documents checklist, step-by-step guide, scam alert, processing time, direct apply link
- Shareable **PDF benefit card**
- Validated REST API (`/api/check`, `/api/schemes`) for integrations

## Quick Start

```bash
# 1. Create virtualenv and install
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
pip install -e .

# 2. Run the server
uvicorn scheme_checker.api:app --reload --port 8000

# 3. Open browser
# http://localhost:8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Frontend HTML |
| POST | `/api/check` | Check eligibility (returns matched schemes) |
| GET | `/api/schemes` | List all schemes (optional ?state=Gujarat&category=agriculture) |
| GET | `/api/schemes/{id}` | Get single scheme by ID |
| GET | `/api/health` | Health check |

### Example: Check eligibility

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Gujarat",
    "age": 35,
    "gender": "Male",
    "caste": "OBC",
    "annual_income": 120000,
    "occupation": "farmer",
    "land_acres": 2.5,
    "has_bpl_card": false,
    "is_differently_abled": false,
    "is_widow": false
  }'
```

## Run Tests

```bash
pytest -v
```

## CLI

```bash
scheme-check --state Gujarat --age 35 --occupation farmer --land 2.0 --income 120000
scheme-check --state Maharashtra --age 40 --bpl --json   # machine-readable output
```

## Deployment

The app is containerised and deploys free on Render/Railway/Fly.

```bash
# Local Docker run
docker build -t scheme-checker .
docker run -p 8000:8000 scheme-checker
```

- **Render:** New → Blueprint → connect this repo (uses `render.yaml`).
- **Railway/Heroku:** uses the `Procfile`.
- Health check: `GET /api/health`.

## Admin dashboard (`/admin`)

A password-gated dashboard for the site owner (FastAPI + Jinja + Alpine.js + Chart.js):

- **Overview** — scheme/category counts, total & today's checks, most-matched schemes, recent activity
- **Analytics** — privacy-safe charts (checks/day, by state, most-matched schemes, catalogue by category). **No personal data is stored** — only aggregate rows (state + counts), logged to a separate `data/events.db`.
- **Scheme manager** — search + add / edit / delete schemes via a form; writes to the JSON source and rebuilds SQLite live.

Enable it by setting an env var (the dashboard is **disabled** until you do, so there's no default-password hole):

```bash
export ADMIN_PASSWORD="your-strong-password"
export SESSION_SECRET="any-long-random-string"   # optional; keeps you logged in across restarts
```

Then visit `/admin`. On Render, set both in the service's **Environment** tab.

> ⚠️ On an ephemeral host (Render free tier) logged analytics and dashboard edits reset on redeploy. For durable data, point `SCHEME_EVENTS_DB` / `SCHEME_DB_PATH` at a persistent disk or external DB. Scheme edits are best made in git (the source of truth) for production.

## Storage

JSON files in `data/` are the **source of truth** (human-editable, reviewed in
PRs, validated by `tests/test_data.py`). At runtime, `db.py` builds an indexed
**SQLite** database from them and auto-rebuilds whenever a JSON file changes, so
the two never drift. Set `SCHEME_DB_PATH` to relocate the DB on read-only hosts.

## Keeping schemes up to date (sync pipeline)

The app can stay current with new and updated government schemes via a
**review-gated** sync pipeline (`src/scheme_checker/sync/`):

```
myScheme (via API Setu) → fetch → Claude-normalize → validate → diff → open PR
```

- A scheduled GitHub Action (`.github/workflows/sync-schemes.yml`, weekly + manual)
  fetches schemes, normalizes them to our schema with Claude, drops anything that
  fails validation, diffs against the database, and **opens a pull request** with
  new/changed schemes.
- **Nothing auto-publishes** — a human reviews and merges the PR. This protects
  eligibility accuracy and scam-alert integrity. On merge, SQLite rebuilds and the
  changes go live.
- Run locally: `scheme-sync --max 25 --last-verified 2026-06-28 --apply`
- Secrets required in CI: `MYSCHEME_API_KEY` (API Setu key) and `ANTHROPIC_API_KEY`.

## Project Structure

```
├── src/scheme_checker/
│   ├── core.py       # UserProfile + match_schemes() eligibility engine
│   ├── db.py         # SQLite runtime store built from JSON
│   ├── schemes.py    # Access layer (load_schemes / get_scheme_by_id)
│   ├── api.py        # FastAPI app
│   └── cli.py        # CLI tool
├── data/
│   ├── schemes_central.json        # 49 central schemes
│   ├── schemes_gujarat.json        # Gujarat state schemes
│   ├── schemes_maharashtra.json    # Maharashtra
│   ├── schemes_rajasthan.json      # Rajasthan
│   └── schemes_uttar_pradesh.json  # Uttar Pradesh
├── frontend/
│   └── index.html    # Multilingual 10-step form + shareable PDF card
├── tests/            # core, api, cli, db, schema, sync, data-integrity (140+ tests)
├── Dockerfile · render.yaml · Procfile   # deployment
└── .mcp.json         # GitHub MCP server config
```

## MCP Configuration

A GitHub MCP server is configured in `.mcp.json`. To use it, set your personal access token:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```

## Roadmap

- [x] Shareable PDF benefit card
- [x] State schemes: Maharashtra, Rajasthan, UP
- [x] SQLite storage layer
- [x] Honest, type-aware benefit totals + "almost eligible" guidance
- [x] Review-gated Claude sync pipeline (myScheme → PR)
- [ ] Translate per-scheme content (benefit text, steps, docs) to Hindi & Gujarati
- [ ] WhatsApp bot integration (Twilio)
- [ ] Application status tracker
- [ ] Offline PWA mode
