"""
Βήμα 4.1 → 7.1: συστηματική δοκιμή του Krikri ως presenter, πάνω σε ΣΥΝΘΕΤΙΚΕΣ αποφάσεις.

Για κάθε κανόνα × κάθε κατάσταση που φτάνει στο παιδί × εύρος ηλικίας × επαναλήψεις (διαφορετικό seed):
καλεί το Krikri, περνά την έξοδο από τον validator και καταγράφει. 10 κανόνες × ~4 καταστάσεις × 2 εύρη ×
3 επαναλήψεις = 228 κλήσεις: η αρχή των «100+ test cases» του Βήματος 7.1.

    python scripts/eval_krikri_presenter.py --base-url http://localhost:11434/v1 \\
        --model hf.co/ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M --repeats 3

Έξοδοι (στο eval_out/, εκτός git):
    krikri_eval.jsonl   όλα τα στοιχεία κάθε κλήσης
    krikri_review.csv   σταθερό κείμενο | κείμενο Krikri | πέρασε; | λόγοι — για αξιολόγηση από διαιτολόγο
Σύνοψη: ποσοστό που πέρασε τον validator, συχνότεροι λόγοι απόρριψης, χρόνος (διάμεσος, 95ο εκατοστημόριο).

ΠΡΟΣΟΧΗ: «πέρασε τον validator» σημαίνει ασφαλές ως προς τους κανόνες του 4.2, ΟΧΙ σωστό ή καλό. Το αν η
διατύπωση είναι κατάλληλη το κρίνει άνθρωπος στο krikri_review.csv.
"""
import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter, clean_output   # noqa: E402
from ai_pipeline.presentation.prompts import build_messages                          # noqa: E402
from ai_pipeline.presentation.safety_validator import validate_child_text            # noqa: E402
from ai_pipeline.presentation.templates import render_fallback                       # noqa: E402
from ai_pipeline.text.krikri_client import LLMError, OpenAICompatibleClient          # noqa: E402
from rule_engine.models import IntakeStatus as S, NutrientEvaluation                 # noqa: E402
from rule_engine.rules import all_nutrient_rules                                     # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--base-url", required=True)
p.add_argument("--model", default="hf.co/ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M")
p.add_argument("--repeats", type=int, default=3)
p.add_argument("--temperature", type=float, default=0.3)
p.add_argument("--timeout", type=float, default=60.0)
p.add_argument("--out", type=Path, default=ROOT / "eval_out")
args = p.parse_args()

client = OpenAICompatibleClient(args.base_url, args.model, timeout_s=args.timeout)
presenter = KrikriPresenter(client)      # για λεξικό και παραμέτρους· οι κλήσεις γίνονται εδώ, μία-μία
args.out.mkdir(parents=True, exist_ok=True)
rows, latencies, codes = [], [], Counter()

for rule in all_nutrient_rules():
    statuses = ([S.ABOVE_REFERENCE, S.LIKELY_ADEQUATE] if rule.nutrient_id == "sodium"
                else [S.LIKELY_INADEQUATE, S.UNCERTAIN, S.NO_CONCLUSION, S.LIKELY_ADEQUATE])
    for status in statuses:
        d = rule.decide(NutrientEvaluation(rule.nutrient_id, status, 4, None, "", {}))
        tid, template = render_fallback(d, presenter.lexicon)
        for age in (11, 14):
            msgs = build_messages(d, template, presenter.lexicon, age)
            for rep in range(args.repeats):
                row = {"rule_id": rule.rule_id, "status": status.value, "age_band": "10-12" if age <= 12 else "13-16",
                       "repeat": rep, "template_id": tid, "template": template}
                try:
                    r = client.generate(msgs, args.temperature, presenter.params["max_tokens"], seed=42 + rep)
                    text = clean_output(r.text)
                    v = validate_child_text(text, d, presenter.lexicon)
                    row.update(llm_text=text, raw=r.text, passed=v.passed, codes=sorted(v.codes),
                               details=[f.detail for f in v.failures], latency_s=round(r.latency_s, 2))
                    latencies.append(r.latency_s)
                    codes.update(v.codes)
                except LLMError as e:
                    row.update(llm_text=None, passed=False, codes=["LLM-ERROR"], details=[str(e)], latency_s=None)
                    codes["LLM-ERROR"] += 1
                rows.append(row)
                print(f"{rule.rule_id:8s} {status.value:17s} {row['age_band']} #{rep}: "
                      f"{'OK ' if row['passed'] else 'ΟΧΙ'} {row.get('llm_text') or row['details']}")

with (args.out / "krikri_eval.jsonl").open("w", encoding="utf-8") as f:
    meta = {"model": args.model, "base_url": args.base_url, "temperature": args.temperature,
            "params": presenter.params, "lexicon_versions": presenter.lexicon.versions}
    f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with (args.out / "krikri_review.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rule_id", "status", "age_band", "repeat", "σταθερό κείμενο", "κείμενο Krikri", "validator",
                "λόγοι", "κρίση διαιτολόγου (κατάλληλο/όχι)", "σχόλιο"])
    for r in rows:
        w.writerow([r["rule_id"], r["status"], r["age_band"], r["repeat"], r["template"], r.get("llm_text") or "",
                    "OK" if r["passed"] else "ΑΠΟΡΡΙΦΘΗΚΕ", "; ".join(r["codes"]), "", ""])

n = len(rows)
passed = sum(r["passed"] for r in rows)
print(f"\nΣύνολο: {n} κλήσεις, πέρασαν τον validator {passed} ({passed / n:.0%}).")
print("Λόγοι απόρριψης:", dict(codes.most_common()))
if latencies:
    q = statistics.quantiles(latencies, n=20) if len(latencies) >= 20 else [max(latencies)] * 19
    print(f"Χρόνος ανά κλήση: διάμεσος {statistics.median(latencies):.1f} s, 95ο εκατοστημόριο {q[18]:.1f} s")
print(f"Αρχεία: {args.out / 'krikri_eval.jsonl'}, {args.out / 'krikri_review.csv'}")
