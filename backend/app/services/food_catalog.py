"""
app/services/food_catalog.py — ο πίνακας τροφίμων (στατικά δεδομένα από CSV, όχι πίνακας της βάσης).

ΠΡΟΣΟΧΗ: σήμερα υπάρχει ΜΟΝΟ το data/demo_foods.csv. Οι τιμές του είναι ΕΝΔΕΙΚΤΙΚΕΣ (source = «DEMO — ΟΧΙ
πραγματικές τιμές», is_demo = true) και ΔΕΝ χρησιμοποιούνται ποτέ για την έρευνα: σε ENVIRONMENT=production η
εφαρμογή αρνείται να ξεκινήσει αν ο πίνακας έχει έστω μία demo γραμμή (create_app).

Μορφή (FOODS_CSV):
  food_id, name_el, food_group (κωδικός του food_groups.csv), portion_small_g, portion_medium_g, portion_large_g,
  <nutrient_id>__<μονάδα> ανά 100 g (π.χ. iron__mg, sodium__g, vitamin_a__ug_RE, folate__ug_DFE), source, is_demo.
Η μονάδα κάθε θρεπτικού ΠΡΕΠΕΙ να είναι ο αριθμητής της στήλης unit του efsa_drv.csv ("mg/d" -> "mg",
"g/kg_bw/d" -> "g", "ug_DFE/d" -> "ug_DFE"), γιατί έτσι αθροίζει το rule_engine/evaluation.py· αλλιώς η φόρτωση
σταματά. Κενή τιμή = άγνωστη, όχι μηδέν. Οι μερίδες σε γραμμάρια είναι ΠΡΟΣΧΕΔΙΟ (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ).
Συνώνυμα (FOOD_ALIASES_CSV): food_id, alias.

Ομάδες εμφάνισης (DISPLAY_FOOD_GROUPS_CSV, ΠΡΟΣΧΕΔΙΟ — έγκριση διαιτολόγου): code, label_el, shown, sort, status.
Οι 11 κύριες ομάδες (Απόφαση 16) όπως τις βλέπει το παιδί. shown=false: η ομάδα υπάρχει για αναζήτηση/κατηγορίες,
αλλά το UI δεν τη δείχνει ως «ομάδα που είχες» (δεν μπαίνει στο food_groups_today ούτε στην απάντηση του confirm).
Κάθε κύρια ομάδα τροφίμου του πίνακα πρέπει να υπάρχει εδώ· αλλιώς η φόρτωση σταματά.

Κάθε αρχείο παίρνει sha256 (versions): μπαίνει στα data_versions του engine και στο audit (Κανόνας 5).
"""
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ai_pipeline.food_resolver import CANDIDATE_MIN_PREFIX, CANDIDATE_MIN_RATIO, FoodResolver, key as resolver_key
from rule_engine.models import FoodItem

from app.db.models.enums import Portion

FOOD_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
BASE_COLUMNS = ("food_id", "name_el", "food_group", "portion_small_g", "portion_medium_g", "portion_large_g",
                "source", "is_demo")
PORTION_COLUMNS = {Portion.SMALL.value: "portion_small_g", Portion.MEDIUM.value: "portion_medium_g",
                   Portion.LARGE.value: "portion_large_g"}


class FoodCatalogError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class CatalogFood:
    item: FoodItem                     # ό,τι χρειάζεται ο rule engine (θρεπτικά ανά 100 g)
    portions_g: dict[str, float]       # small | medium | large -> γραμμάρια
    is_demo: bool

    @property
    def food_id(self) -> str:
        return self.item.food_id

    @property
    def name_el(self) -> str:
        return self.item.name_el

    @property
    def food_group(self) -> str:
        return self.item.food_group


@dataclass(frozen=True)
class DisplayGroup:
    code: str
    label_el: str
    shown: bool                        # False: δεν εμφανίζεται ως «ομάδα που είχες»
    sort: int                          # σειρά εμφάνισης (βγαίνει στο /food-groups· δεν είναι τιμή θρεπτικού)


