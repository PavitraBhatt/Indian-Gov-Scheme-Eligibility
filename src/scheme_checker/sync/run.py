"""Sync orchestrator: fetch -> normalize -> diff -> write a proposal.

Run as a module or via the ``scheme-sync`` entry point. It never publishes
directly: it writes the proposed new/changed schemes to a JSON file (default
``data/_sync_proposal.json``) and prints a summary. A GitHub Action turns that
proposal into a pull request for human review.

    scheme-sync --max 20 --out data/_sync_proposal.json

Requires MYSCHEME_API_KEY (source) and ANTHROPIC_API_KEY (normalizer) for a
real run; both are injected from CI secrets.
"""

import argparse
import json
import sys
from pathlib import Path

from ..schemes import load_schemes
from .diff import CHANGED, NEW, diff_schemes, summarize
from .normalize import normalize_scheme
from .sources import MyySchemeSource

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_DEFAULT_OUT = Path(__file__).parent.parent.parent.parent / "data" / "_sync_proposal.json"


def run_sync(
    source=None,
    completer=None,
    last_verified: str = "",
    max_schemes: int | None = None,
    current: list | None = None,
) -> dict:
    """Run the pipeline and return the proposal dict (no file I/O)."""
    source = source or MyySchemeSource(max_schemes=max_schemes)
    raw_schemes = source.fetch()

    normalized, dropped = [], []
    for raw in raw_schemes:
        scheme, errors = normalize_scheme(raw, last_verified=last_verified, completer=completer)
        if errors:
            dropped.append({"id": scheme.get("id"), "errors": errors})
        else:
            normalized.append(scheme)

    if current is None:
        # central schemes only — the sync targets central schemes
        current = load_schemes()
    buckets = diff_schemes(normalized, current)

    return {
        "summary": summarize(buckets),
        "new": buckets[NEW],
        "changed": buckets[CHANGED],
        "dropped": dropped,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scheme-sync", description="Sync schemes from myScheme.")
    p.add_argument("--max", type=int, default=None, help="Cap number of schemes fetched")
    p.add_argument("--out", default=str(_DEFAULT_OUT), help="Proposal output path")
    p.add_argument("--last-verified", default="", help="ISO date stamp for synced schemes")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    proposal = run_sync(last_verified=args.last_verified, max_schemes=args.max)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Sync proposal: {proposal['summary']}")
    if proposal["dropped"]:
        print(f"Dropped {len(proposal['dropped'])} invalid scheme(s):")
        for d in proposal["dropped"]:
            print(f"  - {d['id']}: {'; '.join(d['errors'][:2])}")
    print(f"Written to {out}")

    # Exit code 0 = nothing to propose, 10 = changes await review (for CI gating)
    has_changes = bool(proposal["new"] or proposal["changed"])
    return 10 if has_changes else 0


if __name__ == "__main__":
    sys.exit(main())
