"""
rule_engine/evaluation.py — Layer 2: τι έφαγε το παιδί σε σχέση με τις τιμές αναφοράς.

Δύο βήματα:
1. daily_nutrient_totals(): από τα επιβεβαιωμένα γεύματα μιας ημέρας -> DailyIntake.
2. evaluate_intake(): από τις ημέρες του παραθύρου (EvaluationContext) και το Assessment
   του Layer 1 -> ένα NutrientEvaluation ανά θρεπτικό.

Αρχές (βλ. «Κανόνες EFSA για τη μηχανή κανόνων», ενότητα 1):
- Συγκρίνεται η ΣΥΝΗΘΗΣ πρόσληψη (μέσος όρος πλήρων ημερών), ποτέ ένα γεύμα ή μία ημέρα.
- Λιγότερες από min_complete_days πλήρεις ημέρες -> INSUFFICIENT_DATA.
- Τιμή που λείπει από τον πίνακα τροφίμων = άγνωστο, όχι μηδέν.

Σύμβαση μονάδων για τον πίνακα τροφίμων (FoodItem.nutrients_per_100g):
κάθε θρεπτικό στη μονάδα της τιμής αναφοράς χωρίς το "/d" (σίδηρος mg, νάτριο g, φυλλικό
ug_DFE κ.λπ.)· ενέργεια σε MJ· λίπος, υδατάνθρακες, πρωτεΐνη, φυτικές ίνες, LA, ALA σε g.
Η μετατροπή από τις μονάδες της πηγής γίνεται κατά τη φόρτωση του πίνακα, όχι εδώ.
"""
from datetime import date
from statistics import mean
from typing import Iterable, Mapping, Optional

from .assessment import Assessment
from .models import (
    DailyIntake, DRVType, EvaluationContext, FoodItem, IntakeStatus, MealEntry,
    NutrientEvaluation, ValueBasis,
)

# Συντελεστές ενέργειας, Κανονισμός (ΕΕ) 1169/2011, Παράρτημα XIV (kJ ανά g).
# Για τα ποσοστά ενέργειας (RI). Σταθερές, όχι κανόνες.
ENERGY_KJ_PER_G = {"fat_total": 37.0, "carbohydrate": 17.0, "la": 37.0, "ala": 37.0}
ENERGY_NUTRIENT = "energy"   # MJ ανά ημέρα στα DailyIntake.totals


# --------------------------------------------------------------- βήμα 1

def daily_nutrient_totals(meals: Iterable[MealEntry], foods: Mapping[str, FoodItem], day: date,
                          is_complete: bool) -> DailyIntake:
    """Αθροίζει grams/100 × τιμή ανά 100 g για τα ΕΠΙΒΕΒΑΙΩΜΕΝΑ τρόφιμα της ημέρας.
    Γεύματα άλλων ημερών αγνοούνται. Άγνωστο food_id σταματά με σφάλμα: ο Food Resolver
    πρέπει να έχει επιστρέψει μόνο τρόφιμα της βάσης."""
    items = [i for m in meals if m.logged_at.date() == day for i in m.confirmed_items()]
    for i in items:
        if i.food_id not in foods:
            raise KeyError(f"food_id not in food table: {i.food_id}")

    all_nutrients = {n for i in items for n in foods[i.food_id].nutrients_per_100g}
    totals: dict[str, float] = {}
    missing: set[str] = set()
    for n in all_nutrients:
        values = [foods[i.food_id].nutrients_per_100g.get(n) for i in items]
        if any(v is None for v in values):
            missing.add(n)            # κάποιο τρόφιμο δεν έχει τιμή: σύνολο άγνωστο
            continue
        totals[n] = sum(v * i.grams / 100.0 for v, i in zip(values, items))
    return DailyIntake(day=day, totals=totals, is_complete=is_complete, missing_nutrients=frozenset(missing))


# --------------------------------------------------------------- βήμα 2

def _usable_days(ctx: EvaluationContext, nutrient_ids: Iterable[str]) -> list[DailyIntake]:
    needed = set(nutrient_ids)
    return [d for d in ctx.complete_days()
            if not (needed & d.missing_nutrients) and all(n in d.totals for n in needed)]


def _usual(days: list[DailyIntake], nutrient_id: str) -> float:
    return mean(d.totals[nutrient_id] for d in days)


def _insufficient(nutrient_id: str, days_used: int, reason: str) -> NutrientEvaluation:
    return NutrientEvaluation(nutrient_id, IntakeStatus.INSUFFICIENT_DATA, days_used, reason=reason)


