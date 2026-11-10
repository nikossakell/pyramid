"""/feedback/today: rule engine + presenter + ασφάλεια από alerts. R1: κανένας αριθμός στο παιδί· τα research_values
μόνο στο feedback_record. Ανοιχτό alert kind=safety -> κανένα μήνυμα."""
import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter
from ai_pipeline.text.krikri_client import ScriptedClient
from app.core.clock import local_today, utcnow
from app.db.models import Alert, AuditLog, FeedbackRecord

from .conftest import add_participant, assert_no_numbers, build_app, login

FEEDBACK = "/api/v1/feedback/today"
# Μενού που δίνει «λιγότερο από αρκετό» ασβέστιο και σίδηρο με τα demo τρόφιμα (βλ. test_messages_*).
MENU = [{"food_id": f, "portion": p} for f, p in (("milk", "medium"), ("wholegrain_bread", "medium"),
                                                   ("chicken", "medium"), ("apple", "medium"), ("crisps", "small"))]


def today():
    return local_today(ZoneInfo("Europe/Athens"), utcnow())


@pytest.fixture
def settings_overrides():
    return {"MEAL_BACKDATE_DAYS": 6}            # για να μπουν συνθετικά γεύματα σε προηγούμενες ημέρες


def log_days(client, headers, n_days, complete=True, menu=MENU):
    for k in range(n_days):
        day = (today() - timedelta(days=k)).isoformat()
        r = client.post("/api/v1/meals/confirm", json={"eaten_on": day, "meal_slot": "lunch", "source": "manual",
                                                       "items": menu}, headers=headers)
        assert r.status_code == 201, r.text
        if complete:
            assert client.post(f"/api/v1/days/{day}/complete", headers=headers).status_code == 200


def test_messages_from_three_complete_days(client, child, db):
    p, _, headers = child
    log_days(client, headers, 3)
    r = client.get(FEEDBACK, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"messages", "food_groups_today"}
    assert 1 <= len(body["messages"]) <= 2 and all(set(m) == {"id", "text"} for m in body["messages"])
    assert all(uuid.UUID(m["id"]) for m in body["messages"])
    texts = " ".join(m["text"] for m in body["messages"])
    assert "ασβέστιο" in texts and "σίδηρο" in texts
    assert body["food_groups_today"] == ["dairy", "fruit", "meat", "salty_snacks", "whole_grains"]
    assert_no_numbers(body)                                                     # R1
    for forbidden in ("R-", "MSG-", "likely_", "status", "rule_id", "usual_intake", "PRI"):
        assert forbidden not in r.text

    record = db.query(FeedbackRecord).one()                                    # research_values μόνο στη βάση
    assert record.participant_id == p.id and record.as_of == today()
    decisions = {d["rule_id"]: d for d in record.engine_audit["decisions"]}
    assert decisions["R-CA-01"]["research_values"]["usual_intake"] > 0
    assert decisions["R-PR-01"]["status"] == "insufficient_data"               # χωρίς βάρος (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ)
    assert record.engine_audit["data_versions"]["efsa_drv.csv"]
    shown = [x["shown_text"] for x in record.presented if x["shown_text"]]
    assert shown == [m["text"] for m in body["messages"]]
    assert all("research_values" not in x for x in record.presented)
    a = db.query(AuditLog).filter_by(event="feedback_presented").one()
    assert a.payload["reused"] is False and a.payload["n_messages"] == len(body["messages"])


def test_insufficient_data_gives_no_messages_but_food_groups(client, child, db):
    _, _, headers = child
    log_days(client, headers, 1)                                               # 1 πλήρης ημέρα < 3
    body = client.get(FEEDBACK, headers=headers).json()
    assert body["messages"] == [] and "dairy" in body["food_groups_today"]
    assert db.query(FeedbackRecord).count() == 1


def test_incomplete_days_do_not_count(client, child):
    _, _, headers = child
    log_days(client, headers, 3, complete=False)
    assert client.get(FEEDBACK, headers=headers).json()["messages"] == []


@pytest.mark.parametrize("kind, status, expect_messages", [
    ("safety", "new", False), ("safety", "in_progress", False), ("safety", "closed", True),
    ("operational", "new", True),
])
def test_alerts(client, child, db, kind, status, expect_messages):
    p, _, headers = child
    log_days(client, headers, 3)
    db.add(Alert(participant_id=p.id, kind=kind, category="disordered_eating", status=status))
    db.commit()
    body = client.get(FEEDBACK, headers=headers).json()
    assert bool(body["messages"]) is expect_messages
    record = db.query(FeedbackRecord).one()
    assert record.engine_audit["safety"]["category"] == ("disordered_eating" if not expect_messages else None)
    if not expect_messages:
        assert record.engine_audit["withheld"] and not record.engine_audit["feedback"]
        assert all(x["reason"] == "safety" for x in record.presented)


