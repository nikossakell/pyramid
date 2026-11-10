"""Κάρτες (νυχτερινή εργασία idempotent, μόνο ομάδα παρέμβασης), /cards, admin (X-Admin-Token, χωρίς γεύματα), /ask 501,
scripts/create_alert.py."""
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core.clock import utcnow
from app.db.models import Alert, AuditLog, CardDrop, DayStatus, Meal, MealItem, Participant
from app.jobs import daily_card_drops
from app.services.card_service import run_card_drops

from .conftest import SECRETS, add_participant, assert_no_numbers, login

ADMIN = {"X-Admin-Token": SECRETS["ADMIN_TOKEN"]}
ROOT = Path(__file__).resolve().parents[3]
DAY = date(2026, 11, 9)


def add_day(db, participant_id, day, foods=("lentils", "milk", "apple", "spinach"), complete=True):
    meal = Meal(participant_id=participant_id, eaten_on=day, meal_slot="lunch", source="manual")
    meal.items = [MealItem(position=n, food_id=f, portion="medium", grams=100, ai_suggested=False)
                  for n, f in enumerate(foods)]
    db.add(meal)
    if complete:
        db.add(DayStatus(participant_id=participant_id, day=day, completed=True, completed_at=utcnow()))
    db.commit()


# ---------- νυχτερινή εργασία ----------

def test_card_job_is_idempotent_and_only_for_active_intervention(app, db):
    catalog = app.state.catalog
    a, _ = add_participant(app, enrollment_date=DAY - timedelta(days=10))
    control, _ = add_participant(app, arm="control", enrollment_date=DAY - timedelta(days=10))
    inactive, _ = add_participant(app, active=False, enrollment_date=DAY - timedelta(days=10))
    for p in (a, control, inactive):
        for k in range(3):                                         # 3 συνεχόμενες ημέρες -> streak 3
            add_day(db, p.id, DAY - timedelta(days=k))

    first = run_card_drops(db, catalog, DAY)
    assert first == {"day": DAY.isoformat(), "participants": 1, "new_cards": 3}
    rules = sorted(c.rule_id for c in db.query(CardDrop).filter_by(participant_id=a.id))
    # 4 υποψήφιες (LOG, DAY, VAR, STR-03)· MAX_CARDS_PER_DAY = 3 κρατά τις σπανιότερες και την πρώτη κοινή
    assert rules == ["C-LOG-01", "C-STR-03", "C-VAR-01"]
    assert run_card_drops(db, catalog, DAY)["new_cards"] == 0      # δεύτερη εκτέλεση: καμία διπλή κάρτα
    assert db.query(CardDrop).count() == 3
    assert db.query(CardDrop).filter(CardDrop.participant_id.in_([control.id, inactive.id])).count() == 0
    assert db.query(AuditLog).filter_by(event="cards_dropped").count() == 1


def test_card_job_cli(app, db, capsys, tmp_path):
    from alembic import command
    from .test_cli_alembic import alembic_config
    from .conftest import make_settings
    db_file = tmp_path / "job.db"
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}")
    from app.main import create_app
    job_app = create_app(settings)
    p, _ = add_participant(job_app, enrollment_date=DAY)
    with job_app.state.sessionmaker() as s:
        add_day(s, p.id, DAY)
    for _ in range(2):
        assert daily_card_drops.main(["--date", DAY.isoformat()], settings=settings) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [f"day={DAY.isoformat()} participants=1 new_cards=3", f"day={DAY.isoformat()} participants=1 new_cards=0"]
    job_app.state.engine.dispose()


# ---------- /cards ----------

def test_cards_list_and_open_only_own(app, client, db):
    a, a_key = add_participant(app, enrollment_date=DAY - timedelta(days=5))
    b, b_key = add_participant(app, enrollment_date=DAY - timedelta(days=5))
    add_day(db, a.id, DAY)
    add_day(db, b.id, DAY)
    run_card_drops(db, app.state.catalog, DAY)
    a_headers, b_headers = login(client, a_key), login(client, b_key)

    cards = client.get("/api/v1/cards", headers=a_headers).json()
    assert len(cards) == 3 and all(set(c) == {"id", "tier", "day", "opened"} for c in cards)   # LOG, DAY, VAR
    assert all(c["opened"] is False and c["day"] == DAY.isoformat() for c in cards)
    assert_no_numbers(cards)
    card_id = cards[0]["id"]
    assert client.post(f"/api/v1/cards/{card_id}/open", headers=b_headers).status_code == 404   # όχι 403
    r = client.post(f"/api/v1/cards/{card_id}/open", headers=a_headers)
    assert r.status_code == 200 and r.json()["opened"] is True
    assert client.post(f"/api/v1/cards/{card_id}/open", headers=a_headers).status_code == 200    # ξανά: ίδιο
    assert db.query(AuditLog).filter_by(event="card_opened").count() == 1
    assert client.post("/api/v1/cards/00000000-0000-0000-0000-000000000000/open", headers=a_headers).status_code == 404
    assert not any(c["opened"] for c in client.get("/api/v1/cards", headers=b_headers).json())   # του Β ανέγγιχτες


def test_cards_and_ask_require_token(client):
    assert client.get("/api/v1/cards").status_code == 401
    assert client.post("/api/v1/ask").status_code == 401


def test_ask_is_not_implemented(client, child):
    _, _, headers = child
    r = client.post("/api/v1/ask", headers=headers)
    assert r.status_code == 501 and r.json() == {"not_implemented": "5.2"}


