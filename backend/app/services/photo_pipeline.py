"""
app/services/photo_pipeline.py — φωτογραφία γεύματος: ΜΟΝΟ στη RAM, ποτέ σε δίσκο, βάση ή log (R4, Κανόνες 7-8).

Σειρά (κάθε βήμα απορρίπτει με PhotoRejected· fail-closed σε κάθε σφάλμα):
    πρόσβαση (JWT, ομάδα ελέγχου, αναστολή)          — στο api/meals.py, πριν διαβαστεί το σώμα
    μορφή: Content-Type image/jpeg, ≤ MAX_PHOTO_BYTES, υπογραφή FF D8 FF, Pillow (MAX_IMAGE_PIXELS, μεγαλύτερη
           πλευρά ≤ PHOTO_MAX_EDGE_PX ελεγμένη ΠΡΙΝ την αποσυμπίεση), νέα κωδικοποίηση JPEG στη RAM (χωρίς EXIF)
    NSFW (ContentFilter) -> food / non-food #2 (ContentFilter) -> αναγνώριση (FoodRecognizer)

Εδώ ορίζονται τα interfaces (Protocol). Επιλογή ανά component (2026-11-16): PHOTO_CONTENT_FILTER (none | demo | real)
για NSFW + food gate #2, PHOTO_RECOGNIZER (none | demo | olivegemma). Τα demo ενεργοποιούνται ΜΟΝΟ με
ENVIRONMENT=development (το DEMO_MODE=true είναι συντόμευση «όλα demo»). NSFW και food gate #2 δεν υπάρχουν ακόμα
(real -> None). Χωρίς ρυθμισμένα και τα τρία, η φωτογραφία είναι «μη διαθέσιμη» (503), όχι απόρριψη: δεν
επεξεργάζεται τίποτα και δεν μετρά στο όριο απορρίψεων. Το ίδιο 503 όταν ο πραγματικός recognizer δεν φόρτωσε
(RecognizerUnavailable) και 503 photo_busy όταν η ουρά του είναι γεμάτη (RecognizerBusy).
Οι πραγματικές υλοποιήσεις ζουν στο ai_pipeline/vision/ (OliveGemma: olivegemma.py) και τηρούν τα ίδια Protocols.
"""
import io
import logging
import warnings
from dataclasses import dataclass
from typing import Literal, Optional, Protocol, runtime_checkable

from PIL import Image, ImageStat

from ai_pipeline.vision.types import RecognizedFood, RecognizerBusy, RecognizerUnavailable   # noqa: F401 (ξαναεξάγονται)
from app.config import Settings

JPEG_SIGNATURE = b"\xff\xd8\xff"
REENCODE_QUALITY = 90
ComponentKind = Literal["demo", "real", "missing"]
PipelineKind = Literal["demo", "mixed", "real"]
log = logging.getLogger("pyramid.startup")


class PhotoRejected(Exception):
    """Ο λόγος πηγαίνει ΜΟΝΟ στο audit· το παιδί παίρνει πάντα το ίδιο 422 {"rejected": true}."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@runtime_checkable
class ContentFilter(Protocol):
    name: str
    version: str

    def allows(self, jpeg: bytes) -> bool:
        """True = επιτρέπεται. Οποιαδήποτε exception = απόρριψη (fail-closed)."""


@runtime_checkable
class FoodRecognizer(Protocol):
    version: str

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        """Μπορεί να σηκώσει RecognizerUnavailable (503) ή RecognizerBusy (503 photo_busy)· κάθε άλλη exception = απόρριψη.
        Προαιρετικά: is_demo (bool, προεπιλογή False) και ready (bool, προεπιλογή True· False = «μη διαθέσιμη»)."""


def component_kind(component: object) -> ComponentKind:
    if component is None:
        return "missing"
    return "demo" if getattr(component, "is_demo", False) else "real"


# ------------------------------------------------------------------ demo (μόνο ENVIRONMENT=development)

class DemoNsfwFilter:
    """DEMO: δεν υπάρχει μοντέλο NSFW· επιτρέπει τα πάντα. Μόνο για επίδειξη της ροής."""
    name, version, is_demo = "demo_nsfw", "demo-0", True

    def allows(self, jpeg: bytes) -> bool:
        return True


class DemoBrightnessFilter:
    """DEMO food gate #2: απορρίπτει εικόνα με μέση φωτεινότητα < 10 (σχεδόν μαύρη), για να δοκιμάζεται η απόρριψη."""
    name, version, is_demo = "demo_brightness", "demo-0", True
    MIN_MEAN = 10

    def allows(self, jpeg: bytes) -> bool:
        with Image.open(io.BytesIO(jpeg)) as img:
            return ImageStat.Stat(img.convert("L")).mean[0] >= self.MIN_MEAN


