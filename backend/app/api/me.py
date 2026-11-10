"""
GET/PATCH /me — ΜΟΝΟ {arm, avatar_id, photo_available}. Καμία άλλη πληροφορία για το παιδί.

photo_available: υπάρχει ρυθμισμένη διαδρομή φωτογραφίας (σήμερα μόνο η demo, με DEMO_MODE) και ο κωδικός δεν είναι
σε αναστολή φωτογραφίας.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.core import audit
from app.db.models import Participant
from app.dependencies import CurrentParticipant, DbDep, NowDep, SettingsDep
from app.schemas.me import MeResponse, MeUpdate
from app.services.suggestion_service import photo_available

router = APIRouter(tags=["me"])


def _me(participant: Participant, request: Request, now: datetime) -> MeResponse:
    return MeResponse(arm=participant.arm, avatar_id=participant.avatar_id,
                      photo_available=photo_available(participant, request.app.state.photo_pipeline, now))


@router.get("/me", response_model=MeResponse, summary="Το προφίλ μου (ομάδα, avatar, φωτογραφία διαθέσιμη;)")
def get_me(request: Request, participant: CurrentParticipant, now: NowDep):
    return _me(participant, request, now)


@router.patch("/me", response_model=MeResponse, summary="Αλλαγή avatar (μόνο από κλειστή λίστα)")
def update_me(body: MeUpdate, request: Request, participant: CurrentParticipant, db: DbDep, settings: SettingsDep,
              now: NowDep):
    if body.avatar_id is not None and body.avatar_id not in settings.avatar_ids:
        raise HTTPException(422, "unknown_avatar")
    participant.avatar_id = body.avatar_id
    audit.record(db, "avatar_changed", participant.id, avatar_id=body.avatar_id)
    db.commit()
    return _me(participant, request, now)
