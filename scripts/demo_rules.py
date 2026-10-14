"""
Χειροκίνητη δοκιμή Layers 1-3 με ΣΥΝΘΕΤΙΚΕΣ ημέρες (όχι πραγματικά τρόφιμα).
Τρέξτε από τον φάκελο nutriscan/:
    python scripts/demo_rules.py --sex F --age 13
    python scripts/demo_rules.py --sex F --age 13 --risk high
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rule_engine.assessment import assess                                        # noqa: E402
from rule_engine.data_loader import load_reference_values                        # noqa: E402
from rule_engine.evaluation import evaluate_intake                               # noqa: E402
from rule_engine.models import DailyIntake, EvaluationContext, Sex, UserProfile  # noqa: E402
from rule_engine.recommendations import apply_recommendation_rules, select_daily_feedback  # noqa: E402
from rule_engine.safety_rules import RiskLevel, SafetySignals, apply_safety, evaluate_safety  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--sex", choices=["M", "F"], required=True)
p.add_argument("--age", type=int, required=True)
p.add_argument("--weight", type=float, default=None)
p.add_argument("--days", type=int, default=4)
p.add_argument("--risk", choices=["none", "moderate", "high"], default="none")
args = p.parse_args()

# Συνθετικές ημερήσιες τιμές (ίδιες κάθε ημέρα)
totals = {"iron": 9.0, "calcium": 800.0, "fibre": 15.0, "sodium": 2.4, "protein": 55.0,
          "vitamin_c": 80.0, "vitamin_d": 3.0, "folate": 300.0, "vitamin_a": 650.0, "vitamin_b12": 4.5}
refs = load_reference_values(ROOT / "data" / "efsa_drv.csv")
profile = UserProfile("DEMO", Sex(args.sex), args.age, weight_kg=args.weight)
start = date(2026, 10, 1)
days = tuple(DailyIntake(start + timedelta(days=i), totals, True) for i in range(args.days))
ctx = EvaluationContext(profile, start + timedelta(days=args.days - 1), days, refs)

decisions = apply_recommendation_rules(evaluate_intake(ctx, assess(profile, refs)))
print("Όλες οι αποφάσεις (audit):")
for d in decisions:
    print(f"  {d.rule_id:<9} {d.status.value:<18} {d.message_template_id:<30} hint={list(d.food_group_hint)}")

safety = evaluate_safety(SafetySignals(text_risk_level=RiskLevel(args.risk)))
out = apply_safety(select_daily_feedback(decisions), safety)
print(f"\nΑσφάλεια: κανόνες={list(safety.rule_ids)} ενέργειες={[a.value for a in safety.actions]}")
print("Στο παιδί σήμερα:", [d.message_template_id for d in out.to_child] or "τίποτα")
if out.withheld:
    print("Κρατήθηκαν λόγω ασφάλειας:", [d.message_template_id for d in out.withheld])
