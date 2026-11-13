"""/health και /me: το /me δίνει ΜΟΝΟ {arm, avatar_id, photo_available, photo_status} (R1, R2)."""
from datetime import timedelta

import pytest

from app.core.clock import utcnow
from app.db.models import AuditLog, Participant

ME = "/api/v1/me"


def test_health_without_token(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_me_has_exactly_four_fields(client, child):
    _, _, headers = child
    body = client.get(ME, headers=headers).json()
    assert body == {"arm": "intervention", "avatar_id": None, "photo_available": False,
                    "photo_status": "unavailable"}                                        # DEMO_MODE=false: χωρίς μοντέλα


@pytest.mark.parametrize("settings_overrides", [{"DEMO_MODE": True}])
def test_photo_available_in_demo_unless_suspended(client, child, db):
    p, _, headers = child
    status = lambda: (lambda b: (b["photo_available"], b["photo_status"]))(client.get(ME, headers=headers).json())
    assert status() == (True, "available")
    db.get(Participant, p.id).photo_suspended_until = utcnow() + timedelta(hours=1)
    db.commit()
    assert status() == (False, "suspended")
    body = client.get(ME, headers=headers).json()
    assert set(body) == {"arm", "avatar_id", "photo_available", "photo_status"}   # καμία ημερομηνία λήξης προς το παιδί
    assert "until" not in str(body) and "202" not in str(body)
    db.get(Participant, p.id).photo_suspended_until = utcnow() - timedelta(minutes=1)
    db.commit()
    assert status() == (True, "available")


def test_unavailable_wins_over_suspended_without_models(client, child, db):
    """Χωρίς ρυθμισμένα μοντέλα (DEMO_MODE=false) η κατάσταση είναι unavailable ακόμα κι αν υπάρχει αναστολή: ίδια
    σειρά ελέγχου με το /meals/photo (503 πριν από 403)."""
    p, _, headers = child
    db.get(Participant, p.id).photo_suspended_until = utcnow() + timedelta(hours=1)
    db.commit()
    body = client.get(ME, headers=headers).json()
    assert (body["photo_available"], body["photo_status"]) == (False, "unavailable")
    assert client.patch(ME, json={"avatar_id": "avatar_03"}, headers=headers).json()["photo_status"] == "unavailable"


def test_patch_avatar(client, child, db):
    p, _, headers = child
    r = client.patch(ME, json={"avatar_id": "avatar_03"}, headers=headers)
    assert r.status_code == 200 and r.json()["avatar_id"] == "avatar_03"
    assert db.query(AuditLog).filter_by(event="avatar_changed").one().payload == {"avatar_id": "avatar_03"}
    assert client.patch(ME, json={"avatar_id": None}, headers=headers).json()["avatar_id"] is None


@pytest.mark.parametrize("body", [
    {"avatar_id": "Μαρία"},                          # ελεύθερο κείμενο (π.χ. όνομα) δεν γίνεται δεκτό (R2)
    {"avatar_id": "avatar_99"},
    {"avatar_id": "avatar_01", "name": "Μαρία"},     # κανένα άλλο πεδίο
    {"avatar_id": "x" * 33},
])
def test_patch_rejects_anything_else(client, child, body):
    _, _, headers = child
    assert client.patch(ME, json=body, headers=headers).status_code == 422


def test_me_requires_token(client):
    assert client.get(ME).status_code == 401
    assert client.patch(ME, json={"avatar_id": "avatar_01"}).status_code == 401
