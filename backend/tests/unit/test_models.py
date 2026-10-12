from datetime import date, datetime

import pytest

from rule_engine.models import (
    DailyIntake, DRVType, EvaluationContext, IntakeStatus, MealEntry, MealItem,
    MealSource, ReferenceValue, RuleDecision, Sex, UserProfile,
)


def make_profile(**kw):
    base = dict(pseudonym_id="P-001", sex=Sex.FEMALE, age_years=13)
    base.update(kw)
    return UserProfile(**base)


def test_profile_valid():
    p = make_profile(weight_kg=45.0)
    assert p.sex is Sex.FEMALE and p.weight_kg == 45.0


@pytest.mark.parametrize("age", [9, 17])
def test_profile_rejects_age_outside_protocol(age):
    with pytest.raises(ValueError):
        make_profile(age_years=age)


def test_profile_requires_pseudonym():
    with pytest.raises(ValueError):
        make_profile(pseudonym_id="")


def test_reference_applies_to_age_band():
    iron_f = ReferenceValue("iron", DRVType.AR, Sex.FEMALE, 12, 17, 7, "mg/d")
    assert iron_f.applies_to(Sex.FEMALE, 12)
    assert iron_f.applies_to(Sex.FEMALE, 16)
    assert not iron_f.applies_to(Sex.FEMALE, 11)
    assert not iron_f.applies_to(Sex.MALE, 13)


def test_meal_item_rejects_non_positive_grams():
    with pytest.raises(ValueError):
        MealItem("moussaka", 0, True)


def test_only_confirmed_items_count():
    meal = MealEntry("m1", "P-001", datetime(2026, 10, 12, 13, 0), MealSource.CAMERA,
                     (MealItem("moussaka", 300, True), MealItem("bread", 50, False)))
    assert [i.food_id for i in meal.confirmed_items()] == ["moussaka"]


def test_context_enough_days():
    days = tuple(DailyIntake(date(2026, 10, d), {"iron": 8.0}, is_complete=(d != 3)) for d in range(1, 5))
    ctx = EvaluationContext(make_profile(), date(2026, 10, 5), days, ())
    assert len(ctx.complete_days()) == 3
    assert ctx.has_enough_days()


def test_profile_is_immutable():
    p = make_profile()
    with pytest.raises(Exception):
        p.age_years = 14


def test_decision_defaults():
    d = RuleDecision("R-FE-01", "0.1", "iron", IntakeStatus.INSUFFICIENT_DATA, 1, "EFSA Journal 13(10):4254")
    assert d.research_values == {} and d.food_group_hint == ()