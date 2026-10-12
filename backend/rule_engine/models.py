"""
rule_engine/models.py — τα δεδομένα με τα οποία δουλεύει η μηχανή κανόνων.

Ρόλος
-----
Ορίζει ΜΟΝΟ δομές δεδομένων (dataclasses και enums). Δεν περιέχει λογική κανόνων,
δεν διαβάζει αρχεία, δεν μιλά με βάση δεδομένων ή με το FastAPI.

    data_loader.py   διαβάζει τα CSV          -> ReferenceValue, FoodItem
    assessment.py    βρίσκει τιμές αναφοράς    -> ReferenceValue για το προφίλ
    evaluation.py    αθροίζει γεύματα          -> DailyIntake, συνήθης πρόσληψη
    rules/*.py       αποφασίζουν               -> RuleDecision
    engine.py        τα συνδέει όλα με είσοδο ένα EvaluationContext

Δεν είναι το ίδιο με το app/db/models/ (πίνακες SQLAlchemy) ούτε με το app/schemas/
(Pydantic για το API). Το service layer μετατρέπει εκείνα σε αυτά, ώστε η μηχανή
κανόνων να δοκιμάζεται μόνη της, χωρίς βάση και χωρίς server.

Τα αναγνωριστικά θρεπτικών (nutrient_id) και οι τύποι τιμών ακολουθούν το
data/efsa_drv.csv. Τα nutrient_id του πίνακα τροφίμων πρέπει να είναι τα ίδια.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

# Ηλικίες συμμετεχόντων κατά το πρωτόκολλο μελέτης.
MIN_AGE_YEARS = 10
MAX_AGE_YEARS = 16


class Sex(str, Enum):
    MALE = "M"
    FEMALE = "F"


class DRVType(str, Enum):
    """Τύποι τιμών αναφοράς της EFSA, όπως στη στήλη drv_type του efsa_drv.csv."""
    AR = "AR"      # Average Requirement
    PRI = "PRI"    # Population Reference Intake
    AI = "AI"      # Adequate Intake
    RI = "RI"      # Reference Intake range (ποσοστό ενέργειας)
    SAI = "SAI"    # Safe and Adequate Intake (νάτριο, χλώριο)
    ALAP = "ALAP"  # As Low As Possible (κορεσμένα, trans)
    UL = "UL"      # Tolerable Upper Intake Level (efsa_ul.csv)


class ValueBasis(str, Enum):
    """Πώς εκφράζεται η τιμή, όπως στη στήλη basis του efsa_drv.csv."""
    PER_DAY = "per day"
    PER_KG_BODY_WEIGHT = "per kg body weight"   # π.χ. πρωτεΐνη: × βάρος
    PER_MJ_ENERGY = "per MJ of energy"          # π.χ. θειαμίνη, νιασίνη: × ενέργεια
    SHARE_OF_ENERGY = "share of energy"         # π.χ. λίπος, υδατάνθρακες: % ενέργειας
    NONE = ""


class IntakeStatus(str, Enum):
    """Αποτέλεσμα σύγκρισης συνήθους πρόσληψης με τιμή αναφοράς
    (βλ. «Κανόνες EFSA για τη μηχανή κανόνων», ενότητα 1)."""
    LIKELY_INADEQUATE = "likely_inadequate"   # < AR
    UNCERTAIN = "uncertain"                   # >= AR και < PRI
    LIKELY_ADEQUATE = "likely_adequate"       # >= PRI ή >= AI
    NO_CONCLUSION = "no_conclusion"           # < AI: δεν τεκμηριώνει ανεπάρκεια
    ABOVE_REFERENCE = "above_reference"       # > SAI (νάτριο)
    INSUFFICIENT_DATA = "insufficient_data"   # λίγες ημέρες ή λείπει βάρος


class MealSource(str, Enum):
    CAMERA = "camera"   # OliveGemma, επιβεβαιωμένο από το παιδί
    TEXT = "text"       # Krikri, επιβεβαιωμένο από το παιδί
    MANUAL = "manual"   # χειροκίνητη καταχώριση


# --------------------------------------------------------------------- προφίλ

@dataclass(frozen=True)
class UserProfile:
    """Μόνο όσα χρειάζεται η μηχανή κανόνων. Καμία ταυτότητα: ο server γνωρίζει
    μόνο τον κωδικό συμμετέχοντα (πρωτόκολλο, έντυπα συγκατάθεσης)."""
    pseudonym_id: str
    sex: Sex
    age_years: int                       # συμπληρωμένα έτη την ημέρα αξιολόγησης
    weight_kg: Optional[float] = None    # προαιρετικό (βιομετρικά στην εφαρμογή)
    height_cm: Optional[float] = None    # προαιρετικό

    def __post_init__(self) -> None:
        if not self.pseudonym_id:
            raise ValueError("pseudonym_id is required")
        if not MIN_AGE_YEARS <= self.age_years <= MAX_AGE_YEARS:
            raise ValueError(f"age_years must be {MIN_AGE_YEARS}-{MAX_AGE_YEARS} (protocol), got {self.age_years}")
        if self.weight_kg is not None and not 15 <= self.weight_kg <= 200:
            raise ValueError(f"implausible weight_kg: {self.weight_kg}")
        if self.height_cm is not None and not 100 <= self.height_cm <= 220:
            raise ValueError(f"implausible height_cm: {self.height_cm}")


# ----------------------------------------------------------- τιμές αναφοράς

@dataclass(frozen=True)
class ReferenceValue:
    """Μία γραμμή του efsa_drv.csv (ή του efsa_ul.csv)."""
    nutrient_id: str
    drv_type: DRVType
    sex: Sex
    age_min_y: int
    age_max_y: int
    value: float
    unit: str                            # π.χ. "mg/d", "g/kg_bw/d"
    basis: ValueBasis = ValueBasis.PER_DAY
    value_max: Optional[float] = None    # άνω άκρο για εύρη (RI)
    pal: Optional[float] = None          # μόνο για ενέργεια
    source: str = ""                     # π.χ. "V4 Tables 4/6"
    checked: str = ""                    # π.χ. "2 documents agree"

    def applies_to(self, sex: Sex, age_years: int) -> bool:
        return self.sex == sex and self.age_min_y <= age_years <= self.age_max_y


# ------------------------------------------------------------------ τρόφιμα

@dataclass(frozen=True)
class FoodItem:
    """Τρόφιμο του πίνακα σύνθεσης. Τιμές ανά 100 g βρώσιμου μέρους."""
    food_id: str                          # canonical_food_id
    name_el: str
    food_group: str                       # από food_groups.csv
    nutrients_per_100g: dict[str, float]  # nutrient_id -> ποσότητα (μονάδα του πίνακα)
    source: str = ""                      # π.χ. "HHF", "USDA SR Legacy 12345"


@dataclass(frozen=True)
class MealItem:
    food_id: str
    grams: float
    user_confirmed: bool                  # Κανόνας 3: μόνο επιβεβαιωμένα μετρούν

    def __post_init__(self) -> None:
        if self.grams <= 0:
            raise ValueError(f"grams must be > 0, got {self.grams}")


@dataclass(frozen=True)
class MealEntry:
    meal_id: str
    pseudonym_id: str
    logged_at: datetime
    source: MealSource
    items: tuple[MealItem, ...]

    def confirmed_items(self) -> tuple[MealItem, ...]:
        return tuple(i for i in self.items if i.user_confirmed)


# -------------------------------------------------------------- πρόσληψη

@dataclass(frozen=True)
class DailyIntake:
    """Σύνολα μίας ημέρας, από το evaluation.py."""
    day: date
    totals: dict[str, float]              # nutrient_id -> ποσότητα την ημέρα
    is_complete: bool                     # αν το παιδί δήλωσε ότι κατέγραψε όλη την ημέρα


@dataclass(frozen=True)
class EvaluationContext:
    """Η μοναδική είσοδος του engine.evaluate()."""
    profile: UserProfile
    as_of: date
    days: tuple[DailyIntake, ...]         # παράθυρο αξιολόγησης
    references: tuple[ReferenceValue, ...]
    min_complete_days: int = 3            # ΠΡΟΣΧΕΔΙΟ: να οριστεί πριν το πάγωμα

    def complete_days(self) -> tuple[DailyIntake, ...]:
        return tuple(d for d in self.days if d.is_complete)

    def has_enough_days(self) -> bool:
        return len(self.complete_days()) >= self.min_complete_days


# ---------------------------------------------------------------- έξοδος

@dataclass(frozen=True)
class RuleDecision:
    """Έξοδος κάθε κανόνα. Οι αριθμοί μένουν στο research_values· το τι βλέπει
    το παιδί αποφασίζεται στο presentation layer."""
    rule_id: str                          # π.χ. "R-FE-01"
    rule_version: str
    nutrient_id: str
    status: IntakeStatus
    days_used: int
    citation: str
    research_values: dict[str, float] = field(default_factory=dict)
    food_group_hint: tuple[str, ...] = ()
    message_template_id: Optional[str] = None