@dataclass(frozen=True)
class FoodCatalog:
    foods: dict[str, CatalogFood]
    resolver: FoodResolver
    versions: dict[str, str]           # όνομα αρχείου -> sha256
    display_groups: tuple[DisplayGroup, ...] = ()   # ταξινομημένες κατά sort· κενό = χωρίς αρχείο εμφάνισης

    @property
    def has_demo(self) -> bool:
        return any(f.is_demo for f in self.foods.values())

    def get(self, food_id: str) -> Optional[CatalogFood]:
        return self.foods.get(food_id)

    def grams(self, food_id: str, portion: str) -> float:
        return self.foods[food_id].portions_g[portion]

    def food_items(self) -> dict[str, FoodItem]:
        return {fid: f.item for fid, f in self.foods.items()}

    @property
    def group_codes(self) -> frozenset[str]:
        """Οι κύριες ομάδες που δέχεται το API (αρχείο εμφάνισης ή, αν λείπει, οι ομάδες των τροφίμων)."""
        return frozenset(g.code for g in self.display_groups) or frozenset(f.food_group for f in self.foods.values())

    def shown_groups(self, codes: Iterable[str]) -> list[str]:
        """Από τους κωδικούς, μόνο όσοι έχουν shown=true, με τη σειρά εμφάνισης. Χωρίς αρχείο εμφάνισης: όλοι, αλφαβητικά."""
        codes = set(codes)
        if not self.display_groups:
            return sorted(codes)
        return [g.code for g in self.display_groups if g.shown and g.code in codes]

    def foods_in_group(self, code: str) -> list[CatalogFood]:
        return sorted((f for f in self.foods.values() if f.food_group == code), key=lambda f: resolver_key(f.name_el))


def drv_unit_numerators(efsa_drv_csv: Path) -> dict[str, str]:
    """nutrient_id -> αριθμητής της μονάδας του efsa_drv.csv (π.χ. "g/kg_bw/d" -> "g")."""
    out: dict[str, str] = {}
    with Path(efsa_drv_csv).open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            unit = (r.get("unit") or "").strip()
            if not unit:
                continue
            num = unit.split("/")[0]
            if out.setdefault(r["nutrient_id"].strip(), num) != num:
                raise FoodCatalogError(f"efsa_drv.csv: {r['nutrient_id']} has more than one unit")
    return out


def _group_ids(food_groups_csv: Path) -> set[str]:
    with Path(food_groups_csv).open(encoding="utf-8", newline="") as f:
        return {r["group_id"].strip() for r in csv.DictReader(f)}


def _float(value: str, where: str, allow_empty: bool) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        if allow_empty:
            return None
        raise FoodCatalogError(f"{where}: empty value")
    try:
        v = float(value)
    except ValueError as e:
        raise FoodCatalogError(f"{where}: not a number: {value!r}") from e
    if v < 0:
        raise FoodCatalogError(f"{where}: negative value")
    return v


DISPLAY_COLUMNS = ("code", "label_el", "shown", "sort")


def load_display_groups(display_csv: Path, known_groups: set[str]) -> tuple[DisplayGroup, ...]:
    display_csv = Path(display_csv)
    out: dict[str, DisplayGroup] = {}
    with display_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in DISPLAY_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise FoodCatalogError(f"{display_csv.name}: missing columns {missing}")
        for line, r in enumerate(reader, start=2):
            where = f"{display_csv.name} line {line}"
            code, label = (r["code"] or "").strip(), (r["label_el"] or "").strip()
            shown, sort = (r["shown"] or "").strip().lower(), (r["sort"] or "").strip()
            if code not in known_groups:
                raise FoodCatalogError(f"{where}: group {code!r} not in food_groups.csv")
            if code in out:
                raise FoodCatalogError(f"{where}: duplicate group {code!r}")
            if not label or re.search(r"\d", label):
                raise FoodCatalogError(f"{where}: label_el empty or with digits")
            if shown not in ("true", "false") or not sort.isdigit():
                raise FoodCatalogError(f"{where}: shown must be true/false and sort a whole number")
            out[code] = DisplayGroup(code, label, shown == "true", int(sort))
    if not out:
        raise FoodCatalogError(f"{display_csv.name}: no groups")
    return tuple(sorted(out.values(), key=lambda g: (g.sort, g.code)))


