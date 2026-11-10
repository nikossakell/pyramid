"""
app/services/suggestion_service.py — προτάσεις τροφίμων από φωτογραφία ή κείμενο, και αναστολή φωτογραφίας.

R3 (Κανόνας 3): οι προτάσεις ΔΕΝ αποθηκεύονται ποτέ. Το παιδί τις διορθώνει και στέλνει τη λίστα στο /meals/confirm.
Στο παιδί: food_id (ή null αν δεν βρέθηκε στον πίνακα), ελληνικό όνομα, και «σίγουρο» / «ίσως» — ποτέ αριθμός (R1).

Κείμενο: interface TextExtractor (μελλοντικά Krikri, Βήμα 3.2). Η σημερινή υλοποίηση είναι ντετερμινιστική: χωρίζει
σε «και» και κόμμα· κάθε τμήμα δοκιμάζεται ολόκληρο στον food resolver (ώστε το «μακαρόνια με κιμά» να βρεθεί ως
ένα φαγητό) και μόνο αν δεν βρεθεί χωρίζεται και σε «με». Δεν χρησιμοποιεί μοντέλο, άρα ισχύει και χωρίς DEMO_MODE.

Αναστολή: μετά από PHOTO_REJECT_LIMIT απορρίψεις σε PHOTO_REJECT_WINDOW_HOURS (μετριούνται από τα photo_rejected του
audit, μετά το τέλος της προηγούμενης αναστολής), photo_suspended_until = τώρα + PHOTO_SUSPENSION_HOURS. Γράφεται
μόνο στο audit (photo_suspended)· κανένα alert. Κείμενο και αναζήτηση μένουν διαθέσιμα.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core import audit
from app.core.clock import aware
from app.db.models import AuditLog, Participant
from ai_pipeline.food_resolver import key
from app.services.food_catalog import FoodCatalog
from app.services.meal_service import MAX_ITEMS_PER_MEAL
from app.services.photo_pipeline import PhotoPipeline, RecognizedFood

SURE, MAYBE = "σίγουρο", "ίσως"
MAX_TEXT_CHARS = 300
MAX_UNRESOLVED_NAME_CHARS = 60


@dataclass(frozen=True)
class Suggestion:
    food_id: Optional[str]
    name_el: str
    confidence_word: str
    label_en: Optional[str] = None


# ------------------------------------------------------------------ κείμενο

class TextExtractor(Protocol):
    version: str

    def extract(self, text: str) -> list[str]:
        """Φράσεις που περιγράφουν ένα τρόφιμο η καθεμιά."""


_SPLIT_AND = re.compile(r"\s*(?:,|;|\bκαι\b|\bκ\.)\s*", re.IGNORECASE)
_SPLIT_WITH = re.compile(r"\s+\bμε\b\s+", re.IGNORECASE)
# Αρχικές λέξεις ποσότητας / άρθρα που δεν ανήκουν στο όνομα («ένα μήλο» -> «μήλο»). Η μερίδα τη διαλέγει το παιδί.
_LEADING_WORDS = frozenset(key(w) for w in (
    "ένα", "μια", "μία", "ένας", "δύο", "τρία", "λίγο", "λίγα", "λίγη", "λίγες", "πολύ", "πολλά", "μισό", "μισή",
    "ένα πιάτο", "πιάτο", "ποτήρι", "κομμάτι", "φέτα", "το", "τα", "η", "ο", "οι", "την", "τη", "τον", "τις", "τους"))


def _strip_leading(phrase: str) -> str:
    words = phrase.split()
    while len(words) > 1 and key(words[0]) in _LEADING_WORDS:
        words = words[1:]
    return " ".join(words)


class DeterministicTextExtractor:
    version = "deterministic-0"

    def __init__(self, catalog: FoodCatalog):
        self.catalog = catalog

    def extract(self, text: str) -> list[str]:
        phrases = []
        for part in (_strip_leading(p.strip()) for p in _SPLIT_AND.split(text) if p and p.strip()):
            if self.catalog.resolver.resolve(part) is not None:
                phrases.append(part)
            else:
                phrases.extend(_strip_leading(p.strip()) for p in _SPLIT_WITH.split(part) if p.strip())
        return phrases


def suggestions_from_text(catalog: FoodCatalog, extractor: TextExtractor, text: str) -> list[Suggestion]:
    out, seen = [], set()
    for phrase in extractor.extract(text[:MAX_TEXT_CHARS]):
        r = catalog.resolver.resolve(phrase)
        if r is None:
            out.append(Suggestion(None, phrase[:MAX_UNRESOLVED_NAME_CHARS], MAYBE))
        elif r.food_id not in seen:
            seen.add(r.food_id)
            out.append(Suggestion(r.food_id, catalog.foods[r.food_id].name_el, SURE if r.method != "fuzzy" else MAYBE))
    return out[:MAX_ITEMS_PER_MEAL]


# ------------------------------------------------------------------ φωτογραφία

def suggestions_from_photo(catalog: FoodCatalog, found: list[RecognizedFood], confident_min: float) -> list[Suggestion]:
    out, seen = [], set()
    for f in sorted(found, key=lambda x: -x.confidence):
        r = catalog.resolver.resolve(f.name_el) if f.name_el else None
        word = SURE if f.confidence >= confident_min and r is not None and r.method != "fuzzy" else MAYBE
        if r is None:
            out.append(Suggestion(None, (f.name_el or f.label_en)[:MAX_UNRESOLVED_NAME_CHARS], MAYBE, f.label_en))
        elif r.food_id not in seen:
            seen.add(r.food_id)
            out.append(Suggestion(r.food_id, catalog.foods[r.food_id].name_el, word, f.label_en))
    return out[:MAX_ITEMS_PER_MEAL]


def photo_suspended(participant: Participant, now: datetime) -> bool:
    until = aware(participant.photo_suspended_until)
    return until is not None and now < until


def photo_available(participant: Participant, pipeline: PhotoPipeline, now: datetime) -> bool:
    return pipeline.available and not photo_suspended(participant, now)


def record_rejection(db: Session, participant: Participant, reason: str, settings: Settings, now: datetime) -> None:
    audit.record(db, "photo_rejected", participant.id, reason=reason, stored_bytes=0)
    db.flush()
    since = now - timedelta(hours=settings.PHOTO_REJECT_WINDOW_HOURS)
    previous_end = aware(participant.photo_suspended_until)
    if previous_end is not None and previous_end > since:
        since = previous_end                 # μετά από αναστολή, το μέτρημα ξεκινά από την αρχή
    n = db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.participant_id == participant.id, AuditLog.event == "photo_rejected", AuditLog.ts > since))
    if n >= settings.PHOTO_REJECT_LIMIT:
        participant.photo_suspended_until = now + timedelta(hours=settings.PHOTO_SUSPENSION_HOURS)
        audit.record(db, "photo_suspended", participant.id, n_rejections=n,
                     until=participant.photo_suspended_until.isoformat())
    db.commit()
