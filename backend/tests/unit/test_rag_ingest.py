"""Βήμα 5.1: ingestion της βάσης γνώσης, με ΣΥΝΘΕΤΙΚΑ PDF (το περιεχόμενό τους είναι επινοημένο,
όχι απόσπασμα των πραγματικών πηγών). Χωρίς μοντέλο: HashingEmbedder και ψεύτικο e5.

ChromaDB: τα περισσότερα tests χρησιμοποιούν FakeChroma (στη μνήμη), που υλοποιεί μόνο ό,τι καλεί ο κώδικάς
μας και ΑΠΟΤΥΓΧΑΝΕΙ αν ζητηθεί embedding function ή query_texts. Το test_real_chromadb_roundtrip τρέχει με
το πραγματικό chromadb όταν είναι εγκατεστημένο (αλλιώς παραλείπεται)."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ai_pipeline.rag import chunk_filter
from ai_pipeline.rag.chunking import chunk_pages
from ai_pipeline.rag.embedder import E5Embedder, HashingEmbedder
from ai_pipeline.rag.index import ChromaIndex, read_back
from ai_pipeline.rag.ingest import build_index, prepare, verify_identity
from ai_pipeline.rag.pdf_text import PageText, clean_text, extract_pages
from ai_pipeline.rag.retriever import Retriever
from ai_pipeline.rag.sources import (Source, fill_missing_hashes, load_sources, parse_pages, resolve_file,
                                     select_sources, sha256_file)

reportlab = pytest.importorskip("reportlab")
from reportlab.pdfbase import pdfmetrics            # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont         # noqa: E402
from reportlab.pdfgen import canvas                  # noqa: E402

# Γραμματοσειρά με ελληνικά: Linux (Debian/Ubuntu, Fedora), macOS, Windows
FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
                   "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                   "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                   "/Library/Fonts/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                   "C:/Windows/Fonts/arial.ttf"]
FONT = next((f for f in FONT_CANDIDATES if Path(f).is_file()), None)
if FONT is None:
    pytest.skip("no Greek-capable TTF font found for synthetic PDFs", allow_module_level=True)


# ---------------- ψεύτικο ChromaDB ----------------

class _FakeCollection:
    def __init__(self, name, space):
        self.name, self.space = name, space
        self.ids, self.docs, self.metas, self.embs = [], [], [], []

    def add(self, ids, documents, metadatas, embeddings):
        assert len(ids) == len(documents) == len(metadatas) == len(embeddings)
        assert all(isinstance(v, (str, int, float, bool)) for m in metadatas for v in m.values())
        self.ids += ids; self.docs += documents; self.metas += metadatas
        self.embs += [list(map(float, e)) for e in embeddings]

    def count(self):
        return len(self.ids)

    def get(self, include, limit=None):
        n = len(self.ids) if limit is None else limit
        return {"ids": self.ids[:n], "documents": self.docs[:n], "metadatas": self.metas[:n],
                "embeddings": np.array(self.embs[:n], dtype=np.float32)}

    def query(self, query_embeddings=None, n_results=10, include=None, query_texts=None):
        if query_texts is not None or query_embeddings is None:
            raise AssertionError("query_texts must never be used (would use Chroma's default model)")
        q = np.asarray(query_embeddings[0], dtype=np.float32)
        E = np.asarray(self.embs, dtype=np.float32)
        cos = (E @ q) / (np.linalg.norm(E, axis=1) * np.linalg.norm(q) + 1e-12)
        order = np.argsort(1 - cos, kind="stable")[:n_results]
        return {"ids": [[self.ids[i] for i in order]], "distances": [[float(1 - cos[i]) for i in order]]}


class FakeChroma:
    stores: dict = {}

    def __init__(self, path):
        self.cols = FakeChroma.stores.setdefault(path, {})

    def list_collections(self):
        return list(self.cols.values())

    def delete_collection(self, name):
        del self.cols[name]

    def create_collection(self, name, embedding_function="MISSING", configuration=None, metadata=None):
        assert embedding_function is None, "collection must be created WITHOUT a Chroma embedding function"
        assert configuration == {"hnsw": {"space": "cosine"}}
        self.cols[name] = _FakeCollection(name, "cosine")
        return self.cols[name]

    def get_collection(self, name, embedding_function="MISSING"):
        assert embedding_function is None
        return self.cols[name]


class _RoundingCollection(_FakeCollection):
    """Όπως το chromadb 1.5 με cosine: τα διανύσματα αποθηκεύονται με απόκλιση ~1 ulp από την είσοδο."""

    def add(self, ids, documents, metadatas, embeddings):
        e = np.asarray(embeddings, dtype=np.float32)
        super().add(ids, documents, metadatas, np.nextafter(e, np.float32(2)).tolist())


class RoundingChroma(FakeChroma):
    def create_collection(self, name, embedding_function="MISSING", configuration=None, metadata=None):
        super().create_collection(name, embedding_function, configuration, metadata)
        self.cols[name] = _RoundingCollection(name, "cosine")
        return self.cols[name]


@pytest.fixture(autouse=True)
def _clear_fake():
    FakeChroma.stores.clear()


# ---------------- συνθετικά PDF ----------------

GREEK_PAGES = [
    ("Σίδηρος", ["Ο σίδηρος χρειάζεται για τη μεταφορά οξυγόνου στο αίμα.",
                 "Τα όσπρια, το κρέας και τα ψάρια έχουν σίδηρο.",
                 "Η βιταμίνη C βοηθά την απορρό-", "φηση του σιδήρου από τα φυτικά τρόφιμα."]),
    ("Σίδηρος", ["Οι φακές και τα ρεβίθια είναι καλές πηγές σιδήρου για παιδιά.",
                 "Τα πράσινα φυλλώδη λαχανικά έχουν επίσης σίδηρο."]),
    ("Ασβέστιο", ["Το ασβέστιο χρειάζεται για γερά κόκαλα και δόντια.",
                  "Το γάλα, το γιαούρτι και το τυρί είναι πηγές ασβεστίου.",
                  "Στην εφηβεία τα κόκαλα μεγαλώνουν γρήγορα."]),
    ("Ασβέστιο", []),   # σελίδα χωρίς κείμενο (σαν εικόνα)
    ("Ασβέστιο", ["Τα αμύγδαλα και το σουσάμι έχουν ασβέστιο.",
                  "Ο ήλιος βοηθά τον οργανισμό να φτιάξει βιταμίνη D."]),
]


def make_pdf(path, pages, header="Συνθετικός Οδηγός Δοκιμής doi:10.9999/test.0001", outline=True):
    pdfmetrics.registerFont(TTFont("GR", FONT))
    c = canvas.Canvas(str(path))
    last_section = None
    for i, (section, lines) in enumerate(pages, 1):
        c.setFont("GR", 10)
        c.drawString(50, 810, header)
        if outline and section != last_section:
            key = f"s{i}"
            c.bookmarkPage(key)
            c.addOutlineEntry(section, key, level=0)
            last_section = section
        y = 760
        for line in lines:
            c.setFont("GR", 12)
            c.drawString(50, y, line)
            y -= 18
        c.setFont("GR", 9)
        c.drawString(280, 30, f"σελίδα {i}")
        c.showPage()
    c.save()


MANIFEST_FIELDS = ["source_id", "file", "title", "organization", "year", "version", "language", "url",
                   "licence", "sha256", "pages", "status", "approved_by", "approved_date", "check_text", "note"]


def write_manifest(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})


@pytest.fixture
def corpus(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "guide.pdf", GREEK_PAGES)
    make_pdf(pdf_dir / "Other  Doc.pdf", [("Sports", [f"Water is the best drink during training, part {i}.",
                                                      f"Children should drink water before they feel thirsty ({i})."])
                                          for i in ("one", "two", "three")], header="Synthetic English Doc")
    (pdf_dir / "ignored.pdf").write_bytes((pdf_dir / "guide.pdf").read_bytes())   # δεν είναι στο manifest
    base = {"title": "Συνθετικός οδηγός", "organization": "test", "year": "2026", "version": "v1",
            "language": "el", "url": "", "licence": "test"}
    rows = [dict(base, source_id="guide", file="guide.pdf", status="approved", approved_by="dietitian",
                 approved_date="2026-10-28", sha256=sha256_file(pdf_dir / "guide.pdf"), check_text="10.9999/test.0001"),
            dict(base, source_id="other", file="other doc.pdf", language="en", status="draft",
                 sha256=sha256_file(pdf_dir / "Other  Doc.pdf"))]
    manifest = tmp_path / "rag_sources.csv"
    write_manifest(manifest, rows)
    return manifest, pdf_dir


def src(**kw):
    d = dict(source_id="s", file="f.pdf", title="T", organization="O", year="2026", version="v1", language="el",
             url="", licence="", sha256="x", pages="", status="draft", approved_by="", approved_date="")
    d.update(kw)
    return Source(**d)


def build(corpus, tmp_path, emb=None, allow_draft=False, out="db"):
    manifest, pdf_dir = corpus
    return build_index(manifest, pdf_dir, emb or HashingEmbedder(), tmp_path / out, allow_draft,
                       client_factory=FakeChroma)


# ---------- manifest ----------

def test_parse_pages():
    assert parse_pages("", 4) == [1, 2, 3, 4]
    assert parse_pages("2-3, 5", 6) == [2, 3, 5]
    for bad in ("0-2", "3-1", "7", "a-b"):
        with pytest.raises(ValueError):
            parse_pages(bad, 6)


def test_only_manifest_files_and_draft_excluded_unless_allowed(corpus):
    manifest, pdf_dir = corpus
    sources = load_sources(manifest)
    assert [s.source_id for s, _ in select_sources(sources, pdf_dir)] == ["guide"]
    assert [s.source_id for s, _ in select_sources(sources, pdf_dir, allow_draft=True)] == ["guide", "other"]


def test_excluded_never_selected_and_file_not_required(corpus, tmp_path):
    manifest, pdf_dir = corpus
    rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
    rows.append(dict(rows[1], source_id="pending", file="not_downloaded.pdf", status="excluded", sha256=""))
    write_manifest(manifest, rows)
    chosen = [s.source_id for s, _ in select_sources(load_sources(manifest), pdf_dir, allow_draft=True)]
    assert chosen == ["guide", "other"]


def test_loose_file_name_match(corpus):
    _, pdf_dir = corpus
    assert resolve_file(pdf_dir, "other doc.pdf").name == "Other  Doc.pdf"   # κεφαλαία / διπλό κενό
    with pytest.raises(FileNotFoundError):
        resolve_file(pdf_dir, "missing.pdf")


def test_hash_mismatch_rejected(corpus):
    manifest, pdf_dir = corpus
    (pdf_dir / "guide.pdf").write_bytes((pdf_dir / "guide.pdf").read_bytes() + b"%changed")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        select_sources(load_sources(manifest), pdf_dir)


def test_approved_requires_signoff(tmp_path):
    m = tmp_path / "m.csv"
    write_manifest(m, [dict(source_id="a", file="a.pdf", title="t", version="1", language="el", status="approved")])
    with pytest.raises(ValueError, match="approved source needs"):
        load_sources(m)


def test_fill_missing_hashes_never_overwrites(corpus):
    manifest, pdf_dir = corpus
    rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
    rows[0]["sha256"] = "keep-me"
    rows[1]["sha256"] = ""
    write_manifest(manifest, rows)
    assert fill_missing_hashes(manifest, pdf_dir) == ["other"]
    after = list(csv.DictReader(manifest.open(encoding="utf-8")))
    assert after[0]["sha256"] == "keep-me" and after[1]["sha256"] == sha256_file(pdf_dir / "Other  Doc.pdf")


def test_identity_check(corpus):
    _, pdf_dir = corpus
    verify_identity(src(check_text="10.9999/TEST.0001"), pdf_dir / "guide.pdf")          # κεφαλαία: ίδιο
    verify_identity(src(check_text="nope|συνθετικός οδηγός"), pdf_dir / "guide.pdf")     # εναλλακτική
    with pytest.raises(ValueError, match="right document"):
        verify_identity(src(check_text="j.efsa.2015.4254"), pdf_dir / "guide.pdf")


# ---------- εξαγωγή κειμένου ----------

def test_extract_removes_header_footer_and_joins_hyphen(corpus):
    _, pdf_dir = corpus
    pages = extract_pages(pdf_dir / "guide.pdf")
    full = " ".join(p.text for p in pages)
    assert "Συνθετικός Οδηγός Δοκιμής" not in full and "σελίδα" not in full
    assert "απορρόφηση" in full
    assert any("σελίδα 1" in l for p in pages for l in p.removed)


def test_sections_from_outline_and_low_text_flag(corpus):
    _, pdf_dir = corpus
    pages = extract_pages(pdf_dir / "guide.pdf")
    assert [p.section for p in pages] == ["Σίδηρος", "Σίδηρος", "Ασβέστιο", "Ασβέστιο", "Ασβέστιο"]
    assert "low_text" in pages[3].flags


def test_page_selection(corpus):
    _, pdf_dir = corpus
    assert [p.page for p in extract_pages(pdf_dir / "guide.pdf", [3, 5])] == [3, 5]


def test_back_matter_excluded_with_outline(tmp_path):
    pages = [("Εισαγωγή", [f"Ο σίδηρος χρειάζεται στο αίμα ({i})."]) for i in "αβγ"] + [("References", ["Smith J, 2010. A study."]),
                                                                    ("Appendix A", ["Πίνακας στοιχείων."])]
    make_pdf(tmp_path / "o.pdf", pages)
    out = extract_pages(tmp_path / "o.pdf")
    assert [p.page for p in out if "auto_excluded" in p.flags] == [4, 5]
    assert all(p.text == "" for p in out[3:]) and "σίδηρος" in out[0].text


def test_back_matter_excluded_without_outline_keeps_text_before_heading(tmp_path):
    pages = [("x", [f"Κείμενο σελίδας {i} για το ασβέστιο."]) for i in range(1, 4)]
    pages += [("x", ["Τελευταία πρόταση του συμπεράσματος.", "References", "Smith J, 2010. A study."]),
              ("x", ["Jones K, 2011. Another study."])]
    make_pdf(tmp_path / "n.pdf", pages, outline=False)
    out = extract_pages(tmp_path / "n.pdf")
    assert [p.page for p in out if "auto_excluded" in p.flags] == [5]
    assert "συμπεράσματος" in out[3].text and "Smith" not in out[3].text


def test_outline_title_control_chars_removed():
    from ai_pipeline.rag.pdf_text import clean_title
    assert clean_title("6.1.3. Inte\x84gra\x84tion of the evi\x84dence") == "6.1.3. Integration of the evidence"


def test_clean_text():
    assert clean_text("suf\ufb01cient") == "sufficient"        # λιγκατούρα ﬁ
    assert clean_text("γραμ-\nμή\n\nνέα  παράγραφος") == "γραμμή\n\nνέα παράγραφος"


# ---------- chunking ----------

def test_chunks_respect_size_overlap_and_sections():
    words = " ".join(f"λέξη{i}" for i in range(9))
    pages = [PageText(1, ". ".join([words] * 6) + ".", "Α"), PageText(2, f"{words}.", "Β")]
    chunks = chunk_pages(src(), pages, max_words=20, overlap_words=9)
    assert all(len(c.text.split()) <= 20 for c in chunks)
    assert chunks[-1].section == "Β" and all(c.section == "Α" for c in chunks[:-1])
    a = [c for c in chunks if c.section == "Α"]
    assert a[0].text.split(". ")[-1].rstrip(".") in a[1].text   # επικάλυψη μίας πρότασης
    assert [c.chunk_id for c in chunks] == [f"s:{i:04d}" for i in range(1, len(chunks) + 1)]


def test_long_sentence_is_split():
    pages = [PageText(1, " ".join(["λέξη"] * 50) + ".", "")]
    chunks = chunk_pages(src(), pages, max_words=20, overlap_words=5)
    assert all(len(c.text.split()) <= 20 for c in chunks) and len(chunks) == 3


def test_overlap_must_be_smaller():
    with pytest.raises(ValueError):
        chunk_pages(src(), [], max_words=10, overlap_words=10)


# ---------- ChromaDB: κατασκευή, φόρτωση, ανάκτηση ----------

def test_build_load_search(corpus, tmp_path):
    emb = HashingEmbedder()
    index, reports = build(corpus, tmp_path, emb)
    assert index.manifest["release"] is True and {c.source_id for c in index.chunks} == {"guide"}
    assert reports[0].flagged_pages == {4: ("low_text",)}

    r = Retriever.from_dir(tmp_path / "db", emb, client_factory=FakeChroma)
    for mode in ("dense", "bm25", "hybrid"):
        top = r.search("Ποια φαγητά έχουν σίδηρο;", k=3, mode=mode)
        assert top[0].chunk.section == "Σίδηρος", mode
    hit = r.search("γερά κόκαλα ασβέστιο", k=1)[0].chunk
    assert hit.section == "Ασβέστιο" and hit.page_start >= 3 and hit.approved


def test_rebuild_replaces_collection(corpus, tmp_path):
    first, _ = build(corpus, tmp_path)
    second, _ = build(corpus, tmp_path)
    assert second.collection.count() == len(first.chunks)    # όχι διπλά κομμάτια


def test_draft_index_refused_by_default(corpus, tmp_path):
    index, _ = build(corpus, tmp_path, allow_draft=True)
    assert index.manifest["release"] is False
    with pytest.raises(ValueError, match="draft index"):
        ChromaIndex.load(tmp_path / "db", client_factory=FakeChroma)
    assert ChromaIndex.load(tmp_path / "db", allow_draft=True, client_factory=FakeChroma).manifest["n_chunks"] == len(index.chunks)


def test_tampered_collection_refused(corpus, tmp_path):
    index, _ = build(corpus, tmp_path)
    index.collection.docs[0] = index.collection.docs[0].replace("σίδηρο", "ΑΛΛΑΓΗ")
    with pytest.raises(ValueError, match="content_hash mismatch"):
        ChromaIndex.load(tmp_path / "db", client_factory=FakeChroma)


def test_store_rounding_does_not_break_load_but_tampering_does(corpus, tmp_path):
    """Το hash του build() είναι από ό,τι αποθηκεύτηκε, όχι από την είσοδο (αλλιώς το load() αποτυγχάνει πάντα)."""
    manifest, pdf_dir = corpus
    emb = HashingEmbedder()
    index, _ = build_index(manifest, pdf_dir, emb, tmp_path / "db", client_factory=RoundingChroma)
    r = Retriever.from_dir(tmp_path / "db", emb, client_factory=RoundingChroma)
    assert r.search("σίδηρο όσπρια", k=1)[0].chunk.section == "Σίδηρος"
    e = index.collection.embs[0]
    e[0] = float(np.nextafter(np.float32(e[0]), np.float32(2)))     # αλλοίωση ενός ulp σε ένα διάνυσμα
    with pytest.raises(ValueError, match="content_hash mismatch"):
        ChromaIndex.load(tmp_path / "db", client_factory=RoundingChroma)


def test_read_back_normalizes_types_and_rejects_ambiguous(corpus, tmp_path):
    index, _ = build(corpus, tmp_path)
    col = index.collection
    col.metas[0] = dict(col.metas[0], page_start=float(col.metas[0]["page_start"]), approved=1, extra="x")
    ids, docs, metas, emb = read_back(col, col.count())
    assert type(metas[0]["page_start"]) is int and metas[0]["approved"] is True and "extra" not in metas[0]
    assert emb.dtype == np.float32 and emb.shape == (col.count(), 512)
    for bad in ({"approved": "false"}, {"page_end": 2.5}, {"title": 7}):
        col.metas[0] = dict(index.collection.metas[1], **bad)
        with pytest.raises(ValueError, match="metadata"):
            read_back(col, col.count())
    col.metas[0] = {k: v for k, v in col.metas[1].items() if k != "section"}
    with pytest.raises(ValueError, match="missing"):
        read_back(col, col.count())
    with pytest.raises(ValueError, match="expected"):
        read_back(col, col.count() + 1)


def test_chromadb_version_recorded_and_reported(corpus, tmp_path):
    from ai_pipeline.rag.index import chromadb_version
    index, _ = build(corpus, tmp_path)
    path = tmp_path / "db" / "index_manifest.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["chromadb_version"] == chromadb_version()
    if chromadb_version() is None:
        pytest.skip("chromadb not installed: no version to compare")
    saved["chromadb_version"] = "0.0.1"
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.warns(RuntimeWarning, match="index built with chromadb 0.0.1"):
        ChromaIndex.load(tmp_path / "db", client_factory=FakeChroma)          # ίδιο περιεχόμενο: φορτώνει
    index.collection.docs[0] += " "
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError, match="content_hash mismatch.*chromadb version differs"):
        ChromaIndex.load(tmp_path / "db", client_factory=FakeChroma)


def test_other_embedding_model_refused(corpus, tmp_path):
    build(corpus, tmp_path, HashingEmbedder(512))
    with pytest.raises(ValueError, match="index built with"):
        Retriever.from_dir(tmp_path / "db", HashingEmbedder(256), client_factory=FakeChroma)


def test_manifest_records_sources_and_params(corpus, tmp_path):
    index, _ = build(corpus, tmp_path)
    saved = json.loads((tmp_path / "db" / "index_manifest.json").read_text(encoding="utf-8"))
    assert saved == index.manifest and saved["sources"][0]["approved_by"] == "dietitian"
    assert saved["params"]["query_prefix"] == "query: " and saved["distance"] == "cosine"
    assert saved["params"]["chunk_filter"] == chunk_filter.params()        # κατώφλια + έκδοση, για το audit
    assert saved["n_dropped"] == 0 and (tmp_path / "db" / "dropped_chunks.jsonl").read_text(encoding="utf-8") == ""
    assert len(index.version) == 16
    lines = (tmp_path / "db" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == saved["n_chunks"]


def test_prepare_drops_toc_without_renumbering(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    toc = ("Table of contents", ["Σίδηρος ................................ 2", "Ασβέστιο ................................ 3",
                                 "Βιταμίνη D ................................ 5"])
    make_pdf(pdf_dir / "toc.pdf", [toc] + GREEK_PAGES)
    write_manifest(tmp_path / "m.csv", [dict(source_id="toc", file="toc.pdf", title="T", organization="o",
                                             year="2026", version="v1", language="el", licence="t",
                                             status="approved", approved_by="d", approved_date="2026-10-28",
                                             sha256=sha256_file(pdf_dir / "toc.pdf"))])
    prepared, reports = prepare(tmp_path / "m.csv", pdf_dir)
    ids = [c.chunk_id for c in prepared[0][1]]
    assert reports[0].dropped == {"toc": ["toc:0001"]}
    assert ids[0] == "toc:0002" and reports[0].chunks == len(ids)        # κενό στην αρίθμηση = κόπηκε
    assert "Σίδηρος" in reports[0].dropped_samples["toc"] and len(reports[0].dropped_samples["toc"]) <= 80


def test_build_writes_dropped_chunks_audit(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    toc = ("Table of contents", ["Σίδηρος ................................ 2", "Ασβέστιο ................................ 3",
                                 "Βιταμίνη D ................................ 5"])
    make_pdf(pdf_dir / "toc.pdf", [toc] + GREEK_PAGES)
    write_manifest(tmp_path / "m.csv", [dict(source_id="toc", file="toc.pdf", title="T", organization="o",
                                             year="2026", version="v1", language="el", licence="t",
                                             status="approved", approved_by="d", approved_date="2026-10-28",
                                             sha256=sha256_file(pdf_dir / "toc.pdf"))])
    index, _ = build_index(tmp_path / "m.csv", pdf_dir, HashingEmbedder(), tmp_path / "db", client_factory=FakeChroma)
    raw = (tmp_path / "db" / "dropped_chunks.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines()]
    assert [(r["chunk_id"], r["source_id"], r["reason"]) for r in rows] == [("toc:0001", "toc", "toc")]
    assert "Σίδηρος" in rows[0]["text_head"] and len(rows[0]["text_head"]) <= 200
    saved = json.loads((tmp_path / "db" / "index_manifest.json").read_text(encoding="utf-8"))
    assert saved["n_dropped"] == 1 and saved["dropped_chunks_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "toc:0001" not in {c.chunk_id for c in index.chunks}


def test_search_exclude_returns_k_without_excluded(corpus, tmp_path):
    emb = HashingEmbedder()
    index, _ = build(corpus, tmp_path, emb)
    r = Retriever.from_dir(tmp_path / "db", emb, client_factory=FakeChroma)
    q, n = "Ποια φαγητά έχουν σίδηρο;", len(index.chunks)
    for mode in ("dense", "bm25", "hybrid"):
        full = [h.chunk.chunk_id for h in r.search(q, k=n, mode=mode)]
        ex = frozenset(full[:1])
        got = [h.chunk.chunk_id for h in r.search(q, k=3, mode=mode, exclude=ex)]
        assert full[0] not in got and len(got) == min(3, len(full) - 1), mode
        if mode != "hybrid":                         # dense/bm25: ίδια σειρά, απλώς χωρίς το εξαιρούμενο
            assert got == full[1:4], mode


def test_prepare_needs_no_model(corpus):
    manifest, pdf_dir = corpus
    prepared, reports = prepare(manifest, pdf_dir, allow_draft=True)
    assert {r.source_id for r in reports} == {"guide", "other"} and all(cs for _, cs in prepared)


class DenseEmbedder(HashingEmbedder):
    """HashingEmbedder μετά από σταθερή τυχαία περιστροφή: πυκνά float32 διανύσματα (ίδιες ομοιότητες cosine).
    Νόρμα 2.5 και όχι 1: το chromadb (cosine) κανονικοποιεί ό,τι αποθηκεύει, οπότε τέτοια διανύσματα
    επιστρέφονται ΠΑΝΤΑ λίγο διαφορετικά (μοναδιαία, μόνο κάποιες φορές, π.χ. ~25% των e5). Έτσι το test
    αναπαράγει με βεβαιότητα την περίπτωση όπου hash της εισόδου ≠ hash της ανάγνωσης."""

    def __init__(self, dim: int = 256):
        super().__init__(dim)
        self.model_id = f"dense-test-{dim}"
        self.R = np.linalg.qr(np.random.default_rng(0).standard_normal((dim, dim)))[0].astype(np.float32)

    def _vec(self, text):
        v = self.R @ super()._vec(text)
        return (2.5 * v / np.linalg.norm(v)).astype(np.float32)


def _fresh_chroma_client(path):
    """Νέος client χωρίς την κοινή cache του chromadb ανά διαδρομή, σαν να ξεκινά νέα διεργασία."""
    from chromadb.api.shared_system_client import SharedSystemClient
    from ai_pipeline.rag.index import _default_client
    SharedSystemClient.clear_system_cache()
    return _default_client(path)


def test_real_chromadb_roundtrip(corpus, tmp_path):
    """Με το πραγματικό chromadb (παραλείπεται αν δεν είναι εγκατεστημένο): build -> load -> search."""
    pytest.importorskip("chromadb")
    manifest, pdf_dir = corpus
    emb = DenseEmbedder()
    built, _ = build_index(manifest, pdf_dir, emb, tmp_path / "real", client_factory=_fresh_chroma_client)
    r = Retriever.from_dir(tmp_path / "real", emb, client_factory=_fresh_chroma_client)
    assert r.index.manifest["content_hash"] == built.manifest["content_hash"]
    assert [c.chunk_id for c in r.index.chunks] == [c.chunk_id for c in built.chunks]
    for mode in ("dense", "bm25", "hybrid"):
        assert r.search("Ποια φαγητά έχουν σίδηρο;", k=3, mode=mode)[0].chunk.section == "Σίδηρος", mode
    hit = r.search("γερά κόκαλα ασβέστιο", k=1)[0].chunk
    assert hit.section == "Ασβέστιο" and hit.page_start >= 3 and hit.approved


@pytest.mark.parametrize("what", ["document", "metadata", "embedding"])
def test_real_chromadb_tampering_detected(corpus, tmp_path, what):
    pytest.importorskip("chromadb")
    manifest, pdf_dir = corpus
    emb = DenseEmbedder()
    build_index(manifest, pdf_dir, emb, tmp_path / "real", client_factory=_fresh_chroma_client)
    col = _fresh_chroma_client(str(tmp_path / "real" / "chroma")).get_collection("pyramid_kb", embedding_function=None)
    g = col.get(include=["documents", "metadatas", "embeddings"], limit=1)
    cid = g["ids"][0]
    if what == "document":    # το Chroma χωρίς embedding function θέλει και το διάνυσμα· δίνουμε το ίδιο
        col.update(ids=[cid], documents=[g["documents"][0] + " "], embeddings=[g["embeddings"][0]])
        after = col.get(ids=[cid], include=["embeddings"])["embeddings"][0]
        assert np.array_equal(np.asarray(after, np.float32), np.asarray(g["embeddings"][0], np.float32))
    elif what == "metadata":
        col.update(ids=[cid], metadatas=[{"page_end": g["metadatas"][0]["page_end"] + 1}])
    else:
        v = np.asarray(g["embeddings"][0], dtype=np.float32)
        v[0] += 1e-3
        col.update(ids=[cid], embeddings=[(v / np.linalg.norm(v)).tolist()])
    with pytest.raises(ValueError, match="content_hash mismatch"):
        ChromaIndex.load(tmp_path / "real", allow_draft=True, client_factory=_fresh_chroma_client)


# ---------- e5 (ψεύτικο μοντέλο, χωρίς λήψη) ----------

class FakeST:
    def __init__(self):
        self.calls = []
        self.tokenizer = lambda text, add_special_tokens=True: {"input_ids": text.split()}

    def encode(self, texts, batch_size, normalize_embeddings, convert_to_numpy, show_progress_bar):
        self.calls.append((list(texts), normalize_embeddings))
        v = np.ones((len(texts), 4), dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_e5_prefixes_and_normalisation():
    fake = FakeST()
    e = E5Embedder(model=fake)
    e.embed_passages(["κείμενο"])
    e.embed_query("ερώτηση;")
    assert fake.calls[1] == (["passage: κείμενο"], True)
    assert fake.calls[2] == (["query: ερώτηση;"], True)
    assert e.dim == 4 and e.model_id == "intfloat/multilingual-e5-large@default"


def test_e5_reports_truncated_chunks():
    e = E5Embedder(model=FakeST())
    assert e.count_truncated(["λέξη " * 10, "λέξη " * 600]) == [1]