class DemoRecognizer:
    """DEMO: σταθερή πρόταση, ανεξάρτητα από την εικόνα, με εναλλακτικά («Μήπως είναι…»). Η τρίτη δεν υπάρχει στον
    πίνακα (food_id: null): το παιδί διαλέγει από τα alternatives ή ψάχνει."""
    version, is_demo = "demo-1", True

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        return [RecognizedFood("lentil soup", "φακές", 0.92, ("φασολάδα", "ρεβίθια")),
                RecognizedFood("bread", "ψωμί", 0.61, ("βρώμη",)),
                RecognizedFood("greek salad", "χωριάτικη σαλάτα", 0.55, ("ντομάτα", "φέτα"))]


# ------------------------------------------------------------------ pipeline

@dataclass(frozen=True)
class PhotoPipeline:
    nsfw: Optional[ContentFilter]
    food_gate: Optional[ContentFilter]
    recognizer: Optional[FoodRecognizer]
    max_bytes: int
    max_edge_px: int

    @property
    def available(self) -> bool:
        """Και τα τρία ρυθμισμένα ΚΑΙ ο recognizer έτοιμος (ένα πραγματικό μοντέλο που απέτυχε να φορτώσει = όχι)."""
        return (None not in (self.nsfw, self.food_gate, self.recognizer)
                and bool(getattr(self.recognizer, "ready", True)))

    @property
    def versions(self) -> dict:
        return {"nsfw": getattr(self.nsfw, "version", None), "food_gate": getattr(self.food_gate, "version", None),
                "recognizer": getattr(self.recognizer, "version", None)}

    @property
    def components(self) -> dict[str, ComponentKind]:
        """demo | real | missing ανά component, για το /admin/system-status."""
        return {"nsfw": component_kind(self.nsfw), "food_gate": component_kind(self.food_gate),
                "recognizer": component_kind(self.recognizer)}

    @property
    def kind(self) -> PipelineKind:
        """Για το audit (pipeline): demo = όλα demo, real = όλα πραγματικά, mixed = κάποια demo. Μόνο όταν available."""
        kinds = set(self.components.values())
        return "demo" if kinds == {"demo"} else "real" if kinds == {"real"} else "mixed"

    @property
    def has_demo(self) -> bool:
        return "demo" in self.components.values()

    def prepare(self, raw: bytes) -> bytes:
        """Έλεγχος μορφής και νέα κωδικοποίηση στη RAM. Επιστρέφει νέο JPEG (χωρίς EXIF/μεταδεδομένα)."""
        if len(raw) > self.max_bytes:
            raise PhotoRejected("too_large")
        if not raw.startswith(JPEG_SIGNATURE):
            raise PhotoRejected("signature")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as img:
                    if img.format != "JPEG":
                        raise PhotoRejected("format")
                    if max(img.size) > self.max_edge_px:      # από την κεφαλίδα, πριν την αποσυμπίεση
                        raise PhotoRejected("dimensions")
                    img.load()
                    out = io.BytesIO()
                    img.convert("RGB").save(out, format="JPEG", quality=REENCODE_QUALITY)
                    return out.getvalue()
        except PhotoRejected:
            raise
        except Exception:                                       # αλλοιωμένο αρχείο, bomb, οτιδήποτε: απόρριψη
            raise PhotoRejected("decode") from None

    def screen(self, jpeg: bytes) -> None:
        for stage, f in (("nsfw", self.nsfw), ("food_gate", self.food_gate)):
            if f is None:
                raise PhotoRejected(f"{stage}_missing")
            try:
                ok = f.allows(jpeg)
            except Exception:
                raise PhotoRejected(f"{stage}_error") from None
            if ok is not True:
                raise PhotoRejected(stage)

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        if self.recognizer is None:
            raise PhotoRejected("recognizer_missing")
        try:
            found = list(self.recognizer.recognize(jpeg))
        except (RecognizerUnavailable, RecognizerBusy):          # 503, όχι απόρριψη (api/meals.py)
            raise
        except TimeoutError:
            raise PhotoRejected("recognizer_timeout") from None
        except Exception:
            raise PhotoRejected("recognizer_error") from None
        if not all(isinstance(r, RecognizedFood) and isinstance(r.alternatives, tuple)
                   and all(isinstance(a, str) for a in r.alternatives) for r in found):
            raise PhotoRejected("recognizer_error")
        return found


