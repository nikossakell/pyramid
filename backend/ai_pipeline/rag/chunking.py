"""
ai_pipeline/rag/chunking.py — χωρισμός σε κομμάτια (chunks) με όρια προτάσεων.

- Κάθε κομμάτι έχει έως MAX_WORDS λέξεις. Το multilingual-e5-large κόβει ό,τι περνά τα 512 tokens
  (κάρτα μοντέλου). Τα ελληνικά σπάνε σε περισσότερα tokens ανά λέξη από τα αγγλικά, γι' αυτό το όριο
  είναι σε λέξεις με περιθώριο· το script ingestion μετρά τα πραγματικά tokens και αναφέρει όσα κόπηκαν.
- Επικάλυψη OVERLAP_WORDS λέξεων (ολόκληρες προτάσεις) ώστε μια πρόταση στα όρια να μη χάνεται.
- Ένα κομμάτι δεν διασχίζει όρια ενότητας. Μπορεί να διασχίσει σελίδα (κρατά page_start, page_end).

ΑΠΟΚΛΙΣΗ ΑΠΟ ΤΟ final_plan: το chunk_size=500 εκεί δεν ορίζει μονάδα (χαρακτήρες; tokens;) και κόβει
χωρίς όρια προτάσεων. Εδώ η μονάδα είναι ρητή και τα όρια είναι προτάσεις.
"""
import hashlib
import re
from dataclasses import asdict, dataclass

from .pdf_text import PageText
from .sources import Source

MAX_WORDS = 180      # ΠΡΟΣΧΕΔΙΟ: επαληθεύεται με το tokenizer στο ingestion
OVERLAP_WORDS = 30   # ΠΡΟΣΧΕΔΙΟ

_SENT = re.compile(r"(?<=[.!?;;·])\s+|\n{2,}")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str        # evidence ID: "<source_id>:<αύξων>", αυτό παραθέτει το LLM (η έκδοση είναι στα μεταδεδομένα)
    source_id: str
    title: str
    organization: str
    version: str
    language: str
    section: str
    page_start: int
    page_end: int
    text: str
    text_sha256: str
    approved: bool

    def to_dict(self) -> dict:
        return asdict(self)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s and s.strip()]


def _words(s: str) -> int:
    return len(s.split())


def _split_long(sentence: str, max_words: int) -> list[str]:
    w = sentence.split()
    return [" ".join(w[i:i + max_words]) for i in range(0, len(w), max_words)]


def chunk_pages(source: Source, pages: list[PageText],
                max_words: int = MAX_WORDS, overlap_words: int = OVERLAP_WORDS) -> list[Chunk]:
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")

    # (πρόταση, σελίδα, ενότητα) με τη σειρά του εγγράφου
    units: list[tuple[str, int, str]] = []
    for pg in pages:
        for s in split_sentences(pg.text):
            for piece in (_split_long(s, max_words) if _words(s) > max_words else [s]):
                units.append((piece, pg.page, pg.section))

    chunks: list[Chunk] = []

    def emit(buf: list[tuple[str, int, str]]):
        text = " ".join(u[0] for u in buf)
        n = len(chunks) + 1
        chunks.append(Chunk(
            chunk_id=f"{source.source_id}:{n:04d}",
            source_id=source.source_id, title=source.title, organization=source.organization,
            version=source.version, language=source.language, section=buf[0][2],
            page_start=buf[0][1], page_end=buf[-1][1], text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), approved=source.approved,
        ))

    buf: list[tuple[str, int, str]] = []
    for unit in units:
        new_section = bool(buf) and unit[2] != buf[-1][2]
        too_long = bool(buf) and sum(_words(u[0]) for u in buf) + _words(unit[0]) > max_words
        if new_section or too_long:
            emit(buf)
            if new_section:
                buf = []
            else:   # επικάλυψη: οι τελευταίες ολόκληρες προτάσεις έως overlap_words
                tail, count = [], 0
                for u in reversed(buf):
                    if count + _words(u[0]) > overlap_words:
                        break
                    tail.insert(0, u)
                    count += _words(u[0])
                buf = tail if count + _words(unit[0]) <= max_words else []
        buf.append(unit)
    if buf:
        emit(buf)
    return chunks
