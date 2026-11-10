"""Audit append-only και ασφαλές payload (R5)· access log χωρίς query, σώμα, headers (R6)."""
import logging

import pytest
from sqlalchemy import delete, update

from app.core import audit
from app.core.logging import ACCESS_LOGGER
from app.db.models import AuditLog
from app.db.models.audit import AuditAppendOnlyError


def test_audit_is_append_only_in_the_orm(db):
    row = audit.record(db, "test_event", note="x")
    db.commit()
    row.event = "changed"
    with pytest.raises(AuditAppendOnlyError):
        db.commit()
    db.rollback()
    with pytest.raises(AuditAppendOnlyError):
        db.execute(update(AuditLog).values(event="changed"))
    with pytest.raises(AuditAppendOnlyError):
        db.execute(delete(AuditLog))
    db.rollback()
    db.delete(db.query(AuditLog).one())
    with pytest.raises(AuditAppendOnlyError):
        db.commit()


@pytest.mark.parametrize("payload", [
    {"image": "..."}, {"photo_bytes": "..."}, {"access_key": "AAAA"}, {"token": "x"}, {"Authorization": "x"},
    {"data": b"\xff\xd8\xff"}, {"nested": {"ok": [1, bytearray(b"x")]}}, {"nested": {"key": "x"}},
    {"blob": memoryview(b"x")},
])
def test_audit_rejects_bytes_keys_and_tokens(db, payload):
    with pytest.raises(ValueError):
        audit.record(db, "bad", **payload)


def test_access_log_has_no_query_body_or_headers(client, child, caplog):
    _, key, headers = child
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)
    client.get("/api/v1/me?q=SECRETQUERY", headers=headers)
    client.patch("/api/v1/me", json={"avatar_id": "avatar_01", "SECRETBODY": 1}, headers=headers)
    records = [r for r in caplog.records if r.name == ACCESS_LOGGER]
    assert len(records) == 2
    first = records[0].fields
    assert set(first) == {"method", "path", "status", "duration_ms", "pseudonym_id"}
    assert first["path"] == "/api/v1/me" and first["status"] == 200 and first["pseudonym_id"]
    text = caplog.text + repr([r.fields for r in records])
    for secret in ("SECRETQUERY", "SECRETBODY", headers["Authorization"].split()[1], "Bearer", key):
        assert secret not in text


def test_access_log_without_participant(client, caplog):
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)
    client.get("/api/v1/health")
    rec = [r for r in caplog.records if r.name == ACCESS_LOGGER][-1]
    assert rec.fields["pseudonym_id"] is None and rec.fields["status"] == 200
