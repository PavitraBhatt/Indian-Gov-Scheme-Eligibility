from typing import Dict, Any, List


class EligibilityChecker:
    """Simple rule-based eligibility checker.

    This is a small, extensible skeleton. Rules are functions that accept the
    applicant and scheme dicts and return True/False.
    """

    def __init__(self, rules: List = None):
        self.rules = rules or []

    def add_rule(self, rule):
        self.rules.append(rule)

    def is_eligible(self, applicant: Dict[str, Any], scheme: Dict[str, Any]) -> bool:
        """Return True if applicant satisfies all rules for the scheme."""
        for rule in self.rules:
            if not rule(applicant, scheme):
                return False
        return True


# Example rule helper
def age_between(min_age: int, max_age: int):
    def rule(applicant, scheme):
        age = applicant.get("age")
        if age is None:
            return False
        return min_age <= age <= max_age

    return rule
