"""
app/db/models/audit.py — το audit log (Κανόνας 5): append-only.

Η εφαρμογή ΔΕΝ κάνει ποτέ update ή delete εδώ. Τρία δίχτυα:
  1. ORM: before_update / before_delete σε AuditLog και κάθε UPDATE/DELETE statement στο audit_log -> σφάλμα·
  2. βάση: trigger που απορρίπτει UPDATE / DELETE (μετάβαση 001, PostgreSQL και SQLite)·
  3. app.core.audit.record(): απορρίπτει bytes, κλειδιά, tokens (R5).
Χωρίς foreign key προς participants, ώστε το audit να μην εξαρτάται από άλλους πίνακες.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Uuid, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.clock import utcnow

from ..base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    participant_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditAppendOnlyError(RuntimeError):
    pass


@event.listens_for(AuditLog, "before_update")
def _no_update(*_):
    raise AuditAppendOnlyError("audit_log is append-only")


@event.listens_for(AuditLog, "before_delete")
def _no_delete(*_):
    raise AuditAppendOnlyError("audit_log is append-only")


@event.listens_for(Session, "do_orm_execute")
def _no_bulk_changes(state):
    if (state.is_update or state.is_delete) and any(
            getattr(m, "entity", None) is AuditLog or getattr(m, "local_table", None) is AuditLog.__table__
            for m in state.all_mappers):
        raise AuditAppendOnlyError("audit_log is append-only")
