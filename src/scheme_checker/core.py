from typing import Any


class UserProfile:
    def __init__(
        self,
        state: str,
        age: int,
        gender: str,
        caste: str,
        annual_income: int,
        occupation: str,
        land_acres: float | None,
        has_bpl_card: bool,
        is_differently_abled: bool,
        is_widow: bool,
    ):
        self.state = state
        self.age = age
        self.gender = gender
        self.caste = caste
        self.annual_income = annual_income
        self.occupation = occupation
        self.land_acres = land_acres
        self.has_bpl_card = has_bpl_card
        self.is_differently_abled = is_differently_abled
        self.is_widow = is_widow

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(
            state=data.get("state", ""),
            age=int(data.get("age", 0)),
            gender=data.get("gender", ""),
            caste=data.get("caste", "General"),
            annual_income=int(data.get("annual_income", 0)),
            occupation=data.get("occupation", ""),
            land_acres=float(data["land_acres"]) if data.get("land_acres") is not None else None,
            has_bpl_card=bool(data.get("has_bpl_card", False)),
            is_differently_abled=bool(data.get("is_differently_abled", False)),
            is_widow=bool(data.get("is_widow", False)),
        )


def _rupees(n: int) -> str:
    return f"Rs {n:,}"


def _failed_reasons(profile: UserProfile, scheme: dict[str, Any]) -> list[str]:
    """Return a human-readable reason for every eligibility gate the profile fails.

    An empty list means the applicant qualifies. Each reason is phrased as the
    requirement they don't yet meet, so it can power an 'almost eligible' view.
    """
    e = scheme.get("eligibility", {})
    reasons: list[str] = []

    if e.get("states") != "all":
        allowed = e.get("states", [])
        if profile.state not in allowed:
            reasons.append(f"Only for residents of {', '.join(allowed)}")

    min_age, max_age = e.get("age_min"), e.get("age_max")
    if min_age is not None and profile.age < min_age:
        reasons.append(f"You must be at least {min_age} years old")
    if max_age is not None and profile.age > max_age:
        reasons.append(f"You must be {max_age} years old or younger")

    genders = e.get("gender")
    if genders and profile.gender not in genders:
        reasons.append(f"For {', '.join(genders).lower()} applicants only")

    castes = e.get("caste")
    if castes and profile.caste not in castes:
        reasons.append(f"For {', '.join(castes)} category applicants")

    income_max = e.get("income_max")
    if income_max is not None and profile.annual_income > income_max:
        reasons.append(
            f"Household income must be under {_rupees(income_max)} "
            f"(yours is {_rupees(profile.annual_income)})"
        )

    occupations = e.get("occupation")
    if occupations and profile.occupation not in occupations:
        reasons.append(f"For {', '.join(o.replace('_', ' ') for o in occupations)} only")

    land_min = e.get("land_min_acres")
    if land_min is not None and (profile.land_acres is None or profile.land_acres < land_min):
        reasons.append(f"Requires at least {land_min} acres of agricultural land")

    if e.get("requires_bpl") and not profile.has_bpl_card:
        reasons.append("Requires a BPL ration card")
    if e.get("requires_disability") and not profile.is_differently_abled:
        reasons.append("Requires a 40%+ disability certificate")
    if e.get("requires_widow") and not profile.is_widow:
        reasons.append("Available to widows")

    return reasons


def _check_eligibility(profile: UserProfile, scheme: dict[str, Any]) -> bool:
    return not _failed_reasons(profile, scheme)


def match_schemes(profile: UserProfile, schemes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched = [s for s in schemes if _check_eligibility(profile, s)]
    matched.sort(key=lambda s: s.get("benefit_amount", 0), reverse=True)
    return matched


def benefit_totals(matched: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate benefit_amount by type so loans/insurance are never summed as cash.

    Only cash_yearly counts as recurring money received; one-time grants, loan
    ceilings and insurance cover are reported separately. Shared by the API and
    CLI so their numbers can't drift apart.
    """
    totals = {"annual_cash": 0, "one_time": 0, "loan_access": 0, "insurance_cover": 0}
    key = {
        "cash_yearly": "annual_cash",
        "one_time": "one_time",
        "loan": "loan_access",
        "insurance": "insurance_cover",
    }
    for s in matched:
        bucket = key.get(s.get("benefit_type"))
        if bucket:
            totals[bucket] += s.get("benefit_amount", 0)
    return totals


def near_misses(
    profile: UserProfile,
    schemes: list[dict[str, Any]],
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Schemes the applicant narrowly misses — failing exactly one requirement.

    Each result is the scheme dict plus a 'miss_reason' explaining the single
    gate they don't meet (e.g. 'Requires a BPL ration card'). Sorted by benefit
    so the most valuable near-misses surface first.
    """
    out = []
    for s in schemes:
        reasons = _failed_reasons(profile, s)
        if len(reasons) == 1:
            out.append({**s, "miss_reason": reasons[0]})
    out.sort(key=lambda s: s.get("benefit_amount", 0), reverse=True)
    return out[:max_results]


# Legacy helpers kept for backward compatibility
class EligibilityChecker:
    def __init__(self, rules: list = None):
        self.rules = rules or []

    def add_rule(self, rule):
        self.rules.append(rule)

    def is_eligible(self, applicant: dict[str, Any], scheme: dict[str, Any]) -> bool:
        return all(rule(applicant, scheme) for rule in self.rules)


def age_between(min_age: int, max_age: int):
    def rule(applicant, scheme):
        age = applicant.get("age")
        return age is not None and min_age <= age <= max_age

    return rule
