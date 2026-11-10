"""GET /feedback/today — βλ. app/services/feedback_service.py."""
from fastapi import APIRouter, Request

from app.dependencies import CatalogDep, CurrentParticipant, DbDep, NowDep, SettingsDep
from app.schemas.feedback import FeedbackOut, MessageOut
from app.services.feedback_service import today_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/today", response_model=FeedbackOut,
            summary="Η σημερινή ανατροφοδότηση (συνήθης πρόσληψη 7 ημερών, χωρίς αριθμούς)")
def feedback_today(request: Request, participant: CurrentParticipant, db: DbDep, settings: SettingsDep,
                   catalog: CatalogDep, now: NowDep):
    view = today_feedback(db, settings, catalog, request.app.state.references, request.app.state.presenter,
                          participant, now)
    return FeedbackOut(messages=[MessageOut(id=i, text=t) for i, t in view.messages],
                       food_groups_today=view.food_groups_today)
