"""
ai_pipeline/rag/pdf_text.py — κείμενο ανά σελίδα από PDF, καθαρισμένο, με ενότητα από τους σελιδοδείκτες.

Καθαρισμός (ντετερμινιστικός):
- αφαίρεση κεφαλίδων/υποσέλιδων: γραμμές που επαναλαμβάνονται στην αρχή ή στο τέλος των περισσότερων
  σελίδων (π.χ. «EFSA Journal 2015;13(10):4254», αριθμός σελίδας),
- ένωση λέξεων που κόπηκαν με παύλα στο τέλος γραμμής («απορρό-\\nφηση» -> «απορρόφηση»),
- ενιαία κενά, Unicode NFC.

Ενότητα: από τους σελιδοδείκτες (outline) του PDF, σε επίπεδο σελίδας. Αν το PDF δεν έχει σελιδοδείκτες,
η ενότητα μένει κενή και η αναφορά γίνεται μόνο με σελίδα.

Αυτόματη εξαίρεση βιβλιογραφίας και παραρτημάτων (δεν βοηθούν σε ερωτήσεις παιδιών, θορυβούν στην ανάκτηση):
- με σελιδοδείκτες: σελίδες σε ενότητα «References», «Appendix», «Annex», «Abbreviations», «Glossary»·
- χωρίς σελιδοδείκτες: από τη γραμμή-επικεφαλίδα «References» (μετά το πρώτο 30% του εγγράφου) ως το τέλος·
  στη σελίδα της επικεφαλίδας κρατιέται το κείμενο πριν από αυτήν.
Οι εξαιρεμένες σελίδες τυπώνονται στο --inspect για έλεγχο.

ΠΕΡΙΟΡΙΣΜΟΙ: δεν γίνεται OCR (σελίδες-εικόνες βγαίνουν κενές και σημειώνονται)· οι πίνακες βγαίνουν ως
σκόρπιο κείμενο. Γι' αυτό υπάρχει το --inspect του script, για έλεγχο πριν το embedding.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

MIN_PAGE_CHARS = 50          # λιγότερα -> πιθανή σελίδα-εικόνα
EDGE_LINES = 3               # πόσες γραμμές πάνω/κάτω ελέγχονται για κεφαλίδα/υποσέλιδο
REPEAT_SHARE = 0.5           # σε πόσες σελίδες πρέπει να επαναλαμβάνεται μια γραμμή
BACK_MATTER = re.compile(r"^(\d+(\.\d+)*\.?\s*)?(references|reference list|bibliography|appendix|appendices|annex|"
                         r"abbreviations|glossary)\b", re.IGNORECASE)
REF_HEADING = re.compile(r"^(\d+(\.\d+)*\.?\s*)?(references|reference list|bibliography)\s*$", re.IGNORECASE)
REF_SEARCH_FROM = 0.3        # επικεφαλίδα «References» αναζητείται μετά το 30% του εγγράφου
AUTO_EXCLUDED = "auto_excluded"


@dataclass(frozen=True)
class PageText:
    page: int                # αρίθμηση από 1, όπως στο PDF viewer
    text: str
    section: str = ""
    flags: tuple[str, ...] = ()   # π.χ. ("low_text",), ("bad_chars",)
    removed: tuple[str, ...] = () # γραμμές που αφαιρέθηκαν ως κεφαλίδα/υποσέλιδο (για έλεγχο στο --inspect)


def _norm_line(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _outline_sections(reader: PdfReader) -> dict[int, str]:
    """Σελίδα (από 1) -> τίτλος σελιδοδείκτη που ξεκινά εκεί. Τα εμφωλευμένα αφήνουν τον βαθύτερο."""
    starts: dict[int, str] = {}

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
                continue
            try:
                p = reader.get_destination_page_number(it) + 1
            except Exception:   # σπασμένος σελιδοδείκτης: αγνοείται
                continue
            title = clean_title(str(getattr(it, "title", "")))
            if title:
                starts[p] = title
    try:
        walk(reader.outline)
    except Exception:
        return {}
    return starts


def clean_title(title: str) -> str:
    """Οι τίτλοι σελιδοδεικτών μπορεί να έχουν χαρακτήρες ελέγχου μέσα σε λέξεις (π.χ. «Inte\\x84gra\\x84tion»):
    αφαιρούνται χωρίς κενό, μετά ενοποιούνται τα κενά."""
    t = unicodedata.normalize("NFKC", title)
    t = "".join(c for c in t if c.isspace() or unicodedata.category(c)[0] != "C")
    return " ".join(t.split())


def _bad_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(1 for c in text if c == "�" or unicodedata.category(c) in ("Co", "Cs"))
    return bad / len(text)


def clean_text(raw: str) -> str:
    t = unicodedata.normalize("NFKC", raw).replace("­", "")          # soft hyphen
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)                                  # λέξη κομμένη με παύλα
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
    t = re.sub(r"\n{2,}", " ", t)                                      # προσωρινό σημάδι παραγράφου
    t = t.replace("\n", " ").replace(" ", "\n\n")
    t = "".join(c for c in t if c in "\n" or unicodedata.category(c)[0] != "C")
    t = re.sub(r"[  ]{2,}", " ", t)
    return t.strip()


def extract_pages(pdf_path: Path, pages: Optional[list[int]] = None) -> list[PageText]:
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    wanted = pages or list(range(1, n + 1))
    raw = {p: (reader.pages[p - 1].extract_text() or "") for p in wanted}

    # Κεφαλίδες / υποσέλιδα: γραμμές στις άκρες που επαναλαμβάνονται σε >= REPEAT_SHARE των σελίδων
    edge_counts: Counter = Counter()
    for text in raw.values():
        lines = [l for l in text.splitlines() if l.strip()]
        edges = {_norm_line(l) for l in lines[:EDGE_LINES] + lines[-EDGE_LINES:]}
        edge_counts.update(edges)
    min_repeat = max(3, int(REPEAT_SHARE * len(raw)))
    boilerplate = {l for l, c in edge_counts.items() if c >= min_repeat}

    starts = _outline_sections(reader)
    section_at: dict[int, str] = {}
    current = ""
    for p in range(1, n + 1):
        current = starts.get(p, current)
        section_at[p] = current

    # Βιβλιογραφία / παραρτήματα
    excluded: set[int] = set()
    cut_line: dict[int, int] = {}            # σελίδα της επικεφαλίδας -> κρατάμε γραμμές πριν από αυτή
    if starts:
        excluded = {p for p in wanted if BACK_MATTER.match(section_at.get(p, ""))}
    else:
        first = max(1, int(REF_SEARCH_FROM * n))
        for p in (q for q in wanted if q >= first):
            idx = next((i for i, l in enumerate(raw[p].splitlines()) if REF_HEADING.match(l.strip())), None)
            if idx is not None:
                cut_line[p] = idx
                excluded = {q for q in wanted if q > p}
                break

    out = []
    for p in wanted:
        if p in excluded:
            out.append(PageText(p, "", section_at.get(p, ""), (AUTO_EXCLUDED,)))
            continue
        lines = raw[p].splitlines()
        if p in cut_line:
            lines = lines[:cut_line[p]]
        nonblank = [i for i, l in enumerate(lines) if l.strip()]
        edge_idx = set(nonblank[:EDGE_LINES] + nonblank[-EDGE_LINES:])
        drop = {i for i in edge_idx if _norm_line(lines[i]) in boilerplate}
        kept = [l for i, l in enumerate(lines) if i not in drop]
        text = clean_text("\n".join(kept))
        flags = []
        if len(text) < MIN_PAGE_CHARS:
            flags.append("low_text")
        if _bad_char_ratio(text) > 0.01:
            flags.append("bad_chars")
        out.append(PageText(p, text, section_at.get(p, ""), tuple(flags),
                            tuple(lines[i].strip() for i in sorted(drop))))
    return out
