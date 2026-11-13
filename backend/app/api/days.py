"""
/days — «πλήρης ημέρα» (ΠΡΟΣΧΕΔΙΟ, ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ).
POST /days/{day}/complete: το παιδί δηλώνει ότι κατέγραψε όλη την ημέρα. Διαθέσιμο και με COMPLETE_DAY_MODE=auto (η
δήλωση υπερισχύει της αυτόματης σήμανσης).
GET /days?from=&to=: [{day, completed}] για κάθε ημέρα του εύρους (S04, S12). Δεν λέει ΠΟΙΟΣ τη σημείωσε πλήρη.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.clock import local_today
from app.dependencies import CurrentParticipant, DbDep, NowDep, SettingsDep
from app.schemas.meal import DayOut
from app.services import meal_service

router = APIRouter(prefix="/days", tags=["days"])


@router.get("", response_model=list[DayOut],
            summary="Ποιες ημέρες είναι πλήρεις (προεπιλογή: σήμερα, έως 31 ημέρες)")
def list_days(participant: CurrentParticipant, db: DbDep, settings: SettingsDep, now: NowDep,
              from_: Optional[date] = Query(None, alias="from"), to: Optional[date] = Query(None)):
    today = local_today(settings.tz, now)
    try:
        days = meal_service.list_days(db, participant, from_ or to or today, to or from_ or today)
    except meal_service.MealError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return [DayOut(day=d, completed=c) for d, c in days]


@router.post("/{day}/complete", response_model=DayOut,
             summary="Δήλωση «κατέγραψα όλη την ημέρα» (χρειάζεται τουλάχιστον ένα γεύμα)")
def complete(day: date, participant: CurrentParticipant, db: DbDep, settings: SettingsDep, now: NowDep):
    try:
        status = meal_service.complete_day(db, participant, day, settings, now)
    except meal_service.MealError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return DayOut(day=status.day, completed=status.completed)
