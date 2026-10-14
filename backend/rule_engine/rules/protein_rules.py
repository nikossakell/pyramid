from . import NutrientRule

RULES = (
    NutrientRule(
        rule_id="R-PR-01", version="0.1", nutrient_id="protein",
        citation="EFSA NDA Panel 2012, EFSA Journal 10(2):2557; Summary of DRVs v4 (2017), Table 2",
        food_group_hint=("legumes", "eggs", "dairy", "fish", "meat", "nuts"),
    ),
)
