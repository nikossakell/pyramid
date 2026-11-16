"""
ai_pipeline/vision/olivegemma.py — OliveGemma-3B (JamesZar/OliveGemma-3B, fine-tune του PaliGemma 2 3B 448 px) ως
FoodRecognizer του photo pipeline (docs/decisions/2026-11-16_olivegemma_integration.txt).

Ιδιωτικότητα (R4, Κανόνες 7-9):
- Τα βάρη φορτώνονται ΜΟΝΟ από τοπικό φάκελο: HF_HUB_OFFLINE=1, local_files_only=True, trust_remote_code=False.
  Καμία κλήση δικτύου στη φόρτωση ή στην εκτέλεση.
- Είσοδος: το καθαρό JPEG που παράγει ήδη το pipeline (≤ 448 px, χωρίς EXIF), ως PIL Image στη μνήμη. Τίποτα δεν
  γράφεται σε δίσκο· εικόνα και tensors διαγράφονται μετά την απάντηση (del + gc).
- Έξοδος: ΜΟΝΟ ετικέτες (λέξεις). Κανένα σκορ δεν φεύγει από τη μονάδα: το confidence του RecognizedFood παίρνει
  μία από δύο σταθερές (SURE / MAYBE) από τον κανόνα της Απόφασης 6 (ΠΡΟΣΧΕΔΙΟ), ώστε το suggestion_service να βγάλει
  «σίγουρο» / «ίσως». Αριθμοί δεν περνούν ούτε στα components (R1).

Prompt και αποκωδικοποίηση όπως η κάρτα του μοντέλου: "<image>answer en {question}\n", greedy. Top-k με beam search
(num_beams=k, num_return_sequences=k) όπως στη δοκιμή της 19/10 (παράμετροι από την κάρτα, όχι από το notebook).
Ερωτήσεις: dish_name και, μόνο με ingredients=True, likely_ingredients (υλικά συνταγής, ΟΧΙ επιβεβαιωμένα από τη
φωτογραφία, κατά την κάρτα). ΟΧΙ visible_ingredients / visual_evidence (σχεδόν μηδενική ακρίβεια κατά την κάρτα).

Ταυτόχρονα αιτήματα: ένα inference τη φορά (κλείδωμα). Όσα περιμένουν πάνω από max_queue → RecognizerBusy (503,
όχι απόρριψη). Timeout → TimeoutError, που το pipeline μετατρέπει σε απόρριψη (fail-closed, Απόφαση 27).
Γνωστός περιορισμός: νήμα torch δεν διακόπτεται· μετά το timeout η εκτέλεση συνεχίζει μέχρι να τελειώσει και
κρατά το κλείδωμα (τα επόμενα αιτήματα παίρνουν photo_busy). Για τον πιλότο: inference σε ξεχωριστή διεργασία
που τερματίζεται (ανοιχτή απόφαση).

Ακεραιότητα: αν δοθεί sha256, ελέγχεται το model.safetensors πριν τη φόρτωση· διαφορά → ο recognizer δεν φορτώνεται,
WARNING στο log, κάθε αίτημα 503. model_id στο audit: "OliveGemma-3B@<REVISION.txt>".
"""
import csv
import gc
import hashlib
import io
import logging
import os
import re
import resource
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Protocol

from PIL import Image

from ai_pipeline.vision.types import RecognizedFood, RecognizerBusy, RecognizerUnavailable

log = logging.getLogger("pyramid.olivegemma")

