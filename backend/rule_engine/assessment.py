"""
rule_engine/assessment.py — Layer 1: ποιες τιμές αναφοράς ισχύουν για αυτό το παιδί.

Είσοδος: UserProfile + όλες οι ReferenceValue (από το data_loader).
Έξοδος:  Assessment, δηλαδή για κάθε (θρεπτικό, τύπος τιμής) ΜΙΑ τιμή, μετατρεμμένη
         όπου γίνεται σε ποσότητα ανά ημέρα για το συγκεκριμένο παιδί.

Δεν συγκρίνει πρόσληψη (αυτό είναι το evaluation.py, Layer 2) και δεν αποφασίζει
τίποτα (αυτό είναι οι κανόνες, Layer 3).

Τι ΔΕΝ κάνει, και γιατί
-----------------------
- Ατομικές ενεργειακές ανάγκες (EER): η EFSA δίνει την ενέργεια ως μέσο όρο ομάδας ανά
  επίπεδο δραστηριότητας (PAL), «of limited use for individuals». Το έγγραφο πηγών του
  project αποκλείει ατομικό ενεργειακό στόχο. Οι γραμμές ενέργειας αγνοούνται εδώ.
- Εκατοστημόριο ΔΜΣ: υπολογίζεται μόνο στην ερευνητική βάση, ποτέ στην εφαρμογή.
Αν ο επιβλέπων αποφασίσει διαφορετικά, προστίθενται ως ξεχωριστές συναρτήσεις.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import DRVType, ReferenceValue, UserProfile, ValueBasis

EXCLUDED_NUTRIENTS = frozenset({"energy"})   # βλ. docstring


@dataclass(frozen=True)
class AssessedReference:
    """Μία τιμή αναφοράς για ένα συγκεκριμένο παιδί."""
    nutrient_id: str
    drv_type: DRVType
    value: Optional[float]          # στη μονάδα `unit`· None για ALAP
    value_max: Optional[float]      # μόνο για εύρη RI
    unit: str                       # μετά τη μετατροπή, π.χ. "g/d" για πρωτεΐνη
    basis: ValueBasis               # μετά τη μετατροπή
    source: str
    checked: str
    derived_from: Optional[str] = None   # π.χ. "0.71 g/kg_bw/d × 45.0 kg"


@dataclass(frozen=True)
class Assessment:
    profile: UserProfile
    references: dict[tuple[str, DRVType], AssessedReference]
    # θρεπτικά που δεν μπορούν να αξιολογηθούν και γιατί, π.χ. {"protein": "weight_kg missing"}
    unavailable: dict[str, str] = field(default_factory=dict)

    def get(self, nutrient_id: str, drv_type: DRVType) -> Optional[AssessedReference]:
        return self.references.get((nutrient_id, drv_type))


def select_references(profile: UserProfile, references: Iterable[ReferenceValue]) -> dict[tuple[str, DRVType], ReferenceValue]:
    """Βρίσκει τις γραμμές που ισχύουν για φύλο και ηλικία. Οι ηλικιακές ζώνες διαφέρουν ανά
    θρεπτικό, γι' αυτό κάθε γραμμή ελέγχεται με τα δικά της όρια. Αν για ένα (θρεπτικό, τύπο)
    ταιριάζουν δύο γραμμές, ο πίνακας είναι λάθος και σταματάμε."""
    chosen: dict[tuple[str, DRVType], ReferenceValue] = {}
    for ref in references:
        if ref.nutrient_id in EXCLUDED_NUTRIENTS or ref.pal is not None:
            continue
        if not ref.applies_to(profile.sex, profile.age_years):
            continue
        key = (ref.nutrient_id, ref.drv_type)
        if key in chosen:
            raise ValueError(f"ambiguous reference for {key} at age {profile.age_years}, sex {profile.sex.value}")
        chosen[key] = ref
    return chosen


def _personalise(ref: ReferenceValue, profile: UserProfile) -> tuple[Optional[AssessedReference], Optional[str]]:
    """Μετατρέπει τιμές ανά kg βάρους σε ανά ημέρα. Οι τιμές ανά MJ ενέργειας (θειαμίνη,
    νιασίνη) μένουν όπως είναι: χρειάζονται την ενεργειακή πρόσληψη, που είναι στο Layer 2."""
    common = dict(nutrient_id=ref.nutrient_id, drv_type=ref.drv_type, value_max=ref.value_max,
                  source=ref.source, checked=ref.checked)
    if ref.basis is ValueBasis.PER_KG_BODY_WEIGHT:
        if profile.weight_kg is None:
            return None, "weight_kg missing"
        per_day = round(ref.value * profile.weight_kg, 2)
        return AssessedReference(value=per_day, unit=ref.unit.replace("/kg_bw", ""), basis=ValueBasis.PER_DAY,
                                 derived_from=f"{ref.value} {ref.unit} × {profile.weight_kg} kg", **common), None
    return AssessedReference(value=ref.value, unit=ref.unit, basis=ref.basis, **common), None


def assess(profile: UserProfile, references: Iterable[ReferenceValue]) -> Assessment:
    """Layer 1: οι τιμές αναφοράς του παιδιού."""
    out: dict[tuple[str, DRVType], AssessedReference] = {}
    unavailable: dict[str, str] = {}
    for key, ref in select_references(profile, references).items():
        assessed, reason = _personalise(ref, profile)
        if assessed is None:
            unavailable[ref.nutrient_id] = reason or "unavailable"
        else:
            out[key] = assessed
    return Assessment(profile=profile, references=out, unavailable=unavailable)