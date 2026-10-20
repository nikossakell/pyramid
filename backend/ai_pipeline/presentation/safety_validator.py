"""
ai_pipeline/presentation/safety_validator.py — Βήμα 4.2: έλεγχος κάθε κειμένου πριν φτάσει στο παιδί.

ΑΠΟΚΛΙΣΗ ΑΠΟ ΤΟ final_plan (τεκμηριωμένη):
Το πλάνο ελέγχει ότι οι αριθμοί intake/target ΕΜΦΑΝΙΖΟΝΤΑΙ στο κείμενο. Στη Φάση 2 αποφασίσαμε
ότι αριθμοί δεν φτάνουν στο παιδί (μένουν στα research_values· η EFSA: «DRVs are not nutrient
goals for individuals»). Άρα εδώ ο έλεγχος είναι ο αντίστροφος: ΚΑΝΕΝΑΣ αριθμός.

Ο validator είναι ντετερμινιστικός και ελέγχει ΚΑΘΕ κείμενο, και τα σταθερά (ώστε ένα λάθος στο
CSV να πιάνεται στα tests) και την έξοδο του Krikri (Κανόνας 4). Αν αποτύχει -> σταθερό κείμενο·
αν αποτύχει και αυτό -> κανένα μήνυμα.

Έλεγχοι (κωδικοί στο audit):
  V-SAFETY        ενεργός κίνδυνος (safety_rules): τίποτα για πρόσληψη στο παιδί
  V-STATUS        κατάσταση που δεν παρουσιάζεται (π.χ. insufficient_data)
  V-EMPTY         κενό κείμενο
  V-LEN           πάνω από MAX_CHARS χαρακτήρες ή MAX_SENTENCES προτάσεις
  V-LANG          όχι κυρίως ελληνικά
  V-LINK          σύνδεσμος ή email
  V-NUM           ψηφία (εκτός από το όνομα του θρεπτικού, π.χ. B12), ή σύμβολο %
  V-NUMW          αριθμητικό ολογράφως (δύο, δέκα, μισό...)
  V-UNIT          μονάδα μέτρησης (mg, γραμμάρια, λίτρα...)
  V-FORBID        όροι για βάρος, θερμίδες, δίαιτα, στέρηση ή ηθικοποίηση φαγητού
  V-DIAG          διαγνωστική ή ιατρική γλώσσα (έλλειψη, αναιμία, συμπλήρωμα...)
  V-DIR           λάθος κατεύθυνση (π.χ. «λιγότερο» σε κανόνα «περισσότερο»)
  V-NUTR-MISSING  δεν αναφέρεται το θρεπτικό της απόφασης
  V-NUTR-OTHER    αναφέρεται άλλο θρεπτικό
  V-NUTR-UNKNOWN  θρεπτικό χωρίς ελληνικό όνομα στο λεξικό (δεν μπορεί να ελεγχθεί)
  V-FOOD          ομάδα τροφίμων εκτός όσων έδωσε ο κανόνας

ΓΝΩΣΤΟΣ ΠΕΡΙΟΡΙΣΜΟΣ: ο έλεγχος V-FOOD πιάνει μόνο τρόφιμα που υπάρχουν στις λέξεις-κλειδιά του
food_groups.csv. Ένα τρόφιμο εκτός λεξικού (π.χ. «σοκολάτα») δεν ανιχνεύεται. Γι' αυτό το prompt
του Krikri (4.1) θα ζητά ρητά μόνο τα τρόφιμα της απόφασης, και τα 100+ test cases του 7.1
μετρούν πόσο συχνά συμβαίνει.
"""
import re
from dataclasses import dataclass
from typing import Optional

from rule_engine.models import IntakeStatus, RuleDecision
from rule_engine.safety_rules import SafetyDecision

from .lexicon import Lexicon, Term, default_lexicon, normalize, tokens

VALIDATOR_VERSION = "0.1"
MAX_CHARS = 300          # ΠΡΟΣΧΕΔΙΟ
MAX_SENTENCES = 3        # ΠΡΟΣΧΕΔΙΟ
MIN_GREEK_RATIO = 0.9    # ΠΡΟΣΧΕΔΙΟ: ποσοστό ελληνικών γραμμάτων

# Καταστάσεις που μπορούν να φτάσουν στο παιδί (ίδιες με recommendations.select_daily_feedback)
PRESENTABLE_STATUSES = frozenset({
    IntakeStatus.LIKELY_INADEQUATE, IntakeStatus.UNCERTAIN, IntakeStatus.NO_CONCLUSION,
    IntakeStatus.ABOVE_REFERENCE, IntakeStatus.LIKELY_ADEQUATE,
})
INCREASE_STATUSES = frozenset({IntakeStatus.LIKELY_INADEQUATE, IntakeStatus.UNCERTAIN, IntakeStatus.NO_CONCLUSION})

_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
_SENTENCE_END = re.compile(r"[.!;;?…]+")
_LINK = re.compile(r"https?://|www\.|@")


