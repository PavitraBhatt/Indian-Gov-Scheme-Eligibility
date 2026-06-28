"""Command-line interface for the scheme eligibility checker.

Example:
    scheme-check --state Gujarat --age 35 --gender Female --caste OBC \\
        --income 50000 --occupation farmer --land 1.5 --bpl
"""

import argparse
import json
import sys

from .core import UserProfile, match_schemes
from .schemes import load_schemes

# Scheme names are in Hindi/Gujarati too, so force UTF-8 output on consoles
# (notably Windows cp1252) that would otherwise raise UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OCCUPATIONS = [
    "farmer",
    "daily_wage",
    "self_employed",
    "salaried",
    "artisan",
    "student",
    "unemployed",
    "homemaker",
]
CASTES = ["General", "OBC", "SC", "ST", "EWS", "Minority"]
GENDERS = ["Male", "Female", "Other"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scheme-check",
        description="Find Indian government schemes you are eligible for.",
    )
    p.add_argument("--state", required=True, help="State of residence, e.g. Gujarat")
    p.add_argument("--age", type=int, required=True, help="Applicant age")
    p.add_argument("--gender", choices=GENDERS, default="Other")
    p.add_argument("--caste", choices=CASTES, default="General")
    p.add_argument("--income", type=int, default=0, help="Annual household income (Rs)")
    p.add_argument("--occupation", choices=OCCUPATIONS, default="unemployed")
    p.add_argument("--land", type=float, default=None, help="Agricultural land owned (acres)")
    p.add_argument("--bpl", action="store_true", help="Has a BPL ration card")
    p.add_argument("--disabled", action="store_true", help="Person with 40%%+ disability")
    p.add_argument("--widow", action="store_true", help="Is a widow")
    p.add_argument("--json", action="store_true", help="Output raw JSON instead of text")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    profile = UserProfile.from_dict(
        {
            "state": args.state,
            "age": args.age,
            "gender": args.gender,
            "caste": args.caste,
            "annual_income": args.income,
            "occupation": args.occupation,
            "land_acres": args.land,
            "has_bpl_card": args.bpl,
            "is_differently_abled": args.disabled,
            "is_widow": args.widow,
        }
    )

    schemes = load_schemes(states=[args.state])
    matched = match_schemes(profile, schemes)
    total = sum(s.get("benefit_amount", 0) for s in matched)

    if args.json:
        print(
            json.dumps(
                {"count": len(matched), "total_annual_benefit": total, "schemes": matched},
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if not matched:
        print("No schemes matched your profile. Try adjusting your answers.")
        return

    print(f"\n✓ You qualify for {len(matched)} scheme(s) worth up to Rs {total:,}/year\n")
    for i, s in enumerate(matched, 1):
        print(f"{i:>2}. {s['name_en']}")
        print(f"    {s['benefit_en']}")
        print(f"    Apply: {s['apply_link']}\n")


if __name__ == "__main__":
    main()
