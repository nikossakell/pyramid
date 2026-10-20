"""Βήμα 4.2: safety validator και σταθερά κείμενα.

1. Κάθε σταθερό κείμενο, για κάθε κανόνα και κάθε κατάσταση που φτάνει στο παιδί, περνά τον validator.
2. Τα σενάρια του tests/llm_eval/test_cases.jsonl (επινοημένες «κακές» εξόδους LLM) απορρίπτονται
   με τον αναμενόμενο κωδικό· τα «καλά» περνούν.
3. Η ασφάλεια υπερισχύει, οι αριθμοί των research_values δεν φτάνουν ποτέ στο κείμενο.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from ai_pipeline.presentation.lexicon import default_lexicon, load_lexicon, normalize
from ai_pipeline.presentation.safety_validator import validate_child_text
from ai_pipeline.presentation.templates import TemplateError, render_fallback
from rule_engine.data_loader import load_reference_values
from rule_engine.engine import NutritionRuleEngine
from rule_engine.models import DailyIntake, EvaluationContext, IntakeStatus, NutrientEvaluation, RuleDecision, Sex, UserProfile
from rule_engine.rules import all_nutrient_rules
from rule_engine.safety_rules import RiskLevel, SafetySignals, evaluate_safety

S = IntakeStatus
ROOT = Path(__file__).resolve().parents[3]
CASES = [json.loads(l) for l in (ROOT / "backend/tests/llm_eval/test_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def _statuses(rule):
    if rule.nutrient_id == "sodium":
        return [S.ABOVE_REFERENCE, S.LIKELY_ADEQUATE]
    return [S.LIKELY_INADEQUATE, S.UNCERTAIN, S.NO_CONCLUSION, S.LIKELY_ADEQUATE]


TEMPLATE_CASES = [(r, s) for r in all_nutrient_rules() for s in _statuses(r)]


def _decision(rule, status):
    ev = NutrientEvaluation(rule.nutrient_id, status, 4, 5.3, "mg/d", {"AR": 7.0, "PRI": 11.0})
    return rule.decide(ev)


# ---------- σταθερά κείμενα ----------

@pytest.mark.parametrize("rule, status", TEMPLATE_CASES, ids=lambda x: getattr(x, "rule_id", getattr(x, "value", x)))
def test_every_template_passes_validator(rule, status):
    d = _decision(rule, status)
    tid, text = render_fallback(d)
    result = validate_child_text(text, d)
    assert result.passed, (tid, text, result.failures)


def test_research_numbers_never_in_template():
    d = _decision(all_nutrient_rules()[0], S.LIKELY_INADEQUATE)
    _, text = render_fallback(d)
    assert not any(ch.isdigit() for ch in text)


def test_specific_template_wins_over_generic():
    sodium = next(r for r in all_nutrient_rules() if r.nutrient_id == "sodium")
    tid, text = render_fallback(_decision(sodium, S.LIKELY_ADEQUATE))
    assert tid == "MSG-NA-likely_adequate" and "τροφές με αλάτι" not in text


def test_no_template_for_insufficient_data():
    d = _decision(all_nutrient_rules()[0], S.INSUFFICIENT_DATA)
    with pytest.raises(TemplateError):
        render_fallback(d)


def test_increase_template_without_food_groups_raises():
    d = RuleDecision("R-FE-01", "0.1", "iron", S.LIKELY_INADEQUATE, 4, "x",
                     food_group_hint=(), message_template_id="MSG-FE-likely_inadequate")
    with pytest.raises(TemplateError):
        render_fallback(d)


def test_engine_feedback_always_renders_and_passes():
    """Από άκρη σε άκρη: ό,τι επιλέγει το engine για το παιδί βγάζει έγκυρο ελληνικό κείμενο."""
    refs = load_reference_values(ROOT / "data/efsa_drv.csv")
    low = {"iron": 3, "calcium": 300, "fibre": 6, "sodium": 1.0, "protein": 15,
           "vitamin_a": 150, "vitamin_c": 20, "folate": 80, "vitamin_d": 2, "vitamin_b12": 1.0}
    high = {"iron": 20, "calcium": 1500, "fibre": 30, "sodium": 3.5, "protein": 120,
            "vitamin_a": 1000, "vitamin_c": 150, "folate": 450, "vitamin_d": 20, "vitamin_b12": 6.0}
    engine = NutritionRuleEngine()
    start = date(2026, 10, 1)
    for totals in (low, high):
        for sex in Sex:
            for age in range(10, 17):
                days = tuple(DailyIntake(start + timedelta(days=i), dict(totals), True) for i in range(4))
                ctx = EvaluationContext(UserProfile("P-T", sex, age, weight_kg=45.0), start + timedelta(days=3), days, tuple(refs))
                for d in engine.evaluate(ctx).feedback:
                    _, text = render_fallback(d)
                    assert validate_child_text(text, d).passed, text


# ---------- σενάρια LLM ----------

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_llm_eval_cases(case):
    d = RuleDecision("R-TEST", "0", case["nutrient_id"], IntakeStatus(case["status"]), 4, "x",
                     food_group_hint=tuple(case["hint"]))
    r = validate_child_text(case["text"], d)
    if case["expect"] == "pass":
        assert r.passed, r.failures
    else:
        assert not r.passed
        assert set(case["codes"]) <= r.codes, (r.codes, r.failures)


# ---------- ασφάλεια και λεξικό ----------

def test_safety_suppression_blocks_even_valid_text():
    d = _decision(all_nutrient_rules()[0], S.LIKELY_INADEQUATE)
    _, text = render_fallback(d)
    safety = evaluate_safety(SafetySignals(RiskLevel.MODERATE, "disordered_eating"))
    assert "V-SAFETY" in validate_child_text(text, d, safety=safety).codes


def test_unknown_nutrient_cannot_be_validated():
    d = RuleDecision("R-X", "0", "magnesium", S.LIKELY_INADEQUATE, 4, "x")
    assert "V-NUTR-UNKNOWN" in validate_child_text("Μια ιδέα για μαγνήσιο.", d).codes


def test_normalize():
    assert normalize("ΚΌΨΕ τελείως, Πρωτεΐνης") == "κοψε τελειωσ, πρωτεινησ"
    assert normalize("5 µg") == "5 μg"   # σύμβολο micro -> ελληνικό μ


def test_lexicon_versions_for_audit():
    v = default_lexicon().versions
    assert set(v) == {"message_templates_el.csv", "food_groups.csv", "nutrient_names_el.csv", "validator_lexicon_el.csv"}
    assert all(len(h) == 64 for h in v.values())


def test_every_rule_food_group_has_greek_name():
    groups = default_lexicon().food_groups
    missing = {g for r in all_nutrient_rules() for g in r.food_group_hint if g not in groups}
    assert not missing


def test_bad_lexicon_file_rejected(tmp_path):
    for name in ("message_templates_el.csv", "food_groups.csv", "nutrient_names_el.csv"):
        (tmp_path / name).write_text((ROOT / "data" / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "validator_lexicon_el.csv").write_text("category,term,match\nforbidden,θερμιδ,regex\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_lexicon(tmp_path)
