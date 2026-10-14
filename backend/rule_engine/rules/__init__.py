"""
rule_engine/rules/ — ένας κανόνας ανά θρεπτικό, όπως ορίζει η «Προδιαγραφή κανόνων EFSA v0.1».

Κάθε κανόνας είναι δεδομένα (κωδικός, έκδοση, πηγή, ομάδες τροφίμων), όχι κώδικας·
η κοινή λογική είναι στο NutrientRule.decide(). Έτσι η αλλαγή μιας πηγής ή μιας ομάδας
τροφίμων δεν αγγίζει τη λογική, και κάθε απόφαση γράφει στο audit ποια έκδοση κανόνα την έβγαλε.
"""
from dataclasses import dataclass

from ..models import IntakeStatus, NutrientEvaluation, RuleDecision

# Καταστάσεις για τις οποίες ο κανόνας προτείνει ομάδες τροφίμων «περισσότερο».
INCREASE_STATUSES = frozenset({
    IntakeStatus.LIKELY_INADEQUATE, IntakeStatus.UNCERTAIN, IntakeStatus.NO_CONCLUSION,
})


@dataclass(frozen=True)
class NutrientRule:
    rule_id: str                     # π.χ. "R-FE-01"
    version: str
    nutrient_id: str                 # όπως στο efsa_drv.csv
    citation: str
    food_group_hint: tuple[str, ...]  # ΠΡΟΣΧΕΔΙΟ: έγκριση διαιτολόγου, κωδικοί από food_groups.csv
    act_on: frozenset[IntakeStatus] = INCREASE_STATUSES

    @property
    def code(self) -> str:
        return self.rule_id.split("-")[1]          # "R-FE-01" -> "FE"

    def decide(self, ev: NutrientEvaluation) -> RuleDecision:
        if ev.nutrient_id != self.nutrient_id:
            raise ValueError(f"{self.rule_id} expects {self.nutrient_id}, got {ev.nutrient_id}")
        research = dict(ev.reference_values)
        if ev.usual_intake is not None:
            research["usual_intake"] = ev.usual_intake
        return RuleDecision(
            rule_id=self.rule_id,
            rule_version=self.version,
            nutrient_id=self.nutrient_id,
            status=ev.status,
            days_used=ev.days_used,
            citation=self.citation,
            research_values=research,
            food_group_hint=self.food_group_hint if ev.status in self.act_on else (),
            message_template_id=f"MSG-{self.code}-{ev.status.value}",
        )


def all_nutrient_rules() -> tuple[NutrientRule, ...]:
    from . import calcium_rules, fiber_rules, iron_rules, protein_rules, sodium_rules, vitamin_rules
    rules = (*iron_rules.RULES, *calcium_rules.RULES, *sodium_rules.RULES,
             *fiber_rules.RULES, *protein_rules.RULES, *vitamin_rules.RULES)
    ids = [r.rule_id for r in rules]
    nutrients = [r.nutrient_id for r in rules]
    if len(set(ids)) != len(ids) or len(set(nutrients)) != len(nutrients):
        raise ValueError("duplicate rule_id or nutrient_id in rules/")
    return rules
