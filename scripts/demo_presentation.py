"""
Χειροκίνητη δοκιμή του Βήματος 4.2: τι θα έβλεπε το παιδί, και τι κρίνει ο validator.
ΣΥΝΘΕΤΙΚΕΣ ημέρες, όχι πραγματικά δεδομένα. Τρέξτε από τον φάκελο nutriscan/:
    python scripts/demo_presentation.py --sex F --age 13 --profile low
    python scripts/demo_presentation.py --sex M --age 15 --profile high
    python scripts/demo_presentation.py --sex F --age 13 --profile low --risk moderate
    python scripts/demo_presentation.py --check "Φάε δύο μερίδες όσπρια για σίδηρο"
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.presentation.lexicon import default_lexicon                           # noqa: E402
from ai_pipeline.presentation.safety_validator import validate_child_text              # noqa: E402
from ai_pipeline.presentation.templates import TemplateError, render_fallback          # noqa: E402
from rule_engine.data_loader import load_reference_values                              # noqa: E402
from rule_engine.engine import NutritionRuleEngine                                     # noqa: E402
from rule_engine.models import DailyIntake, EvaluationContext, IntakeStatus, RuleDecision, Sex, UserProfile  # noqa: E402
from rule_engine.safety_rules import RiskLevel, SafetySignals                          # noqa: E402

PROFILES = {
    "low": {"iron": 3, "calcium": 300, "fibre": 6, "sodium": 1.0, "protein": 15,
            "vitamin_a": 150, "vitamin_c": 20, "folate": 80, "vitamin_d": 2, "vitamin_b12": 1.0},
    "high": {"iron": 20, "calcium": 1500, "fibre": 30, "sodium": 3.5, "protein": 120,
             "vitamin_a": 1000, "vitamin_c": 150, "folate": 450, "vitamin_d": 20, "vitamin_b12": 6.0},
}

p = argparse.ArgumentParser()
p.add_argument("--sex", choices=["M", "F"], default="F")
p.add_argument("--age", type=int, default=13)
p.add_argument("--profile", choices=list(PROFILES), default="low")
p.add_argument("--risk", choices=["none", "moderate", "high"], default="none")
p.add_argument("--check", help="έλεγχος ελεύθερου κειμένου ως απάντηση για τον σίδηρο (likely_inadequate)")
args = p.parse_args()

if args.check:
    d = RuleDecision("R-FE-01", "0.1", "iron", IntakeStatus.LIKELY_INADEQUATE, 4, "-",
                     food_group_hint=("legumes", "meat", "fish", "leafy_greens", "vitamin_c_foods"))
    r = validate_child_text(args.check, d)
    print("ΠΕΡΝΑ" if r.passed else "ΑΠΟΡΡΙΠΤΕΤΑΙ")
    for f in r.failures:
        print(f"  {f.code}: {f.detail}")
    sys.exit(0)

refs = load_reference_values(ROOT / "data" / "efsa_drv.csv")
start = date(2026, 10, 1)
days = tuple(DailyIntake(start + timedelta(days=i), dict(PROFILES[args.profile]), True) for i in range(4))
ctx = EvaluationContext(UserProfile("P-DEMO", Sex(args.sex), args.age, weight_kg=45.0),
                        start + timedelta(days=3), days, tuple(refs))
signals = SafetySignals(RiskLevel(args.risk), "disordered_eating" if args.risk != "none" else None)
result = NutritionRuleEngine(data_versions=default_lexicon().versions).evaluate(ctx, signals)

print(f"Προφίλ: {args.sex}, {args.age} ετών, '{args.profile}', κίνδυνος: {args.risk}\n")
if not result.feedback:
    print("Κανένα μήνυμα στο παιδί.", f"Κρατήθηκαν λόγω ασφάλειας: {[d.rule_id for d in result.withheld]}"
          if result.withheld else "")
for d in result.feedback:
    try:
        tid, text = render_fallback(d)
    except TemplateError as e:
        print(f"[{d.rule_id}] χωρίς κείμενο: {e}")
        continue
    v = validate_child_text(text, d, safety=result.safety)
    print(f"[{d.rule_id} | {tid} | validator: {'OK' if v.passed else sorted(v.codes)}]")
    print(f"  {text}")
    print(f"  (μόνο για την έρευνα: {d.research_values})\n")
