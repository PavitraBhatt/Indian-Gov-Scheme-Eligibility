from typing import Any, Dict, List, Optional


class UserProfile:
    def __init__(
        self,
        state: str,
        age: int,
        gender: str,
        caste: str,
        annual_income: int,
        occupation: str,
        land_acres: Optional[float],
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
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
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


def _check_eligibility(profile: UserProfile, scheme: Dict[str, Any]) -> bool:
    e = scheme.get("eligibility", {})

    if e.get("states") != "all":
        allowed_states = e.get("states", [])
        if profile.state not in allowed_states:
            return False

    min_age = e.get("age_min")
    max_age = e.get("age_max")
    if min_age is not None and profile.age < min_age:
        return False
    if max_age is not None and profile.age > max_age:
        return False

    allowed_genders = e.get("gender")
    if allowed_genders and profile.gender not in allowed_genders:
        return False

    allowed_castes = e.get("caste")
    if allowed_castes and profile.caste not in allowed_castes:
        return False

    income_max = e.get("income_max")
    if income_max is not None and profile.annual_income > income_max:
        return False

    allowed_occupations = e.get("occupation")
    if allowed_occupations and profile.occupation not in allowed_occupations:
        return False

    land_min = e.get("land_min_acres")
    if land_min is not None:
        if profile.land_acres is None or profile.land_acres < land_min:
            return False

    if e.get("requires_bpl") and not profile.has_bpl_card:
        return False

    if e.get("requires_disability") and not profile.is_differently_abled:
        return False

    if e.get("requires_widow") and not profile.is_widow:
        return False

    return True


def match_schemes(profile: UserProfile, schemes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched = [s for s in schemes if _check_eligibility(profile, s)]
    matched.sort(key=lambda s: s.get("benefit_amount", 0), reverse=True)
    return matched


# Legacy helpers kept for backward compatibility
class EligibilityChecker:
    def __init__(self, rules: List = None):
        self.rules = rules or []

    def add_rule(self, rule):
        self.rules.append(rule)

    def is_eligible(self, applicant: Dict[str, Any], scheme: Dict[str, Any]) -> bool:
        return all(rule(applicant, scheme) for rule in self.rules)


def age_between(min_age: int, max_age: int):
    def rule(applicant, scheme):
        age = applicant.get("age")
        return age is not None and min_age <= age <= max_age
    return rule
