"""Πρόσβαση: login, tokens, ανάκληση, όριο αποτυχιών, ομάδα ελέγχου, κλειδί ποτέ σε audit/log."""
import json
import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.clock import local_today, utcnow
from app.core.security import create_access_token
from app.db.models import AuditLog, Participant

from .conftest import add_participant, build_app, login

LOGIN = "/api/v1/auth/login"


def test_correct_key_gives_token_and_me_works(app, client):
    _, key = add_participant(app)
    r = client.post(LOGIN, json={"access_key": key})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 720 * 60
    assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_key_is_normalised(app, client):
    _, key = add_participant(app)
    messy = " " + key.lower().replace("-", " ").replace("0", "o").replace("1", "l") + " "
    assert client.post(LOGIN, json={"access_key": messy}).status_code == 200


def test_every_failure_gets_the_same_generic_answer(app, client):
    _, inactive_key = add_participant(app, active=False)
    answers = [client.post(LOGIN, json={"access_key": k}) for k in
               ("AAAA-BBBB-CCCC", "not a key", "", inactive_key)]
    assert {r.status_code for r in answers} == {401}
    assert len({r.text for r in answers}) == 1 and answers[0].json() == {"detail": "invalid_credentials"}


def test_missing_bad_and_expired_tokens(app, client):
    p, _ = add_participant(app)
    secret = app.state.settings.JWT_SECRET.get_secret_value()
    expired, _ = create_access_token(p.id, 0, secret, 720, utcnow() - timedelta(minutes=721))
    wrong_secret, _ = create_access_token(p.id, 0, "w" * 40, 720, utcnow())
    for headers in ({}, {"Authorization": "Bearer nonsense"}, {"Authorization": f"Bearer {expired}"},
                    {"Authorization": f"Bearer {wrong_secret}"}, {"Authorization": f"Basic {expired}"}):
        r = client.get("/api/v1/me", headers=headers)
        assert r.status_code == 401 and r.json() == {"detail": "not_authenticated"}, headers


def test_token_version_bump_and_deactivation_revoke_tokens(app, client, db):
    p, key = add_participant(app)
    headers = login(client, key)
    db.get(Participant, p.id).token_version += 1        # π.χ. ανάκληση συγκατάθεσης
    db.commit()
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    headers = login(client, key)
    db.get(Participant, p.id).active = False
    db.commit()
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert client.post(LOGIN, json={"access_key": key}).status_code == 401


def test_failure_limit_per_ip(app):
    limit = app.state.settings.LOGIN_MAX_FAILURES
    assert limit == 30                                               # ΠΡΟΣΧΕΔΙΟ (κοινή IP σε ακαδημίες)
    _, key = add_participant(app)
    with TestClient(app, client=("10.0.0.1", 1111)) as attacker, TestClient(app, client=("10.0.0.2", 2222)) as other:
        for _ in range(limit):
            assert attacker.post(LOGIN, json={"access_key": "AAAA-BBBB-CCCC"}).status_code == 401
        blocked = attacker.post(LOGIN, json={"access_key": key})          # ακόμα και με σωστό κλειδί
        assert blocked.status_code == 429 and blocked.json() == {"detail": "too_many_attempts"}
        assert other.post(LOGIN, json={"access_key": key}).status_code == 200   # άλλη IP: κανονικά
    limiter, later = app.state.login_limiter, utcnow() + timedelta(minutes=15)
    assert not limiter.blocked("10.0.0.1", later)                        # μετά το παράθυρο ξεκλειδώνει


# ---------- IP πίσω από trusted proxy: ψεύτικο X-Forwarded-For δεν αλλάζει την IP που μετρά το όριο ----------

NGINX_SUBNET = "172.28.0.0/24"     # προεπιλογή του FORWARDED_ALLOW_IPS (docker-compose.prod.yml)


