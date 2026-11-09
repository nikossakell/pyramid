"""
ai_pipeline/rag/chunk_filter.py — φίλτρα ποιότητας κομματιών (Απόφαση 9).

Κάποια κομμάτια των γνωμοδοτήσεων EFSA δεν απαντούν ποτέ σε ερώτηση, αλλά μοιάζουν αρκετά με αυτήν ώστε
να βγαίνουν πρώτα: πίνακας περιεχομένων, σελίδες τίτλου/διοικητικά στοιχεία, το τυποποιημένο
«Background / Terms of reference» της Επιτροπής, πίνακες με αριθμούς. classify() επιστρέφει τον λόγο
απόρριψης ή None.

Αρχή: ΑΝ ΑΜΦΙΒΑΛΛΕΙ, ΚΡΑΤΑ. Οι ετικέτες ενότητας είναι ανά σελίδα (pdf_text) και συχνά λάθος: σελίδες
πίνακα περιεχομένων παίρνουν την ετικέτα «Summary» ή «Background», και το «ASSESSMENT 1. Introduction»
βρίσκεται κάτω από άλλη ετικέτα. Γι' αυτό η προστασία των Abstract / Summary / Introduction / Dietary
sources γίνεται από το ΚΕΙΜΕΝΟ (επικεφαλίδα μέσα στο κομμάτι), όχι από την ετικέτα:
  - front_matter και background ΔΕΝ εφαρμόζονται σε κομμάτι με τέτοια επικεφαλίδα·
  - toc και front_matter ΔΕΝ εφαρμόζονται σε κομμάτι με ≥ MIXED_PROSE_WORDS λέξεις κειμένου πριν από
    την πρώτη τελεία-οδηγό / τον πρώτο δείκτη (μικτό κομμάτι: π.χ. τέλος της Summary + αρχή του πίνακα
    περιεχομένων, ή τέλος του Abstract + KEY WORDS / Panel members)·
  - numeric_table εφαρμόζεται παντού (σαφώς πίνακας).

Τα κατώφλια είναι ΠΡΟΣΧΕΔΙΟ, βαθμονομημένα στα 1994 κομμάτια των 10 γνωμοδοτήσεων EFSA (09/11/2026).
Γράφονται στο index_manifest.json (params.chunk_filter) με το CHUNK_FILTER_VERSION, για το audit.
"""
import re
from typing import Optional

from .chunking import Chunk

CHUNK_FILTER_VERSION = "1"

MIN_LEADER_RUNS = 3          # ΠΡΟΣΧΕΔΙΟ: ακολουθίες τελειών-οδηγών για «πίνακας περιεχομένων»
MIN_FRONT_MATTER_MARKERS = 2  # ΠΡΟΣΧΕΔΙΟ: διαφορετικοί δείκτες σελίδας τίτλου / διοικητικών στοιχείων
MIXED_PROSE_WORDS = 40       # ΠΡΟΣΧΕΔΙΟ: λέξεις πριν τον 1ο δείκτη (toc/front_matter) => «μικτό», κρατιέται
BACKGROUND_HEAD_WORDS = 40   # ΠΡΟΣΧΕΔΙΟ: η επικεφαλίδα Background/ToR πρέπει να είναι στις πρώτες τόσες λέξεις
DIGIT_SHARE = 0.35           # ΠΡΟΣΧΕΔΙΟ: ποσοστό tokens με ψηφίο για «πίνακας με αριθμούς»
MIN_TOKENS_NUMERIC = 25      # ΠΡΟΣΧΕΔΙΟ: κάτω από τόσα tokens δεν κρίνεται ως πίνακας (π.χ. μία πρόταση με τιμές)

REASONS = ("toc", "front_matter", "background", "numeric_table")

