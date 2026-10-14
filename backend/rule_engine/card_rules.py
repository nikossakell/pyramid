"""
rule_engine/card_rules.py — Layer 3b: πότε το παιδί κερδίζει κάρτα για το παιχνίδι.

Δεν προκύπτουν από την EFSA. Είναι σχεδιαστική απόφαση· όλα εδώ είναι ΠΡΟΣΧΕΔΙΟ προς έγκριση.
Βάση: το πρωτόκολλο ορίζει ότι η τακτική χρήση και οι σωστές επιλογές γευμάτων επιβραβεύονται
σε παιχνίδι καρτών εναντίον του υπολογιστή.

Αρχές ασφαλείας (δεν αλλάζουν χωρίς έγκριση παιδίατρου):
- Επιβράβευση μόνο για καταγραφή και για ποικιλία ομάδων τροφίμων που ενθαρρύνονται.
- ΠΟΤΕ για λιγότερο φαγητό, παράλειψη γεύματος, θερμίδες ή βάρος.
- Καμία σύγκριση με άλλα παιδιά (χωρίς leaderboards).
- Ανώτατο όριο καρτών την ημέρα, για να μην ενθαρρύνεται εμμονική καταγραφή.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

CARD_RULES_VERSION = "0.1"
MAX_CARDS_PER_DAY = 3
# ΠΡΟΣΧΕΔΙΟ: ομάδες που ενθαρρύνονται (κωδικοί από food_groups.csv, έγκριση διαιτολόγου)
ENCOURAGED_GROUPS = frozenset({"vegetables", "fruit", "legumes", "whole_grains", "dairy", "fish", "nuts"})
VARIETY_MIN_GROUPS = 3


@dataclass(frozen=True)
class DayActivity:
    day: date
    confirmed_meals: int
    is_complete: bool
    food_groups: frozenset[str] = frozenset()   # ομάδες των επιβεβαιωμένων τροφίμων της ημέρας


@dataclass(frozen=True)
class CardDrop:
    rule_id: str
    rule_version: str
    tier: str            # "common" | "rare" | "epic"
    day: date
    reason: str


def _streak(today: DayActivity, history: Iterable[DayActivity]) -> int:
    """Συνεχόμενες ημέρες με >= 1 επιβεβαιωμένο γεύμα, που τελειώνουν σήμερα."""
    logged = {d.day for d in history if d.confirmed_meals > 0}
    if today.confirmed_meals > 0:
        logged.add(today.day)
    n, d = 0, today.day
    while d in logged:
        n += 1
        d -= timedelta(days=1)
    return n


def card_drops(today: DayActivity, history: Iterable[DayActivity]) -> list[CardDrop]:
    """Οι κάρτες της ημέρας. Τρέχει μία φορά τη νύχτα (jobs/daily_card_drops.py)."""
    history = [h for h in history if h.day < today.day]
    v = CARD_RULES_VERSION
    drops: list[CardDrop] = []
    if today.confirmed_meals >= 1:
        drops.append(CardDrop("C-LOG-01", v, "common", today.day, "logged at least one meal"))
    if today.is_complete:
        drops.append(CardDrop("C-DAY-01", v, "common", today.day, "logged a complete day"))
    if len(today.food_groups & ENCOURAGED_GROUPS) >= VARIETY_MIN_GROUPS:
        drops.append(CardDrop("C-VAR-01", v, "rare", today.day, f">= {VARIETY_MIN_GROUPS} encouraged food groups"))
    streak = _streak(today, history)
    if streak and streak % 7 == 0:
        drops.append(CardDrop("C-STR-07", v, "epic", today.day, f"{streak}-day logging streak"))
    elif streak and streak % 3 == 0:
        drops.append(CardDrop("C-STR-03", v, "rare", today.day, f"{streak}-day logging streak"))
    # Ανώτατο όριο: κρατά τις πιο σπάνιες
    order = {"epic": 0, "rare": 1, "common": 2}
    return sorted(drops, key=lambda c: order[c.tier])[:MAX_CARDS_PER_DAY]
