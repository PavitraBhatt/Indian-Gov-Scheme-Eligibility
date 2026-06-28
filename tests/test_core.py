from scheme_checker import EligibilityChecker, UserProfile, age_between, match_schemes


def test_age_rule_passes():
    checker = EligibilityChecker(rules=[age_between(18, 25)])
    assert checker.is_eligible({"age": 20}, {}) is True


def test_age_rule_fails():
    checker = EligibilityChecker(rules=[age_between(18, 25)])
    assert checker.is_eligible({"age": 30}, {}) is False


def _farmer_profile(**overrides):
    defaults = dict(
        state="Gujarat", age=35, gender="Male", caste="OBC",
        annual_income=120000, occupation="farmer", land_acres=2.0,
        has_bpl_card=False, is_differently_abled=False, is_widow=False,
    )
    defaults.update(overrides)
    return UserProfile.from_dict(defaults)


def test_match_schemes_farmer_gets_kisan():
    from scheme_checker import load_schemes
    schemes = load_schemes(states=["Gujarat"])
    profile = _farmer_profile()
    matched_ids = {s["id"] for s in match_schemes(profile, schemes)}
    assert "pm_kisan" in matched_ids


def test_match_schemes_income_filter():
    from scheme_checker import load_schemes
    schemes = load_schemes()
    # High income — should NOT get pm_kisan (income_max=200000)
    profile = _farmer_profile(annual_income=500000)
    matched_ids = {s["id"] for s in match_schemes(profile, schemes)}
    assert "pm_kisan" not in matched_ids


def test_match_schemes_bpl_required():
    from scheme_checker import load_schemes
    schemes = load_schemes()
    # Without BPL card
    profile_no_bpl = _farmer_profile(has_bpl_card=False)
    matched_ids = {s["id"] for s in match_schemes(profile_no_bpl, schemes)}
    assert "ayushman_bharat" not in matched_ids

    # With BPL card
    profile_bpl = _farmer_profile(has_bpl_card=True)
    matched_ids_bpl = {s["id"] for s in match_schemes(profile_bpl, schemes)}
    assert "ayushman_bharat" in matched_ids_bpl


def test_match_schemes_gender_filter():
    from scheme_checker import load_schemes
    schemes = load_schemes()
    # pm_ujjwala requires Female + BPL
    male_profile = _farmer_profile(gender="Male", has_bpl_card=True)
    female_profile = _farmer_profile(gender="Female", has_bpl_card=True)

    male_ids = {s["id"] for s in match_schemes(male_profile, schemes)}
    female_ids = {s["id"] for s in match_schemes(female_profile, schemes)}

    assert "pm_ujjwala" not in male_ids
    assert "pm_ujjwala" in female_ids


def test_gujarat_schemes_only_in_gujarat():
    from scheme_checker import load_schemes
    gujarat_schemes = load_schemes(states=["Gujarat"])
    other_schemes = load_schemes(states=["Maharashtra"])

    gujarat_ids = {s["id"] for s in gujarat_schemes}
    other_ids = {s["id"] for s in other_schemes}

    assert "gu_ikhedut" in gujarat_ids
    assert "gu_ikhedut" not in other_ids


def test_each_supported_state_loads_its_schemes():
    from scheme_checker import load_schemes
    expectations = {
        "Maharashtra": "mh_ladki_bahin",
        "Rajasthan": "rj_chiranjeevi_health",
        "Uttar Pradesh": "up_kanya_sumangala",
    }
    for state, expected_id in expectations.items():
        ids = {s["id"] for s in load_schemes(states=[state])}
        assert expected_id in ids, f"{state} should load {expected_id}"


def test_central_schemes_load_without_state():
    from scheme_checker import load_schemes
    central = load_schemes()
    # State-specific schemes must NOT appear when no state requested
    ids = {s["id"] for s in central}
    assert "mh_ladki_bahin" not in ids
    assert "pm_kisan" in ids


def test_results_sorted_by_benefit_amount():
    from scheme_checker import load_schemes
    schemes = load_schemes()
    profile = _farmer_profile(has_bpl_card=True, annual_income=50000)
    matched = match_schemes(profile, schemes)
    amounts = [s["benefit_amount"] for s in matched]
    assert amounts == sorted(amounts, reverse=True)
