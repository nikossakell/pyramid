"""
app/services/meal_service.py — επιβεβαίωση, λίστα και (προαιρετικά) διαγραφή γευμάτων· δήλωση «πλήρης ημέρα».

R3 (Κανόνας 3): αποθηκεύεται ΜΟΝΟ ό,τι στέλνει το παιδί στο /meals/confirm. Τα grams τα υπολογίζει ο server από τη
μερίδα του τροφίμου· ο client δεν στέλνει ποτέ γραμμάρια και δεν τα παίρνει πίσω (R1).
Ημερομηνίες: «σήμερα» στη ζώνη APP_TIMEZONE· γεύμα και «πλήρης ημέρα» από σήμερα έως MEAL_BACKDATE_DAYS πριν.
Idempotency: το client_meal_id είναι μοναδικό ανά συμμετέχοντα. Ίδιο κλειδί με ίδιο περιεχόμενο -> το υπάρχον γεύμα
(created=False), χωρίς νέα γραμμή και ΠΡΙΝ από τον έλεγχο ημερομηνίας (η ουρά offline μπορεί να ξαναστείλει μετά από
ημέρες). Ίδιο κλειδί με άλλο περιεχόμενο, ή για γεύμα που διαγράφηκε -> 409.
Πλήρης ημέρα (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ): δήλωση του παιδιού (complete_day, ≥ 1 γεύμα, completed_by=child) και, μόνο με
COMPLETE_DAY_MODE=auto, η νυχτερινή εργασία (auto_complete_day, ≥ AUTO_COMPLETE_MIN_MEALS γεύματα, completed_by=auto).
Η δήλωση υπερισχύει: ημέρα «auto» που τη δηλώνει το παιδί γίνεται «child»· το αντίστροφο δεν γίνεται ποτέ.
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
from app.db.models.enums import CompletedBy
from app.services.food_catalog import FoodCatalog

MAX_ITEMS_PER_MEAL = 10       # όπως η προδιαγραφή
MAX_LIST_RANGE_DAYS = 31      # ΠΡΟΣΧΕΔΙΟ: μέγιστο εύρος του GET /meals και του GET /days
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


def _same_meal(meal: Meal, eaten_on: date, meal_slot: str, source: str, items: list[dict]) -> bool:
    return (meal.eaten_on, meal.meal_slot, meal.source) == (eaten_on, meal_slot, source) and \
        [(i.food_id, i.portion, i.ai_suggested) for i in meal.items] == \
        [(i["food_id"], i["portion"], i["ai_suggested"]) for i in items]


def _replay(db: Session, participant: Participant, client_meal_id: uuid.UUID, eaten_on: date, meal_slot: str,
            source: str, items: list[dict]) -> Optional[Meal]:
    """Το γεύμα που έχει ήδη αυτό το client_meal_id (None αν δεν υπάρχει)· 409 αν διαφέρει ή έχει διαγραφεί."""
    existing = db.scalar(select(Meal).options(selectinload(Meal.items)).where(
        Meal.participant_id == participant.id, Meal.client_meal_id == client_meal_id))
    if existing is None:
        return None
    if existing.deleted_at is not None or not _same_meal(existing, eaten_on, meal_slot, source, items):
        raise MealError(409, "client_meal_id_conflict")
    return existing


def confirm_meal(db: Session, catalog: FoodCatalog, participant: Participant, *, client_meal_id: uuid.UUID,
                 eaten_on: date, meal_slot: str, source: str, items: list[dict], settings: Settings,
                 now: datetime) -> tuple[Meal, bool]:
    """Επιστρέφει (γεύμα, created). created=False: επανάληψη του ίδιου client_meal_id, τίποτα νέο δεν γράφτηκε."""
    existing = _replay(db, participant, client_meal_id, eaten_on, meal_slot, source, items)
    if existing is not None:
        audit.record(db, "meal_confirm_repeated", participant.id, meal_id=str(existing.id))
        db.commit()
        return existing, False
    _check_day(eaten_on, settings, now, "eaten_on_out_of_range")
    if not 1 <= len(items) <= MAX_ITEMS_PER_MEAL:
        raise MealError(422, "bad_item_count")
    unknown = [i["food_id"] for i in items if catalog.get(i["food_id"]) is None]
    if unknown:
        raise MealError(422, "unknown_food_id")
    meal = Meal(participant_id=participant.id, client_meal_id=client_meal_id, eaten_on=eaten_on, meal_slot=meal_slot,
                source=source)
    meal.items = [MealItem(position=n, food_id=i["food_id"], portion=i["portion"], ai_suggested=i["ai_suggested"],
                           grams=catalog.grams(i["food_id"], i["portion"])) for n, i in enumerate(items)]
    db.add(meal)
    try:
        db.flush()
        audit.record(db, "meal_confirmed", participant.id, meal_id=str(meal.id), source=source, meal_slot=meal_slot,
                     eaten_on=eaten_on.isoformat(), n_items=len(items),
                     n_ai_suggested=sum(1 for i in items if i["ai_suggested"]))
        db.commit()
    except IntegrityError:                 # ταυτόχρονη αποστολή του ίδιου client_meal_id: κέρδισε η άλλη
        db.rollback()
        existing = _replay(db, participant, client_meal_id, eaten_on, meal_slot, source, items)
        if existing is None:
            raise
        return existing, False
    return meal, True


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


def _count_meals(db: Session, participant: Participant, day: date) -> int:
    return len(db.scalars(select(Meal.id).where(Meal.participant_id == participant.id, Meal.eaten_on == day,
                                                 Meal.deleted_at.is_(None))).all())


def _day_status(db: Session, participant: Participant, day: date) -> Optional[DayStatus]:
    return db.scalar(select(DayStatus).where(DayStatus.participant_id == participant.id, DayStatus.day == day))


def complete_day(db: Session, participant: Participant, day: date, settings: Settings, now: datetime) -> DayStatus:
    _check_day(day, settings, now, "day_out_of_range")
    n_meals = _count_meals(db, participant, day)
    if n_meals < MIN_MEALS_FOR_COMPLETE_DAY:
        raise MealError(422, "day_has_no_meals")
    status = _day_status(db, participant, day)
    if status is None:
        status = DayStatus(participant_id=participant.id, day=day)
        db.add(status)
    if not status.completed:
        status.completed, status.completed_at, status.completed_by = True, now, CompletedBy.CHILD.value
        audit.record(db, "day_completed", participant.id, day=day.isoformat(), n_meals=n_meals,
                     by=CompletedBy.CHILD.value)
    elif status.completed_by == CompletedBy.AUTO.value:      # η δήλωση του παιδιού υπερισχύει της αυτόματης
        status.completed_by = CompletedBy.CHILD.value
        audit.record(db, "day_completed", participant.id, day=day.isoformat(), n_meals=n_meals,
                     by=CompletedBy.CHILD.value, was=CompletedBy.AUTO.value)
    try:
        db.commit()
    except IntegrityError:                 # ταυτόχρονο αίτημα για την ίδια ημέρα: υπάρχει ήδη
        db.rollback()
        status = db.scalar(select(DayStatus).where(DayStatus.participant_id == participant.id, DayStatus.day == day))
    return status


def auto_complete_day(db: Session, participant: Participant, day: date, settings: Settings, now: datetime) -> bool:
    """Νυχτερινή εργασία, ΜΟΝΟ με COMPLETE_DAY_MODE=auto: σημειώνει πλήρη την ημέρα αν έχει ≥ AUTO_COMPLETE_MIN_MEALS
    επιβεβαιωμένα γεύματα. True αν τη σημείωσε τώρα. Δεν αγγίζει ημέρα που είναι ήδη πλήρης (δήλωση ή auto)."""
    if settings.COMPLETE_DAY_MODE != "auto":
        return False
    n_meals = _count_meals(db, participant, day)
    if n_meals < settings.AUTO_COMPLETE_MIN_MEALS:
        return False
    status = _day_status(db, participant, day)
    if status is not None and status.completed:
        return False
    if status is None:
        status = DayStatus(participant_id=participant.id, day=day)
        db.add(status)
    status.completed, status.completed_at, status.completed_by = True, now, CompletedBy.AUTO.value
    audit.record(db, "day_completed", participant.id, day=day.isoformat(), n_meals=n_meals, by=CompletedBy.AUTO.value)
    try:
        db.commit()
    except IntegrityError:                 # το παιδί τη δήλωσε την ίδια στιγμή: μένει η δήλωσή του
        db.rollback()
        return False
    return True


def list_days(db: Session, participant: Participant, start: date, end: date) -> list[tuple[date, bool]]:
    """Κάθε ημέρα του εύρους (έως MAX_LIST_RANGE_DAYS) με το αν είναι πλήρης· ημέρα χωρίς εγγραφή: όχι πλήρης."""
    if start > end or (end - start).days >= MAX_LIST_RANGE_DAYS:
        raise MealError(422, "bad_date_range")
    completed = set(db.scalars(select(DayStatus.day).where(
        DayStatus.participant_id == participant.id, DayStatus.completed.is_(True),
        DayStatus.day >= start, DayStatus.day <= end)))
    return [(d, d in completed) for d in (start + timedelta(days=k) for k in range((end - start).days + 1))]
