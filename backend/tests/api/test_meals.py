"""/meals/confirm, /meals, DELETE /meals/{id}, /days/{day}/complete: επικύρωση, γραμμάρια από τη μερίδα, R1, R3,
απομόνωση μεταξύ παιδιών (404, όχι 403)."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.clock import local_today, utcnow
from app.db.models import AuditLog, DayStatus, Meal, MealItem

from .conftest import add_participant, assert_no_numbers, login

CONFIRM, MEALS = "/api/v1/meals/confirm", "/api/v1/meals"


def today():
    return local_today(ZoneInfo("Europe/Athens"), utcnow())


def meal_body(day=None, items=None, **over):
    body = {"eaten_on": (day or today()).isoformat(), "meal_slot": "lunch", "source": "manual",
            "items": items if items is not None else [
                {"food_id": "lentils", "portion": "medium", "ai_suggested": False},
                {"food_id": "wholegrain_bread", "portion": "small", "ai_suggested": True}]}
    body.update(over)
    return body


def test_confirm_stores_grams_from_portion_and_returns_no_numbers(client, child, db):
    p, _, headers = child
    r = client.post(CONFIRM, json=meal_body(), headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert [(i["food_id"], i["name_el"], i["portion"]) for i in body["items"]] == [
        ("lentils", "Φακές", "medium"), ("wholegrain_bread", "Ψωμί ολικής άλεσης", "small")]
    assert_no_numbers(body)                                                   # R1: ούτε γραμμάρια
    items = db.query(MealItem).order_by(MealItem.position).all()
    assert [(i.food_id, i.grams, i.ai_suggested) for i in items] == [("lentils", 250.0, False),
                                                                      ("wholegrain_bread", 30.0, True)]
    a = db.query(AuditLog).filter_by(event="meal_confirmed").one()
    assert a.participant_id == p.id and a.payload["n_items"] == 2 and a.payload["n_ai_suggested"] == 1


@pytest.mark.parametrize("change, detail", [
    ({"items": [{"food_id": "pizza", "portion": "medium"}]}, "unknown_food_id"),
    ({"items": []}, None),
    ({"items": [{"food_id": "apple", "portion": "small"}] * 11}, None),
    ({"items": [{"food_id": "apple", "portion": "huge"}]}, None),
    ({"items": [{"food_id": "apple", "portion": "small", "grams": 500}]}, None),     # γραμμάρια από τον client: όχι
    ({"meal_slot": "brunch"}, None),
    ({"source": "ai"}, None),
    ({"eaten_on": "yesterday"}, None),
    ({"note": "κάτι"}, None),
])
def test_confirm_validation(client, child, db, change, detail):
    _, _, headers = child
    r = client.post(CONFIRM, json=meal_body(**change), headers=headers)
    assert r.status_code == 422
    if detail:
        assert r.json() == {"detail": detail}
    assert db.query(Meal).count() == 0


@pytest.mark.parametrize("offset, ok", [(0, True), (1, True), (2, False), (-1, False)])
def test_backdate_window(client, child, offset, ok):
    _, _, headers = child
    r = client.post(CONFIRM, json=meal_body(day=today() - timedelta(days=offset)), headers=headers)
    assert r.status_code == (201 if ok else 422)
    if not ok:
        assert r.json() == {"detail": "eaten_on_out_of_range"}


def test_list_only_own_meals_without_grams(app, client, child):
    _, _, a_headers = child
    _, b_key = add_participant(app)
    b_headers = login(client, b_key)
    client.post(CONFIRM, json=meal_body(), headers=a_headers)
    client.post(CONFIRM, json=meal_body(day=today() - timedelta(days=1), meal_slot="dinner"), headers=a_headers)
    client.post(CONFIRM, json=meal_body(items=[{"food_id": "apple", "portion": "large"}]), headers=b_headers)

    mine = client.get(MEALS, headers=a_headers).json()                      # προεπιλογή: σήμερα
    assert len(mine) == 1 and mine[0]["meal_slot"] == "lunch"
    week = client.get(MEALS, params={"from": (today() - timedelta(days=6)).isoformat(),
                                     "to": today().isoformat()}, headers=a_headers).json()
    assert len(week) == 2 and {m["meal_slot"] for m in week} == {"lunch", "dinner"}
    assert_no_numbers(week)
    theirs = client.get(MEALS, headers=b_headers).json()
    assert [i["food_id"] for m in theirs for i in m["items"]] == ["apple"]  # το Β δεν βλέπει γεύματα του Α


@pytest.mark.parametrize("params", [{"from": "2026-11-10", "to": "2026-11-01"}, {"from": "2026-01-01", "to": "2026-03-01"},
                                    {"from": "not-a-date"}])
def test_list_bad_range(client, child, params):
    _, _, headers = child
    assert client.get(MEALS, params=params, headers=headers).status_code == 422


def test_delete_disabled_by_default(client, child, db):
    _, _, headers = child
    meal_id = client.post(CONFIRM, json=meal_body(), headers=headers).json()["id"]
    r = client.delete(f"{MEALS}/{meal_id}", headers=headers)
    assert r.status_code == 403 and r.json() == {"detail": "meal_delete_disabled"}
    assert db.query(Meal).one().deleted_at is None


@pytest.mark.parametrize("settings_overrides", [{"ALLOW_MEAL_DELETE": True}])
def test_delete_when_enabled_only_own_and_soft(app, client, child, db):
    _, _, a_headers = child
    _, b_key = add_participant(app)
    b_headers = login(client, b_key)
    meal_id = client.post(CONFIRM, json=meal_body(), headers=a_headers).json()["id"]
    assert client.delete(f"{MEALS}/{meal_id}", headers=b_headers).status_code == 404       # όχι 403
    assert client.delete(f"{MEALS}/00000000-0000-0000-0000-000000000000", headers=a_headers).status_code == 404
    assert client.delete(f"{MEALS}/{meal_id}", headers=a_headers).status_code == 204
    assert client.delete(f"{MEALS}/{meal_id}", headers=a_headers).status_code == 404       # ήδη διαγραμμένο
    assert client.get(MEALS, headers=a_headers).json() == []
    db.expire_all()
    assert db.query(Meal).one().deleted_at is not None                                      # soft delete
    assert db.query(AuditLog).filter_by(event="meal_deleted").count() == 1


def test_complete_day(app, client, child, db):
    p, _, headers = child
    url = f"/api/v1/days/{today().isoformat()}/complete"
    r = client.post(url, headers=headers)
    assert r.status_code == 422 and r.json() == {"detail": "day_has_no_meals"}
    client.post(CONFIRM, json=meal_body(), headers=headers)
    for _ in range(2):                                                                      # idempotent
        r = client.post(url, headers=headers)
        assert r.status_code == 200 and r.json() == {"day": today().isoformat(), "completed": True}
    assert db.query(DayStatus).filter_by(participant_id=p.id).count() == 1
    assert db.query(AuditLog).filter_by(event="day_completed").count() == 1
    for bad in (today() + timedelta(days=1), today() - timedelta(days=2)):
        r = client.post(f"/api/v1/days/{bad.isoformat()}/complete", headers=headers)
        assert r.status_code == 422 and r.json() == {"detail": "day_out_of_range"}
    _, b_key = add_participant(app)                                     # το Β δεν «κληρονομεί» την ημέρα του Α
    assert client.post(url, headers=login(client, b_key)).json() == {"detail": "day_has_no_meals"}


def test_meal_endpoints_require_token(client):
    for method, url in (("post", CONFIRM), ("get", MEALS), ("delete", f"{MEALS}/00000000-0000-0000-0000-000000000000"),
                        ("post", f"/api/v1/days/{today().isoformat()}/complete")):
        assert getattr(client, method)(url).status_code == 401
