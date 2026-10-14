"""Βήμα 2.5: συνθετικά προφίλ που περνούν από όλη την αλυσίδα του engine.
Οι ημερήσιες τιμές είναι επινοημένες ώστε να πέφτουν σαφώς πάνω ή κάτω από τις τιμές της EFSA·
δεν είναι πραγματικά δεδομένα πρόσληψης."""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from rule_engine.data_loader import load_reference_values
from rule_engine.engine import NutritionRuleEngine
from rule_engine.models import DailyIntake, EvaluationContext, IntakeStatus, Sex, UserProfile
from rule_engine.rules import all_nutrient_rules
from rule_engine.safety_rules import RiskLevel, SafetySignals

DRV_CSV = Path(__file__).resolve().parents[3] / "data" / "efsa_drv.csv"
S = IntakeStatus

# Πολύ χαμηλές / πολύ υψηλές τιμές για 10-16 ετών (κάτω από κάθε AR/AI, πάνω από κάθε PRI/AI)
LOW = {"iron": 3, "calcium": 300, "fibre": 6, "sodium": 1.0, "protein": 15,
       "vitamin_a": 150, "vitamin_c": 20, "folate": 80, "vitamin_d": 2, "vitamin_b12": 1.0}
HIGH = {"iron": 20, "calcium": 1500, "fibre": 30, "sodium": 3.5, "protein": 120,
        "vitamin_a": 1000, "vitamin_c": 150, "folate": 450, "vitamin_d": 20, "vitamin_b12": 6.0}


@pytest.fixture(scope="module")
def refs():
    return load_reference_values(DRV_CSV)


@pytest.fixture(scope="module")
def engine():
    return NutritionRuleEngine()


def ctx(refs, totals, sex=Sex.FEMALE, age=13, weight=45.0, n_days=4, complete=True):
    profile = UserProfile("P-TEST", sex, age, weight_kg=weight)
    start = date(2026, 10, 1)
    days = tuple(DailyIntake(start + timedelta(days=i), dict(totals), complete) for i in range(n_days))
    return EvaluationContext(profile, start + timedelta(days=n_days - 1), days, tuple(refs))


# 14 συνθετικά προφίλ × 2 σενάρια = 28 περιπτώσεις μέσα από όλη την αλυσίδα
PROFILES = [(sex, age) for sex in (Sex.MALE, Sex.FEMALE) for age in range(10, 17)]


@pytest.mark.parametrize("sex, age", PROFILES)
def test_low_intake_profile(refs, engine, sex, age):
    r = engine.evaluate(ctx(refs, LOW, sex, age))
    st = {d.nutrient_id: d.status for d in r.decisions}
    assert st["iron"] is S.LIKELY_INADEQUATE and st["calcium"] is S.LIKELY_INADEQUATE
    assert st["fibre"] is S.NO_CONCLUSION and st["vitamin_d"] is S.NO_CONCLUSION
    assert st["sodium"] is S.LIKELY_ADEQUATE
    assert 1 <= len(r.feedback) <= 2
    assert all(d.status is S.LIKELY_INADEQUATE for d in r.feedback)


@pytest.mark.parametrize("sex, age", PROFILES)
def test_high_intake_profile(refs, engine, sex, age):
    r = engine.evaluate(ctx(refs, HIGH, sex, age))
    st = {d.nutrient_id: d.status for d in r.decisions}
    assert st["sodium"] is S.ABOVE_REFERENCE
    assert all(v is S.LIKELY_ADEQUATE for k, v in st.items() if k != "sodium")
    assert [d.rule_id for d in r.feedback] == ["R-NA-01"]


def test_every_rule_fires_at_least_once(refs, engine):
    """Κάλυψη κάθε κανόνα: κάθε ένας βγάζει απόφαση με ομάδες τροφίμων σε κάποιο σενάριο."""
    fired = set()
    for totals in (LOW, HIGH):
        for d in engine.evaluate(ctx(refs, totals)).decisions:
            if d.food_group_hint:
                fired.add(d.rule_id)
    assert fired == {r.rule_id for r in all_nutrient_rules()}


def test_too_few_days_nothing_to_child(refs, engine):
    r = engine.evaluate(ctx(refs, LOW, n_days=2))
    assert all(d.status is S.INSUFFICIENT_DATA for d in r.decisions)
    assert r.feedback == []


def test_incomplete_days_nothing_to_child(refs, engine):
    assert engine.evaluate(ctx(refs, LOW, complete=False)).feedback == []


def test_no_weight_protein_insufficient(refs, engine):
    r = engine.evaluate(ctx(refs, LOW, weight=None))
    assert next(d for d in r.decisions if d.nutrient_id == "protein").status is S.INSUFFICIENT_DATA
    assert r.audit_record()["unavailable"] == {"protein": "weight_kg missing"}


def test_high_risk_overrides_feedback(refs, engine):
    r = engine.evaluate(ctx(refs, LOW), SafetySignals(RiskLevel.HIGH, "disordered_eating"))
    assert r.feedback == [] and len(r.withheld) >= 1
    assert "alert_researcher" in r.audit_record()["safety"]["actions"]


def test_deterministic(refs, engine):
    a = engine.evaluate(ctx(refs, LOW)).audit_record()
    b = engine.evaluate(ctx(refs, LOW)).audit_record()
    assert a == b


def test_audit_record_is_json_and_has_versions(refs):
    eng = NutritionRuleEngine(data_versions={"efsa_drv.csv": "test-hash"})
    rec = eng.evaluate(ctx(refs, LOW)).audit_record()
    json.dumps(rec)   # πρέπει να αποθηκεύεται ως JSON
    assert rec["engine_version"] == "0.1" and rec["data_versions"] == {"efsa_drv.csv": "test-hash"}
    assert all("rule_version" in d and "citation" in d for d in rec["decisions"])
    assert "name" not in json.dumps(rec).lower()


def test_max_daily_items_configurable(refs):
    r = NutritionRuleEngine(max_daily_items=1).evaluate(ctx(refs, LOW))
    assert len(r.feedback) == 1