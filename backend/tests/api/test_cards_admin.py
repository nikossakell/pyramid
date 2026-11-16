"""Κάρτες (νυχτερινή εργασία idempotent, μόνο ομάδα παρέμβασης), /cards, admin (X-Admin-Token, χωρίς γεύματα), /ask 501,
scripts/create_alert.py."""
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core.clock import utcnow
from app.db.models import Alert, AlertEvent, AuditLog, CardDrop, DayStatus, JobRun, Meal, MealItem, Participant
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


def test_card_job_ignores_participants_whose_study_ended_before_the_day(app, db):
    """Η εργασία τρέχει την επομένη: κοιτά την ΗΜΕΡΑ-ΣΤΟΧΟ. Τελευταία ημέρα μελέτης: κάρτες· η επόμενη: τίποτα."""
    settings, catalog = app.state.settings, app.state.catalog
    n = settings.STUDY_DURATION_DAYS
    last_day, _ = add_participant(app, enrollment_date=DAY - timedelta(days=n - 1))     # DAY = τελευταία ημέρα
    ended, _ = add_participant(app, enrollment_date=DAY - timedelta(days=n))            # τελείωσε χθες
    for p in (last_day, ended):
        add_day(db, p.id, DAY)
    summary = run_card_drops(db, catalog, DAY, settings, utcnow())
    assert summary["participants"] == 1 and summary["new_cards"] > 0
    assert {c.participant_id for c in db.query(CardDrop)} == {last_day.id}
    add_day(db, last_day.id, DAY + timedelta(days=1))                                   # γεύμα μετά το τέλος (π.χ. seed)
    assert run_card_drops(db, catalog, DAY + timedelta(days=1), settings, utcnow())["participants"] == 0
    assert db.query(CardDrop).filter_by(day=DAY + timedelta(days=1)).count() == 0


@pytest.mark.parametrize("settings_overrides", [{"POST_STUDY_ACCESS": True}])
def test_card_job_continues_with_post_study_access(app, db):
    p, _ = add_participant(app, enrollment_date=DAY - timedelta(days=200))
    add_day(db, p.id, DAY)
    assert run_card_drops(db, app.state.catalog, DAY, app.state.settings, utcnow())["participants"] == 1


def test_card_job_cli_prints_auto_completed_only_in_auto_mode(capsys, tmp_path):
    from alembic import command
    from .test_cli_alembic import alembic_config
    from .conftest import make_settings
    from app.main import create_app
    db_file = tmp_path / "auto.db"
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}", COMPLETE_DAY_MODE="auto")
    job_app = create_app(settings)
    p, _ = add_participant(job_app, enrollment_date=DAY)
    with job_app.state.sessionmaker() as s:
        add_day(s, p.id, DAY, complete=False)
        add_day(s, p.id, DAY, complete=False)
    assert daily_card_drops.main(["--date", DAY.isoformat()], settings=settings) == 0
    assert capsys.readouterr().out.strip() == f"day={DAY.isoformat()} participants=1 new_cards=3 auto_completed=1"
    with job_app.state.sessionmaker() as s:
        assert s.query(DayStatus).one().completed_by == "auto"
    job_app.state.engine.dispose()


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
               ("get", "/api/v1/admin/alerts/00000000-0000-0000-0000-000000000000", None),
               ("get", "/api/v1/admin/participants", None),
               ("get", "/api/v1/admin/system-status", None),
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
    for url in ("/api/v1/admin/alerts", "/api/v1/admin/participants", "/api/v1/admin/system-status"):
        assert client.get(url, headers=headers).status_code == 401


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


# ---------- κονσόλα ερευνητή: χρονολόγιο alert (A02), καρτέλες (A01), συμμετέχοντες (A04), σύστημα (A03) ----------

from app.services import alert_service  # noqa: E402

ALERTS = "/api/v1/admin/alerts"
SECRET_NOTE = "ενημερώθηκε ο παιδίατρος ΧΨΩ"


def _events(db, alert_id):
    return [(e.event, e.from_status, e.to_status) for e in
            db.query(AlertEvent).filter_by(alert_id=alert_id).order_by(AlertEvent.id)]


