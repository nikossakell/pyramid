"""
ai_pipeline/rag/index.py — η βάση γνώσης σε ChromaDB, όπως ορίζουν το final_plan και η Δομή_project.

    rag_db/chroma/               αρχεία του ChromaDB (PersistentClient): διανύσματα, κείμενα, μεταδεδομένα
    rag_db/chunks.jsonl          αναγνώσιμο αντίγραφο των κομματιών, για έλεγχο από άνθρωπο και για το audit
    rag_db/index_manifest.json   μοντέλο, παράμετροι, πηγές με έγκριση και sha256, content_hash, release/draft
    rag_db/dropped_chunks.jsonl  audit: κομμάτια που έκοψαν τα φίλτρα ποιότητας (chunk_id, source_id, λόγος,
                                 πρώτοι 200 χαρακτήρες)· πλήθος και sha256 στο manifest

ΔΙΟΡΘΩΣΗ ΤΟΥ ΣΦΑΛΜΑΤΟΣ ΤΟΥ final_plan: η συλλογή δημιουργείται ΧΩΡΙΣ embedding function του Chroma
(embedding_function=None). Τα διανύσματα τα φτιάχνει πάντα το e5 μας και δίνονται ρητά (embeddings= στο add,
query_embeddings= στο query). Ο κώδικας ΔΕΝ χρησιμοποιεί ποτέ query_texts, οπότε το Chroma δεν μπορεί να
χρησιμοποιήσει σιωπηλά το προεπιλεγμένο του μοντέλο (all-MiniLM-L6-v2).

Ακεραιότητα: τα αρχεία του Chroma αλλάζουν όταν ανοίγει η βάση (SQLite), άρα hash αρχείων δεν είναι
αξιόπιστο. Αντί γι' αυτό, το content_hash υπολογίζεται από το ΠΕΡΙΕΧΟΜΕΝΟ (id, κείμενο, μεταδεδομένα,
διανύσματα) κατά την κατασκευή και ξαναϋπολογίζεται κατά τη φόρτωση. Αν διαφέρει, η φόρτωση αποτυγχάνει.
Και τα δύο hash υπολογίζονται από ό,τι ΔΙΑΒΑΖΕΤΑΙ από τη συλλογή (read_back), όχι από ό,τι της δόθηκε:
το chromadb 1.5 με απόσταση cosine αποθηκεύει τα διανύσματα με απόκλιση ~1 ulp (σχετική ~1e-7) από την
είσοδο, οπότε hash της εισόδου δεν ταιριάζει ποτέ με hash της ανάγνωσης. Η ανάγνωση είναι ντετερμινιστική
(ίδια πριν και μετά το κλείσιμο της βάσης), άρα κάθε αλλαγή μετά την κατασκευή εξακολουθεί να εντοπίζεται.

Αναζήτηση: dense από το Chroma (HNSW, απόσταση cosine) + BM25 (λέξεις) υπολογισμένο τοπικά από τα κείμενα
της συλλογής, ενωμένα με Reciprocal Rank Fusion (Cormack et al., 2009). Η Αρχιτεκτονική v0.4 ορίζει
«hybrid keyword + vector search». Το HNSW είναι προσεγγιστικό· σε λίγες χιλιάδες κομμάτια η διαφορά από
την ακριβή αναζήτηση είναι αμελητέα, και επιτρέπει κλιμάκωση αν η βάση μεγαλώσει.
"""
import hashlib
import json
import math
import re
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .chunking import Chunk

INDEX_FORMAT = "pyramid-rag-chroma-1"
COLLECTION = "pyramid_kb"
RRF_K = 60           # σταθερά του RRF από το αρχικό άρθρο
ADD_BATCH = 500      # κάτω από το όριο batch του Chroma
META_FIELDS = ("source_id", "title", "organization", "version", "language", "section",
               "page_start", "page_end", "text_sha256", "approved")


