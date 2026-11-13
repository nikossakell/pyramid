"""
app/db/models/alert.py — ειδοποιήσεις προς τον ερευνητή/εφημερεύοντα.

Μόνο κωδικός συμμετέχοντα, είδος και κατηγορία· ΠΟΤΕ κείμενο συνομιλίας ή γεύματος. Το note είναι σημείωση του
ερευνητή για τη διαχείριση (π.χ. «ενημερώθηκε ο παιδίατρος»), όχι περιεχόμενο του παιδιού.
kind=safety και status≠closed -> καμία ανατροφοδότηση πρόσληψης στο παιδί (/feedback/today). Κανένα αυτόματο
alert: δημιουργούνται μόνο με scripts/create_alert.py (docs/backend_spec_v1.md, Τροποποίηση 4).

alert_events: το χρονολόγιο κάθε alert (οθόνη A02), append-only όπως το audit_log (ORM, triggers της μετάβασης 004,
μία συνάρτηση εγγραφής: alert_service.record_event). Μόνο είδος γεγονότος, καταστάσεις και χρόνος· ΠΟΤΕ το κείμενο
της σημείωσης. Τα γράφει μόνο το app/services/alert_service.py.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base
from .append_only import append_only
from .enums import AlertEventType, AlertKind, AlertStatus, check_in

MAX_NOTE_CHARS = 500   # ΠΡΟΣΧΕΔΙΟ


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default=AlertStatus.NEW.value)
    note: Mapped[Optional[str]] = mapped_column(String(MAX_NOTE_CHARS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint(check_in("kind", AlertKind), name="kind"),
        CheckConstraint(check_in("status", AlertStatus), name="status"),
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), index=True)
    event: Mapped[str] = mapped_column(String(16))
    from_status: Mapped[Optional[str]] = mapped_column(String(16))     # μόνο στο status_changed
    to_status: Mapped[Optional[str]] = mapped_column(String(16))       # created: η αρχική· note_updated: η τρέχουσα
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(check_in("event", AlertEventType), name="event"),
        CheckConstraint(check_in("from_status", AlertStatus), name="from_status"),
        CheckConstraint(check_in("to_status", AlertStatus), name="to_status"),
    )


append_only(AlertEvent)