def build_recognizer(settings: Settings, foods: Optional[dict] = None) -> Optional[FoodRecognizer]:
    choice = settings.photo_recognizer
    if choice == "demo":
        return DemoRecognizer()
    if choice == "olivegemma":
        from ai_pipeline.vision.olivegemma import OliveGemmaRecognizer, load_label_map   # torch φορτώνεται lazy, στο load()
        foods = foods or {}
        label_map = load_label_map(settings.data_path(settings.OLIVEGEMMA_LABEL_MAP_CSV), foods.keys())
        recognizer = OliveGemmaRecognizer(
            settings.OLIVEGEMMA_DIR, label_map, foods, dtype=settings.OLIVEGEMMA_DTYPE,
            threads=settings.OLIVEGEMMA_THREADS, timeout_s=settings.OLIVEGEMMA_TIMEOUT_S, topk=settings.OLIVEGEMMA_TOPK,
            ingredients=settings.OLIVEGEMMA_INGREDIENTS, sha256=settings.OLIVEGEMMA_SHA256,
            max_queue=settings.OLIVEGEMMA_MAX_QUEUE)
        if settings.OLIVEGEMMA_PRELOAD:
            try:
                recognizer.load()
            except RecognizerUnavailable:                       # ήδη WARNING στο log· η φωτογραφία θα δίνει 503
                pass
        return recognizer
    return None


def build_content_filters(settings: Settings) -> tuple[Optional[ContentFilter], Optional[ContentFilter]]:
    choice = settings.photo_content_filter
    if choice == "demo":
        return DemoNsfwFilter(), DemoBrightnessFilter()
    if choice == "real":
        log.warning("photo_content_filter_not_implemented",      # NSFW + food gate #2 (Βήματα 3.1b/3.1c) δεν υπάρχουν
                    extra={"fields": {"content_filter": "real", "effect": "photo_unavailable"}})
    return None, None


def build_photo_pipeline(settings: Settings, foods: Optional[dict] = None) -> PhotoPipeline:
    """foods: ο πίνακας τροφίμων (food_id -> name_el, food_group) για την αντιστοίχιση ετικετών του OliveGemma."""
    # Pillow: όριο pixels για κάθε εικόνα της διεργασίας (δίχτυ για decompression bombs, πέρα από τον έλεγχο πλευράς).
    Image.MAX_IMAGE_PIXELS = settings.PHOTO_MAX_EDGE_PX * settings.PHOTO_MAX_EDGE_PX
    nsfw, food_gate = build_content_filters(settings)
    return PhotoPipeline(nsfw, food_gate, build_recognizer(settings, foods),
                         settings.MAX_PHOTO_BYTES, settings.PHOTO_MAX_EDGE_PX)
