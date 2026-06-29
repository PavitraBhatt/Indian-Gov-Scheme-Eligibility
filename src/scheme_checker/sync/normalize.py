"""Claude-assisted normalization of raw scheme blobs into our strict schema.

A raw scheme from a government source is loosely structured prose. This module
asks Claude to map it into the exact shape ``scheme_checker.schema`` defines —
including Hindi/Gujarati names, a plain-language application guide, and a scam
note — then validates the result against the same rules the hand-written
database is held to. Anything that fails validation is returned with its errors
so the pipeline can drop it rather than publish bad data.

The Claude call is injected via ``completer`` so tests (and CI) run without
network or an API key. The default completer uses the official Anthropic SDK.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from ..schema import VALID_BENEFIT_TYPES, VALID_CATEGORIES, validate_scheme

# The model is responsible for the human-authored content fields only. Identity
# and provenance (id, source_url, last_verified, state_specific) are filled in
# by code so they can't be hallucinated.
_ELIGIBILITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "states": {"type": "string", "enum": ["all"]},
        "age_min": {"type": "integer"},
        "age_max": {"type": "integer"},
        "gender": {"type": "array", "items": {"type": "string"}},
        "caste": {"type": "array", "items": {"type": "string"}},
        "income_max": {"type": "integer"},
        "occupation": {"type": "array", "items": {"type": "string"}},
        "land_min_acres": {"type": "number"},
        "requires_bpl": {"type": "boolean"},
        "requires_disability": {"type": "boolean"},
        "requires_widow": {"type": "boolean"},
    },
    "required": ["states"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name_en": {"type": "string"},
        "name_hi": {"type": "string"},
        "name_gu": {"type": "string"},
        "ministry": {"type": "string"},
        "category": {"type": "string", "enum": sorted(VALID_CATEGORIES)},
        "benefit_en": {"type": "string"},
        "benefit_amount": {"type": "integer"},
        "benefit_type": {"type": "string", "enum": sorted(VALID_BENEFIT_TYPES)},
        "apply_link": {"type": "string"},
        "eligibility": _ELIGIBILITY_SCHEMA,
        "documents": {"type": "array", "items": {"type": "string"}},
        "steps_en": {"type": "array", "items": {"type": "string"}},
        "rejection_reasons": {"type": "array", "items": {"type": "string"}},
        "scam_note": {"type": "string"},
        "processing_days": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "name_en",
        "name_hi",
        "name_gu",
        "ministry",
        "category",
        "benefit_en",
        "benefit_amount",
        "benefit_type",
        "apply_link",
        "eligibility",
        "documents",
        "steps_en",
        "rejection_reasons",
        "scam_note",
        "processing_days",
        "tags",
    ],
}

SYSTEM_PROMPT = """\
You convert raw Indian government welfare-scheme descriptions into a strict \
JSON record for an eligibility-checker app used by low-income citizens.

Rules:
- name_hi and name_gu are the scheme name in Hindi and Gujarati script.
- category MUST be one of: agriculture, health, housing, insurance, finance, \
women_children, education_youth, senior_disability, energy.
- benefit_amount is the headline rupee value as an integer (0 if not monetary).
- benefit_type MUST be one of: cash_yearly (recurring annual/monthly cash), \
one_time (one-time cash/asset/subsidy/stipend), loan (a loan or credit ceiling \
to be repaid), insurance (cover paid only if the event happens), service \
(non-monetary service or savings). Never call a loan or insurance ceiling cash.
- steps_en: 3-6 short, plain-language steps at a Class 8 reading level.
- documents: the documents an applicant must bring.
- scam_note: one or two sentences stating the scheme is free and where to \
report fraud. Never omit this.
- eligibility: include only fields you can determine from the text. Always set \
"states" to "all" (central scheme). Only add age_min/age_max/income_max/\
occupation/caste/gender/requires_bpl/requires_disability/requires_widow when \
the text clearly supports them. Do NOT invent eligibility rules.
- Be accurate and conservative. If unsure, leave a field out rather than guess.
"""


def _build_user(raw: dict[str, Any]) -> str:
    return (
        f"Scheme name: {raw.get('name_en', '')}\n"
        f"Source URL: {raw.get('source_url', '')}\n\n"
        f"Description:\n{raw.get('text', '')}"
    )


def slug_to_id(slug: str) -> str:
    """Turn a source slug like 'pm-kisan-samman' into a scheme id 'pm_kisan_samman'."""
    s = re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")
    return s or "scheme"


def _anthropic_completer(model: str) -> Callable[[str, str, dict], dict]:
    def completer(system: str, user: str, schema: dict) -> dict:
        import anthropic  # lazy: only needed for real runs, not tests/CI

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)

    return completer


def normalize_scheme(
    raw: dict[str, Any],
    last_verified: str,
    completer: Callable[[str, str, dict], dict] | None = None,
    model: str = "claude-opus-4-8",
) -> tuple[dict[str, Any], list[str]]:
    """Normalize one raw scheme into our schema.

    Returns (scheme, errors). An empty errors list means the scheme is valid and
    safe to propose; a non-empty list means it should be dropped/flagged.
    """
    completer = completer or _anthropic_completer(model)
    content = completer(SYSTEM_PROMPT, _build_user(raw), OUTPUT_SCHEMA)

    scheme: dict[str, Any] = {
        "id": slug_to_id(raw.get("source_id") or raw.get("name_en", "")),
        **content,
        "source_url": raw.get("source_url", ""),
        "last_verified": last_verified,
        "state_specific": False,
    }
    # central schemes always apply to all states
    elig = scheme.get("eligibility")
    if isinstance(elig, dict) and not elig.get("states"):
        elig["states"] = "all"

    return scheme, validate_scheme(scheme)