# ---------- admin ----------

ADMIN_CALLS = [("get", "/api/v1/admin/alerts", None),
               ("post", "/api/v1/admin/alerts/00000000-0000-0000-0000-000000000000/status", {"status": "closed"}),
               ("post", "/api/v1/admin/participants/00000000-0000-0000-0000-000000000000/deactivate", None),
               ("get", "/api/v1/admin/photo-suspensions", None)]


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}, {"X-Admin-Token": ""},
                                     {"Authorization": f"Bearer {SECRETS['ADMIN_TOKEN']}"}])
def test_admin_requires_token(client, headers):
    for method, url, body in ADMIN_CALLS:
        r = getattr(client, method)(url, headers=headers, **({"json": body} if body else {}))
        assert r.status_code == 401 and r.json() == {"detail": "not_authenticated"}, url


def test_child_token_is_not_admin(client, child):
    _, _, headers = child
    assert client.get("/api/v1/admin/alerts", headers=headers).status_code == 401


def test_alerts_list_and_status(client, child, db):
    p, _, _ = child
    alert = Alert(participant_id=p.id, kind="safety", category="disordered_eating")
    db.add(alert)
    db.commit()
    rows = client.get("/api/v1/admin/alerts", headers=ADMIN).json()
    assert [(r["participant_id"], r["kind"], r["category"], r["status"]) for r in rows] == [
        (str(p.id), "safety", "disordered_eating", "new")]
    assert all(rows[0][k].endswith(("Z", "+00:00")) for k in ("created_at", "updated_at"))   # UTC, όχι αμφίσημο
    r = client.post(f"/api/v1/admin/alerts/{alert.id}/status", json={"status": "closed", "note": "ok"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["note"] == "ok"
    assert client.get("/api/v1/admin/alerts", params={"status": "new"}, headers=ADMIN).json() == []
    a = db.query(AuditLog).filter_by(event="alert_status_changed").one()
    assert a.payload == {"alert_id": str(alert.id), "from_status": "new", "to_status": "closed"}
    assert client.post(f"/api/v1/admin/alerts/{alert.id}/status", json={"status": "done"}, headers=ADMIN).status_code == 422


def test_deactivate_revokes_access(client, child, db):
    p, key, headers = child
    r = client.post(f"/api/v1/admin/participants/{p.id}/deactivate", headers=ADMIN)
    assert r.status_code == 200 and r.json() == {"participant_id": str(p.id), "active": False}
    assert client.get("/api/v1/me", headers=headers).status_code == 401           # token ακυρώθηκε
    assert client.post("/api/v1/auth/login", json={"access_key": key}).status_code == 401
    db.expire_all()
    assert db.get(Participant, p.id).token_version == 1
    assert db.query(AuditLog).filter_by(event="participant_deactivated").count() == 1


@pytest.mark.parametrize("settings_overrides", [{"DEMO_MODE": True}])
def test_photo_suspensions_endpoint(client, child):
    from .photos import dark_jpeg
    p, _, headers = child
    for _ in range(5):
        client.post("/api/v1/meals/photo", content=dark_jpeg(), headers={**headers, "Content-Type": "image/jpeg"})
    rows = client.get("/api/v1/admin/photo-suspensions", headers=ADMIN).json()
    assert len(rows) == 1 and set(rows[0]) == {"participant_id", "suspended_until", "n_rejections"}
    assert rows[0]["participant_id"] == str(p.id) and rows[0]["n_rejections"] == 5


def test_admin_responses_contain_no_meals(app, client, child, db):
    p, _, headers = child
    add_day(db, p.id, DAY)
    db.add(Alert(participant_id=p.id, kind="operational", category="device_lost"))
    db.commit()
    dump = json.dumps([client.get(url, headers=ADMIN).json() for _, url, _ in ADMIN_CALLS if _ == "get"],
                      ensure_ascii=False)
    for forbidden in ("lentils", "Φακές", "milk", "meal", "food", "grams", "portion", "text"):
        assert forbidden not in dump


# ---------- scripts/create_alert.py ----------

def _cli():
    spec = importlib.util.spec_from_file_location("create_alert", ROOT / "scripts" / "create_alert.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_create_alert_cli(tmp_path, capsys):
    from alembic import command
    from .test_cli_alembic import alembic_config
    from .conftest import make_settings
    from app.main import create_app
    db_file = tmp_path / "alert.db"
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}")
    app = create_app(settings)
    p, _ = add_participant(app)
    cli = _cli()
    assert cli.main(["--participant", str(p.id), "--kind", "safety", "--category", "disordered_eating"],
                    settings=settings) == 0
    assert "alert_id:" in capsys.readouterr().out
    assert cli.main(["--participant", "00000000-0000-0000-0000-000000000000", "--kind", "safety",
                     "--category", "x_y"], settings=settings) == 1
    for bad in (["--kind", "urgent", "--category", "x"], ["--kind", "safety", "--category", "Το παιδί είπε ..."]):
        with pytest.raises(SystemExit):
            cli.parse_args(["--participant", str(p.id), *bad])
    with app.state.sessionmaker() as s:
        alert = s.query(Alert).one()
        assert (alert.kind, alert.category, alert.status) == ("safety", "disordered_eating", "new")
        assert s.query(AuditLog).filter_by(event="alert_created").one().payload["category"] == "disordered_eating"
    app.state.engine.dispose()