MODEL_NAME = "OliveGemma-3B"
WEIGHTS_FILE = "model.safetensors"
REVISION_FILE = "REVISION.txt"
PROMPT = "<image>answer en {question}\n"                      # ακριβώς όπως η κάρτα· το \n είναι μέρος του prompt
DISH_QUESTION = "What is the name of this dish?"
INGREDIENTS_QUESTION = "What ingredients are typically found in this food?"
MAX_NEW_TOKENS = 64
MAX_LABEL_CHARS = 60                                            # ίδιο με το MAX_AUDIT_LABEL_CHARS
MAX_COMPONENTS = 10                                             # ΠΡΟΣΧΕΔΙΟ
MAX_COMPONENT_CHARS = 40                                        # ΠΡΟΣΧΕΔΙΟ
# Εσωτερικές τιμές του RecognizedFood.confidence. MAYBE = 0 είναι πάντα κάτω από το PHOTO_CONFIDENT_MIN (> 0), SURE = 1
# πάντα πάνω: έτσι ο κανόνας «σίγουρο / ίσως» αποφασίζεται ΕΔΩ (Απόφαση 6) και όχι από κατώφλι σκορ.
SURE, MAYBE = 1.0, 0.0
_SPACES = re.compile(r"\s+")
_COMPONENT_SPLIT = re.compile(r"[,.;:\n]|\band\b|\bor\b")
_COMPONENT_NOISE = ("ingredient", "confirmable", "typical", "etc", "commonly", "visible", "present")


class FoodLike(Protocol):
    name_el: str
    food_group: str


class Backend(Protocol):
    """Ό,τι χρειάζεται ο recognizer από το μοντέλο· τα unit tests δίνουν ψεύτικη υλοποίηση χωρίς βάρη."""

    def answer(self, image: Image.Image, question: str, k: int) -> list[str]:
        """Έως k απαντήσεις (beam search, από την πιο πιθανή) για την ερώτηση πάνω στην εικόνα."""


# ------------------------------------------------------------------ βοηθητικά

def normalize_label(text: str) -> str:
    return _SPACES.sub(" ", (text or "").strip().lower())


def sha256_file(path: Path, chunk: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def rss_mb() -> int:
    """Μέγιστο RSS της διεργασίας σε MB (Linux: ru_maxrss σε KB)."""
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)


def load_label_map(path: Path, known_food_ids: Optional[Iterable[str]] = None) -> dict[str, str]:
    """data/olivegemma_label_map.csv -> {ετικέτα (κανονικοποιημένη): food_id}. Διαβάζονται ΜΟΝΟ οι στήλες
    olivegemma_label και food_id (οι default_portion_g / confidence_floor ΔΕΝ χρησιμοποιούνται, Απόφαση 5).
    Γραμμές χωρίς food_id παραλείπονται. Διπλή ετικέτα με άλλο food_id ή άγνωστο food_id: σφάλμα δεδομένων."""
    path = Path(path)
    known = set(known_food_ids) if known_food_ids is not None else None
    out: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"olivegemma_label", "food_id"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        for line, row in enumerate(reader, start=2):
            label = normalize_label(row.get("olivegemma_label") or "")
            food_id = (row.get("food_id") or "").strip()
            if not label or not food_id:
                continue
            if known is not None and food_id not in known:
                raise ValueError(f"{path.name} line {line}: unknown food_id {food_id!r}")
            if out.get(label, food_id) != food_id:
                raise ValueError(f"{path.name} line {line}: {label!r} maps to both {out[label]!r} and {food_id!r}")
            out[label] = food_id
    return out


def parse_components(text: str) -> tuple[str, ...]:
    """Υλικά από την απάντηση likely_ingredients: λέξεις χωρισμένες σε κόμματα/τελείες, χωρίς τις φράσεις-πλαίσιο της
    κάρτας («Visible-typical ingredients: …», «Commonly-present but not visually confirmable: …»). Κάθε τμήμα με ψηφίο
    απορρίπτεται (R1: καμία ποσότητα). ΠΡΟΣΧΕΔΙΟ."""
    out: list[str] = []
    for part in _COMPONENT_SPLIT.split(text or ""):
        p = normalize_label(part)
        if not p or any(ch.isdigit() for ch in p) or any(w in p for w in _COMPONENT_NOISE):
            continue
        p = p[:MAX_COMPONENT_CHARS]
        if p not in out:
            out.append(p)
        if len(out) >= MAX_COMPONENTS:
            break
    return tuple(out)