def _classify_ar_pri(intake: float, ar: float, pri: float) -> IntakeStatus:
    if intake < ar:
        return IntakeStatus.LIKELY_INADEQUATE
    if intake < pri:
        return IntakeStatus.UNCERTAIN
    return IntakeStatus.LIKELY_ADEQUATE


def _evaluate_one(nutrient_id: str, refs: dict, ctx: EvaluationContext) -> Optional[NutrientEvaluation]:
    """refs: {DRVType: AssessedReference} για ένα θρεπτικό."""
    if DRVType.ALAP in refs and len(refs) == 1:
        return None   # «όσο λιγότερο γίνεται»: δεν υπάρχει αριθμός για σύγκριση

    any_ref = next(iter(refs.values()))
    per_mj = any_ref.basis is ValueBasis.PER_MJ_ENERGY
    share = any_ref.basis is ValueBasis.SHARE_OF_ENERGY
    needed = [nutrient_id] + ([ENERGY_NUTRIENT] if (per_mj or share) else [])

    days = _usable_days(ctx, needed)
    if len(days) < ctx.min_complete_days:
        why = (f"{len(days)} usable days < {ctx.min_complete_days}"
               if len(ctx.complete_days()) >= ctx.min_complete_days else
               f"{len(ctx.complete_days())} complete days < {ctx.min_complete_days}")
        if len(ctx.complete_days()) >= ctx.min_complete_days:
            why += " (missing food composition values)"
        return _insufficient(nutrient_id, len(days), why)

    intake = _usual(days, nutrient_id)

    # Εύρος ως ποσοστό ενέργειας (RI)
    if share:
        ri = refs.get(DRVType.RI) or refs.get(DRVType.AI)   # LA, ALA: AI σε % ενέργειας
        energy_kj = _usual(days, ENERGY_NUTRIENT) * 1000.0
        if ri is None or nutrient_id not in ENERGY_KJ_PER_G or energy_kj <= 0:
            return _insufficient(nutrient_id, len(days), "cannot compute share of energy")
        pct = intake * ENERGY_KJ_PER_G[nutrient_id] / energy_kj * 100.0
        refs_out = {"RI_min": ri.value}
        if ri.value_max is None:   # AI ως ποσοστό ενέργειας (LA, ALA)
            status = IntakeStatus.LIKELY_ADEQUATE if pct >= ri.value else IntakeStatus.NO_CONCLUSION
        else:
            refs_out["RI_max"] = ri.value_max
            status = (IntakeStatus.BELOW_RANGE if pct < ri.value else
                      IntakeStatus.ABOVE_RANGE if pct > ri.value_max else IntakeStatus.WITHIN_RANGE)
        return NutrientEvaluation(nutrient_id, status, len(days), round(pct, 1), "E%", refs_out)

    # Τιμές ανά MJ (θειαμίνη, νιασίνη): × συνήθη ενεργειακή πρόσληψη
    scale = _usual(days, ENERGY_NUTRIENT) if per_mj else 1.0
    vals = {t.value: r.value * scale for t, r in refs.items() if r.value is not None}
    unit = any_ref.unit.replace("/MJ", "/d") if per_mj else any_ref.unit

    if "AR" in vals and "PRI" in vals:
        status = _classify_ar_pri(intake, vals["AR"], vals["PRI"])
    elif "AI" in vals:
        status = IntakeStatus.LIKELY_ADEQUATE if intake >= vals["AI"] else IntakeStatus.NO_CONCLUSION
    elif "SAI" in vals:
        status = IntakeStatus.ABOVE_REFERENCE if intake > vals["SAI"] else IntakeStatus.LIKELY_ADEQUATE
    else:
        return None
    return NutrientEvaluation(nutrient_id, status, len(days), round(intake, 3), unit,
                              {k: round(v, 3) for k, v in vals.items()})


def evaluate_intake(ctx: EvaluationContext, assessment: Assessment) -> dict[str, NutrientEvaluation]:
    """Layer 2: ένα NutrientEvaluation για κάθε θρεπτικό του Assessment. Όσα δεν
    αξιολογούνται στο Layer 1 (π.χ. πρωτεΐνη χωρίς βάρος) επιστρέφονται ως INSUFFICIENT_DATA."""
    by_nutrient: dict[str, dict] = {}
    for (nutrient_id, drv_type), ref in assessment.references.items():
        by_nutrient.setdefault(nutrient_id, {})[drv_type] = ref

    out: dict[str, NutrientEvaluation] = {}
    for nutrient_id, refs in sorted(by_nutrient.items()):
        ev = _evaluate_one(nutrient_id, refs, ctx)
        if ev is not None:
            out[nutrient_id] = ev
    for nutrient_id, reason in assessment.unavailable.items():
        out[nutrient_id] = _insufficient(nutrient_id, 0, reason)
    return out