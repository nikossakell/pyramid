"""
ai_pipeline/presentation/krikri_presenter.py — Βήμα 4.1: φιλική διατύπωση με Krikri, πάντα με δίχτυ ασφαλείας.

Για κάθε απόφαση που φτάνει στο παιδί (EngineResult.feedback):

    ασφάλεια ενεργή (safety.suppress)? ──► τίποτα (το Krikri ΔΕΝ καλείται)
    σταθερό κείμενο (templates.py) ──► validator ──► αποτυχία ──► τίποτα (το Krikri ΔΕΝ καλείται)
    Krikri (αν υπάρχει client) ──► καθαρισμός ──► validator ──► OK ──► κείμενο Krikri
                                                              └─► αποτυχία / σφάλμα / timeout ──► σταθερό κείμενο

Κανόνας 1: το Krikri δεν αποφασίζει τίποτα· κανόνας 2: δεν βλέπει και δεν γράφει αριθμούς·
κανόνας 4: validator μετά από κάθε έξοδο· κανόνας 5: audit με hashes prompt και εξόδου.
Ο presenter δεν γράφει σε βάση: επιστρέφει PresentedMessage με audit(), όπως το engine.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from rule_engine.models import RuleDecision
from rule_engine.safety_rules import SafetyDecision

from ai_pipeline.text.krikri_client import ChatClient, LLMError

from .lexicon import Lexicon, default_lexicon
from .prompts import PROMPT_VERSION, build_messages, prompt_hash
from .safety_validator import VALIDATOR_VERSION, validate_child_text
from .templates import TemplateError, render_fallback

PRESENTER_VERSION = "0.1"
DEFAULT_PARAMS = {"temperature": 0.3, "max_tokens": 150, "seed": 42}   # 0,3 όπως το final_plan· seed για επανάληψη

_LABEL = re.compile(r"^\s*(νέα διατύπωση|διατύπωση|μήνυμα|απάντηση)\s*:\s*", re.IGNORECASE)
_QUOTES = "\"'«»“”„‘’"


def clean_output(text: str) -> str:
    """Μόνο μορφή, ποτέ περιεχόμενο: κενά, εισαγωγικά, ετικέτα «Μήνυμα:», markdown έντονα.
    Ο validator κρίνει το καθαρισμένο κείμενο, δηλαδή ακριβώς αυτό που θα δει το παιδί."""
    t = " ".join(text.split())
    t = _LABEL.sub("", t)
    t = t.replace("**", "").replace("__", "")
    t = t.strip().strip(_QUOTES).strip()
    return t


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PresentedMessage:
    decision: RuleDecision
    text: Optional[str]                       # None = τίποτα στο παιδί
    source: str                               # "llm" | "template" | "none"
    template_id: Optional[str] = None
    reason: Optional[str] = None              # γιατί όχι llm: no_client | llm_error | validator | safety | no_template | template_invalid
    llm_model: Optional[str] = None
    llm_prompt_hash: Optional[str] = None
    llm_output_hashes: tuple[str, ...] = ()
    llm_failures: tuple[tuple[str, ...], ...] = ()   # κωδικοί validator ανά απορριφθείσα προσπάθεια
    llm_error: Optional[str] = None
    latency_s: float = 0.0
    lexicon_versions: dict = field(default_factory=dict)

    def audit(self) -> dict:
        """Κανόνας 5. Χωρίς ταυτότητα παιδιού (την προσθέτει το service layer), χωρίς research_values."""
        d = self.decision
        return {
            "rule_id": d.rule_id, "rule_version": d.rule_version, "message_template_id": d.message_template_id,
            "template_used": self.template_id, "source": self.source, "reason": self.reason,
            "shown_text": self.text, "shown_text_sha256": _sha(self.text) if self.text else None,
            "safety_validator_passed": self.source in ("llm", "template"),
            "llm_model": self.llm_model, "llm_prompt_hash": self.llm_prompt_hash,
            "llm_output_hashes": list(self.llm_output_hashes),
            "llm_failures": [list(f) for f in self.llm_failures], "llm_error": self.llm_error,
            "latency_s": round(self.latency_s, 3), "citation": d.citation,
            "presenter_version": PRESENTER_VERSION, "prompt_version": PROMPT_VERSION,
            "validator_version": VALIDATOR_VERSION, "lexicon_versions": dict(self.lexicon_versions),
        }


class KrikriPresenter:
    def __init__(self, client: Optional[ChatClient] = None, lexicon: Optional[Lexicon] = None,
                 params: Optional[dict] = None, retries: int = 0):
        """client=None: μόνο σταθερά κείμενα (η εφαρμογή λειτουργεί και χωρίς LLM).
        retries: επιπλέον προσπάθειες αν ο validator απορρίψει (κάθε προσπάθεια κοστίζει χρόνο GPU)."""
        self.client = client
        self.lexicon = lexicon or default_lexicon()
        self.params = dict(DEFAULT_PARAMS, **(params or {}))
        self.retries = retries

    def present(self, decision: RuleDecision, safety: Optional[SafetyDecision] = None,
                age_years: Optional[int] = None) -> PresentedMessage:
        lex_v = self.lexicon.versions
        if safety is not None and safety.suppress:
            return PresentedMessage(decision, None, "none", reason="safety", lexicon_versions=lex_v)
        try:
            tid, fallback = render_fallback(decision, self.lexicon)
        except TemplateError:
            return PresentedMessage(decision, None, "none", reason="no_template", lexicon_versions=lex_v)
        if not validate_child_text(fallback, decision, self.lexicon, safety).passed:
            return PresentedMessage(decision, None, "none", template_id=tid, reason="template_invalid",
                                    lexicon_versions=lex_v)
        if self.client is None:
            return PresentedMessage(decision, fallback, "template", template_id=tid, reason="no_client",
                                    lexicon_versions=lex_v)

        messages = build_messages(decision, fallback, self.lexicon, age_years)
        p_hash = prompt_hash(messages, {**self.params, "model": self.client.model_id})
        outputs, failures, latency, error = [], [], 0.0, None
        for _ in range(1 + self.retries):
            try:
                result = self.client.generate(messages, self.params["temperature"], self.params["max_tokens"],
                                              self.params.get("seed"))
            except LLMError as e:
                error = str(e)
                break
            latency += result.latency_s
            text = clean_output(result.text)
            outputs.append(_sha(text))
            check = validate_child_text(text, decision, self.lexicon, safety)
            if check.passed:
                return PresentedMessage(decision, text, "llm", template_id=tid, llm_model=result.model,
                                        llm_prompt_hash=p_hash, llm_output_hashes=tuple(outputs),
                                        llm_failures=tuple(failures), latency_s=latency, lexicon_versions=lex_v)
            failures.append(tuple(sorted(check.codes)))
        return PresentedMessage(decision, fallback, "template", template_id=tid,
                                reason="llm_error" if error else "validator", llm_model=self.client.model_id,
                                llm_prompt_hash=p_hash, llm_output_hashes=tuple(outputs),
                                llm_failures=tuple(failures), llm_error=error, latency_s=latency,
                                lexicon_versions=lex_v)

    def present_all(self, engine_result) -> list[PresentedMessage]:
        """Όλη η ανατροφοδότηση μιας αξιολόγησης (EngineResult). Η ηλικία από το προφίλ, ως εύρος."""
        age = engine_result.assessment.profile.age_years
        return [self.present(d, engine_result.safety, age) for d in engine_result.feedback]