# ------------------------------------------------------------------ torch backend

class TorchBackend:
    """AutoProcessor + PaliGemmaForConditionalGeneration από τοπικό φάκελο, εκτός σύνδεσης. CPU εκτός αν δοθεί device."""

    def __init__(self, model_dir: Path, dtype: str = "bfloat16", threads: Optional[int] = None, device: str = "cpu"):
        for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
            os.environ.setdefault(var, "1")
        import torch
        from transformers import AutoProcessor, PaliGemmaForConditionalGeneration
        if threads:
            torch.set_num_threads(int(threads))
        self.torch = torch
        self.device = device
        self.processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
        self.model = PaliGemmaForConditionalGeneration.from_pretrained(
            str(model_dir), dtype=getattr(torch, dtype), local_files_only=True, trust_remote_code=False).to(device).eval()

    def answer(self, image: Image.Image, question: str, k: int) -> list[str]:
        torch = self.torch
        inputs = out = None
        try:
            inputs = self.processor(text=PROMPT.format(question=question), images=image, return_tensors="pt")
            inputs = inputs.to(self.device)
            in_len = inputs["input_ids"].shape[-1]
            with torch.inference_mode():
                out = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                          num_beams=max(1, k), num_return_sequences=max(1, k))
            return [self.processor.decode(seq[in_len:], skip_special_tokens=True).strip() for seq in out]
        finally:
            del inputs, out                                   # κανένα tensor της εικόνας δεν επιζεί της απάντησης
            gc.collect()


# ------------------------------------------------------------------ recognizer

