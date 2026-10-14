from . import NutrientRule

RULES = (
    NutrientRule(
        rule_id="R-CA-01", version="0.1", nutrient_id="calcium",
        citation="EFSA NDA Panel 2015, EFSA Journal 13(5):4101; Summary of DRVs v4 (2017), Tables 4-7",
        food_group_hint=("dairy", "leafy_greens", "legumes", "nuts"),
    ),
)
