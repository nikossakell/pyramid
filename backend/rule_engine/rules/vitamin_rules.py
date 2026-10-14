from . import NutrientRule

_V4 = "Summary of DRVs v4 (2017), Tables 8-11"
RULES = (
    NutrientRule("R-VA-01", "0.1", "vitamin_a", f"EFSA NDA Panel 2015, EFSA Journal 13(3):4028; {_V4}",
                 ("orange_vegetables", "leafy_greens", "dairy", "eggs")),
    NutrientRule("R-VC-01", "0.1", "vitamin_c", f"EFSA NDA Panel 2013, EFSA Journal 11(11):3418; {_V4}",
                 ("citrus", "peppers", "kiwi", "tomato")),
    NutrientRule("R-FO-01", "0.1", "folate", f"EFSA NDA Panel 2014, EFSA Journal 12(11):3893; {_V4}",
                 ("leafy_greens", "legumes")),
    # Βιταμίνη D: AI 15 μg προϋποθέτει ελάχιστη σύνθεση στο δέρμα· κάτω από το AI μόνο NO_CONCLUSION.
    NutrientRule("R-VD-01", "0.1", "vitamin_d", f"EFSA NDA Panel 2016, EFSA Journal 14(10):4547; {_V4}",
                 ("oily_fish", "eggs")),
    NutrientRule("R-B12-01", "0.1", "vitamin_b12", f"EFSA NDA Panel 2015, EFSA Journal 13(7):4150; {_V4}",
                 ("meat", "fish", "dairy", "eggs")),
)
