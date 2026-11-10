"""
app/services/meal_service.py — επιβεβαίωση, λίστα και (προαιρετικά) διαγραφή γευμάτων· δήλωση «πλήρης ημέρα».

R3 (Κανόνας 3): αποθηκεύεται ΜΟΝΟ ό,τι στέλνει το παιδί στο /meals/confirm. Τα grams τα υπολογίζει ο server από τη
μερίδα του τροφίμου· ο client δεν στέλνει ποτέ γραμμάρια και δεν τα παίρνει πίσω (R1).
Ημερομηνίες: «σήμερα» στη ζώνη APP_TIMEZONE· γεύμα και «πλήρης ημέρα» από σήμερα έως MEAL_BACKDATE_DAYS πριν.
Τα σφάλματα είναι MealError(status, detail) και τα μετατρέπει σε HTTP το api/.
"""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.core import audit
from app.core.clock import local_today
from app.db.models import DayStatus, Meal, MealItem, Participant
from app.services.food_catalog import FoodCatalog

MAX_ITEMS_PER_MEAL = 10       # όπως η προδιαγραφή
MAX_LIST_RANGE_DAYS = 31      # ΠΡΟΣΧΕΔΙΟ: μέγιστο εύρος του GET /meals
# ΠΡΟΣΧΕΔΙΟ: «πλήρης ημέρα» μόνο με τουλάχιστον ένα γεύμα. Μια ημέρα «πλήρης» χωρίς γεύματα θα μετρούσε στον rule
# engine ως μηδενική πρόσληψη και θα έβγαζε «φάε περισσότερο» χωρίς λόγο.
MIN_MEALS_FOR_COMPLETE_DAY = 1


class MealError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def allowed_days(settings: Settings, now: datetime) -> tuple[date, date]:
    today = local_today(settings.tz, now)
    return today - timedelta(days=settings.MEAL_BACKDATE_DAYS), today


def _check_day(day: date, settings: Settings, now: datetime, detail: str) -> None:
    first, last = allowed_days(settings, now)
    if not first <= day <= last:
        raise MealError(422, detail)


def confirm_meal(db: Session, catalog: FoodCatalog, participant: Participant, *, eaten_on: date, meal_slot: str,
                 source: str, items: list[dict], settings: Settings, now: datetime) -> Meal:
    _check_day(eaten_on, settings, now, "eaten_on_out_of_range")
    if not 1 <= len(items) <= MAX_ITEMS_PER_MEAL:
        raise MealError(422, "bad_item_count")
    unknown = [i["food_id"] for i in items if catalog.get(i["food_id"]) is None]
    if unknown:
        raise MealError(422, "unknown_food_id")
    meal = Meal(participant_id=participant.id, eaten_on=eaten_on, meal_slot=meal_slot, source=source)
    meal.items = [MealItem(position=n, food_id=i["food_id"], portion=i["portion"], ai_suggested=i["ai_suggested"],
                           grams=catalog.grams(i["food_id"], i["portion"])) for n, i in enumerate(items)]
    db.add(meal)
    db.flush()
    audit.record(db, "meal_confirmed", participant.id, meal_id=str(meal.id), source=source, meal_slot=meal_slot,
                 eaten_on=eaten_on.isoformat(), n_items=len(items),
                 n_ai_suggested=sum(1 for i in items if i["ai_suggested"]))
    db.commit()
    return meal


def list_meals(db: Session, participant: Participant, start: date, end: date) -> list[Meal]:
    if start > end or (end - start).days >= MAX_LIST_RANGE_DAYS:
        raise MealError(422, "bad_date_range")
    return list(db.scalars(
        select(Meal).options(selectinload(Meal.items))
        .where(Meal.participant_id == participant.id, Meal.deleted_at.is_(None),
               Meal.eaten_on >= start, Meal.eaten_on <= end)
        .order_by(Meal.eaten_on, Meal.created_at)))


def delete_meal(db: Session, participant: Participant, meal_id: uuid.UUID, settings: Settings, now: datetime) -> None:
    if not settings.ALLOW_MEAL_DELETE:
        raise MealError(403, "meal_delete_disabled")
    meal: Optional[Meal] = db.get(Meal, meal_id)
    if meal is None or meal.participant_id != participant.id or meal.deleted_at is not None:
        raise MealError(404, "not_found")          # και για γεύμα άλλου παιδιού: 404, όχι 403
    meal.deleted_at = now
    audit.record(db, "meal_deleted", participant.id, meal_id=str(meal.id))
    db.commit()


def complete_day(db: Session, participant: Participant, day: date, settings: Settings, now: datetime) -> DayStatus:
    _check_day(day, settings, now, "day_out_of_range")
    n_meals = len(db.scalars(select(Meal.id).where(Meal.participant_id == participant.id, Meal.eaten_on == day,
                                                    Meal.deleted_at.is_(None))).all())
    if n_meals < MIN_MEALS_FOR_COMPLETE_DAY:
        raise MealError(422, "day_has_no_meals")
    status = db.scalar(select(DayStatus).where(DayStatus.participant_id == participant.id, DayStatus.day == day))
    if status is None:
        status = DayStatus(participant_id=participant.id, day=day)
        db.add(status)
    if not status.completed:
        status.completed, status.completed_at = True, now
        audit.record(db, "day_completed", participant.id, day=day.isoformat(), n_meals=n_meals)
    try:
        db.commit()
    except IntegrityError:                 # ταυτόχρονο αίτημα για την ίδια ημέρα: υπάρχει ήδη
        db.rollback()
        status = db.scalar(select(DayStatus).where(DayStatus.participant_id == participant.id, DayStatus.day == day))
    return status