_LEADERS = re.compile(r"\.{5,}|…{2,}|(?:\.\s){4,}\.")
_TOC_SECTION = re.compile(r"^\s*(table of contents|contents)\s*$", re.IGNORECASE)
_FRONT_MATTER = [re.compile(p, re.IGNORECASE) for p in (
    r"\bkey\s?words\b",
    r"\bquestion\s+(number|no\b)",
    r"\brequestor\b",
    r"\bpanel members\b",
    r"\bcorrespondence\s*:",
    r"©\s*(\d{4}\s*,?\s*)?european food safety authority",
    r"\bsuggested citation\b",
    r"\badopted on\b",
    r"\backnowledge?ments?\b",
    r"\bdeclarations? of interests?\b",
)]
_BACKGROUND = re.compile(r"\b(background as provided by|terms of reference)\b", re.IGNORECASE)
_BACKGROUND_SECTION = re.compile(r"^\s*(background as provided by|terms of reference)", re.IGNORECASE)
# Επικεφαλίδες ενοτήτων που δεν κόβονται (εκτός από toc / numeric_table). Κεφαλαία ή αριθμημένες,
# ώστε η λέξη «summary» μέσα σε πρόταση να μη μετρά.
_PROTECTED = re.compile(r"\bABSTRACT\b|\bSUMMARY\b|\bINTRODUCTION\b|\bASSESSMENT\b"
                        r"|\b\d+(\.\d+)*\.?\s+Introduction\b|\bDietary sources\b|^\s*(Abstract|Summary|Introduction)\b")


def params() -> dict:
    """Για το index_manifest.json (params.chunk_filter)."""
    return {"version": CHUNK_FILTER_VERSION, "min_leader_runs": MIN_LEADER_RUNS,
            "min_front_matter_markers": MIN_FRONT_MATTER_MARKERS, "mixed_prose_words": MIXED_PROSE_WORDS,
            "background_head_words": BACKGROUND_HEAD_WORDS, "digit_share": DIGIT_SHARE,
            "min_tokens_numeric": MIN_TOKENS_NUMERIC}


def _words_before(text: str, pos: int) -> int:
    return len(text[:pos].split())


def digit_share(text: str) -> float:
    toks = text.split()
    return sum(any(ch.isdigit() for ch in t) for t in toks) / len(toks) if toks else 0.0


def classify(chunk: Chunk) -> Optional[str]:
    """Λόγος απόρριψης ("toc", "front_matter", "background", "numeric_table") ή None (κρατιέται)."""
    text, section = chunk.text, chunk.section or ""

    # a) πίνακας περιεχομένων: τελείες-οδηγοί, ή ετικέτα «Table of contents» με τουλάχιστον μία
    leaders = [m.start() for m in _LEADERS.finditer(text)]
    if ((len(leaders) >= MIN_LEADER_RUNS or (_TOC_SECTION.match(section) and leaders))
            and _words_before(text, leaders[0]) < MIXED_PROSE_WORDS):
        return "toc"

    protected = bool(_PROTECTED.search(text))

    # b) σελίδες τίτλου / διοικητικά στοιχεία
    hits = [m.start() for p in _FRONT_MATTER for m in [p.search(text)] if m]
    if (len(hits) >= MIN_FRONT_MATTER_MARKERS and not protected
            and _words_before(text, min(hits)) < MIXED_PROSE_WORDS):
        return "front_matter"

    # c) τυποποιημένο Background / Terms of reference της Επιτροπής
    if not protected:
        m = _BACKGROUND.search(text)
        if (m and _words_before(text, m.start()) < BACKGROUND_HEAD_WORDS) or _BACKGROUND_SECTION.match(section):
            return "background"

    # d) πίνακας με αριθμούς
    if len(text.split()) >= MIN_TOKENS_NUMERIC and digit_share(text) > DIGIT_SHARE:
        return "numeric_table"
    return None


def filter_chunks(chunks: list[Chunk]) -> tuple[list[Chunk], dict[str, list[str]]]:
    """(κομμάτια που μένουν, {λόγος: [chunk_id, ...]}). Τα chunk_id ΔΕΝ ξαναριθμούνται."""
    kept, dropped = [], {}
    for c in chunks:
        reason = classify(c)
        if reason is None:
            kept.append(c)
        else:
            dropped.setdefault(reason, []).append(c.chunk_id)
    return kept, dropped
