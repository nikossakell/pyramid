from pathlib import Path

import pytest

from rule_engine.assessment import assess, select_references
from rule_engine.data_loader import load_reference_values
from rule_engine.models import DRVType, ReferenceValue, Sex, UserProfile, ValueBasis

DRV_CSV = Path(__file__).resolve().parents[3] / "data" / "efsa_drv.csv"


@pytest.fixture(scope="module")
def refs():
    return load_reference_values(DRV_CSV)


def child(sex=Sex.FEMALE, age=13, weight=None):
    return UserProfile("P-001", sex, age, weight_kg=weight)


@pytest.mark.parametrize("sex", [Sex.MALE, Sex.FEMALE])
@pytest.mark.parametrize("age", range(10, 17))
def test_every_protocol_age_resolves_without_ambiguity(refs, sex, age):
    chosen = select_references(child(sex, age), refs)
    assert ("iron", DRVType.AR) in chosen and ("calcium", DRVType.PRI) in chosen
    assert not any(n == "energy" for n, _ in chosen)


def test_iron_girl_13(refs):
    a = assess(child(Sex.FEMALE, 13), refs)
    assert a.get("iron", DRVType.AR).value == 7
    assert a.get("iron", DRVType.PRI).value == 13


def test_calcium_band_changes_at_11(refs):
    assert assess(child(age=10), refs).get("calcium", DRVType.PRI).value == 800
    assert assess(child(age=11), refs).get("calcium", DRVType.PRI).value == 1150


def test_protein_scaled_by_weight(refs):
    a = assess(child(Sex.MALE, 16, weight=60.0), refs)
    ar = a.get("protein", DRVType.AR)
    assert ar.value == pytest.approx(0.71 * 60.0)
    assert ar.unit == "g/d" and ar.basis is ValueBasis.PER_DAY


def test_protein_unavailable_without_weight(refs):
    a = assess(child(), refs)
    assert a.get("protein", DRVType.AR) is None
    assert a.unavailable["protein"] == "weight_kg missing"


def test_per_mj_values_left_for_layer2(refs):
    th = assess(child(), refs).get("thiamin", DRVType.PRI)
    assert th.basis is ValueBasis.PER_MJ_ENERGY


def test_ambiguous_table_is_rejected():
    dup = [ReferenceValue("iron", DRVType.AR, Sex.FEMALE, 12, 17, 7, "mg/d"),
           ReferenceValue("iron", DRVType.AR, Sex.FEMALE, 10, 14, 8, "mg/d")]
    with pytest.raises(ValueError):
        select_references(child(age=13), dup)