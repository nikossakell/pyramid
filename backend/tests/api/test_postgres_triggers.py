"""Append-only triggers (audit_log, alert_events) σε ΠΡΑΓΜΑΤΙΚΗ PostgreSQL. Τα υπόλοιπα tests τα ελέγχουν μόνο σε SQLite.

Τρέχει μόνο αν υπάρχει PG_TEST_URL (βλ. backend/README.md, «Tests σε PostgreSQL»), π.χ.
    PG_TEST_URL=postgresql+psycopg://postgres:<κωδικός>@localhost:5433/postgres python -m pytest -q -m postgres
Η βάση πρέπει να είναι ΚΕΝΗ (χωρίς πίνακες): το test κάνει `alembic upgrade head` και στο τέλος `downgrade base`.
Σε βάση με πίνακες αρνείται να τρέξει, ώστε να μην αγγίξει ποτέ πραγματικά δεδομένα.
"""
import os
from datetime import date

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core import audit
from app.db.models import AlertEvent, AuditLog, Participant
from app.services import alert_service

from .test_cli_alembic import alembic_config

PG_TEST_URL = os.environ.get("PG_TEST_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not PG_TEST_URL.startswith("postgresql"),
                       reason="PG_TEST_URL is not set (postgresql+psycopg://...): PostgreSQL trigger tests need a real, "
                              "empty PostgreSQL database — see backend/README.md"),
]

FORBIDDEN_SQL = [
    ("audit_log", "UPDATE audit_log SET event = 'changed'"),
    ("audit_log", "DELETE FROM audit_log"),
    ("audit_log", "TRUNCATE audit_log"),
    ("alert_events", "UPDATE alert_events SET event = 'note_updated'"),
    ("alert_events", "DELETE FROM alert_events"),
    ("alert_events", "TRUNCATE alert_events"),
]


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_TEST_URL)
    existing = [t for t in inspect(engine).get_table_names() if t != "alembic_version"]   # μένει μετά το downgrade
    if existing:
        engine.dispose()
        pytest.fail(f"PG_TEST_URL database is not empty ({len(existing)} tables): refusing to run migrations on it")
    cfg = alembic_config(PG_TEST_URL)
    try:
        command.upgrade(cfg, "head")
        command.check(cfg)                                   # κανένα drift μεταξύ μεταβάσεων και μοντέλων σε PostgreSQL
        with Session(engine) as s:
            p = Participant(key_hmac="h" * 64, sex="F", age_years_at_enrollment=12, arm="intervention",
                            enrollment_date=date(2026, 11, 2))
            s.add(p)
            s.flush()
            alert_service.create_alert(s, p.id, "operational", "test")       # γράφει alert_events και audit_log
            audit.record(s, "test_event", p.id, n=1)
            s.commit()
        yield engine
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")


def _counts(engine) -> tuple[int, int]:
    with Session(engine) as s:
        return s.query(AuditLog).count(), s.query(AlertEvent).count()


def test_upgrade_head_creates_rows_to_protect(pg_engine):
    assert pg_engine.dialect.name == "postgresql"
    audit_rows, event_rows = _counts(pg_engine)
    assert audit_rows >= 2 and event_rows == 1


@pytest.mark.parametrize("table, sql", FORBIDDEN_SQL, ids=[s for _, s in FORBIDDEN_SQL])
def test_raw_sql_cannot_change_append_only_tables(pg_engine, table, sql):
    before = _counts(pg_engine)
    with pytest.raises(DBAPIError, match=f"{table} is append-only"):
        with pg_engine.begin() as con:
            con.execute(text(sql))
    assert _counts(pg_engine) == before                      # τίποτα δεν άλλαξε, τίποτα δεν χάθηκε


def test_truncate_cascade_from_parent_table_is_also_refused(pg_engine):
    before = _counts(pg_engine)
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as con:
            con.execute(text("TRUNCATE alerts CASCADE"))     # θα άδειαζε και το alert_events
    assert _counts(pg_engine) == before


def test_insert_is_still_allowed(pg_engine):
    before = _counts(pg_engine)
    with Session(pg_engine) as s:
        audit.record(s, "test_event", None, n=2)
        s.commit()
    assert _counts(pg_engine) == (before[0] + 1, before[1])


def test_find_analysis_json_lookup_works_on_postgresql(pg_engine):
    """Το analysis_id αναζητείται μέσα στο JSON payload (payload ->> 'analysis_id')· ίδιο query με το SQLite."""
    import uuid

    from app.services import analysis_audit
    aid = uuid.uuid4()
    with Session(pg_engine) as s:
        analysis_audit.record_analysis(s, "text_processed", aid, model_id="t", n_segments=1,
                                       resolved_food_ids=["lentils"], pipeline="real",
                                       shown=[{"food_id": "lentils", "portion": None, "alternatives": []}])
        s.commit()
        assert analysis_audit.find_analysis(s, aid)["resolved_food_ids"] == ["lentils"]
        assert analysis_audit.find_analysis(s, uuid.uuid4()) is None
