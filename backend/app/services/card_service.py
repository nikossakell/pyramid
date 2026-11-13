"""
app/services/card_service.py — κάρτες: νυχτερινή κατανομή (rule_engine.card_rules) και άνοιγμα από το παιδί.

Η κατανομή τρέχει μία φορά τη νύχτα για την ΠΡΟΗΓΟΥΜΕΝΗ ημέρα (app/jobs/daily_card_drops.py), μόνο για ενεργούς
συμμετέχοντες της ομάδας παρέμβασης. Idempotent: ξανά για την ίδια ημέρα δεν δίνει διπλή κάρτα (unique
participant + day + rule_id, και έλεγχος πριν την εισαγωγή).
Τέλος μελέτης: αγνοούνται όσοι είχαν τελειώσει ΠΡΙΝ από την ημέρα-στόχο (auth_service.in_study_on). Η τελευταία ημέρα
μελέτης παίρνει κανονικά τις κάρτες της, αν και η εργασία τρέχει την επομένη (το παιδί δεν τις βλέπει: 403).
Με COMPLETE_DAY_MODE=auto η ίδια εργασία σημειώνει ΠΡΩΤΑ την ημέρα πλήρη (meal_service.auto_complete_day) και μετά
μοιράζει κάρτες, ώστε ο κανόνας «πλήρης ημέρα» του card_rules να βλέπει τη σήμανση.
DayActivity: επιβεβαιωμένα γεύματα της ημέρας, δήλωση πλήρους ημέρας, ομάδες τροφίμων· ιστορικό από την εγγραφή.
"""
import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from rule_engine.card_rules import DayActivity, card_drops

from app.config import Settings
from app.core import audit
from app.core.clock import utcnow
from app.db.models import CardDrop, DayStatus, JobRun, Meal, Participant
from app.db.models.enums import Arm, JobStatus
from app.services import meal_service
from app.services.auth_service import in_study_on
from app.services.food_catalog import FoodCatalog


def _activities(db: Session, catalog: FoodCatalog, participant: Participant, until: date) -> dict[date, DayActivity]:
    meals = db.scalars(select(Meal).options(selectinload(Meal.items)).where(
        Meal.participant_id == participant.id, Meal.deleted_at.is_(None),
        Meal.eaten_on >= participant.enrollment_date, Meal.eaten_on <= until))
    counts: dict[date, int] = defaultdict(int)
    groups: dict[date, set] = defaultdict(set)
    for m in meals:
        counts[m.eaten_on] += 1
        groups[m.eaten_on] |= {f.food_group for i in m.items if (f := catalog.get(i.food_id)) is not None}
    completed = set(db.scalars(select(DayStatus.day).where(
        DayStatus.participant_id == participant.id, DayStatus.completed.is_(True), DayStatus.day <= until)))
    days = set(counts) | completed | {until}
    return {d: DayActivity(d, counts.get(d, 0), d in completed, frozenset(groups.get(d, ()))) for d in days}


def drop_cards_for(db: Session, catalog: FoodCatalog, participant: Participant, day: date) -> list[CardDrop]:
    acts = _activities(db, catalog, participant, day)
    drops = card_drops(acts[day], [a for d, a in acts.items() if d < day])
    existing = set(db.scalars(select(CardDrop.rule_id).where(CardDrop.participant_id == participant.id,
                                                             CardDrop.day == day)))
    new = [CardDrop(participant_id=participant.id, day=day, rule_id=c.rule_id, rule_version=c.rule_version,
                    tier=c.tier, reason=c.reason[:200]) for c in drops if c.rule_id not in existing]
    if not new:
        return []
    db.add_all(new)
    audit.record(db, "cards_dropped", participant.id, day=day.isoformat(), rule_ids=[c.rule_id for c in new])
    try:
        db.commit()
    except IntegrityError:                     # ταυτόχρονη εκτέλεση: οι κάρτες υπάρχουν ήδη
        db.rollback()
        return []
    return new


def run_card_drops(db: Session, catalog: FoodCatalog, day: date, settings: Optional[Settings] = None,
                   now: Optional[datetime] = None) -> dict:
    """settings=None (μόνο tests/παλιές κλήσεις): χωρίς έλεγχο τέλους μελέτης και χωρίς αυτόματη πλήρη ημέρα."""
    participants = list(db.scalars(select(Participant).where(
        Participant.active.is_(True), Participant.arm == Arm.INTERVENTION.value,
        Participant.enrollment_date <= day)))
    extra = {}
    if settings is not None:
        participants = [p for p in participants if in_study_on(p, settings, day)]
        if settings.COMPLETE_DAY_MODE == "auto":
            if now is None:
                raise ValueError("now is required with COMPLETE_DAY_MODE=auto")
            extra["auto_completed"] = sum(meal_service.auto_complete_day(db, p, day, settings, now)
                                          for p in participants)
    new = sum(len(drop_cards_for(db, catalog, p, day)) for p in participants)
    return {"day": day.isoformat(), "participants": len(participants), "new_cards": new, **extra}


CARD_JOB = "daily_card_drops"


def run_card_job(db: Session, catalog: FoodCatalog, day: date, settings: Settings, clock=utcnow) -> dict:
    """Η νυχτερινή εργασία με καταγραφή στο job_runs (για το /admin/system-status): running -> ok / failed."""
    run = JobRun(job=CARD_JOB, day=day, started_at=clock())
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        summary = run_card_drops(db, catalog, day, settings, clock())
    except Exception:
        db.rollback()
        run = db.get(JobRun, run_id)
        run.status, run.finished_at = JobStatus.FAILED.value, clock()
        db.commit()
        raise
    run = db.get(JobRun, run_id)
    run.status, run.finished_at, run.count = JobStatus.OK.value, clock(), summary["new_cards"]
    db.commit()
    return summary


def last_card_job(db: Session) -> Optional[JobRun]:
    return db.scalar(select(JobRun).where(JobRun.job == CARD_JOB).order_by(JobRun.started_at.desc(), JobRun.id.desc())
                     .limit(1))


def list_cards(db: Session, participant: Participant) -> list[CardDrop]:
    return list(db.scalars(select(CardDrop).where(CardDrop.participant_id == participant.id)
                           .order_by(CardDrop.day.desc(), CardDrop.created_at)))


def open_card(db: Session, participant: Participant, card_id: uuid.UUID, now: datetime) -> Optional[CardDrop]:
    card = db.get(CardDrop, card_id)
    if card is None or card.participant_id != participant.id:
        return None                            # ξένη κάρτα: 404 (όχι 403)
    if card.opened_at is None:
        card.opened_at = now
        audit.record(db, "card_opened", participant.id, card_id=str(card.id))
        db.commit()
    return card
