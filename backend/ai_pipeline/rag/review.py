"""
ai_pipeline/rag/review.py — αξιολόγηση σε επίπεδο ΑΠΟΣΠΑΣΜΑΤΟΣ από άνθρωπο (Απόφαση 10).

Το hit@k του eval_retrieval.py μετρά μόνο αν βρέθηκε το σωστό PDF· με ένα PDF ανά θρεπτικό συστατικό
αυτό είναι σχεδόν δεδομένο και δεν λέει αν το απόσπασμα απαντά. Εδώ:
  write_review_csv()  γράφει για κάθε ερώτηση τα REVIEW_RANKS πρώτα αποσπάσματα (utf-8-sig, ανοίγει στο Excel)·
  ένας άνθρωπος συμπληρώνει τη στήλη ANSWER_COL με ναι / μερικώς / όχι·
  read_review() + score_review() (scripts/score_review.py) βγάζουν precision@1, answerable@3 κ.λπ.
"""
import csv
from pathlib import Path

REVIEW_RANKS = 3
REVIEW_TEXT_CHARS = 600
ANSWER_COL = "απαντά (ναι/μερικώς/όχι)"
COMMENT_COL = "σχόλιο"
REVIEW_COLUMNS = ["question", "expected_sources", "rank", "chunk_id", "source_id", "section", "pages", "score",
                  "text", ANSWER_COL, COMMENT_COL]
ANSWER_VALUES = {"ναι": 1.0, "μερικώς": 0.5, "όχι": 0.0}


class ReviewError(ValueError):
    pass


def review_rows(question: str, expected_sources: str, hits) -> list[dict]:
    """Γραμμές για μία ερώτηση από τα Hit του Retriever.search (τα πρώτα REVIEW_RANKS)."""
    rows = []
    for rank, h in enumerate(hits[:REVIEW_RANKS], 1):
        c = h.chunk
        rows.append({"question": question, "expected_sources": expected_sources, "rank": rank,
                     "chunk_id": c.chunk_id, "source_id": c.source_id, "section": c.section,
                     "pages": f"{c.page_start}" if c.page_start == c.page_end else f"{c.page_start}-{c.page_end}",
                     "score": f"{h.score:.4f}", "text": c.text[:REVIEW_TEXT_CHARS], ANSWER_COL: "", COMMENT_COL: ""})
    return rows


def write_review_csv(path: Path, rows: list[dict]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def read_review(path: Path) -> list[dict]:
    """Διαβάζει το συμπληρωμένο CSV. Κάθε τιμή του ANSWER_COL πρέπει να είναι ναι / μερικώς / όχι
    (χωρίς διάκριση πεζών/κεφαλαίων και κενών γύρω). Αλλιώς ReviewError με ΟΛΑ τα λάθη και τη γραμμή
    του αρχείου όπου αρχίζει η εγγραφή (το κείμενο μπορεί να πιάνει πολλές γραμμές)."""
    errors, rows = [], []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in ("question", "expected_sources", "rank", ANSWER_COL) if c not in (reader.fieldnames or [])]
        if missing:
            raise ReviewError(f"{path}: missing columns {missing}")
        start = reader.line_num + 1
        for row in reader:
            line, start = start, reader.line_num + 1
            value = (row[ANSWER_COL] or "").strip().lower()
            if value not in ANSWER_VALUES:
                errors.append(f"line {line}: '{row[ANSWER_COL]}' is not one of ναι / μερικώς / όχι "
                              f"({row['question']!r}, rank {row['rank']})")
            try:
                rank = int(row["rank"])
            except ValueError:
                errors.append(f"line {line}: rank '{row['rank']}' is not a number")
                continue
            rows.append({"line": line, "question": row["question"], "expected_sources": row["expected_sources"],
                         "rank": rank, "answer": value})
    seen = {}
    for r in rows:
        key = (r["question"], r["rank"])
        if key in seen:
            errors.append(f"line {r['line']}: duplicate rank {r['rank']} for {r['question']!r} (also line {seen[key]})")
        seen[key] = r["line"]
    for q in {r["question"] for r in rows}:
        if (q, 1) not in seen:
            errors.append(f"{q!r}: no rank 1 row")
    if errors:
        raise ReviewError("\n".join(errors))
    return rows


def score_review(rows: list[dict]) -> dict:
    """Εντός θέματος (expected_sources μη κενό): precision@1 (ναι=1, μερικώς=0.5, όχι=0), answerable@3
    (ποσοστό ερωτήσεων με τουλάχιστον ένα «ναι» στις θέσεις 1..3), ερωτήσεις χωρίς κανένα «ναι».
    Εκτός θέματος: ποσοστό ερωτήσεων με «ναι» σε οποιαδήποτε θέση (θα έπρεπε 0)."""
    by_q: dict[str, dict] = {}
    for r in rows:
        q = by_q.setdefault(r["question"], {"on_topic": bool(r["expected_sources"].strip()), "answers": {}})
        q["answers"][r["rank"]] = r["answer"]
    on = {q: v for q, v in by_q.items() if v["on_topic"]}
    off = {q: v for q, v in by_q.items() if not v["on_topic"]}
    has_yes = lambda v: any(a == "ναι" for rank, a in v["answers"].items() if rank <= REVIEW_RANKS)
    return {
        "on_topic_n": len(on),
        "precision_at_1": sum(ANSWER_VALUES[v["answers"][1]] for v in on.values()) / len(on) if on else None,
        "answerable_at_3": sum(has_yes(v) for v in on.values()) / len(on) if on else None,
        "no_yes": [q for q, v in on.items() if not has_yes(v)],
        "off_topic_n": len(off),
        "off_topic_yes_share": sum(has_yes(v) for v in off.values()) / len(off) if off else None,
        "off_topic_with_yes": [q for q, v in off.items() if has_yes(v)],
    }