def chromadb_version() -> Optional[str]:
    """Η εγκατεστημένη έκδοση του chromadb (None αν δεν είναι εγκατεστημένο)."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("chromadb")
    except PackageNotFoundError:
        return None


def _default_client(path: str):
    import chromadb   # εισαγωγή μόνο όταν χρειάζεται
    return chromadb.PersistentClient(path=path)


def _create_collection(client, name: str):
    """Νέα συλλογή χωρίς embedding function, με απόσταση cosine.
    Chroma >= 1.0: configuration={"hnsw": {"space": "cosine"}}· παλαιότερες: metadata={"hnsw:space": "cosine"}."""
    try:
        return client.create_collection(name=name, embedding_function=None,
                                        configuration={"hnsw": {"space": "cosine"}})
    except (TypeError, ValueError, AttributeError):   # παλαιότερη έκδοση χωρίς configuration ως dict
        return client.create_collection(name=name, embedding_function=None, metadata={"hnsw:space": "cosine"})


def _meta_bool(cid: str, k: str, v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)) and v in (0, 1):
        return bool(v)
    raise ValueError(f"{cid}: metadata {k}={v!r} is not a boolean")


def _meta_int(cid: str, k: str, v) -> int:
    if isinstance(v, (int, np.integer)) and not isinstance(v, (bool, np.bool_)):
        return int(v)
    if isinstance(v, (float, np.floating)) and float(v).is_integer():
        return int(v)
    raise ValueError(f"{cid}: metadata {k}={v!r} is not an integer")


def _meta_str(cid: str, k: str, v) -> str:
    if isinstance(v, str):
        return v
    raise ValueError(f"{cid}: metadata {k}={v!r} is not a string")


_META_TYPES = {"approved": _meta_bool, "page_start": _meta_int, "page_end": _meta_int}


def _normalize_meta(cid: str, meta: Optional[dict]) -> dict:
    """Μόνο τα πεδία του META_FIELDS, με σταθερούς τύπους. Δεχόμαστε μόνο μετατροπές χωρίς απώλεια
    (π.χ. 3.0 -> 3, 1 -> True)· οτιδήποτε άλλο (π.χ. approved="false", έλλειψη πεδίου) είναι σφάλμα,
    ώστε η κανονικοποίηση να μην μπορεί να «κρύψει» αλλοίωση."""
    meta = meta or {}
    missing = [k for k in META_FIELDS if k not in meta]
    if missing:
        raise ValueError(f"{cid}: metadata missing {missing}")
    return {k: _META_TYPES.get(k, _meta_str)(cid, k, meta[k]) for k in META_FIELDS}


def read_back(col, n: int) -> tuple[list[str], list[str], list[dict], np.ndarray]:
    """Διαβάζει ΟΛΗ τη συλλογή (n εγγραφές) όπως την επιστρέφει το Chroma: ids, κείμενα, κανονικοποιημένα
    μεταδεδομένα και διανύσματα ως np.float32 σχήματος (n, dim). Αυτό είναι η είσοδος του content_hash
    τόσο στο build() όσο και στο load()."""
    got = col.get(include=["documents", "metadatas", "embeddings"], limit=max(n, 1))
    ids = list(got["ids"])
    if len(ids) != n or len(set(ids)) != n:
        raise ValueError(f"collection returned {len(ids)} records ({len(set(ids))} unique), expected {n}")
    docs = list(got["documents"])
    if len(docs) != n or not all(isinstance(d, str) for d in docs):
        raise ValueError("collection returned missing or non-text documents")
    raw_metas = list(got["metadatas"])
    if len(raw_metas) != n:
        raise ValueError("collection returned missing metadatas")
    metas = [_normalize_meta(i, m) for i, m in zip(ids, raw_metas)]
    if got["embeddings"] is None:
        raise ValueError("collection returned no embeddings")
    emb = np.asarray(got["embeddings"], dtype=np.float32) if n else np.zeros((0, 0), dtype=np.float32)
    if emb.ndim != 2 or emb.shape[0] != n:
        raise ValueError(f"embeddings have shape {emb.shape}, expected ({n}, dim)")
    return ids, docs, metas, emb


def content_hash(ids: list[str], documents: list[str], metadatas: list[dict], embeddings: np.ndarray) -> str:
    h = hashlib.sha256()
    for i in np.argsort(np.array(ids, dtype=object), kind="stable"):
        h.update(ids[i].encode())
        h.update(documents[i].encode())
        h.update(json.dumps(metadatas[i], sort_keys=True, ensure_ascii=False).encode())
        h.update(np.asarray(embeddings[i], dtype=np.float32).tobytes())
    return h.hexdigest()


def _bm25_tokens(text: str) -> list[str]:
    from ai_pipeline.presentation.lexicon import normalize
    return [t[:6] for t in re.findall(r"\w+", normalize(text)) if len(t) > 1]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(_bm25_tokens(d)) for d in docs]
        self.len = np.array([sum(c.values()) for c in self.tf], dtype=np.float32)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df = Counter(t for c in self.tf for t in c)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> np.ndarray:
        q = _bm25_tokens(query)
        out = np.zeros(len(self.tf), dtype=np.float32)
        for i, c in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1))
            out[i] = sum(self.idf.get(t, 0.0) * c[t] * (self.k1 + 1) / (c[t] + norm) for t in q if t in c)
        return out


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    dense_rank: Optional[int]
    bm25_rank: Optional[int]


def _chunk_from(cid: str, doc: str, meta: dict) -> Chunk:
    return Chunk(chunk_id=cid, text=doc, **{k: meta[k] for k in META_FIELDS})


class ChromaIndex:
    """Δεν κατασκευάζεται απευθείας: build() για νέα βάση, load() για υπάρχουσα."""

    def __init__(self, collection, chunks: list[Chunk], manifest: dict):
        self.collection, self.chunks, self.manifest = collection, chunks, manifest
        self._pos = {c.chunk_id: i for i, c in enumerate(chunks)}
        self.bm25 = BM25([c.text for c in chunks])

    # ---------- κατασκευή ----------
    @classmethod
    def build(cls, out_dir: Path, chunks: list[Chunk], embeddings: np.ndarray, model_id: str, params: dict,
              sources: list[dict], client_factory: Callable = _default_client,
              dropped: Optional[list[dict]] = None) -> "ChromaIndex":
        """dropped: εγγραφές {chunk_id, source_id, reason, text_head} των κομματιών που έκοψε το chunk_filter·
        γράφονται στο dropped_chunks.jsonl (audit, ΔΕΝ μπαίνουν στη συλλογή ούτε στο content_hash)."""
        dropped = list(dropped or [])
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings differ in length")
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("duplicate chunk_id")
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        client = client_factory(str(out / "chroma"))
        if COLLECTION in [getattr(c, "name", c) for c in client.list_collections()]:
            client.delete_collection(COLLECTION)          # πλήρης ανακατασκευή, ποτέ μερική ενημέρωση
        col = _create_collection(client, COLLECTION)

        ids = [c.chunk_id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [{k: getattr(c, k) for k in META_FIELDS} for c in chunks]
        emb = np.asarray(embeddings, dtype=np.float32)
        for s in range(0, len(ids), ADD_BATCH):
            col.add(ids=ids[s:s + ADD_BATCH], documents=docs[s:s + ADD_BATCH],
                    metadatas=metas[s:s + ADD_BATCH], embeddings=emb[s:s + ADD_BATCH].tolist())

        # Το hash από ό,τι αποθηκεύτηκε πραγματικά (βλ. «Ακεραιότητα» πιο πάνω). Πρώτα έλεγχος ότι η συλλογή
        # είναι αυτό που δώσαμε: ίδια ids, κείμενα, μεταδεδομένα, και διανύσματα μέσα σε σφάλμα στρογγύλευσης.
        r_ids, r_docs, r_metas, r_emb = read_back(col, len(ids))
        pos = {cid: i for i, cid in enumerate(ids)}
        if set(r_ids) != set(pos):
            raise ValueError("collection ids differ from the input after add")
        order = [pos[cid] for cid in r_ids]
        if r_docs != [docs[i] for i in order] or r_metas != [metas[i] for i in order]:
            raise ValueError("collection documents/metadatas differ from the input after add")
        if len(ids) and (r_emb.shape != emb.shape or not np.allclose(r_emb, emb[order], rtol=1e-5, atol=1e-6)):
            raise ValueError("collection embeddings differ from the input after add beyond rounding")

        dropped_text = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dropped)
        manifest = {
            "format": INDEX_FORMAT,
            "collection": COLLECTION,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "embedding_model": model_id,
            "dim": int(emb.shape[1]) if emb.size else 0,
            "distance": "cosine",
            "n_chunks": len(chunks),
            "params": params,
            "sources": sources,
            "release": bool(sources) and all(s["status"] == "approved" for s in sources),
            "chromadb_version": chromadb_version(),
            "n_dropped": len(dropped),
            "dropped_chunks_sha256": hashlib.sha256(dropped_text.encode("utf-8")).hexdigest(),
            "content_hash": content_hash(r_ids, r_docs, r_metas, r_emb),
        }
        with (out / "chunks.jsonl").open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        (out / "dropped_chunks.jsonl").write_text(dropped_text, encoding="utf-8")
        (out / "index_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return cls(col, list(chunks), manifest)

    # ---------- φόρτωση ----------
    @classmethod
    def load(cls, in_dir: Path, expected_model: Optional[str] = None, allow_draft: bool = False,
             client_factory: Callable = _default_client) -> "ChromaIndex":
        d = Path(in_dir)
        m = json.loads((d / "index_manifest.json").read_text(encoding="utf-8"))
        if m.get("format") != INDEX_FORMAT:
            raise ValueError(f"unknown index format {m.get('format')}")
        if expected_model and m["embedding_model"] != expected_model:
            raise ValueError(f"index built with {m['embedding_model']}, query model is {expected_model}")
        if not m["release"] and not allow_draft:
            raise ValueError("draft index (contains non-approved sources); pass allow_draft=True only in development")

        col = client_factory(str(d / "chroma")).get_collection(name=m["collection"], embedding_function=None)
        if col.count() != m["n_chunks"]:
            raise ValueError(f"collection has {col.count()} chunks, manifest says {m['n_chunks']}")
        # Άλλη έκδοση chromadb μπορεί να επιστρέφει τα διανύσματα αλλιώς στρογγυλεμένα (βλ. «Ακεραιότητα»).
        built_with, running = m.get("chromadb_version"), chromadb_version()
        version_note = ""
        if built_with and running and built_with != running:
            version_note = (f"chromadb version differs: index built with chromadb {built_with}, "
                            f"running chromadb {running}")
            warnings.warn(version_note + "; the content_hash check may fail even without real changes",
                          RuntimeWarning, stacklevel=2)
        ids, docs, metas, emb = read_back(col, m["n_chunks"])
        if content_hash(ids, docs, metas, emb) != m["content_hash"]:
            msg = "collection content changed after the index was built (content_hash mismatch)"
            if version_note:
                msg += f". NOTE: {version_note}; install chromadb=={built_with} or rebuild/repair the index"
            raise ValueError(msg)
        by_id = {i: _chunk_from(i, doc, meta) for i, doc, meta in zip(ids, docs, metas)}
        # ίδια σειρά με το chunks.jsonl (σειρά εγγράφου)
        order = [json.loads(l)["chunk_id"] for l in (d / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l]
        if set(order) != set(by_id):
            raise ValueError("chunks.jsonl does not match the collection")
        return cls(col, [by_id[i] for i in order], m)

    @property
    def version(self) -> str:
        """Ταυτότητα έκδοσης της βάσης γνώσης για το audit."""
        return self.manifest["content_hash"][:16]

    # ---------- αναζήτηση ----------
    def search(self, query_vec: np.ndarray, query_text: str, k: int = 5, mode: str = "hybrid",
               pool: int = 50, exclude: frozenset[str] = frozenset()) -> list[Hit]:
        """exclude: chunk_id που αγνοούνται σαν να μην υπήρχαν (scripts/eval_retrieval.py --simulate-filters).
        Το dense ζητά τόσα περισσότερα από το Chroma ώστε να μείνουν pool, και οι θέσεις (για το RRF)
        μετριούνται χωρίς αυτά. Προσέγγιση: το BM25 κρατά τα IDF όλης της συλλογής."""
        if mode not in {"dense", "bm25", "hybrid"}:
            raise ValueError(f"unknown mode {mode}")
        n = len(self.chunks)
        if n == 0:
            return []
        pool = min(pool, n)
        res = self.collection.query(query_embeddings=[np.asarray(query_vec, dtype=np.float32).tolist()],
                                    n_results=min(n, pool + len(exclude)), include=["distances"])
        kept = [(i, dist) for i, dist in zip(res["ids"][0], res["distances"][0]) if i not in exclude][:pool]
        d_ids, d_dist = [i for i, _ in kept], [dist for _, dist in kept]
        dense = {self._pos[i]: 1.0 - float(dist) for i, dist in zip(d_ids, d_dist)}   # cosine distance -> ομοιότητα
        d_rank = {self._pos[i]: r for r, i in enumerate(d_ids, 1)}

        lex = self.bm25.scores(query_text)
        l_order = [int(i) for i in np.argsort(-lex, kind="stable")
                   if lex[i] > 0 and self.chunks[i].chunk_id not in exclude][:pool]
        l_rank = {i: r for r, i in enumerate(l_order, 1)}

        if mode == "dense":
            ranked = [(self._pos[i], dense[self._pos[i]]) for i in d_ids]
        elif mode == "bm25":
            ranked = [(i, float(lex[i])) for i in l_order]
        else:
            fused = Counter()
            for i, r in d_rank.items():
                fused[i] += 1.0 / (RRF_K + r)
            for i, r in l_rank.items():
                fused[i] += 1.0 / (RRF_K + r)
            ranked = sorted(fused.items(), key=lambda x: (-x[1], x[0]))
        return [Hit(self.chunks[i], s, d_rank.get(i), l_rank.get(i)) for i, s in ranked[:k]]
