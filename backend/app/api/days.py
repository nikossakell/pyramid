"""POST /days/{day}/complete — το παιδί δηλώνει ότι κατέγραψε όλη την ημέρα (ΠΡΟΣΧΕΔΙΟ, ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: πλήρης ημέρα)."""
from datetime import date

from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentParticipant, DbDep, NowDep, SettingsDep
from app.schemas.meal import DayOut
from app.services import meal_service

router = APIRouter(prefix="/days", tags=["days"])


@router.post("/{day}/complete", response_model=DayOut,
             summary="Δήλωση «κατέγραψα όλη την ημέρα» (χρειάζεται τουλάχιστον ένα γεύμα)")
def complete(day: date, participant: CurrentParticipant, db: DbDep, settings: SettingsDep, now: NowDep):
    try:
        status = meal_service.complete_day(db, participant, day, settings, now)
    except meal_service.MealError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return DayOut(day=status.day, completed=status.completed)
