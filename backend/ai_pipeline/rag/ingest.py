"""
ai_pipeline/rag/ingest.py — Βήμα 5.1: από τα εγκεκριμένα PDF στο ευρετήριο.

    rag_sources.csv ──► select_sources (hash, έγκριση) ──► extract_pages ──► chunk_pages
                    ──► chunk_filter.filter_chunks ──► embedder.embed_passages ──► ChromaIndex.build(rag_db/)

prepare() κάνει τα πάντα εκτός από embedding (χωρίς μοντέλο): για το --inspect.

Φίλτρα ποιότητας (chunk_filter, Απόφαση 9): μετά το chunk_pages() αφαιρούνται πίνακας περιεχομένων,
σελίδες τίτλου, Background/Terms of reference και πίνακες με αριθμούς. Τα chunk_id που μένουν ΔΕΝ
ξαναριθμούνται: κενό στην αρίθμηση (π.χ. efsa_iron_2015:0003 -> :0005) σημαίνει ότι το :0004 κόπηκε· ο
λόγος του είναι στο SourceReport.dropped, στο ingest_report.json και (audit) στο rag_db/dropped_chunks.jsonl.
Έτσι ένα evidence ID δεν αλλάζει νόημα όταν αλλάζουν τα φίλτρα.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import chunk_filter
from .chunking import MAX_WORDS, OVERLAP_WORDS, Chunk, chunk_pages
from .embedder import Embedder
from .index import ChromaIndex, _default_client
from .pdf_text import AUTO_EXCLUDED, extract_pages
from .sources import Source, load_sources, select_sources


@dataclass
class SourceReport:
    source_id: str
    status: str
    pages: int
    flagged_pages: dict[int, tuple[str, ...]]
    chunks: int                                            # κομμάτια που ΜΕΝΟΥΝ μετά τα φίλτρα
    mean_words: float
    sections: int
    truncated: list[str] = field(default_factory=list)   # chunk_id που ξεπερνούν τα 512 tokens
    removed_lines: list[str] = field(default_factory=list)  # διαφορετικές γραμμές που αφαιρέθηκαν ως κεφαλίδα/υποσέλιδο
    auto_excluded: list[int] = field(default_factory=list)  # σελίδες βιβλιογραφίας / παραρτημάτων
    dropped: dict[str, list[str]] = field(default_factory=dict)   # λόγος (chunk_filter) -> chunk_id που κόπηκαν
    dropped_samples: dict[str, str] = field(default_factory=dict)  # λόγος -> αρχή (80 χαρ.) του 1ου που κόπηκε
    # για το rag_db/dropped_chunks.jsonl (όχι στο ingest_report.json)
    dropped_records: list[dict] = field(default_factory=list, repr=False)


IDENTITY_PAGES = 3
DROPPED_TEXT_CHARS = 200   # πόσο κείμενο κάθε κομματιού που κόπηκε κρατά το dropped_chunks.jsonl


def verify_identity(src: Source, path: Path) -> None:
    """Το check_text (π.χ. DOI) πρέπει να υπάρχει στις πρώτες σελίδες. Σύγκριση χωρίς τόνους/κεφαλαία/κενά."""
    if not src.check_text:
        return
    from pypdf import PdfReader
    from ai_pipeline.presentation.lexicon import normalize
    reader = PdfReader(str(path))
    # ακατέργαστο κείμενο: η αφαίρεση κεφαλίδων θα έσβηνε ακριβώς το «EFSA Journal 2015;13(10):4254»
    head = " ".join((reader.pages[i].extract_text() or "") for i in range(min(IDENTITY_PAGES, len(reader.pages))))
    squash = lambda t: re.sub(r"\s+", "", normalize(t))
    if not any(squash(alt) in squash(head) for alt in src.check_text.split("|") if alt.strip()):
        raise ValueError(f"{src.source_id}: '{src.check_text}' not found in the first {IDENTITY_PAGES} pages of "
                         f"{path.name}: is this the right document?")


def prepare(manifest: Path, pdf_dir: Path, allow_draft: bool = False,
            max_words: int = MAX_WORDS, overlap_words: int = OVERLAP_WORDS
            ) -> tuple[list[tuple[Source, list[Chunk]]], list[SourceReport]]:
    selected = select_sources(load_sources(manifest), pdf_dir, allow_draft)
    if not selected:
        raise ValueError("no sources selected (none approved? use --allow-draft for development)")
    out, reports = [], []
    for src, path in selected:
        verify_identity(src, path)
        from pypdf import PdfReader
        n_pages = len(PdfReader(str(path)).pages)
        pages = extract_pages(path, src.page_numbers(n_pages))
        all_chunks = chunk_pages(src, pages, max_words, overlap_words)
        chunks, dropped = chunk_filter.filter_chunks(all_chunks)
        text_of = {c.chunk_id: c.text for c in all_chunks}
        out.append((src, chunks))
        reports.append(SourceReport(
            source_id=src.source_id, status=src.status, pages=sum(1 for p in pages if AUTO_EXCLUDED not in p.flags),
            flagged_pages={p.page: p.flags for p in pages if p.flags and AUTO_EXCLUDED not in p.flags},
            auto_excluded=[p.page for p in pages if AUTO_EXCLUDED in p.flags],
            chunks=len(chunks),
            mean_words=round(sum(len(c.text.split()) for c in chunks) / len(chunks), 1) if chunks else 0.0,
            sections=len({c.section for c in chunks}),
            removed_lines=sorted({re.sub(r"\d+", "#", l) for p in pages for l in p.removed}),
            dropped=dropped,
            dropped_samples={reason: text_of[ids[0]][:80] for reason, ids in dropped.items()},
            dropped_records=sorted(({"chunk_id": cid, "source_id": src.source_id, "reason": reason,
                                     "text_head": text_of[cid][:DROPPED_TEXT_CHARS]}
                                    for reason, ids in dropped.items() for cid in ids),
                                   key=lambda r: r["chunk_id"]),
        ))
    return out, reports


def build_index(manifest: Path, pdf_dir: Path, embedder: Embedder, out_dir: Path, allow_draft: bool = False,
                max_words: int = MAX_WORDS, overlap_words: int = OVERLAP_WORDS,
                client_factory=_default_client) -> tuple[ChromaIndex, list[SourceReport]]:
    prepared, reports = prepare(manifest, pdf_dir, allow_draft, max_words, overlap_words)
    chunks = [c for _, cs in prepared for c in cs]
    texts = [c.text for c in chunks]

    count_truncated = getattr(embedder, "count_truncated", None)
    if count_truncated:
        too_long = {chunks[i].chunk_id for i in count_truncated(texts)}
        for r in reports:
            r.truncated = sorted(cid for cid in too_long if cid.startswith(f"{r.source_id}:"))

    import numpy as np
    vectors = embedder.embed_passages(texts) if texts else np.zeros((0, embedder.dim), np.float32)
    sources = [{"source_id": s.source_id, "title": s.title, "version": s.version, "sha256": s.sha256,
                "status": s.status, "approved_by": s.approved_by, "approved_date": s.approved_date,
                "licence": s.licence, "url": s.url} for s, _ in prepared]
    index = ChromaIndex.build(out_dir, chunks, vectors, embedder.model_id,
                              {"max_words": max_words, "overlap_words": overlap_words,
                               "passage_prefix": "passage: ", "query_prefix": "query: ",
                               "chunk_filter": chunk_filter.params()},
                              sources, client_factory=client_factory,
                              dropped=[d for r in reports for d in r.dropped_records])
    return index, reports
