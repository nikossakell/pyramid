"""/meals/confirm, /meals, DELETE /meals/{id}, /days/{day}/complete: επικύρωση, γραμμάρια από τη μερίδα, R1, R3,
idempotency (client_meal_id), απομόνωση μεταξύ παιδιών (404, όχι 403)."""
import uuid
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
    body = {"client_meal_id": str(uuid.uuid4()),        # νέο κλειδί σε κάθε κλήση = νέο γεύμα
            "eaten_on": (day or today()).isoformat(), "meal_slot": "lunch", "source": "manual",
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
    assert set(body) == {"meal_id", "eaten_on", "meal_slot", "food_groups", "created"}
    assert body["created"] is True and body["meal_slot"] == "lunch" and body["eaten_on"] == today().isoformat()
    assert body["food_groups"] == ["legumes", "whole_grains"]                 # για το S11, στη σειρά εμφάνισης
    assert uuid.UUID(body["meal_id"]) == db.query(Meal).one().id
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
    ({"client_meal_id": "not-a-uuid"}, None),
    ({"client_meal_id": None}, None),
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
    assert all(set(m) == {"meal_id", "eaten_on", "meal_slot", "source", "created_at", "items"} for m in week)
    assert all(set(i) == {"food_id", "name_el", "portion", "food_group", "ai_suggested"} for m in week for i in m["items"])
    assert [(i["food_id"], i["name_el"], i["portion"], i["food_group"], i["ai_suggested"]) for i in mine[0]["items"]] == [
        ("lentils", "Φακές", "medium", "legumes", False),
        ("wholegrain_bread", "Ψωμί ολικής άλεσης", "small", "whole_grains", True)]
    assert mine[0]["source"] == "manual" and mine[0]["created_at"].endswith(("Z", "+00:00"))
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
    meal_id = client.post(CONFIRM, json=meal_body(), headers=headers).json()["meal_id"]
    r = client.delete(f"{MEALS}/{meal_id}", headers=headers)
    assert r.status_code == 403 and r.json() == {"detail": "meal_delete_disabled"}
    assert db.query(Meal).one().deleted_at is None


@pytest.mark.parametrize("settings_overrides", [{"ALLOW_MEAL_DELETE": True}])
def test_delete_when_enabled_only_own_and_soft(app, client, child, db):
    _, _, a_headers = child
    _, b_key = add_participant(app)
    b_headers = login(client, b_key)
    meal_id = client.post(CONFIRM, json=meal_body(), headers=a_headers).json()["meal_id"]
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
    assert db.query(DayStatus).filter_by(participant_id=p.id).one().completed_by == "child"
    a = db.query(AuditLog).filter_by(event="day_completed").one()
    assert a.payload["by"] == "child"
    for bad in (today() + timedelta(days=1), today() - timedelta(days=2)):
        r = client.post(f"/api/v1/days/{bad.isoformat()}/complete", headers=headers)
        assert r.status_code == 422 and r.json() == {"detail": "day_out_of_range"}
    _, b_key = add_participant(app)                                     # το Β δεν «κληρονομεί» την ημέρα του Α
    assert client.post(url, headers=login(client, b_key)).json() == {"detail": "day_has_no_meals"}


def test_meal_endpoints_require_token(client):
    for method, url in (("post", CONFIRM), ("get", MEALS), ("delete", f"{MEALS}/00000000-0000-0000-0000-000000000000"),
                        ("get", "/api/v1/days"),
                        ("post", f"/api/v1/days/{today().isoformat()}/complete")):
        assert getattr(client, method)(url).status_code == 401


# ---------- idempotency (ουρά offline του PWA: S04δ, S20α) ----------

def test_same_client_meal_id_and_body_returns_the_existing_meal(client, child, db):
    _, _, headers = child
    body = meal_body()
    first = client.post(CONFIRM, json=body, headers=headers)
    assert first.status_code == 201 and first.json()["created"] is True
    for _ in range(2):
        again = client.post(CONFIRM, json=body, headers=headers)
        assert again.status_code == 200
        assert again.json() == {**first.json(), "created": False}
    assert db.query(Meal).count() == 1 and db.query(MealItem).count() == 2          # κανένα διπλό γεύμα
    assert db.query(AuditLog).filter_by(event="meal_confirmed").count() == 1
    assert db.query(AuditLog).filter_by(event="meal_confirm_repeated").count() == 2
    assert len(client.get(MEALS, headers=headers).json()) == 1


@pytest.mark.parametrize("change", [
    {"meal_slot": "dinner"}, {"source": "text"},
    {"items": [{"food_id": "lentils", "portion": "large", "ai_suggested": False},
               {"food_id": "wholegrain_bread", "portion": "small", "ai_suggested": True}]},
    {"items": [{"food_id": "lentils", "portion": "medium", "ai_suggested": False}]},
    {"items": [{"food_id": "wholegrain_bread", "portion": "small", "ai_suggested": True},
               {"food_id": "lentils", "portion": "medium", "ai_suggested": False}]},
    {"items": [{"food_id": "pizza", "portion": "medium"}]},                         # 409 πριν από κάθε άλλο έλεγχο
])
def test_same_client_meal_id_with_different_body_is_a_conflict(client, child, db, change):
    _, _, headers = child
    body = meal_body()
    assert client.post(CONFIRM, json=body, headers=headers).status_code == 201
    r = client.post(CONFIRM, json={**body, **change}, headers=headers)
    assert r.status_code == 409 and r.json() == {"detail": "client_meal_id_conflict"}
    assert db.query(Meal).count() == 1 and db.query(MealItem).count() == 2


def test_different_eaten_on_with_same_client_meal_id_is_a_conflict(client, child):
    _, _, headers = child
    body = meal_body()
    assert client.post(CONFIRM, json=body, headers=headers).status_code == 201
    other_day = {**body, "eaten_on": (today() - timedelta(days=1)).isoformat()}
    assert client.post(CONFIRM, json=other_day, headers=headers).status_code == 409


def test_client_meal_id_is_unique_per_participant_not_globally(app, client, child, db):
    _, _, a_headers = child
    _, b_key = add_participant(app)
    body = meal_body()
    assert client.post(CONFIRM, json=body, headers=a_headers).status_code == 201
    r = client.post(CONFIRM, json=body, headers=login(client, b_key))          # το Β δεν «βλέπει» το κλειδί του Α
    assert r.status_code == 201 and r.json()["created"] is True
    assert db.query(Meal).count() == 2


def test_replay_after_the_backdate_window_still_returns_the_meal(app, client, child, db):
    """Η ουρά offline μπορεί να ξαναστείλει μετά από ημέρες: το ήδη αποθηκευμένο γεύμα δεν γίνεται 422."""
    from app.services import meal_service
    p, _, headers = child
    body = meal_body()
    meal_id = client.post(CONFIRM, json=body, headers=headers).json()["meal_id"]
    args = dict(eaten_on=today(), meal_slot="lunch", source="manual", settings=app.state.settings,
                items=[{**i, "ai_suggested": i.get("ai_suggested", False)} for i in body["items"]],
                now=utcnow() + timedelta(days=5))
    meal, created = meal_service.confirm_meal(db, app.state.catalog, p, client_meal_id=uuid.UUID(body["client_meal_id"]),
                                              **args)
    assert str(meal.id) == meal_id and created is False
    with pytest.raises(meal_service.MealError) as e:                          # ΝΕΟ γεύμα εκτός παραθύρου: όχι
        meal_service.confirm_meal(db, app.state.catalog, p, client_meal_id=uuid.uuid4(), **args)
    assert (e.value.status_code, e.value.detail) == (422, "eaten_on_out_of_range")
    assert db.query(Meal).count() == 1


@pytest.mark.parametrize("settings_overrides", [{"ALLOW_MEAL_DELETE": True}])
def test_client_meal_id_of_a_deleted_meal_is_a_conflict(client, child, db):
    _, _, headers = child
    body = meal_body()
    meal_id = client.post(CONFIRM, json=body, headers=headers).json()["meal_id"]
    assert client.delete(f"{MEALS}/{meal_id}", headers=headers).status_code == 204
    r = client.post(CONFIRM, json=body, headers=headers)
    assert r.status_code == 409 and r.json() == {"detail": "client_meal_id_conflict"}
    assert db.query(Meal).count() == 1 and client.get(MEALS, headers=headers).json() == []


def test_confirm_food_groups_hide_groups_that_are_not_shown(client, child):
    _, _, headers = child
    items = [{"food_id": f, "portion": "small"} for f in ("crisps", "sausage", "apple", "spinach", "apple")]
    r = client.post(CONFIRM, json=meal_body(items=items), headers=headers)
    assert r.status_code == 201 and r.json()["food_groups"] == ["vegetables", "fruit"]   # χωρίς salty_snacks, processed_meat
    only_hidden = client.post(CONFIRM, json=meal_body(items=items[:2]), headers=headers)
    assert only_hidden.status_code == 201 and only_hidden.json()["food_groups"] == []


# ---------- GET /days και αυτόματη «πλήρης ημέρα» (COMPLETE_DAY_MODE, ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ) ----------

DAYS = "/api/v1/days"


def test_list_days(app, client, child):
    _, _, headers = child
    assert client.get(DAYS, headers=headers).json() == [{"day": today().isoformat(), "completed": False}]
    client.post(CONFIRM, json=meal_body(), headers=headers)
    client.post(f"{DAYS}/{today().isoformat()}/complete", headers=headers)
    start = today() - timedelta(days=6)
    week = client.get(DAYS, params={"from": start.isoformat(), "to": today().isoformat()}, headers=headers).json()
    assert [d["day"] for d in week] == [(start + timedelta(days=k)).isoformat() for k in range(7)]   # κάθε ημέρα
    assert [d["completed"] for d in week] == [False] * 6 + [True]
    assert all(set(d) == {"day", "completed"} for d in week)                    # όχι ποιος τη σημείωσε
    assert_no_numbers(week)
    _, b_key = add_participant(app)                                             # το Β δεν βλέπει τις ημέρες του Α
    assert client.get(DAYS, headers=login(client, b_key)).json() == [{"day": today().isoformat(), "completed": False}]
    for params in ({"from": "2026-11-10", "to": "2026-11-01"}, {"from": "2026-01-01", "to": "2026-03-01"},
                   {"from": "x"}):
        assert client.get(DAYS, params=params, headers=headers).status_code == 422
    month = client.get(DAYS, params={"from": (today() - timedelta(days=30)).isoformat(), "to": today().isoformat()},
                       headers=headers)
    assert month.status_code == 200 and len(month.json()) == 31


def _job(app, db, day):
    from app.services.card_service import run_card_drops
    return run_card_drops(db, app.state.catalog, day, app.state.settings, utcnow())


def test_complete_day_defaults():
    from .conftest import make_settings
    s = make_settings()
    assert s.COMPLETE_DAY_MODE == "declared" and s.AUTO_COMPLETE_MIN_MEALS == 2   # ΠΡΟΣΧΕΔΙΟ
    with pytest.raises(ValueError):
        make_settings(COMPLETE_DAY_MODE="always")


def test_declared_mode_never_completes_a_day_automatically(app, client, child, db):
    p, _, headers = child
    for slot in ("breakfast", "lunch", "dinner"):
        client.post(CONFIRM, json=meal_body(meal_slot=slot), headers=headers)
    assert "auto_completed" not in _job(app, db, today())
    assert db.query(DayStatus).count() == 0
    assert client.get(DAYS, headers=headers).json()[0]["completed"] is False


@pytest.mark.parametrize("settings_overrides", [{"COMPLETE_DAY_MODE": "auto"}])
def test_auto_mode_completes_days_with_enough_meals(app, client, child, db):
    p, _, headers = child
    yesterday = today() - timedelta(days=1)
    client.post(CONFIRM, json=meal_body(day=yesterday, meal_slot="breakfast"), headers=headers)   # χθες: 1 γεύμα
    for slot in ("breakfast", "lunch"):                                                          # σήμερα: 2 γεύματα
        client.post(CONFIRM, json=meal_body(meal_slot=slot), headers=headers)

    assert _job(app, db, yesterday)["auto_completed"] == 0                       # 1 < AUTO_COMPLETE_MIN_MEALS
    assert db.query(DayStatus).count() == 0
    first = _job(app, db, today())
    assert first["auto_completed"] == 1
    status = db.query(DayStatus).one()
    assert (status.day, status.completed, status.completed_by) == (today(), True, "auto")
    assert status.completed_at is not None
    assert db.query(AuditLog).filter_by(event="day_completed").one().payload["by"] == "auto"
    from app.db.models import CardDrop
    assert "C-DAY-01" in {c.rule_id for c in db.query(CardDrop).filter_by(day=today())}   # η σήμανση ΠΡΙΝ από τις κάρτες
    assert _job(app, db, today())["auto_completed"] == 0                         # idempotent
    assert db.query(AuditLog).filter_by(event="day_completed").count() == 1
    assert client.get(DAYS, headers=headers).json() == [{"day": today().isoformat(), "completed": True}]

    # Η δήλωση του παιδιού μένει διαθέσιμη και υπερισχύει.
    r = client.post(f"{DAYS}/{today().isoformat()}/complete", headers=headers)
    assert r.status_code == 200 and r.json()["completed"] is True
    db.expire_all()
    assert db.query(DayStatus).filter_by(day=today()).one().completed_by == "child"
    assert db.query(AuditLog).filter_by(event="day_completed").order_by(AuditLog.id.desc()).first().payload == {
        "day": today().isoformat(), "n_meals": 2, "by": "child", "was": "auto"}
    r = client.post(f"{DAYS}/{yesterday.isoformat()}/complete", headers=headers)                 # και με 1 γεύμα
    assert r.status_code == 200
    assert _job(app, db, yesterday)["auto_completed"] == 0                       # ποτέ child -> auto
    db.expire_all()
    assert {s.completed_by for s in db.query(DayStatus)} == {"child"}


@pytest.mark.parametrize("settings_overrides", [{"COMPLETE_DAY_MODE": "auto", "AUTO_COMPLETE_MIN_MEALS": 3,
                                                 "ALLOW_MEAL_DELETE": True}])
def test_auto_mode_threshold_is_a_setting_and_ignores_deleted_meals(app, client, child, db):
    _, _, headers = child
    ids = [client.post(CONFIRM, json=meal_body(meal_slot=s), headers=headers).json()["meal_id"]
           for s in ("breakfast", "lunch", "dinner")]
    client.delete(f"{MEALS}/{ids[0]}", headers=headers)
    assert _job(app, db, today())["auto_completed"] == 0                         # 2 ενεργά < 3
    client.post(CONFIRM, json=meal_body(meal_slot="snack"), headers=headers)
    assert _job(app, db, today())["auto_completed"] == 1
