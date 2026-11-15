"""
ai_pipeline/food_resolver.py — Βήμα 3.3: ελληνικό όνομα τροφίμου -> food_id του πίνακα τροφίμων. Ντετερμινιστικό, χωρίς LLM.

    κανονικοποίηση ──► ακριβές όνομα ──► alias ──► fuzzy (difflib, ratio ≥ FUZZY_MIN_RATIO) ──► None

Κανονικοποίηση: το normalize() του presentation/lexicon.py (πεζά, χωρίς τόνους και διαλυτικά, ς -> σ) και, επιπλέον,
ό,τι δεν είναι γράμμα ή ψηφίο γίνεται ένα κενό. Έτσι «Φακές!», «φακες» και «ΦΑΚΈΣ» είναι το ίδιο.

Αν αμφιβάλλει, ΔΕΝ μαντεύει: όταν δύο διαφορετικά τρόφιμα έχουν το ίδιο καλύτερο fuzzy σκορ, επιστρέφει None και
το παιδί διαλέγει από την αναζήτηση. Ο resolver δεν γνωρίζει θρεπτικά ούτε βάση: παίρνει μόνο (food_id, όνομα)
και (food_id, alias), ώστε να δουλεύει ίδια με τον demo πίνακα τροφίμων και με τον πραγματικό.

search() δίνει υποψήφια food_id για αυτόματη συμπλήρωση: ίδιο όνομα, αρχή λέξης, υποσυμβολοσειρά, fuzzy.
candidates() δίνει έως k «κοντινά» food_id για να διαλέξει το παιδί («Μήπως είναι…», «Δεν το βρήκα, διάλεξε»),
και όταν η resolve() επιστρέφει None (ισοπαλία ή χαμηλό σκορ). Πιο χαλαρό κατώφλι, ποτέ αυτόματη επιλογή, ποτέ σκορ
στην έξοδο. Η resolve() δεν αλλάζει.
"""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional

from ai_pipeline.presentation.lexicon import normalize

FUZZY_MIN_RATIO = 0.85     # ΠΡΟΣΧΕΔΙΟ: όπως το final_plan
MAX_SEARCH_LIMIT = 50
# Προεπιλογές των δύο κατωφλίων του candidates(). Η εφαρμογή τα περνά από τις ρυθμίσεις (CANDIDATE_MIN_RATIO,
# CANDIDATE_PREFIX_MIN του app/config.py) στον constructor· εδώ μένουν μόνο ως default για χρήση χωρίς ρυθμίσεις.
CANDIDATE_MIN_RATIO = 0.75  # ΠΡΟΣΧΕΔΙΟ: ελάχιστη ομοιότητα για να ΠΡΟΤΑΘΕΙ (όχι να επιλεγεί) ένα τρόφιμο
CANDIDATE_MIN_PREFIX = 4    # ΠΡΟΣΧΕΔΙΟ: ή κοινή αρχή λέξης τόσων γραμμάτων (σύνθετες λέξεις, υποκοριστικά)
MAX_CANDIDATES = 10
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
    def __init__(self, names: Iterable[tuple[str, str]], aliases: Iterable[tuple[str, str]] = (),
                 candidate_prefix_min: int = CANDIDATE_MIN_PREFIX, candidate_min_ratio: float = CANDIDATE_MIN_RATIO):
        """names: (food_id, name_el)· aliases: (food_id, alias). Συγκρούσεις (ίδια κανονική μορφή για δύο
        διαφορετικά τρόφιμα) είναι σφάλμα δεδομένων και σταματούν τη φόρτωση.
        candidate_prefix_min / candidate_min_ratio: τα κατώφλια του candidates() (ρυθμίσεις της εφαρμογής)."""
        if candidate_prefix_min < 1 or not 0 < candidate_min_ratio <= 1:
            raise ValueError("candidate_prefix_min must be >= 1 and candidate_min_ratio in (0, 1]")
        self.candidate_prefix_min = candidate_prefix_min
        self.candidate_min_ratio = candidate_min_ratio
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

    def candidates(self, text: str, k: int = 3) -> list[str]:
        """Έως k food_id που μοιάζουν με το text, για να διαλέξει το παιδί. Πρώτα όσα δίνει η search() (ίδιο κείμενο,
        αρχή λέξης, υποσυμβολοσειρά, fuzzy ≥ FUZZY_MIN_RATIO)· μετά όσα μοιράζονται αρχή λέξης ≥ candidate_prefix_min
        γραμμάτων («ντοματοσαλάτα» ~ «ντομάτα») ή έχουν ομοιότητα ≥ candidate_min_ratio (ολόκληρο κείμενο ή λέξη προς
        λέξη), από το πιο όμοιο. Ντετερμινιστικό· δεν επιστρέφει σκορ."""
        q = key(text)
        k = max(0, min(k, MAX_CANDIDATES))
        if not q or not k:
            return []
        out = self.search(q, k)
        if len(out) >= k:
            return out[:k]
        prefix_min, min_ratio = self.candidate_prefix_min, self.candidate_min_ratio
        q_words = [w for w in q.split() if len(w) >= prefix_min]
        best: dict[str, tuple[int, float]] = {}                  # food_id -> (κοινή αρχή λέξης, ομοιότητα)
        for e in self._entries:
            if e.food_id in out:
                continue
            words = e.text.split()
            prefix = max((_common_prefix(a, b) for a in q_words for b in words), default=0)
            ratio = max(SequenceMatcher(None, a, b).ratio() for a in {q, *q_words} for b in {e.text, *words})
            if prefix < prefix_min and ratio < min_ratio:
                continue
            score = (prefix if prefix >= prefix_min else 0, ratio)
            if score > best.get(e.food_id, (-1, 0.0)):
                best[e.food_id] = score
        out += sorted(best, key=lambda fid: (-best[fid][0], -best[fid][1], self._order[fid]))
        return out[:k]


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n
