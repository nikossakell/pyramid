"""
app/services/alert_service.py — δημιουργία και αλλαγή alerts, με χρονολόγιο (alert_events, οθόνη A02).

Ο ΜΟΝΟΣ κώδικας που γράφει alerts και alert_events: scripts/create_alert.py, scripts/seed_demo.py και το admin API
περνούν από εδώ, ώστε κάθε δημιουργία και κάθε αλλαγή να αφήνει γεγονός. Κανένα αυτόματο alert (Τροποποίηση 4).
Το γεγονός κρατά μόνο είδος, καταστάσεις και χρόνο· το κείμενο της σημείωσης μένει μόνο στο alerts.note (δεν μπαίνει
ούτε στο event ούτε στο audit). Το commit το κάνει ο καλών, στην ίδια συναλλαγή.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.clock import utcnow
from app.db.models import Alert, AlertEvent
from app.db.models.enums import AlertEventType, AlertStatus


def record_event(db: Session, alert: Alert, event: AlertEventType, from_status: Optional[str] = None,
                 to_status: Optional[str] = None, at: Optional[datetime] = None) -> AlertEvent:
    """Η μία συνάρτηση εγγραφής του alert_events: σταθερές στήλες, καμία θέση για ελεύθερο κείμενο."""
    row = AlertEvent(alert_id=alert.id, event=AlertEventType(event).value,
                     from_status=AlertStatus(from_status).value if from_status is not None else None,
                     to_status=AlertStatus(to_status).value if to_status is not None else None, at=at or utcnow())
    db.add(row)
    return row


def create_alert(db: Session, participant_id: uuid.UUID, kind: str, category: str, note: Optional[str] = None,
                 now: Optional[datetime] = None) -> Alert:
    alert = Alert(participant_id=participant_id, kind=kind, category=category, note=note)
    db.add(alert)
    db.flush()
    record_event(db, alert, AlertEventType.CREATED, to_status=alert.status, at=now)
    audit.record(db, "alert_created", participant_id, alert_id=str(alert.id), kind=kind, category=category)
    return alert


def set_status(db: Session, alert: Alert, status: str, note: Optional[str] = None,
               now: Optional[datetime] = None) -> Alert:
    """note=None: η σημείωση δεν αλλάζει. Γεγονότα: status_changed αν άλλαξε η κατάσταση, note_updated αν άλλαξε η
    σημείωση (και τα δύο αν άλλαξαν και τα δύο)."""
    previous = alert.status
    alert.status = status
    if status != previous:
        record_event(db, alert, AlertEventType.STATUS_CHANGED, from_status=previous, to_status=status, at=now)
    if note is not None and note != alert.note:
        alert.note = note
        record_event(db, alert, AlertEventType.NOTE_UPDATED, to_status=status, at=now)
    audit.record(db, "alert_status_changed", alert.participant_id, alert_id=str(alert.id),
                 from_status=previous, to_status=status)             # η σημείωση δεν μπαίνει στο audit
    return alert


def events_of(db: Session, alert: Alert) -> list[AlertEvent]:
    return list(db.scalars(select(AlertEvent).where(AlertEvent.alert_id == alert.id).order_by(AlertEvent.id)))
