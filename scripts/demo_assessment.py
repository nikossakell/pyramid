"""
Γρήγορη χειροκίνητη δοκιμή του Layer 1.
Τρέξτε από τον φάκελο nutriscan/:
    python scripts/demo_assessment.py --sex F --age 13 --weight 45
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from rule_engine.assessment import assess                  # noqa: E402
from rule_engine.data_loader import load_reference_values  # noqa: E402
from rule_engine.models import Sex, UserProfile            # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--sex", choices=["M", "F"], required=True)
p.add_argument("--age", type=int, required=True)
p.add_argument("--weight", type=float, default=None)
args = p.parse_args()

refs = load_reference_values(ROOT / "data" / "efsa_drv.csv")
profile = UserProfile("DEMO", Sex(args.sex), args.age, weight_kg=args.weight)
a = assess(profile, refs)

print(f"Φορτώθηκαν {len(refs)} γραμμές από efsa_drv.csv")
print(f"Παιδί: {args.sex}, {args.age} ετών, βάρος {args.weight or '—'} kg\n")
print(f"{'θρεπτικό':<18}{'τύπος':<7}{'τιμή':>10}  μονάδα")
for (nutrient, drv), r in sorted(a.references.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
    val = "—" if r.value is None else (f"{r.value}–{r.value_max}" if r.value_max else f"{r.value}")
    print(f"{nutrient:<18}{drv.value:<7}{val:>10}  {r.unit}")
if a.unavailable:
    print("\nΔεν αξιολογούνται:", ", ".join(f"{k} ({v})" for k, v in a.unavailable.items()))