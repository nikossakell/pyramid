"""
rule_engine/recommendations.py — Layer 3a: από τα NutrientEvaluation στις αποφάσεις ανατροφοδότησης.

1. apply_recommendation_rules(): κάθε κανόνας του rules/ πάνω στην αξιολόγηση του θρεπτικού του
   -> μία RuleDecision ανά θρεπτικό (και για INSUFFICIENT_DATA, ώστε να φαίνεται στο audit).
2. select_daily_feedback(): ποιες από αυτές φτάνουν στο παιδί σήμερα.

Το κείμενο του μηνύματος δεν βγαίνει εδώ· βγαίνει το message_template_id, και τη διατύπωση
την κάνει το presentation layer (πρότυπο ή Krikri + έλεγχος εξόδου).
"""
from typing import Iterable, Mapping, Optional

from .models import IntakeStatus, NutrientEvaluation, RuleDecision
from .rules import NutrientRule, all_nutrient_rules

# ΠΡΟΣΧΕΔΙΟ: σειρά προτεραιότητας για την ημερήσια ανατροφοδότηση (μικρότερο = πρώτο).
PRIORITY = {
    IntakeStatus.LIKELY_INADEQUATE: 1,
    IntakeStatus.ABOVE_REFERENCE: 1,
    IntakeStatus.UNCERTAIN: 2,
    IntakeStatus.NO_CONCLUSION: 3,
    IntakeStatus.LIKELY_ADEQUATE: 4,
}
IMPROVEMENT_STATUSES = frozenset({
    IntakeStatus.LIKELY_INADEQUATE, IntakeStatus.ABOVE_REFERENCE,
    IntakeStatus.UNCERTAIN, IntakeStatus.NO_CONCLUSION,
})
MAX_DAILY_ITEMS = 2   # ΠΡΟΣΧΕΔΙΟ: λίγα μηνύματα την ημέρα, για να μη γίνεται η εφαρμογή «δίαιτα»


def apply_recommendation_rules(evaluations: Mapping[str, NutrientEvaluation],
                               rules: Optional[Iterable[NutrientRule]] = None) -> list[RuleDecision]:
    """Μία απόφαση για κάθε κανόνα που έχει αξιολόγηση. Θρεπτικά χωρίς κανόνα αγνοούνται·
    κανόνας χωρίς αξιολόγηση (π.χ. δεν υπάρχει τιμή αναφοράς) δεν βγάζει απόφαση."""
    rules = tuple(rules) if rules is not None else all_nutrient_rules()
    return [r.decide(evaluations[r.nutrient_id]) for r in rules if r.nutrient_id in evaluations]


def select_daily_feedback(decisions: Iterable[RuleDecision], max_items: int = MAX_DAILY_ITEMS) -> list[RuleDecision]:
    """Έως max_items αποφάσεις για το παιδί. Πρώτα όσες ζητούν βελτίωση, κατά προτεραιότητα·
    αν δεν υπάρχει καμία, μία θετική. Ποτέ INSUFFICIENT_DATA (δεν λέμε τίποτα χωρίς δεδομένα)."""
    decisions = list(decisions)
    improve = sorted((d for d in decisions if d.status in IMPROVEMENT_STATUSES),
                     key=lambda d: (PRIORITY[d.status], d.rule_id))
    if improve:
        return improve[:max_items]
    positive = sorted((d for d in decisions if d.status is IntakeStatus.LIKELY_ADEQUATE), key=lambda d: d.rule_id)
    return positive[:1]
