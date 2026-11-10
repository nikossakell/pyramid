"""Food resolver (Βήμα 3.3): ακριβές όνομα, alias, fuzzy, None· κανονικοποίηση· αναζήτηση· συγκρούσεις δεδομένων."""
import pytest

from ai_pipeline.food_resolver import FUZZY_MIN_RATIO, FoodResolver, key

NAMES = [("lentils", "Φακές"), ("spinach", "Σπανάκι"), ("chicken", "Κοτόπουλο ψητό"), ("yogurt", "Γιαούρτι στραγγιστό"),
         ("spaghetti", "Σπαγγέτι με κιμά")]
ALIASES = [("lentils", "φακόσουπα"), ("yogurt", "γιαούρτι"), ("spaghetti", "μακαρόνια με κιμά")]


@pytest.fixture
def resolver():
    return FoodResolver(NAMES, ALIASES)


def test_normalisation():
    assert key("  ΦΑΚΈΣ!! ") == key("φακες") == "φακεσ"
    assert key("Κοτόπουλο-ψητό") == "κοτοπουλο ψητο"


@pytest.mark.parametrize("text, food_id, method", [
    ("Φακές", "lentils", "exact"), ("φακες", "lentils", "exact"), ("ΚΟΤΟΠΟΥΛΟ ΨΗΤΟ", "chicken", "exact"),
    ("φακόσουπα", "lentils", "alias"), ("μακαρόνια με κιμά", "spaghetti", "alias"), ("Γιαούρτι", "yogurt", "alias"),
    ("σπανακκι", "spinach", "fuzzy"), ("κοτοπουλο ψιτο", "chicken", "fuzzy"),
])
def test_resolve(resolver, text, food_id, method):
    r = resolver.resolve(text)
    assert r is not None and (r.food_id, r.method) == (food_id, method)
    assert r.score == 1.0 if method != "fuzzy" else FUZZY_MIN_RATIO <= r.score < 1.0


@pytest.mark.parametrize("text", ["πίτσα", "", "   ", "!!!", "φα", "σοκολάτα"])
def test_unresolvable_gives_none(resolver, text):
    assert resolver.resolve(text) is None


def test_fuzzy_tie_between_two_foods_gives_none():
    r = FoodResolver([("a", "μηλοα"), ("b", "μηλοβ")])
    assert r.resolve("μηλογ") is None            # ίδιο σκορ για δύο τρόφιμα: δεν μαντεύει


def test_conflicting_data_rejected():
    with pytest.raises(ValueError, match="maps to both"):
        FoodResolver([("a", "Φακές"), ("b", "ΦΑΚΕΣ")])
    with pytest.raises(ValueError, match="maps to both"):
        FoodResolver([("a", "Φακές"), ("b", "Ρεβίθια")], [("b", "φακες")])
    with pytest.raises(ValueError, match="unknown food_id"):
        FoodResolver([("a", "Φακές")], [("zzz", "κάτι")])


def test_search(resolver):
    assert resolver.search("φα") == ["lentils"]
    assert resolver.search("κιμ") == ["spaghetti"]                  # αρχή λέξης μέσα στο όνομα
    assert resolver.search("γιαουρτι")[0] == "yogurt"
    assert resolver.search("σπανακκι") == ["spinach"]               # fuzzy
    assert resolver.search("") == [] and resolver.search("x") == []
    assert len(resolver.search("σ", limit=2)) == 2 and resolver.search("σ", limit=0) == []