def _behind_proxy(app, peer):
    """Όπως στην παραγωγή: uvicorn --proxy-headers --forwarded-allow-ips=<subnet του Nginx>."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    return TestClient(ProxyHeadersMiddleware(app, trusted_hosts=NGINX_SUBNET), client=(peer, 4321))


def test_spoofed_forwarded_for_does_not_change_counted_ip(app):
    limit = app.state.settings.LOGIN_MAX_FAILURES
    _, key = add_participant(app)
    nginx, real_child, other_child = "172.28.0.5", "203.0.113.7", "203.0.113.8"
    with _behind_proxy(app, nginx) as via_nginx:
        # Ο client αλλάζει κάθε φορά το δικό του X-Forwarded-For. Με παλιό Nginx ($proxy_add_x_forwarded_for)
        # το header θα ήταν «ψεύτικη, πραγματική»· μετρά η πραγματική (η δεξιότερη μη έμπιστη).
        for i in range(limit):
            spoofed = {"X-Forwarded-For": f"198.51.100.{i}, {real_child}"}
            assert via_nginx.post(LOGIN, json={"access_key": "AAAA-BBBB-CCCC"}, headers=spoofed).status_code == 401
        # Με τον Nginx του repo ($remote_addr) το header είναι μόνο η πραγματική IP.
        assert via_nginx.post(LOGIN, json={"access_key": key},
                              headers={"X-Forwarded-For": real_child}).status_code == 429
        assert via_nginx.post(LOGIN, json={"access_key": key},
                              headers={"X-Forwarded-For": other_child}).status_code == 200
    assert app.state.login_limiter.blocked(real_child, utcnow())
    assert not any(app.state.login_limiter.blocked(f"198.51.100.{i}", utcnow()) for i in range(limit))


def test_forwarded_for_ignored_from_untrusted_peer(app):
    """Client που μιλά απευθείας (όχι από το subnet του Nginx): το X-Forwarded-For του αγνοείται."""
    limit = app.state.settings.LOGIN_MAX_FAILURES
    direct = "192.0.2.50"
    with _behind_proxy(app, direct) as client:
        for i in range(limit):
            client.post(LOGIN, json={"access_key": "AAAA-BBBB-CCCC"}, headers={"X-Forwarded-For": f"10.9.9.{i}"})
    assert app.state.login_limiter.blocked(direct, utcnow())
    assert not app.state.login_limiter.blocked("10.9.9.0", utcnow())


# ---------- ομάδα ελέγχου (docs/backend_spec_v1.md, Τροποποίηση 6) ----------

def _today():
    from zoneinfo import ZoneInfo
    return local_today(ZoneInfo("Europe/Athens"), utcnow())


@pytest.mark.parametrize("access_from", [None, "future"])
def test_control_arm_blocked_before_control_access_from(access_from):
    start = None if access_from is None else _today() + timedelta(days=30)
    app = build_app(CONTROL_ACCESS_FROM=start)
    p, key = add_participant(app, arm="control")
    with TestClient(app) as client:
        r = client.post(LOGIN, json={"access_key": key})
        assert r.status_code == 403 and r.json() == {"detail": "not_yet_available"}
        token, _ = create_access_token(p.id, 0, app.state.settings.JWT_SECRET.get_secret_value(), 720, utcnow())
        assert client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        _, other_key = add_participant(app)                     # η ομάδα παρέμβασης δεν επηρεάζεται
        assert client.post(LOGIN, json={"access_key": other_key}).status_code == 200
    with app.state.sessionmaker() as s:
        assert s.query(AuditLog).filter_by(event="login_denied_control").count() == 1


def test_control_arm_full_access_from_control_access_from():
    app = build_app(CONTROL_ACCESS_FROM=_today())
    _, key = add_participant(app, arm="control")
    with TestClient(app) as client:
        headers = login(client, key)
        r = client.get("/api/v1/me", headers=headers)
        assert r.status_code == 200 and r.json()["arm"] == "control"


def test_control_denial_does_not_count_as_failure():
    app = build_app(CONTROL_ACCESS_FROM=None)
    _, key = add_participant(app, arm="control")
    with TestClient(app) as client:
        for _ in range(7):
            assert client.post(LOGIN, json={"access_key": key}).status_code == 403   # ποτέ 429


# ---------- το κλειδί και το token ποτέ σε audit ή log (R5, R6) ----------

def test_key_and_token_never_in_audit_or_log(app, client, db, caplog):
    caplog.set_level(logging.DEBUG)
    p, key = add_participant(app)
    r = client.post(LOGIN, json={"access_key": key})
    token = r.json()["access_token"]
    client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    client.post(LOGIN, json={"access_key": key[:-1] + ("0" if key[-1] != "0" else "1")})   # αποτυχία
    stored = db.get(Participant, p.id).key_hmac
    audit_dump = json.dumps([[a.event, a.payload] for a in db.query(AuditLog).all()], ensure_ascii=False)
    log_dump = caplog.text + json.dumps([getattr(rec, "fields", {}) for rec in caplog.records])
    for secret in (key, key.replace("-", ""), token, stored, "Bearer"):
        assert secret not in audit_dump
        assert secret not in log_dump
    events = [a.event for a in db.query(AuditLog).order_by(AuditLog.id)]
    assert events == ["login_succeeded", "login_failed"]
