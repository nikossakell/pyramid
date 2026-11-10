"""Πίνακας τροφίμων (demo) και /foods/search. Οι μονάδες του demo_foods.csv ταιριάζουν με το efsa_drv.csv."""
import csv

import pytest

from app.services.food_catalog import FoodCatalogError, load_catalog

from .conftest import DATA, assert_no_numbers

DEMO_SOURCE = "DEMO — ΟΧΙ πραγματικές τιμές"
RULE_NUTRIENTS = {"iron", "calcium", "sodium", "fibre", "protein", "vitamin_a", "vitamin_c", "folate", "vitamin_d",
                  "vitamin_b12"}


def _rows(name):
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_demo_food_units_match_efsa_drv_numerators():
    """Ανεξάρτητα από τον loader: κάθε στήλη <nutrient>__<μονάδα> έχει τον αριθμητή του unit του efsa_drv.csv."""
    drv = {}
    for r in _rows("efsa_drv.csv"):
        if r["unit"]:
            drv.setdefault(r["nutrient_id"], set()).add(r["unit"].split("/")[0])
    header = list(_rows("demo_foods.csv")[0])
    nutrient_cols = [c for c in header if "__" in c]
    assert {c.split("__")[0] for c in nutrient_cols} == RULE_NUTRIENTS
    for col in nutrient_cols:
        nutrient, unit = col.split("__")
        assert drv[nutrient] == {unit}, col
    expected = {"sodium": "g", "vitamin_a": "ug_RE", "folate": "ug_DFE", "protein": "g", "iron": "mg"}
    assert {c.split("__")[0]: c.split("__")[1] for c in nutrient_cols if c.split("__")[0] in expected} == expected


def test_every_demo_row_is_marked_demo_and_groups_are_known():
    groups = {r["group_id"] for r in _rows("food_groups.csv")}
    rows = _rows("demo_foods.csv")
    assert 20 <= len(rows) <= 30
    for r in rows:
        assert r["source"] == DEMO_SOURCE and r["is_demo"] == "true", r["food_id"]
        assert r["food_group"] in groups
        assert 0 < float(r["portion_small_g"]) < float(r["portion_medium_g"]) < float(r["portion_large_g"])
    food_ids = {r["food_id"] for r in rows}
    assert {a["food_id"] for a in _rows("demo_food_aliases.csv")} <= food_ids


def _write_variant(tmp_path, transform):
    text = (DATA / "demo_foods.csv").read_text(encoding="utf-8")
    (tmp_path / "f.csv").write_text(transform(text), encoding="utf-8")
    return load_catalog(tmp_path / "f.csv", DATA / "demo_food_aliases.csv", DATA / "efsa_drv.csv", DATA / "food_groups.csv")


@pytest.mark.parametrize("transform, message", [
    (lambda t: t.replace("sodium__g", "sodium__mg"), "efsa_drv.csv uses 'g'"),
    (lambda t: t.replace("folate__ug_DFE", "folate__ug"), "efsa_drv.csv uses 'ug_DFE'"),
    (lambda t: t.replace("iron__mg", "iron"), "is not <nutrient_id>__<unit>"),
    (lambda t: t.replace(",legumes,", ",pulses,", 1), "not in food_groups.csv"),
    (lambda t: t.replace(",true\n", ",false\n", 1), "source and is_demo disagree"),
    (lambda t: t.replace("lentils,Φακές,legumes,150,250,350", "lentils,Φακές,legumes,350,250,150"), "portions"),
])
def test_loader_rejects_bad_tables(tmp_path, transform, message):
    with pytest.raises(FoodCatalogError, match=message):
        _write_variant(tmp_path, transform)


def test_catalog_versions_and_grams(app):
    catalog = app.state.catalog
    assert catalog.has_demo and set(catalog.versions) == {"demo_foods.csv", "demo_food_aliases.csv", "efsa_drv.csv",
                                                          "food_groups.csv"}
    assert all(len(v) == 64 for v in catalog.versions.values())
    assert catalog.grams("lentils", "medium") == 250.0
    assert catalog.foods["lentils"].item.nutrients_per_100g["sodium"] == 0.002     # σε g, όπως το efsa_drv.csv


def test_search_endpoint(client, child):
    _, _, headers = child
    r = client.get("/api/v1/foods/search", params={"q": "φακ"}, headers=headers)
    assert r.status_code == 200
    assert r.json()[0] == {"food_id": "lentils", "name_el": "Φακές", "food_group": "legumes"}
    for q in ("γ", "σ", "μακαρόνια με κιμά", "κοτοπουλο"):
        body = client.get("/api/v1/foods/search", params={"q": q}, headers=headers).json()
        assert len(body) <= 10 and all(set(item) == {"food_id", "name_el", "food_group"} for item in body)
        assert_no_numbers(body)                                                   # R1
    assert client.get("/api/v1/foods/search", params={"q": ""}, headers=headers).json() == []
    assert client.get("/api/v1/foods/search", params={"q": "x" * 101}, headers=headers).status_code == 422


def test_search_requires_token(client):
    assert client.get("/api/v1/foods/search", params={"q": "φακ"}).status_code == 401