def load_catalog(foods_csv: Path, aliases_csv: Path, efsa_drv_csv: Path, food_groups_csv: Path,
                 display_groups_csv: Optional[Path] = None, *, candidate_prefix_min: int = CANDIDATE_MIN_PREFIX,
                 candidate_min_ratio: float = CANDIDATE_MIN_RATIO) -> FoodCatalog:
    foods_csv, aliases_csv = Path(foods_csv), Path(aliases_csv)
    units = drv_unit_numerators(efsa_drv_csv)
    groups = _group_ids(food_groups_csv)

    with foods_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing = [c for c in BASE_COLUMNS if c not in header]
        if missing:
            raise FoodCatalogError(f"{foods_csv.name}: missing columns {missing}")
        nutrient_cols: dict[str, str] = {}
        for col in header:
            if col in BASE_COLUMNS:
                continue
            nutrient_id, sep, unit = col.partition("__")
            if not sep:
                raise FoodCatalogError(f"{foods_csv.name}: column {col!r} is not <nutrient_id>__<unit>")
            if nutrient_id not in units:
                raise FoodCatalogError(f"{foods_csv.name}: {nutrient_id!r} is not in efsa_drv.csv")
            if unit != units[nutrient_id]:
                raise FoodCatalogError(f"{foods_csv.name}: {nutrient_id} in {unit!r}, efsa_drv.csv uses {units[nutrient_id]!r}")
            nutrient_cols[col] = nutrient_id

        foods: dict[str, CatalogFood] = {}
        for line, r in enumerate(reader, start=2):
            where = f"{foods_csv.name} line {line}"
            fid = (r["food_id"] or "").strip()
            if not FOOD_ID.match(fid):
                raise FoodCatalogError(f"{where}: bad food_id {fid!r}")
            if fid in foods:
                raise FoodCatalogError(f"{where}: duplicate food_id {fid!r}")
            name = (r["name_el"] or "").strip()
            group = (r["food_group"] or "").strip()
            if not name or group not in groups:
                raise FoodCatalogError(f"{where}: empty name or food_group {group!r} not in food_groups.csv")
            portions = {p: _float(r[c], f"{where} {c}", allow_empty=False) for p, c in PORTION_COLUMNS.items()}
            if not 0 < portions["small"] < portions["medium"] < portions["large"]:
                raise FoodCatalogError(f"{where}: portions must be 0 < small < medium < large")
            is_demo = (r["is_demo"] or "").strip().lower()
            if is_demo not in ("true", "false"):
                raise FoodCatalogError(f"{where}: is_demo must be true or false")
            source = (r["source"] or "").strip()
            if not source or ("DEMO" in source.upper()) != (is_demo == "true"):
                raise FoodCatalogError(f"{where}: source and is_demo disagree (demo rows: source «DEMO …», is_demo=true)")
            nutrients = {n: v for col, n in nutrient_cols.items()
                         if (v := _float(r[col], f"{where} {col}", allow_empty=True)) is not None}
            foods[fid] = CatalogFood(FoodItem(fid, name, group, nutrients, source), portions, is_demo == "true")

    if not foods:
        raise FoodCatalogError(f"{foods_csv.name}: no foods")
    with aliases_csv.open(encoding="utf-8", newline="") as f:
        aliases = [((r["food_id"] or "").strip(), (r["alias"] or "").strip()) for r in csv.DictReader(f)]
    try:
        resolver = FoodResolver(((fid, f.name_el) for fid, f in foods.items()), aliases,
                                candidate_prefix_min=candidate_prefix_min, candidate_min_ratio=candidate_min_ratio)
    except ValueError as e:
        raise FoodCatalogError(f"{aliases_csv.name}: {e}") from e

    files = [foods_csv, aliases_csv, efsa_drv_csv, food_groups_csv]
    display: tuple[DisplayGroup, ...] = ()
    if display_groups_csv is not None:
        display = load_display_groups(display_groups_csv, groups)
        codes = {g.code for g in display}
        orphan = sorted({f.food_group for f in foods.values()} - codes)
        if orphan:
            raise FoodCatalogError(f"{Path(display_groups_csv).name}: food groups without display row: {orphan}")
        files.append(Path(display_groups_csv))
    versions = {Path(p).name: sha256_file(p) for p in files}
    return FoodCatalog(foods, resolver, versions, display)