def test_alert_timeline(client, child, db):
    p, _, _ = child
    alert = alert_service.create_alert(db, p.id, "safety", "disordered_eating")
    db.commit()
    assert _events(db, alert.id) == [("created", None, "new")]
    url = f"{ALERTS}/{alert.id}"

    assert client.post(f"{url}/status", json={"status": "in_progress"}, headers=ADMIN).status_code == 200
    assert client.post(f"{url}/status", json={"status": "in_progress", "note": SECRET_NOTE}, headers=ADMIN).status_code == 200
    assert client.post(f"{url}/status", json={"status": "in_progress", "note": SECRET_NOTE}, headers=ADMIN).status_code == 200
    assert client.post(f"{url}/status", json={"status": "closed", "note": "τέλος"}, headers=ADMIN).status_code == 200

    r = client.get(url, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "participant_id", "kind", "category", "status", "note", "created_at", "updated_at", "events"}
    assert (body["status"], body["note"], body["participant_id"]) == ("closed", "τέλος", str(p.id))
    assert [(e["event"], e["from_status"], e["to_status"]) for e in body["events"]] == [
        ("created", None, "new"),
        ("status_changed", "new", "in_progress"),
        ("note_updated", None, "in_progress"),            # ίδια κατάσταση, νέα σημείωση
        #                                                   τρίτη κλήση: τίποτα δεν άλλαξε -> κανένα γεγονός
        ("status_changed", "in_progress", "closed"),
        ("note_updated", None, "closed")]
    assert all(set(e) == {"event", "from_status", "to_status", "at"} for e in body["events"])
    assert all(e["at"].endswith(("Z", "+00:00")) for e in body["events"])
    assert [e["at"] for e in body["events"]] == sorted(e["at"] for e in body["events"])
    assert SECRET_NOTE not in json.dumps(body["events"], ensure_ascii=False)          # η σημείωση ποτέ στο γεγονός
    stored = json.dumps([[a.event, a.payload] for a in db.query(AuditLog)], ensure_ascii=False)
    assert SECRET_NOTE not in stored                                                  # ούτε στο audit
    assert client.get(f"{ALERTS}/00000000-0000-0000-0000-000000000000", headers=ADMIN).status_code == 404
    assert client.get(f"{ALERTS}/not-a-uuid", headers=ADMIN).status_code == 422


def test_alert_created_before_the_timeline_has_no_events(client, child, db):
    p, _, _ = child
    old = Alert(participant_id=p.id, kind="operational", category="device_lost")     # όπως πριν από τη μετάβαση 004
    db.add(old)
    db.commit()
    assert client.get(f"{ALERTS}/{old.id}", headers=ADMIN).json()["events"] == []


def test_alert_events_are_append_only_in_the_orm(child, db):
    from app.db.models.append_only import AppendOnlyError
    from sqlalchemy import delete, update
    p, _, _ = child
    alert = alert_service.create_alert(db, p.id, "safety", "x_test")
    db.commit()
    event = db.query(AlertEvent).one()
    event.event = "note_updated"
    with pytest.raises(AppendOnlyError, match="alert_events is append-only"):
        db.commit()
    db.rollback()
    with pytest.raises(AppendOnlyError):
        db.delete(db.query(AlertEvent).one())
        db.commit()
    db.rollback()
    for stmt in (update(AlertEvent).values(event="note_updated"), delete(AlertEvent)):
        with pytest.raises(AppendOnlyError):
            db.execute(stmt)
    assert _events(db, alert.id) == [("created", None, "new")]


def test_record_event_accepts_only_known_values(child, db):
    from app.db.models.enums import AlertEventType
    p, _, _ = child
    alert = alert_service.create_alert(db, p.id, "safety", "x_test")
    for bad in (dict(event="το παιδί είπε ότι...", to_status="new"),
                dict(event=AlertEventType.STATUS_CHANGED, from_status="new", to_status=SECRET_NOTE)):
        with pytest.raises(ValueError):
            alert_service.record_event(db, alert, **bad)                              # καμία θέση για ελεύθερο κείμενο


def test_alert_tabs_by_status(client, child, db):
    p, _, _ = child
    made = {}
    for status in ("new", "in_progress", "closed", "new"):
        alert = alert_service.create_alert(db, p.id, "operational", f"cat_{status}")
        if status != "new":
            alert_service.set_status(db, alert, status)
        db.commit()
        made.setdefault(status, []).append(str(alert.id))
    for status, ids in made.items():
        rows = client.get(ALERTS, params={"status": status}, headers=ADMIN).json()
        assert sorted(r["id"] for r in rows) == sorted(ids) and {r["status"] for r in rows} == {status}
    assert len(client.get(ALERTS, headers=ADMIN).json()) == 4
    assert client.get(ALERTS, params={"status": "open"}, headers=ADMIN).status_code == 422


def test_create_alert_cli_writes_the_created_event(tmp_path):
    from alembic import command
    from .test_cli_alembic import alembic_config
    from .conftest import make_settings
    from app.main import create_app
    db_file = tmp_path / "alerts.db"
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}")
    cli_app = create_app(settings)
    p, _ = add_participant(cli_app)
    assert _cli().main(["--participant", str(p.id), "--kind", "safety", "--category", "self_harm"], settings=settings) == 0
    with cli_app.state.sessionmaker() as s:
        alert = s.query(Alert).one()
        assert _events(s, alert.id) == [("created", None, "new")]
        assert s.query(AuditLog).filter_by(event="alert_created").count() == 1
    cli_app.state.engine.dispose()


