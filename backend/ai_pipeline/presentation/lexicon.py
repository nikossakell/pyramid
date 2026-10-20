"""
ai_pipeline/presentation/lexicon.py — τα ελληνικά λεξικά του presentation layer.

Όλο το λεκτικό περιεχόμενο είναι σε CSV στο data/, όχι στον κώδικα, ώστε ο διαιτολόγος και ο
παιδίατρος να το διορθώνουν χωρίς να αγγίζουν Python:
    message_templates_el.csv   σταθερά κείμενα ανά message_template_id
    food_groups.csv            ελληνικό όνομα και λέξεις-κλειδιά ανά ομάδα τροφίμων
    nutrient_names_el.csv      ελληνικό όνομα και μοτίβο αναγνώρισης ανά θρεπτικό
    validator_lexicon_el.csv   απαγορευμένοι όροι, αριθμητικά, μονάδες, λέξεις κατεύθυνσης

Κάθε αρχείο παίρνει sha256, που μπαίνει στο audit (data_versions), ώστε να φαίνεται ποια έκδοση
λεξικού έκρινε κάθε μήνυμα (Κανόνας 5 του πλάνου).
"""
import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
FILES = {
    "templates": "message_templates_el.csv",
    "food_groups": "food_groups.csv",
    "nutrients": "nutrient_names_el.csv",
    "validator": "validator_lexicon_el.csv",
}
REQUIRED = {
    "templates": {"template_id", "text_el", "status"},
    "food_groups": {"group_id", "name_el", "keywords", "status"},
    "nutrients": {"nutrient_id", "name_el", "pattern", "status"},
    "validator": {"category", "term", "match"},
}
VALIDATOR_CATEGORIES = {"forbidden", "diagnostic", "number_word", "unit", "reduce", "increase", "other_nutrient"}
MATCH_TYPES = {"token", "stem", "phrase"}


def normalize(text: str) -> str:
    """Πεζά, χωρίς τόνους και διαλυτικά, τελικό σίγμα -> σ, σύμβολο μικρο (µ) -> μ.
    Έτσι «ΚΌΨΕ», «Κόψε» και «κοψε» ταιριάζουν όλα με τον όρο «κοψε»."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.lower().replace("ς", "σ")


def tokens(normalized: str) -> list[str]:
    return re.findall(r"\w+", normalized)


@dataclass(frozen=True)
class Term:
    category: str
    term: str        # κανονικοποιημένο
    match: str       # token | stem | phrase


@dataclass(frozen=True)
class FoodGroup:
    group_id: str
    name_el: str
    stems: tuple[str, ...]


@dataclass(frozen=True)
class NutrientName:
    nutrient_id: str
    name_el: str
    pattern: re.Pattern


@dataclass(frozen=True)
class Lexicon:
    templates: dict[str, str]
    food_groups: dict[str, FoodGroup]
    nutrients: dict[str, NutrientName]
    terms: tuple[Term, ...]
    versions: dict[str, str]          # αρχείο -> sha256

    def terms_of(self, category: str) -> tuple[Term, ...]:
        return tuple(t for t in self.terms if t.category == category)


def _read(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        rows = []
        for line, row in enumerate(reader, start=2):
            for col in required:
                if not (row.get(col) or "").strip():
                    raise ValueError(f"{path.name}, line {line}: empty '{col}'")
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lexicon(data_dir: Optional[Path] = None) -> Lexicon:
    d = Path(data_dir) if data_dir else DATA_DIR
    paths = {k: d / v for k, v in FILES.items()}
    rows = {k: _read(p, REQUIRED[k]) for k, p in paths.items()}

    templates = {r["template_id"]: r["text_el"] for r in rows["templates"]}
    food_groups = {
        r["group_id"]: FoodGroup(r["group_id"], r["name_el"],
                                 tuple(normalize(s) for s in r["keywords"].split(";") if s.strip()))
        for r in rows["food_groups"]
    }
    nutrients = {r["nutrient_id"]: NutrientName(r["nutrient_id"], r["name_el"], re.compile(r["pattern"]))
                 for r in rows["nutrients"]}
    terms = []
    for line, r in enumerate(rows["validator"], start=2):
        if r["category"] not in VALIDATOR_CATEGORIES or r["match"] not in MATCH_TYPES:
            raise ValueError(f"{FILES['validator']}, line {line}: bad category or match '{r['category']}/{r['match']}'")
        terms.append(Term(r["category"], normalize(r["term"]), r["match"]))

    for name, keys in (("templates", templates), ("food_groups", food_groups), ("nutrients", nutrients)):
        if len(keys) != len(rows[name]):
            raise ValueError(f"{FILES[name]}: duplicate ids")
    return Lexicon(templates, food_groups, nutrients, tuple(terms),
                   {FILES[k]: _sha256(p) for k, p in paths.items()})


@lru_cache(maxsize=1)
def default_lexicon() -> Lexicon:
    return load_lexicon()
