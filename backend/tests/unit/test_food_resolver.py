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


# ---------- candidates(): υποψήφια για να διαλέξει το παιδί, και όταν η resolve() δίνει None ----------

def test_candidates_when_resolve_gives_none(resolver):
    from ai_pipeline.food_resolver import CANDIDATE_MIN_RATIO
    assert 0 < CANDIDATE_MIN_RATIO < FUZZY_MIN_RATIO
    assert resolver.resolve("σπανακόπιτα") is None                # χαμηλό σκορ για αυτόματη επιλογή ...
    assert resolver.candidates("σπανακόπιτα") == ["spinach"]      # ... αλλά κοινή αρχή λέξης: αρκεί για πρόταση
    assert resolver.resolve("κοτόπουλο") is None
    assert resolver.candidates("κοτόπουλο") == ["chicken"]        # αρχή λέξης (search)
    assert resolver.resolve("κοτόσουπα") is None
    assert resolver.candidates("κοτόσουπα") == ["chicken", "lentils"]   # κοινή αρχή πρώτα, μετά ομοιότητα (φακόσουπα)
    for text in ("πίτσα", "", "   ", "!!!", "σοκολάτα"):
        assert resolver.candidates(text) == []


def test_candidates_on_a_fuzzy_tie_gives_both():
    r = FoodResolver([("a", "μηλοα"), ("b", "μηλοβ")])
    assert r.resolve("μηλογ") is None and r.candidates("μηλογ") == ["a", "b"]


def test_candidates_order_limit_and_types(resolver):
    assert resolver.candidates("φακές")[0] == "lentils"           # ό,τι βρίσκει η search() προηγείται
    many = FoodResolver([(f"f{i}", f"μηλο{c}") for i, c in enumerate("αβγδεζηθ")])
    assert many.candidates("μηλοχ") == ["f0", "f1", "f2"]          # k=3, ισοβαθμία: σειρά του πίνακα
    assert many.candidates("μηλοχ", k=5) == ["f0", "f1", "f2", "f3", "f4"]
    assert many.candidates("μηλοχ", k=0) == [] and len(many.candidates("μηλοχ", k=1000)) == 8
    assert all(isinstance(c, str) for c in many.candidates("μηλοχ"))   # μόνο food_id, ποτέ σκορ


def test_candidates_does_not_change_resolve(resolver):
    before = [resolver.resolve(t) for t in ("Φακές", "φακόσουπα", "σπανακκι", "πίτσα")]
    resolver.candidates("σπανακκι")
    assert [resolver.resolve(t) for t in ("Φακές", "φακόσουπα", "σπανακκι", "πίτσα")] == before