PARTICIPANTS = "/api/v1/admin/participants"


def test_participants_list(app, client, db):
    n = app.state.settings.STUDY_DURATION_DAYS
    from app.core.clock import local_today
    today = local_today(app.state.settings.tz, utcnow())
    a, _ = add_participant(app, enrollment_date=today - timedelta(days=3))
    ended, _ = add_participant(app, enrollment_date=today - timedelta(days=n))
    control, _ = add_participant(app, arm="control", enrollment_date=today - timedelta(days=n + 30))
    gone, _ = add_participant(app, active=False, enrollment_date=today - timedelta(days=1))
    until = utcnow() + timedelta(hours=5)
    db.get(Participant, a.id).photo_suspended_until = until
    db.get(Participant, gone.id).photo_suspended_until = utcnow() - timedelta(hours=1)      # έληξε: null
    db.commit()
    add_day(db, a.id, today)

    rows = client.get(PARTICIPANTS, headers=ADMIN).json()
    assert [r["participant_id"] for r in rows] == [str(x.id) for x in (control, ended, a, gone)]   # κατά ημερομηνία εγγραφής
    assert all(set(r) == {"participant_id", "arm", "active", "enrolled_on", "study_ended", "photo_suspended_until"}
               for r in rows)
    by_id = {r["participant_id"]: r for r in rows}
    assert by_id[str(a.id)] == {"participant_id": str(a.id), "arm": "intervention", "active": True,
                                "enrolled_on": (today - timedelta(days=3)).isoformat(), "study_ended": False,
                                "photo_suspended_until": by_id[str(a.id)]["photo_suspended_until"]}
    assert by_id[str(a.id)]["photo_suspended_until"].endswith(("Z", "+00:00"))
    assert by_id[str(ended.id)]["study_ended"] is True
    assert by_id[str(control.id)]["study_ended"] is False                         # η ομάδα ελέγχου έχει δικό της κανόνα
    assert by_id[str(gone.id)]["active"] is False and by_id[str(gone.id)]["photo_suspended_until"] is None
    text = json.dumps(rows, ensure_ascii=False)
    for forbidden in ("lentils", "Φακές", "meal", "food", "grams", "sex", "age", "key", "avatar"):   # Απόφαση 33
        assert forbidden not in text


STATUS = "/api/v1/admin/system-status"


def test_system_status_without_models(app, client, child, db):
    from app.services.food_catalog import sha256_file
    p, _, _ = child
    add_day(db, p.id, DAY)
    alert_service.create_alert(db, p.id, "safety", "disordered_eating", note=SECRET_NOTE)
    db.commit()
    r = client.get(STATUS, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"demo_mode", "photo_components", "versions", "services"} and body["demo_mode"] is False
    assert body["photo_components"] == {"nsfw": "missing", "food_gate": "missing", "recognizer": "missing"}
    v = body["versions"]
    assert set(v) == {"app", "data_versions", "rag_sources_sha256", "prompt_version", "presenter_version",
                      "foods_is_demo", "models"}
    assert v["data_versions"] == app.state.catalog.versions and "display_food_groups.csv" in v["data_versions"]
    assert v["rag_sources_sha256"] == sha256_file(ROOT / "data" / "rag_sources.csv")
    from ai_pipeline.presentation.prompts import PROMPT_VERSION
    assert v["prompt_version"] == PROMPT_VERSION and v["foods_is_demo"] is True and v["app"] == app.version
    assert v["models"] == {"llm": None, "nsfw": None, "food_gate": None, "recognizer": None}
    assert body["services"] == {"db": "ok", "llm": "not_configured", "photo_pipeline": "unavailable",
                                "last_card_job": None}
    text = r.text                                                                 # κανένα δεδομένο συμμετέχοντα ή μυστικό
    for forbidden in (str(p.id), "lentils", "disordered_eating", SECRET_NOTE, "a" * 40, "j" * 40, "p" * 40, "sqlite"):
        assert forbidden not in text


@pytest.mark.parametrize("settings_overrides", [{"DEMO_MODE": True, "LLM_BASE_URL": "http://llm.internal:8080/v1",
                                                 "LLM_MODEL": "krikri-test"}])
