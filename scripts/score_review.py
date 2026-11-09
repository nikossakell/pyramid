"""
Βαθμολόγηση της αξιολόγησης σε επίπεδο αποσπάσματος (Απόφαση 10).

    python scripts/eval_retrieval.py --allow-draft --review-csv eval_review.csv
    # ένας άνθρωπος συμπληρώνει τη στήλη «απαντά (ναι/μερικώς/όχι)» (και, αν θέλει, «σχόλιο»)
    python scripts/score_review.py eval_review.csv

Εντός θέματος (μη κενό expected_sources): precision@1 (ναι=1, μερικώς=0.5, όχι=0), answerable@3,
ερωτήσεις χωρίς κανένα «ναι». Εκτός θέματος: ποσοστό με «ναι» (θα έπρεπε 0).
ΣΗΜΕΙΩΣΗ: όσες ερωτήσεις έχουν αναμενόμενη πηγή που δεν είναι ακόμα στο ευρετήριο (π.χ. μόνο
gr_guide_children) μετρούν ως εντός θέματος και αναμένεται να μην έχουν «ναι».
Κωδικός εξόδου 1 αν κάποια τιμή δεν είναι ναι / μερικώς / όχι (με αριθμό γραμμής).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.rag.review import ReviewError, read_review, score_review   # noqa: E402

p = argparse.ArgumentParser(description="precision@1 / answerable@3 από συμπληρωμένο CSV αξιολόγησης")
p.add_argument("csv", type=Path)
args = p.parse_args()

try:
    s = score_review(read_review(args.csv))
except ReviewError as e:
    print(f"ΣΦΑΛΜΑ στο {args.csv}:\n{e}", file=sys.stderr)
    sys.exit(1)

pct = lambda x: "-" if x is None else f"{x:.0%}"
print(f"Εντός θέματος (n={s['on_topic_n']}): precision@1="
      f"{'-' if s['precision_at_1'] is None else format(s['precision_at_1'], '.2f')}  "
      f"answerable@3={pct(s['answerable_at_3'])}")
print(f"  χωρίς κανένα «ναι» ({len(s['no_yes'])}):")
for q in s["no_yes"]:
    print(f"    - {q}")
print(f"Εκτός θέματος (n={s['off_topic_n']}): με «ναι» {pct(s['off_topic_yes_share'])} (θα έπρεπε 0)"
      + (f": {s['off_topic_with_yes']}" if s["off_topic_with_yes"] else ""))
