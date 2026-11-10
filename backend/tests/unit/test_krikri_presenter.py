"""Βήμα 4.1: Krikri presenter με ΨΕΥΤΙΚΟ LLM (ScriptedClient) και ψεύτικο HTTP server.
Οι «απαντήσεις του Krikri» εδώ είναι επινοημένες για να ελεγχθεί η ροή, όχι πραγματικές έξοδοι του μοντέλου."""
import json
import re
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter, clean_output
from ai_pipeline.presentation.prompts import age_band, build_messages
from ai_pipeline.presentation.lexicon import default_lexicon
from ai_pipeline.presentation.templates import render_fallback
from ai_pipeline.text.krikri_client import LLMError, OpenAICompatibleClient, ScriptedClient
from rule_engine.data_loader import load_reference_values
from rule_engine.engine import NutritionRuleEngine
from rule_engine.models import DailyIntake, EvaluationContext, IntakeStatus, NutrientEvaluation, Sex, UserProfile
from rule_engine.rules import all_nutrient_rules
from rule_engine.safety_rules import RiskLevel, SafetySignals, evaluate_safety

S = IntakeStatus
ROOT = Path(__file__).resolve().parents[3]
IRON = next(r for r in all_nutrient_rules() if r.nutrient_id == "iron")
SODIUM = next(r for r in all_nutrient_rules() if r.nutrient_id == "sodium")
GOOD_IRON = "Δοκίμασε τις επόμενες μέρες να βάζεις πιο συχνά στο πιάτο σου όσπρια, κρέας ή ψάρια, που έχουν σίδηρο!"


def decision(rule=IRON, status=S.LIKELY_INADEQUATE):
    return rule.decide(NutrientEvaluation(rule.nutrient_id, status, 4, 5.3, "mg/d", {"AR": 7.0, "PRI": 11.0}))


# ---------- prompt ----------

def test_prompt_has_no_numbers_and_no_research_values():
    d = decision()
    _, tpl = render_fallback(d)
    msgs = build_messages(d, tpl, default_lexicon(), age_years=13)
    user = msgs[1]["content"]
    assert not re.search(r"\d", user.replace("10-12", "").replace("13-16", ""))
    assert "5.3" not in json.dumps(msgs) and "11.0" not in json.dumps(msgs)
    assert "σίδηρο" in user and "όσπρια" in user and tpl in user


def test_age_is_sent_as_band():
    assert (age_band(10), age_band(12), age_band(13), age_band(16), age_band(None)) == ("10-12", "10-12", "13-16", "13-16", "10-16")


def test_prompt_direction_differs_for_sodium():
    d = decision(SODIUM, S.ABOVE_REFERENCE)
    _, tpl = render_fallback(d)
    assert "ΠΙΟ ΣΠΑΝΙΑ" in build_messages(d, tpl, default_lexicon())[1]["content"]


def test_no_prompt_for_non_presentable_status():
    with pytest.raises(ValueError):
        build_messages(decision(status=S.INSUFFICIENT_DATA), "x", default_lexicon())


# ---------- presenter ----------

def test_valid_llm_output_is_used():
    p = KrikriPresenter(ScriptedClient([f"«{GOOD_IRON}»"]))
    m = p.present(decision(), age_years=12)
    assert m.source == "llm" and m.text == GOOD_IRON
    a = m.audit()
    assert a["safety_validator_passed"] and len(a["llm_prompt_hash"]) == 64 and len(a["llm_output_hashes"]) == 1


@pytest.mark.parametrize("bad, code", [
    ("Χρειάζεσαι 11 mg σίδηρο: φάε όσπρια.", "V-NUM"),
    ("Φάε δύο μερίδες όσπρια για σίδηρο.", "V-NUMW"),
    ("Τα όσπρια έχουν σίδηρο και λίγες θερμίδες.", "V-FORBID"),
    ("Έχεις έλλειψη σιδήρου, φάε κρέας.", "V-DIAG"),
    ("Eat more beans for iron!", "V-LANG"),
    ("Για σίδηρο δοκίμασε ένα ποτήρι γάλα.", "V-FOOD"),
])
def test_invalid_llm_output_falls_back_to_template(bad, code):
    m = KrikriPresenter(ScriptedClient([bad])).present(decision())
    _, tpl = render_fallback(decision())
    assert m.source == "template" and m.text == tpl and m.reason == "validator"
    assert code in m.llm_failures[0]