def test_reuse_until_something_changes(client, child, db):
    p, _, headers = child
    log_days(client, headers, 3)
    first = client.get(FEEDBACK, headers=headers).json()
    assert client.get(FEEDBACK, headers=headers).json() == first               # ίδια ids και κείμενα
    assert db.query(FeedbackRecord).count() == 1
    assert [a.payload["reused"] for a in db.query(AuditLog).filter_by(event="feedback_presented")] == [False, True]

    log_days(client, headers, 1)                                               # νέο γεύμα -> νέος υπολογισμός
    client.get(FEEDBACK, headers=headers)
    assert db.query(FeedbackRecord).count() == 2

    db.add(Alert(participant_id=p.id, kind="safety", category="self_harm"))    # νέο alert -> αμέσως χωρίς μηνύματα
    db.commit()
    assert client.get(FEEDBACK, headers=headers).json()["messages"] == []
    assert db.query(FeedbackRecord).count() == 3


@pytest.mark.parametrize("reply", ["Φάε 1300 mg ασβέστιο την ημέρα!", RuntimeError("timeout")])
def test_llm_output_with_numbers_or_error_falls_back_to_template(app, client, child, db, reply):
    _, _, headers = child
    app.state.presenter = KrikriPresenter(client=ScriptedClient(lambda _msgs: reply))   # Exception -> LLMError
    log_days(client, headers, 3)
    body = client.get(FEEDBACK, headers=headers).json()
    assert body["messages"] and all("1300" not in m["text"] for m in body["messages"])
    assert_no_numbers(body)
    reasons = {x["reason"] for x in db.query(FeedbackRecord).one().presented if x["shown_text"]}
    assert reasons <= {"validator", "llm_error"}


def test_llm_rewording_that_passes_the_validator_is_shown(app, client, child):
    _, _, headers = child
    app.state.presenter = KrikriPresenter(client=ScriptedClient(lambda m: "Δοκίμασε πιο συχνά τροφές με ασβέστιο, "
                                                                          "όπως γαλακτοκομικά."))
    log_days(client, headers, 3)
    body = client.get(FEEDBACK, headers=headers).json()
    assert any(m["text"] == "Δοκίμασε πιο συχνά τροφές με ασβέστιο, όπως γαλακτοκομικά." for m in body["messages"])
    assert_no_numbers(body)


def test_control_arm_full_access_after_control_access_from():
    app = build_app(CONTROL_ACCESS_FROM=today(), MEAL_BACKDATE_DAYS=6)
    _, key = add_participant(app, arm="control")
    with TestClient(app) as client:
        headers = login(client, key)
        log_days(client, headers, 3)
        body = client.get(FEEDBACK, headers=headers).json()
        assert body["messages"]
        assert_no_numbers(body)


def test_control_arm_blocked_before_control_access_from():
    app = build_app(CONTROL_ACCESS_FROM=today() + timedelta(days=1))
    p, _ = add_participant(app, arm="control")
    from app.core.security import create_access_token
    token, _ = create_access_token(p.id, 0, app.state.settings.JWT_SECRET.get_secret_value(), 720, utcnow())
    with TestClient(app) as client:
        assert client.get(FEEDBACK, headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_feedback_requires_token(client):
    assert client.get(FEEDBACK).status_code == 401


def test_r1_check_allows_only_the_nutrient_name_b12():
    assert_no_numbers({"text": "Μια ιδέα: τροφές με βιταμίνη B12 είναι, για παράδειγμα, ψάρια."})
    for bad in ("Φάε 2 αυγά", "βιταμίνη B12: 3,5", "B6", "περίπου 50%"):
        with pytest.raises(AssertionError):
            assert_no_numbers({"text": bad})


@pytest.mark.parametrize("llm, expect_client", [
    ({}, False), ({"LLM_BASE_URL": "http://llm:8080"}, False), ({"LLM_MODEL": "krikri"}, False),
    ({"LLM_BASE_URL": "", "LLM_MODEL": ""}, False), ({"LLM_BASE_URL": "http://llm:8080", "LLM_MODEL": "krikri"}, True),
])
def test_presenter_uses_llm_only_when_fully_configured(llm, expect_client):
    app = build_app(**llm)
    client = app.state.presenter.client
    assert (client is not None) is expect_client
    if expect_client:
        assert client.model_id == "krikri" and client.timeout_s == app.state.settings.PRESENTER_TIMEOUT_SECONDS
