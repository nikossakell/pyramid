"""
Βήμα 4.1 — demo: τι θα έβλεπε το παιδί με το Krikri, πάνω σε ΣΥΝΘΕΤΙΚΑ δεδομένα (όχι πραγματικό παιδί).
Τρέξτε από τον φάκελο nutriscan/.

    # χωρίς μοντέλο: ψεύτικες απαντήσεις (μία σωστή, μία με αριθμό) για να φανεί το fallback
    python scripts/demo_krikri.py --fake

    # με πραγματικό Krikri τοπικά (Ollama ή llama.cpp, βλ. οδηγίες)
    python scripts/demo_krikri.py --base-url http://localhost:11434/v1 --model hf.co/ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M
    python scripts/demo_krikri.py --base-url http://localhost:8080/v1  --model krikri --sex M --age 15 --profile high
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter                  # noqa: E402
from ai_pipeline.presentation.lexicon import default_lexicon                           # noqa: E402
from ai_pipeline.text.krikri_client import OpenAICompatibleClient, ScriptedClient      # noqa: E402
from rule_engine.data_loader import load_reference_values                              # noqa: E402
from rule_engine.engine import NutritionRuleEngine                                     # noqa: E402
from rule_engine.models import DailyIntake, EvaluationContext, Sex, UserProfile        # noqa: E402
from rule_engine.safety_rules import RiskLevel, SafetySignals                          # noqa: E402

PROFILES = {   # ΣΥΝΘΕΤΙΚΕΣ ημερήσιες τιμές, ίδιες με τα tests
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
p.add_argument("--fake", action="store_true", help="ψεύτικο LLM (χωρίς μοντέλο)")
p.add_argument("--base-url", help="π.χ. http://localhost:11434/v1 (Ollama) ή http://localhost:8080/v1 (llama.cpp)")
p.add_argument("--model", default="hf.co/ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M")
p.add_argument("--timeout", type=float, default=60.0, help="η πρώτη κλήση φορτώνει το μοντέλο: αργεί")
p.add_argument("--retries", type=int, default=0)
p.add_argument("--audit", action="store_true", help="τύπωσε και το audit record κάθε μηνύματος")
args = p.parse_args()

if args.fake:
    calls = {"n": 0}

    def fake(messages):
        calls["n"] += 1
        tpl = messages[1]["content"].split("Εγκεκριμένο μήνυμα: ")[1].split("\n")[0]
        if calls["n"] == 2:                       # δεύτερο μήνυμα: σκόπιμα λάθος, για να φανεί το fallback
            return "Χρειάζεσαι 1000 mg την ημέρα, φάε δύο μερίδες!"
        return "Γεια! " + tpl
    client = ScriptedClient(fake, model_id="fake-demo")
elif args.base_url:
    client = OpenAICompatibleClient(args.base_url, args.model, timeout_s=args.timeout)
    try:
        print("Διαθέσιμα μοντέλα στον server:", client.available_models())
    except Exception as e:
        sys.exit(f"Ο server του μοντέλου δεν απαντά ({e}). Τρέχει το Ollama / llama-server;")
else:
    client = None
    print("(χωρίς --fake ή --base-url: μόνο σταθερά κείμενα)\n")

refs = load_reference_values(ROOT / "data" / "efsa_drv.csv")
start = date(2026, 10, 1)
days = tuple(DailyIntake(start + timedelta(days=i), dict(PROFILES[args.profile]), True) for i in range(4))
ctx = EvaluationContext(UserProfile("P-DEMO", Sex(args.sex), args.age, weight_kg=45.0),
                        start + timedelta(days=3), days, tuple(refs))
signals = SafetySignals(RiskLevel(args.risk), "disordered_eating" if args.risk != "none" else None)
result = NutritionRuleEngine(data_versions=default_lexicon().versions).evaluate(ctx, signals)

print(f"Προφίλ: {args.sex}, {args.age} ετών, '{args.profile}', κίνδυνος: {args.risk}\n")
messages = KrikriPresenter(client, retries=args.retries).present_all(result)
if result.withheld:
    print(f"Κρατήθηκαν λόγω ασφάλειας: {[d.rule_id for d in result.withheld]} (το Krikri δεν κλήθηκε)")
for m in messages:
    tag = {"llm": "KRIKRI", "template": "ΣΤΑΘΕΡΟ", "none": "ΤΙΠΟΤΑ"}[m.source]
    extra = f" (λόγος: {m.reason}; απορρίψεις validator: {[list(f) for f in m.llm_failures]})" if m.reason else ""
    print(f"[{m.decision.rule_id} | {tag} | {m.latency_s:.1f} s]{extra}")
    print(f"  {m.text}\n")
    if args.audit:
        print(json.dumps(m.audit(), ensure_ascii=False, indent=2), "\n")
