from ..models import IntakeStatus
from . import NutrientRule

# Το νάτριο είναι ο μόνος κανόνας «λιγότερο»: ενεργεί μόνο πάνω από την ασφαλή και επαρκή πρόσληψη.
RULES = (
    NutrientRule(
        rule_id="R-NA-01", version="0.1", nutrient_id="sodium",
        citation="EFSA NDA Panel 2019, EFSA Journal 17(9):5778",
        food_group_hint=("processed_meat", "salty_snacks", "ready_sauces"),
        act_on=frozenset({IntakeStatus.ABOVE_REFERENCE}),
    ),
)
