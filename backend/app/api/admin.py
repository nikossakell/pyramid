"""
/admin — για τον ερευνητή/εφημερεύοντα. Header X-Admin-Token = ADMIN_TOKEN (σύγκριση σταθερού χρόνου).

ΣΗΜΑΝΤΙΚΟ: ο Nginx επιτρέπει το /api/v1/admin/ ΜΟΝΟ από το VPN του ΑΠΘ (nginx/sites-available/pyramid.conf). Το token
είναι δεύτερο δίχτυ. Καμία απάντηση δεν περιέχει γεύματα ή κείμενα παιδιών· μόνο κωδικούς, κατηγορίες, καταστάσεις.
"""
import hmac
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from app.core import audit
from app.core.clock import aware
from app.db.models import Alert, AuditLog, Participant
from app.db.models.enums import AlertStatus
from app.dependencies import DbDep, NowDep, SettingsDep
from app.schemas.admin import AlertOut, AlertStatusUpdate, DeactivatedOut, PhotoSuspensionOut

_admin_header = APIKeyHeader(name="X-Admin-Token", auto_error=False, scheme_name="AdminToken",
                             description="Η τιμή του ADMIN_TOKEN (μόνο από το VPN του ΑΠΘ).")


def require_admin(settings: SettingsDep, token: Annotated[Optional[str], Depends(_admin_header)]) -> None:
    expected = settings.ADMIN_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "not_authenticated")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/alerts", response_model=list[AlertOut], summary="Λίστα alerts (κωδικός, είδος, κατηγορία, κατάσταση)")
def list_alerts(db: DbDep, status: Optional[AlertStatus] = Query(None)):
    q = select(Alert).order_by(Alert.created_at.desc())
    if status is not None:
        q = q.where(Alert.status == status.value)
    return list(db.scalars(q))


@router.post("/alerts/{alert_id}/status", response_model=AlertOut, summary="Αλλαγή κατάστασης alert")
def set_alert_status(alert_id: uuid.UUID, body: AlertStatusUpdate, db: DbDep):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "not_found")
    previous = alert.status
    alert.status = body.status.value
    if body.note is not None:
        alert.note = body.note
    audit.record(db, "alert_status_changed", alert.participant_id, alert_id=str(alert.id),
                 from_status=previous, to_status=alert.status)       # η σημείωση δεν μπαίνει στο audit
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/participants/{participant_id}/deactivate", response_model=DeactivatedOut,
             summary="Ανάκληση συγκατάθεσης: active=false και ακύρωση όλων των tokens")
def deactivate(participant_id: uuid.UUID, db: DbDep):
    p = db.get(Participant, participant_id)
    if p is None:
        raise HTTPException(404, "not_found")
    p.active = False
    p.token_version += 1
    audit.record(db, "participant_deactivated", p.id)
    db.commit()
    return DeactivatedOut(participant_id=p.id, active=False)


@router.get("/photo-suspensions", response_model=list[PhotoSuspensionOut],
            summary="Τρέχουσες αναστολές φωτογραφίας (κωδικός, έως πότε, πλήθος απορρίψεων)")
def photo_suspensions(db: DbDep, now: NowDep):
    out = []
    for p in db.scalars(select(Participant).where(Participant.photo_suspended_until.is_not(None))):
        until = aware(p.photo_suspended_until)
        if until is None or until <= now:
            continue
        last = db.scalar(select(AuditLog).where(AuditLog.participant_id == p.id, AuditLog.event == "photo_suspended")
                         .order_by(AuditLog.id.desc()).limit(1))
        out.append(PhotoSuspensionOut(participant_id=p.id, suspended_until=until,
                                      n_rejections=(last.payload or {}).get("n_rejections", 0) if last else 0))
    return sorted(out, key=lambda x: x.suspended_until)
