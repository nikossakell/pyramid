"""
app/db/models/participant.py — ο συμμετέχων: μόνο ψευδώνυμο (UUID) και ό,τι χρειάζεται η μηχανή κανόνων (R2).

Κανένα όνομα, email, τηλέφωνο, ημερομηνία γέννησης. Το κλειδί πρόσβασης δεν αποθηκεύεται· μόνο το
HMAC-SHA256(ACCESS_KEY_PEPPER, κανονικοποιημένο κλειδί), για αναζήτηση στο login.

ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ (βάρος/ύψος): η Αρχιτεκτονική v0.4 κρατά τα βιομετρικά στο χαρτί, άρα δεν υπάρχουν στήλες
βάρους και ύψους. Συνέπεια: ο κανόνας πρωτεΐνης (τιμές ανά kg βάρους) δίνει πάντα insufficient_data. Αυτό είναι
αναμενόμενο. (Το docstring του rule_engine.models.UserProfile και το docs/gdpr-compliance.md λένε ακόμα
«βιομετρικά στην εφαρμογή»· βλ. docs/decisions/2026-11-xx_backend.txt.)
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base
from .enums import Arm, Sex, check_in

MIN_AGE_YEARS, MAX_AGE_YEARS = 10, 16   # πρωτόκολλο (ίδια με rule_engine.models)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)   # pseudonym_id
    key_hmac: Mapped[str] = mapped_column(String(64), unique=True)
    sex: Mapped[str] = mapped_column(String(1))
    age_years_at_enrollment: Mapped[int] = mapped_column(SmallInteger)
    enrollment_date: Mapped[date] = mapped_column(Date)
    arm: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(default=True)
    token_version: Mapped[int] = mapped_column(default=0)
    avatar_id: Mapped[Optional[str]] = mapped_column(String(32))
    photo_suspended_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(check_in("sex", Sex), name="sex"),
        CheckConstraint(check_in("arm", Arm), name="arm"),
        CheckConstraint(f"age_years_at_enrollment BETWEEN {MIN_AGE_YEARS} AND {MAX_AGE_YEARS}", name="age"),
    )
