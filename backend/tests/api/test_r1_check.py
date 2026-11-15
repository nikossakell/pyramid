"""Tests για τον ίδιο τον έλεγχο R1 των tests (assert_no_numbers του conftest): τι πιάνει και ποιες είναι οι μόνες
εξαιρέσεις. Αν χαλαρώσει ο έλεγχος, σπάνε αυτά — όχι σιωπηλά όλα τα υπόλοιπα."""
import pytest

from .conftest import DATE_FIELDS, TEXT_FIELDS, assert_no_numbers

UUID_ = "3f2b8a1c-9d4e-4f6a-8b7c-1a2b3c4d5e6f"


@pytest.mark.parametrize("bad", [
    {"text": "Φάε 2 φρούτα"},
    {"text": "2026-11-13"},                                   # ημερομηνία μέσα σε κείμενο προς το παιδί
    {"text": "2026-11-13T08:30:00Z"},
    {"text": "Στις 08:30 έφαγες πρωινό"},
    {"name_el": "2026-11-13"}, {"label_el": "Ομάδα 3"}, {"message": "2026-11-13"},
    {"text": UUID_},                                          # ούτε αναγνωριστικό μέσα σε κείμενο
    {"messages": [{"id": "m", "text": "Σήμερα 2026-11-13 τα πήγες καλά"}]},
    {"eaten_on": "2026-11-13 και κάτι"},                      # όχι ΟΛΟΚΛΗΡΗ η τιμή ISO
    {"eaten_on": "Φάε 2026-11-13"},
    {"eaten_on": "2026-11-13\nΦάε 2 φρούτα"},
    {"created_at": "13/11/2026"},
    {"eaten_on": 20261113},                                   # αριθμός, ακόμα και σε πεδίο ημερομηνίας
    {"note": "2026-11-13"},                                   # άγνωστο πεδίο: δεν είναι πεδίο ημερομηνίας
    {"food_id": "2026-11-13"},
    {"confidence": 0.92}, {"grams": None}, {"portion": 150}, {"percent": "45%"},
    {"sort": 3},                                              # χωρίς ρητή εξαίρεση του καλούντος
    {"id": UUID_.replace("-", "")},                           # μόνο κανονική μορφή UUID
    "2026-11-13",                                             # τιμή χωρίς όνομα πεδίου
    ["2026-11-13"],
])
def test_r1_check_catches(bad):
    with pytest.raises(AssertionError):
        assert_no_numbers(bad)


@pytest.mark.parametrize("ok", [
    {"eaten_on": "2026-11-13"},
    {"day": "2026-11-13", "created_at": "2026-11-13T08:30:00Z"},
    {"created_at": "2026-11-13T08:30:00.123456+02:00"},
    {"days": [{"day": "2026-11-13", "completed": True}]},
    {"meal_id": UUID_, "id": UUID_},
    {"text": "Φάε δύο φρούτα", "name_el": "Φακές", "portion": None, "created": True},
    {"text": "Τροφές με βιταμίνη B12 είναι τα ψάρια."},       # η μόνη εξαίρεση ονόματος θρεπτικού
])
def test_r1_check_accepts(ok):
    assert_no_numbers(ok)


def test_r1_int_exception_is_explicit_and_per_key():
    row = {"code": "legumes", "label_el": "Όσπρια", "shown": True, "sort": 3}
    assert_no_numbers([row], allow_int_keys=frozenset({"sort"}))
    for bad in ({**row, "grams": 3}, {**row, "other": 3}, {**row, "sort": 3.5}, {**row, "sort": "3"},
                {**row, "label_el": "Όσπρια 3"}):
        with pytest.raises(AssertionError):
            assert_no_numbers([bad], allow_int_keys=frozenset({"sort"}))


def test_r1_date_and_text_field_lists_do_not_overlap():
    assert not DATE_FIELDS & TEXT_FIELDS
    assert {"created_at", "eaten_on", "day", "at", "updated_at", "enrolled_on"} <= DATE_FIELDS
    assert {"text", "name_el", "label_el"} <= TEXT_FIELDS