def test_system_status_services(app, client, db):
    calls = []

    def probe(base_url, timeout_s):
        calls.append((base_url, timeout_s))
        return True

    app.state.llm_probe = probe
    body = client.get(STATUS, headers=ADMIN).json()
    assert calls == [("http://llm.internal:8080/v1", 2.0)]                        # GET /models με timeout 2 s
    assert body["services"]["llm"] == "ok" and body["services"]["photo_pipeline"] == "demo"
    assert body["demo_mode"] is True                                              # ορατό στην κονσόλα (A03)
    assert body["photo_components"] == {"nsfw": "demo", "food_gate": "demo", "recognizer": "demo"}
    assert body["versions"]["models"] == {"llm": "krikri-test", "nsfw": "demo-0", "food_gate": "demo-0",
                                          "recognizer": "demo-1"}
    assert "llm.internal" not in json.dumps(body)                                 # το URL δεν βγαίνει

    app.state.llm_probe = lambda base_url, timeout_s: False
    assert client.get(STATUS, headers=ADMIN).json()["services"]["llm"] == "unavailable"

    def boom(base_url, timeout_s):
        raise RuntimeError("secret detail http://llm.internal")
    app.state.llm_probe = boom
    r = client.get(STATUS, headers=ADMIN)
    assert r.status_code == 200 and r.json()["services"]["llm"] == "unavailable" and "secret detail" not in r.text


def test_http_llm_probe_fails_closed_and_fast():
    from app.services.system_status import LLM_PROBE_TIMEOUT_SECONDS, http_llm_probe
    assert LLM_PROBE_TIMEOUT_SECONDS == 2.0                                       # ΠΡΟΣΧΕΔΙΟ
    assert http_llm_probe("http://127.0.0.1:9/v1", 0.5) is False                  # κλειστή θύρα: unavailable, όχι σφάλμα
    assert http_llm_probe("file:///etc/passwd", 0.5) is False                     # μόνο http/https
    assert http_llm_probe("not a url", 0.5) is False


def test_job_runs_and_last_card_job(app, client, db):
    from app.services.card_service import run_card_job
    settings, catalog = app.state.settings, app.state.catalog
    p, _ = add_participant(app, enrollment_date=DAY)
    add_day(db, p.id, DAY)
    assert run_card_job(db, catalog, DAY, settings)["new_cards"] == 3
    run = db.query(JobRun).one()
    assert (run.job, run.day, run.status, run.count) == ("daily_card_drops", DAY, "ok", 3)
    assert run.finished_at is not None and run.finished_at >= run.started_at
    last = client.get(STATUS, headers=ADMIN).json()["services"]["last_card_job"]
    assert set(last) == {"day", "run_at", "finished_at", "status", "drops"}
    assert (last["day"], last["status"], last["drops"]) == (DAY.isoformat(), "ok", 3)
    assert last["run_at"].endswith(("Z", "+00:00"))

    run_card_job(db, catalog, DAY, settings)                                      # δεύτερη εκτέλεση: καμία νέα κάρτα
    last = client.get(STATUS, headers=ADMIN).json()["services"]["last_card_job"]
    assert (last["status"], last["drops"]) == ("ok", 0) and db.query(JobRun).count() == 2


def test_failed_job_run_is_recorded(app, client, db, monkeypatch):
    from app.services import card_service
    p, _ = add_participant(app, enrollment_date=DAY)
    add_day(db, p.id, DAY)

    def boom(*args, **kwargs):
        raise RuntimeError("rule engine exploded")
    monkeypatch.setattr(card_service, "drop_cards_for", boom)
    with pytest.raises(RuntimeError):
        card_service.run_card_job(db, app.state.catalog, DAY, app.state.settings)
    db.expire_all()
    run = db.query(JobRun).one()
    assert (run.status, run.count) == ("failed", None) and run.finished_at is not None
    last = client.get(STATUS, headers=ADMIN).json()["services"]["last_card_job"]
    assert (last["status"], last["drops"]) == ("failed", None)
    assert "exploded" not in json.dumps(last)                                     # κανένα μήνυμα σφάλματος στην έξοδο


def test_new_admin_responses_contain_no_meals_or_child_text(app, client, child, db):
    p, _, headers = child
    add_day(db, p.id, DAY)
    client.post("/api/v1/meals/text", json={"text": "φακές με ψωμί"}, headers=headers)
    alert = alert_service.create_alert(db, p.id, "operational", "device_lost")
    db.commit()
    for url in (f"{ALERTS}/{alert.id}", PARTICIPANTS, STATUS, f"{ALERTS}?status=new"):
        r = client.get(url, headers=ADMIN)
        assert r.status_code == 200, url
        for forbidden in ("lentils", "spinach", "Φακές", "φακές", "grams", "food_id", "meal_slot", "eaten_on"):
            assert forbidden not in r.text, (url, forbidden)
