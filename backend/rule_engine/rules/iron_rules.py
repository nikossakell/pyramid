from . import NutrientRule

RULES = (
    NutrientRule(
        rule_id="R-FE-01", version="0.1", nutrient_id="iron",
        citation="EFSA NDA Panel 2015, EFSA Journal 13(10):4254; Summary of DRVs v4 (2017), Tables 4-7",
        food_group_hint=("legumes", "meat", "fish", "leafy_greens", "vitamin_c_foods"),
    ),
)