@dataclass(frozen=True)
class Failure:
    code: str
    detail: str


@dataclass(frozen=True)
class ValidationResult:
    failures: tuple[Failure, ...]
    validator_version: str = VALIDATOR_VERSION

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def codes(self) -> set[str]:
        return {f.code for f in self.failures}


def _hits(terms: tuple[Term, ...], norm: str, toks: list[str]) -> list[str]:
    out = []
    for t in terms:
        if t.match == "token" and t.term in toks:
            out.append(t.term)
        elif t.match == "stem" and any(tok.startswith(t.term) for tok in toks):
            out.append(t.term)
        elif t.match == "phrase" and re.search(r"(?<!\w)" + re.escape(t.term), norm):
            out.append(t.term)
    return out


def validate_child_text(text: str, decision: RuleDecision, lexicon: Optional[Lexicon] = None,
                        safety: Optional[SafetyDecision] = None) -> ValidationResult:
    lex = lexicon or default_lexicon()
    fails: list[Failure] = []

    def fail(code: str, detail: str) -> None:
        fails.append(Failure(code, detail))

    if safety is not None and safety.suppress:
        fail("V-SAFETY", f"safety rules {list(safety.rule_ids)} suppress intake feedback")
    if decision.status not in PRESENTABLE_STATUSES:
        fail("V-STATUS", f"status '{decision.status.value}' is never shown to the child")
    if not text or not text.strip():
        fail("V-EMPTY", "empty text")
        return ValidationResult(tuple(fails))

    if len(text) > MAX_CHARS:
        fail("V-LEN", f"{len(text)} chars > {MAX_CHARS}")
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        fail("V-LEN", f"{len(sentences)} sentences > {MAX_SENTENCES}")
    if _LINK.search(text):
        fail("V-LINK", "link or email address")

    norm = normalize(text)
    own = lex.nutrients.get(decision.nutrient_id)
    if own is None:
        fail("V-NUTR-UNKNOWN", f"no entry for '{decision.nutrient_id}' in nutrient_names_el.csv")
        rest = norm
    else:
        if not own.pattern.search(norm):
            fail("V-NUTR-MISSING", f"'{own.name_el}' not mentioned")
        rest = own.pattern.sub(" ", norm)   # το όνομα του θρεπτικού (π.χ. «βιταμίνη B12») εξαιρείται από V-NUM/V-LANG

    # Γλώσσα
    letters = [c for c in rest if c.isalpha()]
    if letters:
        ratio = sum(1 for c in letters if _GREEK.match(c)) / len(letters)
        if ratio < MIN_GREEK_RATIO:
            fail("V-LANG", f"greek letters {ratio:.0%} < {MIN_GREEK_RATIO:.0%}")

    # Αριθμοί
    digits = re.findall(r"\d+", rest)
    if digits:
        fail("V-NUM", f"digits {digits}")
    if "%" in rest or "‰" in rest:
        fail("V-NUM", "percent sign")
    toks = tokens(norm)
    rest_toks = tokens(rest)
    for category, code in (("number_word", "V-NUMW"), ("unit", "V-UNIT"),
                           ("forbidden", "V-FORBID"), ("diagnostic", "V-DIAG")):
        found = _hits(lex.terms_of(category), rest, rest_toks)
        if found:
            fail(code, f"{category}: {found}")

    # Κατεύθυνση
    if decision.status in INCREASE_STATUSES:
        wrong = _hits(lex.terms_of("reduce"), norm, toks)
    elif decision.status is IntakeStatus.ABOVE_REFERENCE:
        wrong = _hits(lex.terms_of("increase"), norm, toks)
    elif decision.status is IntakeStatus.LIKELY_ADEQUATE:
        wrong = _hits(lex.terms_of("reduce") + lex.terms_of("increase"), norm, toks)
    else:
        wrong = []
    if wrong:
        fail("V-DIR", f"direction words {wrong} for status '{decision.status.value}'")

    # Άλλα θρεπτικά
    others = [n.nutrient_id for nid, n in lex.nutrients.items()
              if nid != decision.nutrient_id and n.pattern.search(rest)]
    others += _hits(lex.terms_of("other_nutrient"), rest, rest_toks)
    if not decision.nutrient_id.startswith("vitamin_") and any(t.startswith("βιταμιν") for t in rest_toks):
        others.append("βιταμιν*")
    if others:
        fail("V-NUTR-OTHER", f"other nutrients {sorted(set(others))}")

    # Ομάδες τροφίμων
    allowed = {s for g in decision.food_group_hint if g in lex.food_groups for s in lex.food_groups[g].stems}
    all_stems = {s for g in lex.food_groups.values() for s in g.stems}
    outside = sorted({tok for tok in toks
                      if any(tok.startswith(s) for s in all_stems) and not any(tok.startswith(s) for s in allowed)})
    if outside:
        fail("V-FOOD", f"foods outside rule hint {outside}")

    return ValidationResult(tuple(fails))
