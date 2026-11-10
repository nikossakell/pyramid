"""
ai_pipeline/food_resolver.py — Βήμα 3.3: ελληνικό όνομα τροφίμου -> food_id του πίνακα τροφίμων. Ντετερμινιστικό, χωρίς LLM.

    κανονικοποίηση ──► ακριβές όνομα ──► alias ──► fuzzy (difflib, ratio ≥ FUZZY_MIN_RATIO) ──► None

Κανονικοποίηση: το normalize() του presentation/lexicon.py (πεζά, χωρίς τόνους και διαλυτικά, ς -> σ) και, επιπλέον,
ό,τι δεν είναι γράμμα ή ψηφίο γίνεται ένα κενό. Έτσι «Φακές!», «φακες» και «ΦΑΚΈΣ» είναι το ίδιο.

Αν αμφιβάλλει, ΔΕΝ μαντεύει: όταν δύο διαφορετικά τρόφιμα έχουν το ίδιο καλύτερο fuzzy σκορ, επιστρέφει None και
το παιδί διαλέγει από την αναζήτηση. Ο resolver δεν γνωρίζει θρεπτικά ούτε βάση: παίρνει μόνο (food_id, όνομα)
και (food_id, alias), ώστε να δουλεύει ίδια με τον demo πίνακα τροφίμων και με τον πραγματικό.

search() δίνει υποψήφια food_id για αυτόματη συμπλήρωση: ίδιο όνομα, αρχή λέξης, υποσυμβολοσειρά, fuzzy.
"""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional

from ai_pipeline.presentation.lexicon import normalize

FUZZY_MIN_RATIO = 0.85     # ΠΡΟΣΧΕΔΙΟ: όπως το final_plan
MAX_SEARCH_LIMIT = 50
_NON_WORD = re.compile(r"[\W_]+")


def key(text: str) -> str:
    """Κανονική μορφή για σύγκριση."""
    return _NON_WORD.sub(" ", normalize(text or "")).strip()


@dataclass(frozen=True)
class Resolution:
    food_id: str
    method: str          # "exact" | "alias" | "fuzzy"
    score: float         # 1.0 για exact/alias
    matched: str         # η κανονικοποιημένη μορφή που ταίριαξε


@dataclass(frozen=True)
class _Entry:
    text: str            # κανονικοποιημένο όνομα ή alias
    food_id: str
    kind: str            # "name" | "alias"


class FoodResolver:
    def __init__(self, names: Iterable[tuple[str, str]], aliases: Iterable[tuple[str, str]] = ()):
        """names: (food_id, name_el)· aliases: (food_id, alias). Συγκρούσεις (ίδια κανονική μορφή για δύο
        διαφορετικά τρόφιμα) είναι σφάλμα δεδομένων και σταματούν τη φόρτωση."""
        self._order: dict[str, int] = {}
        self._by_text: dict[str, _Entry] = {}
        self._entries: list[_Entry] = []
        for food_id, name in names:
            self._order.setdefault(food_id, len(self._order))
            self._add(_Entry(key(name), food_id, "name"))
        for food_id, alias in aliases:
            if food_id not in self._order:
                raise ValueError(f"alias {alias!r} refers to unknown food_id {food_id!r}")
            self._add(_Entry(key(alias), food_id, "alias"))

    def _add(self, entry: _Entry) -> None:
        if not entry.text:
            raise ValueError(f"empty name/alias for {entry.food_id!r}")
        existing = self._by_text.get(entry.text)
        if existing is not None:
            if existing.food_id != entry.food_id:
                raise ValueError(f"{entry.text!r} maps to both {existing.food_id!r} and {entry.food_id!r}")
            return
        self._by_text[entry.text] = entry
        self._entries.append(entry)

    def resolve(self, text: str) -> Optional[Resolution]:
        q = key(text)
        if not q:
            return None
        hit = self._by_text.get(q)
        if hit is not None:
            return Resolution(hit.food_id, "exact" if hit.kind == "name" else "alias", 1.0, hit.text)
        best: dict[str, tuple[float, str]] = {}          # food_id -> (καλύτερο σκορ, κείμενο)
        for e in self._entries:
            m = SequenceMatcher(None, q, e.text)
            if m.real_quick_ratio() < FUZZY_MIN_RATIO or m.quick_ratio() < FUZZY_MIN_RATIO:
                continue
            r = m.ratio()
            if r >= FUZZY_MIN_RATIO and r > best.get(e.food_id, (0.0, ""))[0]:
                best[e.food_id] = (r, e.text)
        if not best:
            return None
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
        if len(ranked) > 1 and ranked[0][1][0] == ranked[1][1][0]:
            return None                                   # ισοπαλία δύο τροφίμων: δεν μαντεύουμε
        food_id, (score, text_) = ranked[0]
        return Resolution(food_id, "fuzzy", round(score, 3), text_)

    def search(self, q: str, limit: int = 10) -> list[str]:
        """Έως limit food_id, με σειρά: ίδιο κείμενο, αρχή λέξης, υποσυμβολοσειρά, fuzzy (ανά λέξη ή ολόκληρο)."""
        q = key(q)
        limit = max(0, min(limit, MAX_SEARCH_LIMIT))
        if not q or not limit:
            return []
        rank: dict[str, int] = {}
        for e in self._entries:
            words = e.text.split()
            if e.text == q:
                r = 0
            elif e.text.startswith(q) or any(w.startswith(q) for w in words):
                r = 1
            elif q in e.text:
                r = 2
            elif any(SequenceMatcher(None, q, t).ratio() >= FUZZY_MIN_RATIO for t in (e.text, *words)):
                r = 3
            else:
                continue
            rank[e.food_id] = min(r, rank.get(e.food_id, r))
        return sorted(rank, key=lambda fid: (rank[fid], self._order[fid]))[:limit]
