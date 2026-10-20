"""
ai_pipeline/presentation/templates.py — τα σταθερά ελληνικά κείμενα (fallback του Κανόνα 4).

Κάθε RuleDecision έχει message_template_id = "MSG-{code}-{status}" (rules/__init__.py).
Αναζήτηση: πρώτα το ακριβές id (π.χ. MSG-NA-above_reference), μετά το γενικό της κατάστασης
(MSG-*-likely_inadequate). Το κείμενο παίρνει μόνο το όνομα του θρεπτικού και τα ονόματα των
ομάδων τροφίμων της απόφασης· ΠΟΤΕ αριθμούς από τα research_values.

Τα κείμενα αυτά είναι ό,τι βλέπει το παιδί όταν δεν υπάρχει Krikri ή όταν η έξοδός του
απορριφθεί από τον validator. Άρα η εφαρμογή λειτουργεί πλήρως και χωρίς LLM.
"""
from typing import Optional

from rule_engine.models import RuleDecision

from .lexicon import Lexicon, default_lexicon

MAX_FOOD_GROUPS_IN_MESSAGE = 3   # ΠΡΟΣΧΕΔΙΟ: σύντομα μηνύματα· οι πρώτες ομάδες του κανόνα


class TemplateError(ValueError):
    """Δεν υπάρχει κατάλληλο κείμενο για την απόφαση· το μήνυμα δεν εμφανίζεται (ασφαλής πλευρά)."""


def _join_el(names: list[str], conj: str) -> str:
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} {conj} {names[-1]}"


def find_template(decision: RuleDecision, lexicon: Lexicon) -> tuple[str, str]:
    """(template_id που χρησιμοποιήθηκε, κείμενο με placeholders)."""
    exact = decision.message_template_id
    generic = f"MSG-*-{decision.status.value}"
    for tid in (exact, generic):
        if tid and tid in lexicon.templates:
            return tid, lexicon.templates[tid]
    raise TemplateError(f"no template for {exact} / {generic}")


def render_fallback(decision: RuleDecision, lexicon: Optional[Lexicon] = None) -> tuple[str, str]:
    """Επιστρέφει (template_id, κείμενο για το παιδί). TemplateError αν δεν μπορεί να βγει κείμενο."""
    lex = lexicon or default_lexicon()
    tid, text = find_template(decision, lex)
    nutrient = lex.nutrients.get(decision.nutrient_id)
    if nutrient is None:
        raise TemplateError(f"no Greek name for nutrient '{decision.nutrient_id}'")

    needs_foods = "{foods_or}" in text or "{foods_and}" in text
    groups = decision.food_group_hint[:MAX_FOOD_GROUPS_IN_MESSAGE]
    if needs_foods and not groups:
        raise TemplateError(f"{tid} needs food groups but {decision.rule_id} gave none")
    unknown = [g for g in groups if g not in lex.food_groups]
    if unknown:
        raise TemplateError(f"unknown food groups {unknown} in {decision.rule_id}")
    names = [lex.food_groups[g].name_el for g in groups]

    return tid, text.format(
        nutrient=nutrient.name_el,
        foods_or=_join_el(names, "ή") if names else "",
        foods_and=_join_el(names, "και") if names else "",
    )
