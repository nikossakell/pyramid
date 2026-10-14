from rule_engine.models import IntakeStatus, NutrientEvaluation
from rule_engine.recommendations import apply_recommendation_rules, select_daily_feedback
from rule_engine.rules import all_nutrient_rules


def ev(n, status, intake=None, refs=None, days=4):
    return NutrientEvaluation(n, status, days, intake, "mg/d", refs or {})


def test_ten_rules_unique():
    rules = all_nutrient_rules()
    assert len(rules) == 10
    assert {r.nutrient_id for r in rules} >= {"iron", "calcium", "sodium", "fibre", "protein", "vitamin_d"}


def test_iron_inadequate_gets_hint_and_template():
    d = apply_recommendation_rules({"iron": ev("iron", IntakeStatus.LIKELY_INADEQUATE, 6.0, {"AR": 7, "PRI": 13})})[0]
    assert d.rule_id == "R-FE-01" and d.message_template_id == "MSG-FE-likely_inadequate"
    assert "legumes" in d.food_group_hint
    assert d.research_values == {"AR": 7, "PRI": 13, "usual_intake": 6.0}
    assert "4254" in d.citation


def test_adequate_has_no_hint():
    d = apply_recommendation_rules({"iron": ev("iron", IntakeStatus.LIKELY_ADEQUATE, 14.0)})[0]
    assert d.food_group_hint == ()


def test_sodium_acts_only_above_reference():
    above = apply_recommendation_rules({"sodium": ev("sodium", IntakeStatus.ABOVE_REFERENCE, 2.5)})[0]
    within = apply_recommendation_rules({"sodium": ev("sodium", IntakeStatus.LIKELY_ADEQUATE, 1.5)})[0]
    assert above.food_group_hint and not within.food_group_hint


def test_nutrients_without_rule_ignored():
    assert apply_recommendation_rules({"zinc": ev("zinc", IntakeStatus.LIKELY_INADEQUATE)}) == []


def test_insufficient_data_recorded_but_never_shown():
    ds = apply_recommendation_rules({"iron": ev("iron", IntakeStatus.INSUFFICIENT_DATA)})
    assert len(ds) == 1 and select_daily_feedback(ds) == []


def test_daily_feedback_priority_and_cap():
    ds = apply_recommendation_rules({
        "fibre": ev("fibre", IntakeStatus.NO_CONCLUSION),
        "calcium": ev("calcium", IntakeStatus.LIKELY_INADEQUATE),
        "iron": ev("iron", IntakeStatus.UNCERTAIN),
        "sodium": ev("sodium", IntakeStatus.ABOVE_REFERENCE),
    })
    picked = select_daily_feedback(ds)
    assert [d.rule_id for d in picked] == ["R-CA-01", "R-NA-01"]


def test_daily_feedback_one_positive_when_all_fine():
    ds = apply_recommendation_rules({
        "iron": ev("iron", IntakeStatus.LIKELY_ADEQUATE),
        "calcium": ev("calcium", IntakeStatus.LIKELY_ADEQUATE),
    })
    assert [d.rule_id for d in select_daily_feedback(ds)] == ["R-CA-01"]
