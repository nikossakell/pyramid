"""
Γρήγορη χειροκίνητη δοκιμή του Layer 2 με ΣΥΝΘΕΤΙΚΕΣ ημέρες (όχι πραγματικά τρόφιμα).
Τρέξτε από τον φάκελο nutriscan/:
    python scripts/demo_evaluation.py --sex F --age 13 --iron 9 --days 4
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rule_engine.assessment import assess                  # noqa: E402
from rule_engine.data_loader import load_reference_values  # noqa: E402
from rule_engine.evaluation import evaluate_intake         # noqa: E402
from rule_engine.models import DailyIntake, EvaluationContext, Sex, UserProfile  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--sex", choices=["M", "F"], required=True)
p.add_argument("--age", type=int, required=True)
p.add_argument("--weight", type=float, default=None)
p.add_argument("--days", type=int, default=4, help="πλήρεις ημέρες στο παράθυρο")
p.add_argument("--iron", type=float, default=9.0, help="mg/ημέρα")
p.add_argument("--calcium", type=float, default=800.0, help="mg/ημέρα")
p.add_argument("--fibre", type=float, default=15.0, help="g/ημέρα")
p.add_argument("--sodium", type=float, default=2.4, help="g/ημέρα")
p.add_argument("--protein", type=float, default=55.0, help="g/ημέρα")
args = p.parse_args()

refs = load_reference_values(ROOT / "data" / "efsa_drv.csv")
profile = UserProfile("DEMO", Sex(args.sex), args.age, weight_kg=args.weight)
start = date(2026, 10, 1)
day_totals = {"iron": args.iron, "calcium": args.calcium, "fibre": args.fibre,
              "sodium": args.sodium, "protein": args.protein}
days = tuple(DailyIntake(start + timedelta(days=i), day_totals, True) for i in range(args.days))
ctx = EvaluationContext(profile, start + timedelta(days=args.days - 1), days, refs)

results = evaluate_intake(ctx, assess(profile, refs))
print(f"Παιδί: {args.sex}, {args.age} ετών, βάρος {args.weight or '—'} kg · {args.days} πλήρεις ημέρες\n")
for n in ["iron", "calcium", "fibre", "sodium", "protein"]:
    ev = results[n]
    extra = f"πρόσληψη {ev.usual_intake} {ev.unit} · αναφορά {ev.reference_values}" if ev.usual_intake is not None else ev.reason
    print(f"{n:<9} {ev.status.value:<18} {extra}")