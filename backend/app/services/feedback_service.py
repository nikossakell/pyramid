"""
app/services/feedback_service.py — η σημερινή ανατροφοδότηση: rule engine -> ασφάλεια -> KrikriPresenter.

    γεύματα του παραθύρου (EVALUATION_WINDOW_DAYS) ──► DailyIntake ανά ημέρα ──► EvaluationContext
    ανοιχτά alerts kind=safety ──► SafetySignals(HIGH)                       ──► NutritionRuleEngine.evaluate
    ──► KrikriPresenter.present_all ──► μόνο τα κείμενα (χωρίς rule_id, status, αριθμούς) στο παιδί (R1)
    ──► feedback_record: engine.audit_record() (με τα research_values) + presenter audit, ΜΟΝΟ στη βάση

Χτίσιμο του EvaluationContext:
  - UserProfile: φύλο, ηλικία = ηλικία εγγραφής + ολόκληρα έτη από την εγγραφή, weight_kg=None (βιομετρικά στο
    χαρτί: η πρωτεΐνη δίνει insufficient_data — ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ).
  - MealEntry με logged_at = eaten_on στις 12:00: το rule_engine/evaluation.py ομαδοποιεί με logged_at.date().
  - is_complete από το day_status. Ημέρα με τρόφιμο που δεν υπάρχει πια στον πίνακα: όχι πλήρης (άγνωστο, όχι μηδέν).
  - data_versions = sha256 των CSV (πίνακας τροφίμων, συνώνυμα, efsa_drv, food_groups).
Ασφάλεια: όσο υπάρχει alert με kind=safety και status ≠ closed, καμία ανατροφοδότηση πρόσληψης δεν φτάνει στο παιδί
(ΠΡΟΣΧΕΔΙΟ, έγκριση παιδίατρου). Τα alerts kind=operational δεν επηρεάζουν.

Επαναχρησιμοποίηση: αν υπάρχει σημερινό feedback_record και από τότε δεν άλλαξαν γεύματα, ημέρες, alerts ή εκδόσεις
δεδομένων, επιστρέφονται τα ίδια κείμενα (σταθερά για το παιδί, χωρίς νέα κλήση στο LLM).
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ai_pipeline.presentation.krikri_presenter import KrikriPresenter
from rule_engine.engine import NutritionRuleEngine
from rule_engine.evaluation import daily_nutrient_totals
from rule_engine.models import EvaluationContext, MealEntry, MealItem as EngineMealItem, MealSource, ReferenceValue, \
    Sex, UserProfile
from rule_engine.safety_rules import RiskLevel, SafetySignals

from app.config import Settings
from app.core import audit
from app.core.clock import aware, local_today
from app.db.models import Alert, DayStatus, FeedbackRecord, Meal, Participant
from app.db.models.enums import AlertKind, AlertStatus
from app.services.food_catalog import FoodCatalog

MEAL_TIME = time(12, 0)    # βλ. docstring: η ημερομηνία του γεύματος είναι αυτή που μετρά


@dataclass(frozen=True)
class FeedbackView:
    messages: list[tuple[uuid.UUID, str]]
    food_groups_today: list[str]
    record_id: Optional[uuid.UUID]
    reused: bool


def age_years(participant: Participant, today: date) -> int:
    e = participant.enrollment_date
    years = today.year - e.year - ((today.month, today.day) < (e.month, e.day))
    return participant.age_years_at_enrollment + max(0, years)


def _message_id(record_id: uuid.UUID, index: int) -> uuid.UUID:
    return uuid.uuid5(record_id, str(index))


def _open_safety_alert(db: Session, participant_id: uuid.UUID) -> Optional[Alert]:
    return db.scalar(select(Alert).where(Alert.participant_id == participant_id, Alert.kind == AlertKind.SAFETY.value,
                                         Alert.status != AlertStatus.CLOSED.value)
                     .order_by(Alert.created_at.desc()).limit(1))


def _last_change(db: Session, participant_id: uuid.UUID, start: date, end: date) -> Optional[datetime]:
    in_window = (Meal.participant_id == participant_id, Meal.eaten_on >= start, Meal.eaten_on <= end)
    candidates = [
        db.scalar(select(func.max(Meal.created_at)).where(*in_window)),
        db.scalar(select(func.max(Meal.deleted_at)).where(*in_window)),
        db.scalar(select(func.max(DayStatus.completed_at)).where(
            DayStatus.participant_id == participant_id, DayStatus.day >= start, DayStatus.day <= end)),
        db.scalar(select(func.max(Alert.updated_at)).where(Alert.participant_id == participant_id)),
        db.scalar(select(func.max(Alert.created_at)).where(Alert.participant_id == participant_id)),
    ]
    stamps = [aware(c) for c in candidates if c is not None]
    return max(stamps) if stamps else None


def _food_groups_today(meals: list[Meal], catalog: FoodCatalog, today: date) -> list[str]:
    return sorted({f.food_group for m in meals if m.eaten_on == today for i in m.items
                   if (f := catalog.get(i.food_id)) is not None})


def _view_from_record(record: FeedbackRecord, groups: list[str], reused: bool) -> FeedbackView:
    msgs = [(_message_id(record.id, n), p["shown_text"]) for n, p in enumerate(record.presented) if p.get("shown_text")]
    return FeedbackView(msgs, groups, record.id, reused)


def build_context(participant: Participant, meals: list[Meal], completed: set[date], catalog: FoodCatalog,
                  references: tuple[ReferenceValue, ...], today: date, window_days: int) -> EvaluationContext:
    pid = str(participant.id)
    days_in_window = [today - timedelta(days=k) for k in range(window_days)]
    foods = catalog.food_items()
    entries, unknown_days = [], set()
    for m in meals:
        items = tuple(EngineMealItem(i.food_id, i.grams, user_confirmed=True) for i in m.items if i.food_id in foods)
        if len(items) != len(m.items):
            unknown_days.add(m.eaten_on)
        entries.append(MealEntry(str(m.id), pid, datetime.combine(m.eaten_on, MEAL_TIME), MealSource(m.source), items))
    days = tuple(daily_nutrient_totals(entries, foods, d, d in completed and d not in unknown_days)
                 for d in sorted(days_in_window))
    profile = UserProfile(pid, Sex(participant.sex), age_years(participant, today), weight_kg=None)
    return EvaluationContext(profile, today, days, references)


def today_feedback(db: Session, settings: Settings, catalog: FoodCatalog, references: tuple[ReferenceValue, ...],
                   presenter: KrikriPresenter, participant: Participant, now: datetime) -> FeedbackView:
    today = local_today(settings.tz, now)
    start = today - timedelta(days=settings.EVALUATION_WINDOW_DAYS - 1)
    meals = list(db.scalars(select(Meal).options(selectinload(Meal.items)).where(
        Meal.participant_id == participant.id, Meal.deleted_at.is_(None), Meal.eaten_on >= start, Meal.eaten_on <= today)))
    groups = _food_groups_today(meals, catalog, today)

    existing = db.scalar(select(FeedbackRecord).where(FeedbackRecord.participant_id == participant.id,
                                                      FeedbackRecord.as_of == today)
                         .order_by(FeedbackRecord.created_at.desc()).limit(1))
    if existing is not None and existing.engine_audit.get("data_versions") == catalog.versions:
        changed = _last_change(db, participant.id, start, today)
        if changed is None or aware(existing.created_at) >= changed:
            audit.record(db, "feedback_presented", participant.id, feedback_record_id=str(existing.id), reused=True)
            db.commit()
            return _view_from_record(existing, groups, reused=True)

    completed = set(db.scalars(select(DayStatus.day).where(
        DayStatus.participant_id == participant.id, DayStatus.completed.is_(True),
        DayStatus.day >= start, DayStatus.day <= today)))
    try:
        ctx = build_context(participant, meals, completed, catalog, references, today, settings.EVALUATION_WINDOW_DAYS)
    except ValueError as e:                      # π.χ. ηλικία εκτός 10-16: καμία ανατροφοδότηση
        audit.record(db, "feedback_unavailable", participant.id, reason=str(e)[:200])
        db.commit()
        return FeedbackView([], groups, None, reused=False)

    alert = _open_safety_alert(db, participant.id)
    signals = SafetySignals(RiskLevel.HIGH, alert.category) if alert is not None else None
    result = NutritionRuleEngine(data_versions=catalog.versions).evaluate(ctx, signals)
    presented = presenter.present_all(result)

    record = FeedbackRecord(participant_id=participant.id, as_of=today, engine_audit=result.audit_record(),
                            presented=[m.audit() for m in presented])
    db.add(record)
    db.flush()
    audit.record(db, "feedback_presented", participant.id, feedback_record_id=str(record.id), reused=False,
                 n_messages=sum(1 for m in presented if m.text), safety_suppressed=result.safety.suppress)
    db.commit()
    return _view_from_record(record, groups, reused=False)
