"""
app/services/photo_pipeline.py — φωτογραφία γεύματος: ΜΟΝΟ στη RAM, ποτέ σε δίσκο, βάση ή log (R4, Κανόνες 7-8).

Σειρά (κάθε βήμα απορρίπτει με PhotoRejected· fail-closed σε κάθε σφάλμα):
    πρόσβαση (JWT, ομάδα ελέγχου, αναστολή)          — στο api/meals.py, πριν διαβαστεί το σώμα
    μορφή: Content-Type image/jpeg, ≤ MAX_PHOTO_BYTES, υπογραφή FF D8 FF, Pillow (MAX_IMAGE_PIXELS, μεγαλύτερη
           πλευρά ≤ PHOTO_MAX_EDGE_PX ελεγμένη ΠΡΙΝ την αποσυμπίεση), νέα κωδικοποίηση JPEG στη RAM (χωρίς EXIF)
    NSFW (ContentFilter) -> food / non-food #2 (ContentFilter) -> αναγνώριση (FoodRecognizer)

Τα μοντέλα (NSFW, food gate #2, OliveGemma) δεν υπάρχουν ακόμα: εδώ ορίζονται τα interfaces (Protocol). Οι demo
υλοποιήσεις ενεργοποιούνται ΜΟΝΟ με DEMO_MODE=true (που απαγορεύεται σε production). Χωρίς ρυθμισμένα και τα τρία,
η φωτογραφία είναι «μη διαθέσιμη» (503), όχι απόρριψη: δεν επεξεργάζεται τίποτα και δεν μετρά στο όριο απορρίψεων.
Οι πραγματικές υλοποιήσεις θα μπουν στο ai_pipeline/vision/ και θα τηρούν τα ίδια Protocols.
"""
import io
import warnings
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from PIL import Image, ImageStat

from app.config import Settings

JPEG_SIGNATURE = b"\xff\xd8\xff"
REENCODE_QUALITY = 90


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


@dataclass(frozen=True)
class RecognizedFood:
    label_en: str
    name_el: Optional[str]          # ελληνικό όνομα για τον food resolver (None αν δεν υπάρχει)
    confidence: float               # 0..1· ΠΟΤΕ στο παιδί (μόνο «σίγουρο» / «ίσως»)


@runtime_checkable
class FoodRecognizer(Protocol):
    version: str

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        ...


# ------------------------------------------------------------------ demo (μόνο DEMO_MODE=true)

class DemoNsfwFilter:
    """DEMO: δεν υπάρχει μοντέλο NSFW· επιτρέπει τα πάντα. Μόνο για επίδειξη της ροής (DEMO_MODE)."""
    name, version = "demo_nsfw", "demo-0"

    def allows(self, jpeg: bytes) -> bool:
        return True


class DemoBrightnessFilter:
    """DEMO food gate #2: απορρίπτει εικόνα με μέση φωτεινότητα < 10 (σχεδόν μαύρη), για να δοκιμάζεται η απόρριψη."""
    name, version = "demo_brightness", "demo-0"
    MIN_MEAN = 10

    def allows(self, jpeg: bytes) -> bool:
        with Image.open(io.BytesIO(jpeg)) as img:
            return ImageStat.Stat(img.convert("L")).mean[0] >= self.MIN_MEAN


class DemoRecognizer:
    """DEMO: σταθερή πρόταση, ανεξάρτητα από την εικόνα. Η τρίτη δεν υπάρχει στον πίνακα (food_id: null)."""
    version = "demo-0"

    def recognize(self, jpeg: bytes) -> list[RecognizedFood]:
        return [RecognizedFood("lentil soup", "φακές", 0.92), RecognizedFood("bread", "ψωμί", 0.61),
                RecognizedFood("greek salad", "χωριάτικη σαλάτα", 0.55)]


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
        return None not in (self.nsfw, self.food_gate, self.recognizer)

    @property
    def versions(self) -> dict:
        return {"nsfw": getattr(self.nsfw, "version", None), "food_gate": getattr(self.food_gate, "version", None),
                "recognizer": getattr(self.recognizer, "version", None)}

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
        except Exception:
            raise PhotoRejected("recognizer_error") from None
        if not all(isinstance(r, RecognizedFood) for r in found):
            raise PhotoRejected("recognizer_error")
        return found


def build_photo_pipeline(settings: Settings) -> PhotoPipeline:
    # Pillow: όριο pixels για κάθε εικόνα της διεργασίας (δίχτυ για decompression bombs, πέρα από τον έλεγχο πλευράς).
    Image.MAX_IMAGE_PIXELS = settings.PHOTO_MAX_EDGE_PX * settings.PHOTO_MAX_EDGE_PX
    if settings.DEMO_MODE:
        return PhotoPipeline(DemoNsfwFilter(), DemoBrightnessFilter(), DemoRecognizer(),
                             settings.MAX_PHOTO_BYTES, settings.PHOTO_MAX_EDGE_PX)
    return PhotoPipeline(None, None, None, settings.MAX_PHOTO_BYTES, settings.PHOTO_MAX_EDGE_PX)
