"""
rule_engine/safety_rules.py — Layer 3c: κανόνες ασφαλείας για διατροφικές διαταραχές.

Οι κλινικές αποφάσεις (τι θεωρείται κίνδυνος, ποια όρια) ανήκουν στον παιδίατρο. Ο κώδικας
εδώ υλοποιεί μόνο τον ΜΗΧΑΝΙΣΜΟ:
- σήματα που έρχονται από αλλού (π.χ. το φίλτρο κινδύνου κειμένου του ai_pipeline),
- ποια ενέργεια προκαλεί κάθε σήμα,
- την υπερίσχυση της ασφάλειας πάνω στις συστάσεις.

Κανόνες με αριθμητικό όριο (π.χ. πολύ χαμηλή καταγεγραμμένη πρόσληψη για πολλές ημέρες) είναι
ΑΠΕΝΕΡΓΟΙ μέχρι να οριστεί όριο και μέθοδος από τον παιδίατρο (LOW_INTAKE_THRESHOLD = None).
Η υποκαταγραφή είναι συχνή, άρα ένα αυθαίρετο όριο θα έβγαζε ψευδείς συναγερμούς.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

from .models import RuleDecision

SAFETY_RULES_VERSION = "0.1"
LOW_INTAKE_THRESHOLD: Optional[float] = None   # ορίζεται από τον παιδίατρο· None = κανόνας ανενεργός


class RiskLevel(str, Enum):
    NONE = "none"
    MODERATE = "moderate"
    HIGH = "high"


class SafetyAction(str, Enum):
    SUPPRESS_INTAKE_FEEDBACK = "suppress_intake_feedback"   # καμία ανατροφοδότηση πρόσληψης στο παιδί
    ALERT_RESEARCHER = "alert_researcher"                   # ειδοποίηση εφημερεύοντα: κωδικός + κατηγορία


@dataclass(frozen=True)
class SafetySignals:
    text_risk_level: RiskLevel = RiskLevel.NONE          # από το φίλτρο κινδύνου κειμένου
    text_risk_category: Optional[str] = None             # π.χ. "disordered_eating", "self_harm"
    low_intake_days: Optional[int] = None                # για τον ανενεργό κανόνα S-INT-01


@dataclass(frozen=True)
class SafetyDecision:
    rule_ids: tuple[str, ...]
    actions: frozenset[SafetyAction]
    category: Optional[str] = None
    rule_version: str = SAFETY_RULES_VERSION

    @property
    def suppress(self) -> bool:
        return SafetyAction.SUPPRESS_INTAKE_FEEDBACK in self.actions


def evaluate_safety(signals: SafetySignals) -> SafetyDecision:
    rule_ids: list[str] = []
    actions: set[SafetyAction] = set()
    if signals.text_risk_level is RiskLevel.HIGH:
        rule_ids.append("S-TXT-01")
        actions |= {SafetyAction.ALERT_RESEARCHER, SafetyAction.SUPPRESS_INTAKE_FEEDBACK}
    elif signals.text_risk_level is RiskLevel.MODERATE:
        rule_ids.append("S-TXT-02")
        actions.add(SafetyAction.SUPPRESS_INTAKE_FEEDBACK)   # αν θα ειδοποιείται και ερευνητής: απόφαση παιδίατρου
    if LOW_INTAKE_THRESHOLD is not None and signals.low_intake_days is not None \
            and signals.low_intake_days >= LOW_INTAKE_THRESHOLD:
        rule_ids.append("S-INT-01")
        actions |= {SafetyAction.ALERT_RESEARCHER, SafetyAction.SUPPRESS_INTAKE_FEEDBACK}
    return SafetyDecision(tuple(rule_ids), frozenset(actions), signals.text_risk_category)


@dataclass(frozen=True)
class FilteredFeedback:
    to_child: list[RuleDecision]
    withheld: list[RuleDecision] = field(default_factory=list)   # για το audit


def apply_safety(feedback: Iterable[RuleDecision], safety: SafetyDecision) -> FilteredFeedback:
    """Η ασφάλεια υπερισχύει: με ενεργό κίνδυνο δεν φτάνει στο παιδί καμία ανατροφοδότηση
    πρόσληψης («περισσότερο» ή «λιγότερο»). Οι αποφάσεις κρατιούνται ως withheld για το audit."""
    feedback = list(feedback)
    if not safety.suppress:
        return FilteredFeedback(to_child=feedback)
    return FilteredFeedback(to_child=[], withheld=feedback)
