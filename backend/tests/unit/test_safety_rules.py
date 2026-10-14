import rule_engine.safety_rules as sr
from rule_engine.models import IntakeStatus, RuleDecision
from rule_engine.safety_rules import RiskLevel, SafetyAction, SafetySignals, apply_safety, evaluate_safety

FEEDBACK = [RuleDecision("R-FE-01", "0.1", "iron", IntakeStatus.LIKELY_INADEQUATE, 4, "x")]


def test_no_risk_no_action():
    s = evaluate_safety(SafetySignals())
    assert s.actions == frozenset() and apply_safety(FEEDBACK, s).to_child == FEEDBACK


def test_high_text_risk_alerts_and_suppresses():
    s = evaluate_safety(SafetySignals(RiskLevel.HIGH, "disordered_eating"))
    assert s.actions == {SafetyAction.ALERT_RESEARCHER, SafetyAction.SUPPRESS_INTAKE_FEEDBACK}
    out = apply_safety(FEEDBACK, s)
    assert out.to_child == [] and out.withheld == FEEDBACK
    assert s.category == "disordered_eating" and s.rule_ids == ("S-TXT-01",)


def test_moderate_text_risk_suppresses_without_alert():
    s = evaluate_safety(SafetySignals(RiskLevel.MODERATE))
    assert s.actions == {SafetyAction.SUPPRESS_INTAKE_FEEDBACK}


def test_low_intake_rule_disabled_by_default():
    assert sr.LOW_INTAKE_THRESHOLD is None
    assert evaluate_safety(SafetySignals(low_intake_days=30)).actions == frozenset()


def test_low_intake_rule_when_threshold_set(monkeypatch):
    monkeypatch.setattr(sr, "LOW_INTAKE_THRESHOLD", 5)
    s = evaluate_safety(SafetySignals(low_intake_days=5))
    assert "S-INT-01" in s.rule_ids and s.suppress
