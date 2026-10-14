"""
rule_engine/data_loader.py — φόρτωση των στατικών πινάκων αναφοράς (CSV) σε models.

Προς το παρόν μόνο το data/efsa_drv.csv. Ο πίνακας τροφίμων προστίθεται όταν υπάρξει.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .models import DRVType, ReferenceValue, Sex, ValueBasis

DRV_REQUIRED_COLUMNS = {
    "nutrient_id", "drv_type", "sex", "age_min_y", "age_max_y", "pal",
    "value", "value_max", "unit", "basis", "source", "checked",
}


def _opt_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    return float(s) if s else None


def load_reference_values(path: str | Path) -> tuple[ReferenceValue, ...]:
    """Διαβάζει το efsa_drv.csv. Σταματά με σφάλμα αν λείπει στήλη ή αν μια γραμμή
    δεν διαβάζεται, ώστε ένα χαλασμένο αρχείο να μη φτάσει σιωπηλά στη μηχανή κανόνων."""
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = DRV_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        rows = []
        for line_no, r in enumerate(reader, start=2):
            try:
                drv_type = DRVType(r["drv_type"].strip())
                value = _opt_float(r["value"])
                if value is None and drv_type is not DRVType.ALAP:
                    raise ValueError("empty value")
                rows.append(ReferenceValue(
                    nutrient_id=r["nutrient_id"].strip(),
                    drv_type=drv_type,
                    sex=Sex(r["sex"].strip()),
                    age_min_y=int(float(r["age_min_y"])),
                    age_max_y=int(float(r["age_max_y"])),
                    value=value,
                    unit=r["unit"].strip(),
                    basis=ValueBasis(r["basis"].strip()),
                    value_max=_opt_float(r["value_max"]),
                    pal=_opt_float(r["pal"]),
                    source=r["source"].strip(),
                    checked=r["checked"].strip(),
                ))
            except (ValueError, KeyError) as e:
                raise ValueError(f"{path.name} line {line_no}: {e}") from e
    return tuple(rows)