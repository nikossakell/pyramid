"""
rule_engine/engine.py — ο ενορχηστρωτής: τρέχει όλη την αλυσίδα με είσοδο ένα EvaluationContext.

    Layer 1  assessment.assess()                      τιμές αναφοράς του παιδιού
    Layer 2  evaluation.evaluate_intake()             συνήθης πρόσληψη έναντι τιμών
    Layer 3a recommendations.apply_recommendation_rules() + select_daily_feedback()
    Layer 3c safety_rules.evaluate_safety() + apply_safety()   η ασφάλεια υπερισχύει

Οι κάρτες (Layer 3b) ΔΕΝ τρέχουν εδώ: εξαρτώνται από τη δραστηριότητα της ημέρας, όχι από την
αξιολόγηση θρεπτικών, και τρέχουν μία φορά τη νύχτα (app/jobs/daily_card_drops.py).

Το engine είναι ντετερμινιστικό: ίδια είσοδος -> ίδια έξοδος. Δεν γράφει σε βάση· επιστρέφει
EngineResult και ένα audit_record() που το service layer αποθηκεύει (Κανόνας 5 του πλάνου).
"""
from dataclasses import dataclass, field
from typing import Optional

from .assessment import Assessment, assess
from .evaluation import evaluate_intake
from .models import EvaluationContext, NutrientEvaluation, RuleDecision
from .recommendations import MAX_DAILY_ITEMS, apply_recommendation_rules, select_daily_feedback
from .rules import NutrientRule, all_nutrient_rules
from .safety_rules import SafetyDecision, SafetySignals, apply_safety, evaluate_safety

ENGINE_VERSION = "0.1"


@dataclass(frozen=True)
class EngineResult:
    pseudonym_id: str
    as_of: str
    assessment: Assessment
    evaluations: dict[str, NutrientEvaluation]
    decisions: list[RuleDecision]            # όλες, για το audit και την έρευνα
    feedback: list[RuleDecision]             # όσα φτάνουν στο παιδί (μετά την ασφάλεια)
    withheld: list[RuleDecision]             # όσα κρατήθηκαν λόγω ασφάλειας
    safety: SafetyDecision
    engine_version: str = ENGINE_VERSION
    data_versions: dict[str, str] = field(default_factory=dict)

    def audit_record(self) -> dict:
        """Ό,τι χρειάζεται για να αναπαραχθεί η απόφαση. Χωρίς ονόματα, χωρίς εικόνες."""
        return {
            "pseudonym_id": self.pseudonym_id,
            "as_of": self.as_of,
            "engine_version": self.engine_version,
            "data_versions": dict(self.data_versions),
            "safety": {"rule_ids": list(self.safety.rule_ids),
                       "actions": sorted(a.value for a in self.safety.actions),
                       "category": self.safety.category,
                       "rule_version": self.safety.rule_version},
            "decisions": [{"rule_id": d.rule_id, "rule_version": d.rule_version, "status": d.status.value,
                           "days_used": d.days_used, "research_values": d.research_values,
                           "citation": d.citation} for d in self.decisions],
            "feedback": [d.message_template_id for d in self.feedback],
            "withheld": [d.message_template_id for d in self.withheld],
            "unavailable": dict(self.assessment.unavailable),
        }


class NutritionRuleEngine:
    def __init__(self, rules: Optional[tuple[NutrientRule, ...]] = None,
                 max_daily_items: int = MAX_DAILY_ITEMS, data_versions: Optional[dict[str, str]] = None):
        self.rules = rules if rules is not None else all_nutrient_rules()
        self.max_daily_items = max_daily_items
        self.data_versions = data_versions or {}   # π.χ. {"efsa_drv.csv": "<sha256>"}

    def evaluate(self, ctx: EvaluationContext, signals: Optional[SafetySignals] = None) -> EngineResult:
        assessment = assess(ctx.profile, ctx.references)
        evaluations = evaluate_intake(ctx, assessment)
        decisions = apply_recommendation_rules(evaluations, self.rules)
        safety = evaluate_safety(signals or SafetySignals())
        filtered = apply_safety(select_daily_feedback(decisions, self.max_daily_items), safety)
        return EngineResult(
            pseudonym_id=ctx.profile.pseudonym_id, as_of=ctx.as_of.isoformat(),
            assessment=assessment, evaluations=evaluations, decisions=decisions,
            feedback=filtered.to_child, withheld=filtered.withheld, safety=safety,
            data_versions=dict(self.data_versions),
        )