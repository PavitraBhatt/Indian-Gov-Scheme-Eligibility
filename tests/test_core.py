from scheme_checker import EligibilityChecker, age_between


def test_age_rule_passes():
    checker = EligibilityChecker(rules=[age_between(18, 25)])
    applicant = {"age": 20}
    assert checker.is_eligible(applicant, {}) is True


def test_age_rule_fails():
    checker = EligibilityChecker(rules=[age_between(18, 25)])
    applicant = {"age": 30}
    assert checker.is_eligible(applicant, {}) is False
