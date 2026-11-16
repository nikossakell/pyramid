"""
ai_pipeline/vision/types.py — κοινοί τύποι ανάμεσα στο photo pipeline της εφαρμογής και στις υλοποιήσεις αναγνώρισης.

Ζουν εδώ (και όχι στο app/) ώστε το ai_pipeline να μην εισάγει τίποτα από το app: η εφαρμογή εξαρτάται από το
ai_pipeline, ποτέ το αντίστροφο. Το app/services/photo_pipeline.py τα ξαναεξάγει με τα ίδια ονόματα.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RecognizedFood:
    label_en: str
    name_el: Optional[str]          # ελληνικό όνομα για τον food resolver (None αν δεν υπάρχει)
    confidence: float               # 0..1· ΠΟΤΕ στο παιδί (μόνο «σίγουρο» / «ίσως»)
    # Τα επόμενα υποψήφια του μοντέλου για το ΙΔΙΟ τρόφιμο (ελληνικά ονόματα, από το πιο πιθανό), χωρίς σκορ.
    alternatives: tuple[str, ...] = ()
    # Υλικά συνταγής κατά το μοντέλο (ΠΡΟΣΧΕΔΙΟ, μόνο με OLIVEGEMMA_INGREDIENTS=true): λέξεις, ποτέ ποσότητες.
    components: tuple[str, ...] = ()


class RecognizerUnavailable(Exception):
    """Ο recognizer υπάρχει στη ρύθμιση αλλά δεν μπορεί να δουλέψει (δεν φορτώθηκε, λάθος sha256, λείπουν βάρη).
    Η εφαρμογή απαντά 503 photo_unavailable· ΔΕΝ είναι απόρριψη και δεν μετρά στην αναστολή."""


class RecognizerBusy(Exception):
    """Η ουρά inference είναι γεμάτη. Η εφαρμογή απαντά 503 photo_busy· ΔΕΝ είναι απόρριψη."""