class OliveGemmaRecognizer:
    is_demo = False

    def __init__(self, model_dir: Path, label_map: Mapping[str, str], foods: Mapping[str, FoodLike], *,
                 dtype: str = "bfloat16", threads: Optional[int] = None, timeout_s: float = 600.0, topk: int = 3,
                 ingredients: bool = False, sha256: Optional[str] = None, max_queue: int = 2,
                 backend_factory: Optional[Callable[[], Backend]] = None):
        self.model_dir = Path(model_dir)
        self.label_map = {normalize_label(k): v for k, v in label_map.items()}
        self.foods = foods
        self.dtype, self.threads, self.timeout_s = dtype, threads, float(timeout_s)
        self.topk, self.ingredients = max(1, int(topk)), bool(ingredients)
        self.sha256 = sha256.strip().lower() if sha256 else None
        self.max_queue = max(0, int(max_queue))
        self._backend_factory = backend_factory or (lambda: TorchBackend(self.model_dir, self.dtype, self.threads))
        self.version = f"{MODEL_NAME}@{self._revision()}"
        self._backend: Optional[Backend] = None
        self._failed = False
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._pending = 0                 # αιτήματα που έχουν μπει και δεν τελείωσαν (το ένα τρέχει, τα άλλα περιμένουν)

    # ---- κατάσταση

    @property
    def ready(self) -> bool:
        """False μετά από αποτυχημένη φόρτωση: η φωτογραφία γίνεται «μη διαθέσιμη» (503) μέχρι επανεκκίνηση."""
        return not self._failed

    @property
    def loaded(self) -> bool:
        return self._backend is not None

    def _revision(self) -> str:
        try:
            return (self.model_dir / REVISION_FILE).read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            return "unknown"

    def _verify_files(self) -> None:
        weights = self.model_dir / WEIGHTS_FILE
        if not weights.is_file():
            raise FileNotFoundError("weights_missing")
        if self.sha256 is not None and sha256_file(weights) != self.sha256:
            raise ValueError("sha256_mismatch")

    def load(self) -> None:
        """Φορτώνει μία φορά (lazy στο πρώτο αίτημα ή ρητά στην εκκίνηση). Στο log: χρόνος και μνήμη, ποτέ περιεχόμενο."""
        with self._load_lock:
            if self._backend is not None:
                return
            if self._failed:
                raise RecognizerUnavailable("load_failed")
            t0 = time.monotonic()
            try:
                self._verify_files()
                self._backend = self._backend_factory()
            except Exception as e:
                self._failed = True
                log.warning("olivegemma_load_failed", extra={"fields": {
                    "model_id": self.version, "reason": str(e)[:60] or type(e).__name__}})
                raise RecognizerUnavailable(type(e).__name__) from None
            log.info("olivegemma_loaded", extra={"fields": {
                "model_id": self.version, "load_seconds": round(time.monotonic() - t0, 1), "rss_mb": rss_mb(),
                "dtype": self.dtype, "threads": self.threads, "topk": self.topk, "ingredients": self.ingredients}})

    # ---- αναγνώριση

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        if self._failed:
            raise RecognizerUnavailable("load_failed")
        with self._count_lock:
            if self._pending > self.max_queue:                # ένα τρέχει + έως max_queue περιμένουν
                raise RecognizerBusy()
            self._pending += 1
        result: dict = {}
        done, cancelled = threading.Event(), threading.Event()

        def work() -> None:
            try:
                with self._infer_lock:
                    if cancelled.is_set():                    # ο καλών έφυγε με timeout όσο περίμενε τη σειρά του
                        return
                    self.load()
                    result["value"] = self._infer(jpeg)
            except BaseException as e:                        # noqa: BLE001 — μεταφέρεται στον καλούντα
                result["error"] = e
            finally:
                with self._count_lock:
                    self._pending -= 1
                done.set()

        threading.Thread(target=work, name="olivegemma-infer", daemon=True).start()
        if not done.wait(self.timeout_s):
            cancelled.set()
            raise TimeoutError("olivegemma_timeout")
        if "error" in result:
            raise result["error"]
        return result["value"]

    def _infer(self, jpeg: bytes) -> list[RecognizedFood]:
        assert self._backend is not None
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        try:
            labels = self._backend.answer(img, DISH_QUESTION, self.topk)
            components: tuple[str, ...] = ()
            if self.ingredients:
                answers = self._backend.answer(img, INGREDIENTS_QUESTION, 1)
                components = parse_components(answers[0] if answers else "")
        finally:
            img.close()
            del img
            gc.collect()
        return [self.assemble(labels, components)]

    def assemble(self, labels: list[str], components: tuple[str, ...] = ()) -> RecognizedFood:
        """Beams -> label map -> ένα RecognizedFood: η 1η ετικέτα ως πρόταση, οι υπόλοιπες αντιστοιχισμένες και
        διαφορετικές ως alternatives (χωρίς διπλά, Απόφαση 5γ της 19/10). Κανόνας «σίγουρο» (Απόφαση 6, ΠΡΟΣΧΕΔΙΟ):
        η 1η αντιστοιχίστηκε ΚΑΙ η 2η (αν υπάρχει και αντιστοιχίζεται) είναι το ίδιο τρόφιμο ή της ίδιας ομάδας."""
        clean = [normalize_label(x)[:MAX_LABEL_CHARS] for x in labels if x and x.strip()]
        if not clean:
            raise ValueError("empty_output")
        mapped = [self.label_map.get(x) for x in clean]
        mapped = [fid if fid in self.foods else None for fid in mapped]
        top_label, top_id = clean[0], mapped[0]
        alt_ids: list[str] = []
        for fid in mapped[1:]:
            if fid is not None and fid != top_id and fid not in alt_ids:
                alt_ids.append(fid)
        second = mapped[1] if len(mapped) > 1 else None
        sure = top_id is not None and (second is None or second == top_id
                                       or self.foods[second].food_group == self.foods[top_id].food_group)
        return RecognizedFood(label_en=top_label, name_el=self.foods[top_id].name_el if top_id else None,
                              confidence=SURE if sure else MAYBE,
                              alternatives=tuple(self.foods[f].name_el for f in alt_ids), components=components)
