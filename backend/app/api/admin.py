"""
/admin — για τον ερευνητή/εφημερεύοντα. Header X-Admin-Token = ADMIN_TOKEN (σύγκριση σταθερού χρόνου).

ΣΗΜΑΝΤΙΚΟ: ο Nginx επιτρέπει το /api/v1/admin/ ΜΟΝΟ από το VPN του ΑΠΘ (nginx/sites-available/pyramid.conf). Το token
είναι δεύτερο δίχτυ. Καμία απάντηση δεν περιέχει γεύματα ή κείμενα παιδιών· μόνο κωδικούς, κατηγορίες, καταστάσεις.
"""
import hmac
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from app.core import audit
from app.core.clock import aware
from app.db.models import Alert, AuditLog, Participant
from app.db.models.enums import AlertStatus
from app.dependencies import CatalogDep, DbDep, NowDep, SettingsDep
from app.schemas.admin import (AlertDetailOut, AlertEventOut, AlertOut, AlertStatusUpdate, DeactivatedOut, ParticipantOut,
                               PhotoSuspensionOut, SystemStatusOut)
from app.services import alert_service
from app.services.auth_service import study_ended
from app.services.system_status import system_status

_admin_header = APIKeyHeader(name="X-Admin-Token", auto_error=False, scheme_name="AdminToken",
                             description="Η τιμή του ADMIN_TOKEN (μόνο από το VPN του ΑΠΘ).")


def require_admin(settings: SettingsDep, token: Annotated[Optional[str], Depends(_admin_header)]) -> None:
    expected = settings.ADMIN_TOKEN.get_secret_value()
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "not_authenticated")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/alerts", response_model=list[AlertOut],
            summary="Λίστα alerts (κωδικός, είδος, κατηγορία, κατάσταση)· ?status=new|in_progress|closed για τις καρτέλες")
def list_alerts(db: DbDep, status: Optional[AlertStatus] = Query(None)):
    q = select(Alert).order_by(Alert.created_at.desc())
    if status is not None:
        q = q.where(Alert.status == status.value)
    return list(db.scalars(q))


@router.get("/alerts/{alert_id}", response_model=AlertDetailOut,
            summary="Ένα alert με το χρονολόγιό του (δημιουργία, αλλαγές κατάστασης, ενημέρωση σημείωσης)")
def get_alert(alert_id: uuid.UUID, db: DbDep):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "not_found")
    events = [AlertEventOut(event=e.event, from_status=e.from_status, to_status=e.to_status, at=e.at)
              for e in alert_service.events_of(db, alert)]
    return AlertDetailOut(**AlertOut.model_validate(alert, from_attributes=True).model_dump(), events=events)


@router.post("/alerts/{alert_id}/status", response_model=AlertOut,
             summary="Αλλαγή κατάστασης ή/και σημείωσης alert (γράφει γεγονός στο χρονολόγιο)")
def set_alert_status(alert_id: uuid.UUID, body: AlertStatusUpdate, db: DbDep, now: NowDep):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "not_found")
    alert_service.set_status(db, alert, body.status.value, body.note, now)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/participants", response_model=list[ParticipantOut],
            summary="Συμμετέχοντες: κωδικός, ομάδα, ενεργός, εγγραφή, τέλος μελέτης, αναστολή φωτογραφίας")
def list_participants(db: DbDep, settings: SettingsDep, now: NowDep):
    out = []
    for p in db.scalars(select(Participant).order_by(Participant.enrollment_date, Participant.created_at, Participant.id)):
        until = aware(p.photo_suspended_until)
        out.append(ParticipantOut(participant_id=p.id, arm=p.arm, active=p.active, enrolled_on=p.enrollment_date,
                                  study_ended=study_ended(p, settings, now),
                                  photo_suspended_until=until if until is not None and until > now else None))
    return out


@router.get("/system-status", response_model=SystemStatusOut,
            summary="Εκδόσεις δεδομένων/μοντέλων και κατάσταση υπηρεσιών (χωρίς δεδομένα συμμετεχόντων)")
def get_system_status(request: Request, db: DbDep, settings: SettingsDep, catalog: CatalogDep):
    state = request.app.state
    return system_status(db, settings, catalog, state.photo_pipeline, state.llm_probe, request.app.version)


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
