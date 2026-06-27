import json
from pathlib import Path
from typing import List, Dict, Any

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_schemes(states: List[str] = None) -> List[Dict[str, Any]]:
    """Load schemes from JSON files. Filters by states if provided."""
    all_schemes: List[Dict[str, Any]] = []

    central_path = _DATA_DIR / "schemes_central.json"
    if central_path.exists():
        with open(central_path, encoding="utf-8") as f:
            all_schemes.extend(json.load(f))

    state_file_map = {
        "Gujarat": "schemes_gujarat.json",
        "Maharashtra": "schemes_maharashtra.json",
        "Rajasthan": "schemes_rajasthan.json",
    }

    if states:
        for state in states:
            state_file = state_file_map.get(state)
            if state_file:
                path = _DATA_DIR / state_file
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        all_schemes.extend(json.load(f))

    return all_schemes


def get_scheme_by_id(scheme_id: str) -> Dict[str, Any] | None:
    all_schemes = load_schemes(states=list({"Gujarat", "Maharashtra", "Rajasthan"}))
    for scheme in all_schemes:
        if scheme.get("id") == scheme_id:
            return scheme
    return None
