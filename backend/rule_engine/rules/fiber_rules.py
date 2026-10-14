from . import NutrientRule

RULES = (
    NutrientRule(
        rule_id="R-FI-01", version="0.1", nutrient_id="fibre",
        citation="EFSA NDA Panel 2010, EFSA Journal 8(3):1462; Summary of DRVs v4 (2017), Table 3",
        food_group_hint=("vegetables", "fruit", "legumes", "whole_grains"),
    ),
)