def test_retry_then_success():
    m = KrikriPresenter(ScriptedClient(["Φάε δύο μερίδες όσπρια για σίδηρο.", GOOD_IRON]), retries=1).present(decision())
    assert m.source == "llm" and len(m.llm_failures) == 1 and len(m.llm_output_hashes) == 2


def test_llm_error_falls_back():
    m = KrikriPresenter(ScriptedClient([TimeoutError("timeout")])).present(decision())
    assert m.source == "template" and m.reason == "llm_error" and "timeout" in m.llm_error


def test_safety_suppression_never_calls_llm():
    client = ScriptedClient([GOOD_IRON])
    safety = evaluate_safety(SafetySignals(RiskLevel.MODERATE, "disordered_eating"))
    m = KrikriPresenter(client).present(decision(), safety=safety)
    assert m.source == "none" and m.text is None and client.calls == []


def test_non_presentable_status_never_calls_llm():
    client = ScriptedClient([GOOD_IRON])
    m = KrikriPresenter(client).present(decision(status=S.INSUFFICIENT_DATA))
    assert m.source == "none" and m.reason == "no_template" and client.calls == []


def test_without_client_uses_template():
    m = KrikriPresenter(None).present(decision())
    assert m.source == "template" and m.reason == "no_client"


def test_clean_output():
    assert clean_output('  Μήνυμα: «Γεια **σου**!»\n') == "Γεια σου!"
    assert clean_output("Νέα διατύπωση: \"Κείμενο.\"") == "Κείμενο."


def test_audit_has_no_research_values():
    a = KrikriPresenter(ScriptedClient([GOOD_IRON])).present(decision()).audit()
    assert "5.3" not in json.dumps(a) and "research_values" not in a
    json.dumps(a)


def test_present_all_from_engine():
    refs = load_reference_values(ROOT / "data/efsa_drv.csv")
    low = {"iron": 3, "calcium": 300, "fibre": 6, "sodium": 1.0, "protein": 15,
           "vitamin_a": 150, "vitamin_c": 20, "folate": 80, "vitamin_d": 2, "vitamin_b12": 1.0}
    start = date(2026, 10, 1)
    days = tuple(DailyIntake(start + timedelta(days=i), dict(low), True) for i in range(4))
    ctx = EvaluationContext(UserProfile("P-T", Sex.FEMALE, 14, weight_kg=45.0), start + timedelta(days=3), days, tuple(refs))
    result = NutritionRuleEngine().evaluate(ctx)
    client = ScriptedClient(lambda msgs: "Eat more!")        # πάντα άκυρο -> πάντα fallback
    out = KrikriPresenter(client).present_all(result)
    assert len(out) == len(result.feedback) >= 1
    assert all(m.source == "template" for m in out)
    assert all("13-16" in c[1]["content"] for c in client.calls)


# ---------- OpenAI-compatible client με τοπικό ψεύτικο server ----------

class _Handler(BaseHTTPRequestHandler):
    received = []
    reply = {"model": "krikri-test", "choices": [{"message": {"content": GOOD_IRON}, "finish_reason": "stop"}]}

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Handler.received.append((self.path, dict(self.headers), body))
        data = json.dumps(_Handler.reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        data = json.dumps({"data": [{"id": "krikri-test"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def stub_server():
    _Handler.received.clear()
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def test_openai_client_request_and_parse(stub_server):
    c = OpenAICompatibleClient(stub_server, "krikri-test", api_key="k")
    r = c.generate([{"role": "user", "content": "x"}], temperature=0.3, max_tokens=50, seed=42)
    path, headers, body = _Handler.received[0]
    assert path == "/v1/chat/completions" and headers["Authorization"] == "Bearer k"
    assert body == {"model": "krikri-test", "messages": [{"role": "user", "content": "x"}],
                    "temperature": 0.3, "max_tokens": 50, "stream": False, "seed": 42}
    assert r.text == GOOD_IRON and r.finish_reason == "stop"
    assert c.available_models() == ["krikri-test"]


def test_openai_client_end_to_end_with_presenter(stub_server):
    m = KrikriPresenter(OpenAICompatibleClient(stub_server, "krikri-test")).present(decision())
    assert m.source == "llm" and m.text == GOOD_IRON


def test_openai_client_unreachable_raises():
    with pytest.raises(LLMError):
        OpenAICompatibleClient("http://127.0.0.1:9/v1", "x", timeout_s=1).generate([], 0.3, 10)
