"""
app/db/models/alert.py — ειδοποιήσεις προς τον ερευνητή/εφημερεύοντα.

Μόνο κωδικός συμμετέχοντα, είδος και κατηγορία· ΠΟΤΕ κείμενο συνομιλίας ή γεύματος. Το note είναι σημείωση του
ερευνητή για τη διαχείριση (π.χ. «ενημερώθηκε ο παιδίατρος»), όχι περιεχόμενο του παιδιού.
kind=safety και status≠closed -> καμία ανατροφοδότηση πρόσληψης στο παιδί (/feedback/today). Κανένα αυτόματο
alert: δημιουργούνται μόνο με scripts/create_alert.py (docs/backend_spec_v1.md, Τροποποίηση 4).
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base
from .enums import AlertKind, AlertStatus, check_in

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
