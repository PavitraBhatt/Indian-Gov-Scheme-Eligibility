# Indian Government Scheme Eligibility Checker

A FastAPI + Tailwind web app that helps Indian citizens discover every government scheme they qualify for — in English, Hindi, and Gujarati.

**10-question form → personalised scheme list → step-by-step application guide + scam alerts**

## Features

- 54 schemes — 49 central + 5 Gujarat state (agriculture, health, housing, finance, women, education, disability, energy, social security)
- Eligibility matching by: state, age, gender, caste, income, occupation, land ownership, BPL card, disability, widow status
- Multilingual UI: English / Hindi / Gujarati
- Per-scheme: documents checklist, step-by-step guide, scam alert, processing time, direct apply link
- REST API (`/api/check`, `/api/schemes`) for future integrations

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

## Project Structure

```
├── src/scheme_checker/
│   ├── core.py       # UserProfile + match_schemes() eligibility engine
│   ├── schemes.py    # JSON loader (central + state schemes)
│   ├── api.py        # FastAPI app
│   └── cli.py        # CLI tool
├── data/
│   ├── schemes_central.json   # 49 central government schemes
│   └── schemes_gujarat.json   # 5 Gujarat state schemes
├── frontend/
│   └── index.html    # Multilingual 10-step form + results
├── tests/
│   ├── test_core.py  # Eligibility engine tests
│   └── test_api.py   # API endpoint tests
└── .mcp.json         # GitHub MCP server config
```

## MCP Configuration

A GitHub MCP server is configured in `.mcp.json`. To use it, set your personal access token:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```

## Roadmap

- [ ] WhatsApp bot integration (Twilio)
- [ ] Shareable PNG benefit summary card
- [ ] State schemes: Maharashtra, Rajasthan, UP
- [ ] Application status tracker
- [ ] Offline PWA mode
