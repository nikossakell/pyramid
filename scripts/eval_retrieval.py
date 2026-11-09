"""
Έλεγχος ανάκτησης (Βήμα 5.1, πριν το Krikri): βρίσκει η αναζήτηση το σωστό έγγραφο για ερωτήσεις
όπως θα τις έγραφε ένα παιδί;

    python scripts/eval_retrieval.py                 # με το backend/rag_db και το e5
    python scripts/eval_retrieval.py --k 5 --show 3  # + τα 3 πρώτα κομμάτια ανά ερώτηση
    python scripts/eval_retrieval.py --review-csv eval_review.csv          # CSV για κρίση από άνθρωπο
    python scripts/eval_retrieval.py --simulate-filters --review-csv f.csv # σαν να είχαν εφαρμοστεί τα φίλτρα

Μετρά για κάθε τρόπο (dense, bm25, hybrid):
- hit@1, hit@k: ποσοστό ερωτήσεων όπου κάποια από τις αναμενόμενες πηγές είναι 1η / στις k πρώτες,
- MRR: μέσος όρος 1/θέση του πρώτου σωστού.
Για τις ερωτήσεις ΕΚΤΟΣ ΘΕΜΑΤΟΣ (κενό expected_sources) τυπώνει το καλύτερο σκορ συνημιτόνου, για να
φανεί αν υπάρχει κατώφλι που χωρίζει «έχω πηγή» από «δεν έχω αξιόπιστη πληροφορία» (5.2).

ΠΕΡΙΟΡΙΣΜΟΣ: οι αναμενόμενες πηγές στο rag_eval_questions.csv είναι ΠΡΟΣΧΕΔΙΟ· πρέπει να επιβεβαιωθούν
από όποιον διαβάσει τα έγγραφα. Μετράμε έγγραφο, όχι σελίδα.

--review-csv (Απόφαση 10): για ΚΑΘΕ ερώτηση (και εκτός θέματος) τα 3 πρώτα αποσπάσματα του --review-mode,
με κενές στήλες «απαντά (ναι/μερικώς/όχι)» και «σχόλιο» για άνθρωπο· βαθμολόγηση με scripts/score_review.py.

--simulate-filters (Απόφαση 9): τρέχει το chunk_filter.classify στο rag_db/chunks.jsonl και αγνοεί στην
αναζήτηση όσα κομμάτια θα κόβονταν (με μεγαλύτερο pool ώστε να μένουν k). Δείχνει το αποτέλεσμα των
φίλτρων χωρίς rebuild· δεν αλλάζει τίποτα στο rag_db.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.rag import chunk_filter            # noqa: E402
from ai_pipeline.rag.chunking import Chunk          # noqa: E402
from ai_pipeline.rag.retriever import Retriever     # noqa: E402
from ai_pipeline.rag.review import review_rows, write_review_csv, REVIEW_RANKS   # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--rag-db", default=ROOT / "backend" / "rag_db", type=Path)
p.add_argument("--questions", default=ROOT / "data" / "rag_eval_questions.csv", type=Path)
p.add_argument("--k", type=int, default=5)
p.add_argument("--show", type=int, default=0)
p.add_argument("--device", default=None)
p.add_argument("--revision", default=None)
p.add_argument("--allow-draft", action="store_true")
p.add_argument("--hashing", action="store_true", help="HashingEmbedder αντί για e5 (μόνο για δοκιμή του script)")
p.add_argument("--review-csv", type=Path, default=None, help="γράψε CSV για κρίση αποσπασμάτων από άνθρωπο")
p.add_argument("--review-mode", choices=("dense", "bm25", "hybrid"), default="hybrid")
p.add_argument("--simulate-filters", action="store_true",
               help="αγνόησε όσα κομμάτια θα έκοβε το chunk_filter (χωρίς rebuild)")
args = p.parse_args()

exclude: frozenset[str] = frozenset()
if args.simulate_filters:
    reasons = {}
    for line in (args.rag_db / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            c = Chunk(**json.loads(line))
            reasons[c.chunk_id] = chunk_filter.classify(c)
    exclude = frozenset(cid for cid, r in reasons.items() if r)
    by_reason = Counter(r for r in reasons.values() if r)
    print(f"Προσομοίωση φίλτρων (chunk_filter v{chunk_filter.CHUNK_FILTER_VERSION}): κόβονται {len(exclude)} από "
          f"{len(reasons)} κομμάτια: " + ", ".join(f"{r}={by_reason.get(r, 0)}" for r in chunk_filter.REASONS))
    by_source = Counter(cid.split(":")[0] for cid in exclude)
    print("  ανά πηγή: " + ", ".join(f"{s}={n}" for s, n in sorted(by_source.items())) + "\n")

if args.hashing:
    from ai_pipeline.rag.embedder import HashingEmbedder
    embedder = HashingEmbedder()
else:
    from ai_pipeline.rag.embedder import E5Embedder
    embedder = E5Embedder(revision=args.revision, device=args.device)
retriever = Retriever.from_dir(args.rag_db, embedder, allow_draft=args.allow_draft)
present = {c.source_id for c in retriever.index.chunks if c.chunk_id not in exclude}

with args.questions.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

for mode in ("dense", "bm25", "hybrid"):
    hits1 = hitsk = rr = n = 0
    misses = []
    for row in rows:
        expected = {s for s in row["expected_sources"].split(";") if s} & present
        if not expected:
            continue
        n += 1
        ranked = [h.chunk.source_id for h in retriever.search(row["question"], k=args.k, mode=mode, exclude=exclude)]
        pos = next((i for i, s in enumerate(ranked, 1) if s in expected), None)
        hits1 += pos == 1
        hitsk += pos is not None
        rr += 1 / pos if pos else 0
        if pos is None:
            misses.append(row["question"])
    if n:
        print(f"{mode:7s} n={n:2d}  hit@1={hits1 / n:.0%}  hit@{args.k}={hitsk / n:.0%}  MRR={rr / n:.2f}"
              + (f"  χωρίς επιτυχία: {misses}" if misses else ""))

print("\nΚαλύτερο σκορ συνημιτόνου (dense):")
for row in rows:
    expected = {s for s in row["expected_sources"].split(";") if s}
    top = retriever.search(row["question"], k=max(1, args.show), mode="dense", exclude=exclude)
    tag = "ΕΚΤΟΣ" if not expected else ("     " if expected & present else "(πηγή όχι στο ευρετήριο)")
    print(f"  {top[0].score:.3f} {tag} {row['question']}" if top else f"  -     {row['question']}")
    for h in top[:args.show]:
        print(f"         {h.chunk.chunk_id} σελ.{h.chunk.page_start} | {h.chunk.text[:120]}…")

if args.review_csv:
    out = []
    for row in rows:
        hits = retriever.search(row["question"], k=REVIEW_RANKS, mode=args.review_mode, exclude=exclude)
        out += review_rows(row["question"], row["expected_sources"], hits)
    write_review_csv(args.review_csv, out)
    print(f"\nCSV αξιολόγησης ({args.review_mode}, {len(rows)} ερωτήσεις, {len(out)} γραμμές): {args.review_csv}")
