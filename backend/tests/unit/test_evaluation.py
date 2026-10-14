"""Tests του Layer 2 με ΣΥΝΘΕΤΙΚΑ τρόφιμα. Οι τιμές θρεπτικών είναι επινοημένες για να
βγαίνουν στρογγυλά νούμερα· δεν είναι δεδομένα σύνθεσης τροφίμων."""
from datetime import date, datetime
from pathlib import Path

import pytest

from rule_engine.assessment import assess
from rule_engine.data_loader import load_reference_values
from rule_engine.evaluation import daily_nutrient_totals, evaluate_intake
from rule_engine.models import (
    DailyIntake, EvaluationContext, FoodItem, IntakeStatus, MealEntry, MealItem,
    MealSource, Sex, UserProfile,
)

DRV_CSV = Path(__file__).resolve().parents[3] / "data" / "efsa_drv.csv"

FOODS = {
    "TEST_A": FoodItem("TEST_A", "δοκιμαστικό Α", "test", {"iron": 2.0, "calcium": 100.0, "energy": 0.5}),
    "TEST_B": FoodItem("TEST_B", "δοκιμαστικό Β", "test", {"iron": 1.0, "energy": 0.4}),   # χωρίς ασβέστιο
}


@pytest.fixture(scope="module")
def refs():
    return load_reference_values(DRV_CSV)


def meal(day, *items, confirmed=True):
    return MealEntry(f"m-{day}", "P-001", datetime(2026, 10, day, 13, 0), MealSource.MANUAL,
                     tuple(MealItem(f, g, confirmed) for f, g in items))


# ---------------------------------------------------------------- βήμα 1

def test_totals_scale_by_grams():
    d = daily_nutrient_totals([meal(1, ("TEST_A", 200))], FOODS, date(2026, 10, 1), True)
    assert d.totals["iron"] == pytest.approx(4.0)
    assert d.totals["calcium"] == pytest.approx(200.0)


def test_unconfirmed_items_ignored():
    d = daily_nutrient_totals([meal(1, ("TEST_A", 200), confirmed=False)], FOODS, date(2026, 10, 1), True)
    assert d.totals == {}


def test_other_days_ignored():
    d = daily_nutrient_totals([meal(2, ("TEST_A", 200))], FOODS, date(2026, 10, 1), True)
    assert d.totals == {}


def test_missing_value_is_unknown_not_zero():
    d = daily_nutrient_totals([meal(1, ("TEST_A", 100), ("TEST_B", 100))], FOODS, date(2026, 10, 1), True)
    assert d.totals["iron"] == pytest.approx(3.0)
    assert "calcium" not in d.totals and "calcium" in d.missing_nutrients


def test_unknown_food_raises():
    with pytest.raises(KeyError):
        daily_nutrient_totals([meal(1, ("NOPE", 100))], FOODS, date(2026, 10, 1), True)


# ---------------------------------------------------------------- βήμα 2

def ctx_with(refs, iron_per_day, n_days=3, complete=True, sex=Sex.FEMALE, age=13, extra=None):
    days = tuple(DailyIntake(date(2026, 10, d), {"iron": iron_per_day, "energy": 8.0, **(extra or {})}, complete)
                 for d in range(1, n_days + 1))
    profile = UserProfile("P-001", sex, age)
    return EvaluationContext(profile, date(2026, 10, n_days), days, tuple(refs)), assess(profile, refs)


@pytest.mark.parametrize("iron, expected", [
    (6.0, IntakeStatus.LIKELY_INADEQUATE),   # κορίτσι 13: AR 7
    (10.0, IntakeStatus.UNCERTAIN),          # ανάμεσα σε AR 7 και PRI 13
    (14.0, IntakeStatus.LIKELY_ADEQUATE),    # >= PRI 13
])
def test_iron_ar_pri_classification(refs, iron, expected):
    ctx, a = ctx_with(refs, iron)
    ev = evaluate_intake(ctx, a)["iron"]
    assert ev.status is expected
    assert ev.reference_values == {"AR": 7.0, "PRI": 13.0}


def test_too_few_days(refs):
    ctx, a = ctx_with(refs, 14.0, n_days=2)
    assert evaluate_intake(ctx, a)["iron"].status is IntakeStatus.INSUFFICIENT_DATA


def test_incomplete_days_not_counted(refs):
    ctx, a = ctx_with(refs, 14.0, complete=False)
    assert evaluate_intake(ctx, a)["iron"].status is IntakeStatus.INSUFFICIENT_DATA


def test_ai_below_is_no_conclusion(refs):
    ctx, a = ctx_with(refs, 10.0, extra={"fibre": 10.0})   # AI 19 g στα 13
    assert evaluate_intake(ctx, a)["fibre"].status is IntakeStatus.NO_CONCLUSION


def test_sodium_above_sai(refs):
    ctx, a = ctx_with(refs, 10.0, extra={"sodium": 2.5})   # SAI 2.0 g στα 11-17
    assert evaluate_intake(ctx, a)["sodium"].status is IntakeStatus.ABOVE_REFERENCE


def test_thiamin_scaled_by_energy(refs):
    ctx, a = ctx_with(refs, 10.0, extra={"thiamin": 0.9})  # PRI 0.1 mg/MJ × 8 MJ = 0.8 mg
    ev = evaluate_intake(ctx, a)["thiamin"]
    assert ev.reference_values["PRI"] == pytest.approx(0.8)
    assert ev.status is IntakeStatus.LIKELY_ADEQUATE and ev.unit == "mg/d"


def test_fat_share_of_energy(refs):
    # 80 g λίπος × 37 kJ = 2960 kJ από 8000 kJ = 37% > 35%
    ctx, a = ctx_with(refs, 10.0, extra={"fat_total": 80.0})
    ev = evaluate_intake(ctx, a)["fat_total"]
    assert ev.usual_intake == pytest.approx(37.0) and ev.status is IntakeStatus.ABOVE_RANGE


def test_nutrient_without_intake_data_is_insufficient(refs):
    ctx, a = ctx_with(refs, 10.0)   # καμία τιμή ασβεστίου στις ημέρες
    assert evaluate_intake(ctx, a)["calcium"].status is IntakeStatus.INSUFFICIENT_DATA


def test_protein_without_weight_reported(refs):
    ctx, a = ctx_with(refs, 10.0)
    ev = evaluate_intake(ctx, a)["protein"]
    assert ev.status is IntakeStatus.INSUFFICIENT_DATA and ev.reason == "weight_kg missing"


def test_end_to_end_from_meals(refs):
    meals = [meal(d, ("TEST_A", 400)) for d in (1, 2, 3)]          # 8 mg σίδηρος/ημέρα
    days = tuple(daily_nutrient_totals(meals, FOODS, date(2026, 10, d), True) for d in (1, 2, 3))
    profile = UserProfile("P-001", Sex.FEMALE, 13)
    ev = evaluate_intake(EvaluationContext(profile, date(2026, 10, 3), days, tuple(refs)), assess(profile, refs))
    assert ev["iron"].usual_intake == pytest.approx(8.0)
    assert ev["iron"].status is IntakeStatus.UNCERTAIN