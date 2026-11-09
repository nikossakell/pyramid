"""
Επισκευή του content_hash ενός ΥΠΑΡΧΟΝΤΟΣ ευρετηρίου RAG χωρίς rebuild.

Γιατί: μέχρι το index.py της 2026-11-09 το build() υπολόγιζε το content_hash από τα διανύσματα ΠΡΙΝ το
col.add(), ενώ το load() από ό,τι επιστρέφει το Chroma. Το chromadb 1.5 με cosine κανονικοποιεί ό,τι
αποθηκεύει, άρα κάποια διανύσματα επιστρέφονται με απόκλιση ~1 ulp και το load() απέτυχε με
«content_hash mismatch» χωρίς πραγματική αλλοίωση.

Το script ΔΕΝ εμπιστεύεται τη συλλογή: ελέγχει ανεξάρτητα, με βάση το chunks.jsonl (γραμμένο στο build()
από τα ίδια chunks), ότι
  - τα ids είναι ακριβώς τα ίδια (πλήθος, σύνολο, χωρίς διπλά),
  - κάθε κείμενο είναι ίδιο με του chunks.jsonl και έχει sha256 ίσο με το text_sha256,
  - κάθε πεδίο μεταδεδομένων έχει ίδια τιμή ΚΑΙ ίδιο τύπο, χωρίς επιπλέον ή χαμένα κλειδιά,
  - κάθε διάνυσμα έχει διάσταση ίση με το "dim" του manifest, πεπερασμένες τιμές και νόρμα 1±1e-3,
  - δύο διαδοχικές αναγνώσεις (read_back) δίνουν το ίδιο hash.
Μόνο αν ΟΛΑ περνούν ΚΑΙ δοθεί --write, γράφει στο index_manifest.json:
  content_hash (νέο, από read_back), content_hash_before_repair (το παλιό), content_hash_repaired_at.
Αλλιώς δεν γράφει τίποτα. Κωδικός εξόδου 1 αν αποτύχει οποιοσδήποτε έλεγχος.

ΣΗΜΕΙΩΣΗ: το chromadb, μόλις ανοίξει τη βάση, προσθέτει μια γραμμή κλειδώματος (acquire_write) στο
chroma.sqlite3. Αυτό γίνεται σε κάθε άνοιγμα (και στο load()) και δεν αλλάζει το περιεχόμενο.

    python scripts/repair_rag_hash.py            # μόνο έλεγχος (dry run)
    python scripts/repair_rag_hash.py --write    # έλεγχος + εγγραφή αν όλα περνούν
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.rag.index import INDEX_FORMAT, META_FIELDS, content_hash, read_back  # noqa: E402

NORM_TOL = 1e-3
MAX_EXAMPLES = 3

p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
p.add_argument("--db", default=ROOT / "backend" / "rag_db", type=Path)
p.add_argument("--write", action="store_true", help="γράψε το νέο content_hash αν περνούν όλοι οι έλεγχοι")
args = p.parse_args()

failures: list[str] = []


def check(name: str, bad: list, detail: str = "") -> None:
    ok = not bad
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)
        for b in bad[:MAX_EXAMPLES]:
            print(f"         e.g. {b}")
        if len(bad) > MAX_EXAMPLES:
            print(f"         ... {len(bad)} in total")


manifest_path = args.db / "index_manifest.json"
manifest_bytes = manifest_path.read_bytes()
m = json.loads(manifest_bytes.decode("utf-8"))
rows = [json.loads(l) for l in (args.db / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l]
n, dim = m.get("n_chunks"), m.get("dim")
print(f"rag_db: {args.db}\nmanifest: format={m.get('format')} collection={m.get('collection')} "
      f"n_chunks={n} dim={dim}\n          content_hash={m.get('content_hash')}")

print("\n[manifest / chunks.jsonl]")
check("manifest format", [] if m.get("format") == INDEX_FORMAT else [m.get("format")], INDEX_FORMAT)
check("chunks.jsonl rows == n_chunks", [] if len(rows) == n else [f"{len(rows)} != {n}"], f"{len(rows)} rows")
dup_ref = [k for k, c in Counter(r["chunk_id"] for r in rows).items() if c > 1]
check("chunks.jsonl ids unique", dup_ref)
check("chunks.jsonl text_sha256 == sha256(text)",
      [r["chunk_id"] for r in rows if hashlib.sha256(r["text"].encode("utf-8")).hexdigest() != r["text_sha256"]])
ref = {r["chunk_id"]: r for r in rows}

import chromadb  # noqa: E402

col = chromadb.PersistentClient(path=str(args.db / "chroma")).get_collection(name=m["collection"],
                                                                              embedding_function=None)
got = col.get(include=["documents", "metadatas", "embeddings"], limit=max(n, 1))
ids = list(got["ids"])

print("\n[ids]")
check("collection.count() == n_chunks", [] if col.count() == n else [f"{col.count()} != {n}"], f"count={col.count()}")
check("get() returned n_chunks records", [] if len(ids) == n else [f"{len(ids)} != {n}"])
check("collection ids unique", [k for k, c in Counter(ids).items() if c > 1])
check("ids only in chunks.jsonl", sorted(set(ref) - set(ids)))
check("ids only in collection", sorted(set(ids) - set(ref)))
common = [i for i in ids if i in ref]

print("\n[documents]")
docs = dict(zip(ids, got["documents"] or [None] * len(ids)))
check("documents are str", [i for i in common if not isinstance(docs[i], str)])
check("sha256(document) == text_sha256",
      [i for i in common if not isinstance(docs[i], str)
       or hashlib.sha256(docs[i].encode("utf-8")).hexdigest() != ref[i]["text_sha256"]])
check("document == chunks.jsonl text", [i for i in common if docs[i] != ref[i]["text"]])

print("\n[metadatas]  (value AND type, no extra/missing keys)")
metas = dict(zip(ids, got["metadatas"] or [None] * len(ids)))
extra, missing, wrong = [], [], []
for i in common:
    meta = metas[i] or {}
    extra += [f"{i}: +{k}={meta[k]!r}" for k in sorted(set(meta) - set(META_FIELDS))]
    missing += [f"{i}: -{k}" for k in META_FIELDS if k not in meta]
    wrong += [f"{i}: {k} jsonl={ref[i][k]!r} ({type(ref[i][k]).__name__}) "
              f"chroma={meta[k]!r} ({type(meta[k]).__name__})"
              for k in META_FIELDS if k in meta and (type(meta[k]) is not type(ref[i][k]) or meta[k] != ref[i][k])]
types = {k: dict(Counter(type((metas[i] or {}).get(k)).__name__ for i in common)) for k in META_FIELDS}
check("no extra metadata keys", extra)
check("no missing metadata keys", missing)
check("metadata value and type == chunks.jsonl", wrong, "types: " + ", ".join(
    f"{k}={'/'.join(v)}" for k, v in types.items()))

print("\n[embeddings]")
raw = got["embeddings"]
emb_bad = []
if raw is None:
    emb_bad.append("get() returned no embeddings")
    E = np.zeros((0, 0), np.float32)
else:
    try:
        E = np.asarray(raw, dtype=np.float64)
    except ValueError as e:   # διανύσματα διαφορετικού μήκους
        emb_bad.append(f"ragged embeddings: {e}")
        E = np.zeros((0, 0))
desc = f"container={type(raw).__name__}" + (f" dtype={raw.dtype}" if isinstance(raw, np.ndarray) else "")
check("embeddings present, 2-D", emb_bad + ([] if E.ndim == 2 else [f"ndim={E.ndim}"]), desc)
check("shape == (n_chunks, manifest dim)", [] if E.shape == (n, dim) else [f"{E.shape} != {(n, dim)}"],
      f"shape={E.shape}")
if E.ndim == 2 and E.size:
    finite = np.isfinite(E).all(axis=1)
    norms = np.linalg.norm(E, axis=1)
    check("all values finite", [ids[k] for k in np.flatnonzero(~finite)])
    check(f"norm == 1 ± {NORM_TOL}", [f"{ids[k]}: norm={norms[k]:.6f}" for k in np.flatnonzero(np.abs(norms - 1) > NORM_TOL)],
          f"min={norms.min():.6f} max={norms.max():.6f}")
    check("float32-exact (no precision lost by the float32 hash)",
          [] if np.array_equal(E, E.astype(np.float32).astype(np.float64)) else ["values not representable in float32"])
else:
    check("embeddings non-empty", ["empty"])

print("\n[content_hash]")
new_hash = None
try:
    h1 = content_hash(*read_back(col, n))
    h2 = content_hash(*read_back(col, n))
    check("read_back is deterministic (two reads, same hash)", [] if h1 == h2 else [f"{h1} != {h2}"])
    new_hash = h1
except ValueError as e:
    check("read_back succeeds", [str(e)])
old_hash = m.get("content_hash")
print(f"  manifest content_hash : {old_hash}")
print(f"  read_back content_hash: {new_hash}")
if "content_hash_before_repair" in m and new_hash != old_hash:
    check("manifest not repaired before", [f"already has content_hash_before_repair="
                                           f"{m['content_hash_before_repair']}; refusing to overwrite it"])

print()
if failures:
    print(f"FAILED ({len(failures)} checks): {failures}\nNothing written.")
    sys.exit(1)
if new_hash == old_hash:
    print("All checks passed. content_hash already matches the collection: nothing to repair.")
    sys.exit(0)
if not args.write:
    print("All checks passed. DRY RUN: nothing written. Re-run with --write to store the new content_hash.")
    sys.exit(0)

if manifest_path.read_bytes() != manifest_bytes:
    print("index_manifest.json changed while checking. Nothing written.")
    sys.exit(1)
m["content_hash_before_repair"] = old_hash
m["content_hash"] = new_hash
m["content_hash_repaired_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")   # ίδια μορφή με build()
print(f"Written: content_hash {old_hash} -> {new_hash}\n         (old value kept in content_hash_before_repair)")
