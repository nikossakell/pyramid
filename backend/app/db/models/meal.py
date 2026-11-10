"""
app/db/models/meal.py — γεύματα που ΕΠΙΒΕΒΑΙΩΣΕ το παιδί (R3, Κανόνας 3) και η δήλωση «πλήρης ημέρα».

Οι προτάσεις του AI (φωτογραφία, κείμενο) δεν αποθηκεύονται ποτέ· αποθηκεύεται μόνο η λίστα που στέλνει το παιδί
στο /meals/confirm. Το ai_suggested λέει μόνο αν το επιβεβαιωμένο τρόφιμο είχε προταθεί, για την έρευνα.
Τα grams τα υπολογίζει ο server από τη μερίδα (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: μερίδες σε γραμμάρια). Δεν υπάρχει πουθενά
πίνακας ή στήλη εικόνας (Κανόνας 7).
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow

from ..base import Base
from .enums import MealSlot, MealSource, Portion, check_in


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"))
    eaten_on: Mapped[date] = mapped_column(Date)
    meal_slot: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))   # soft delete (ALLOW_MEAL_DELETE)

    items: Mapped[list["MealItem"]] = relationship(back_populates="meal", cascade="all, delete-orphan",
                                                   order_by="MealItem.position")

    __table_args__ = (
        CheckConstraint(check_in("meal_slot", MealSlot), name="meal_slot"),
        CheckConstraint(check_in("source", MealSource), name="source"),
        Index("ix_meals_participant_day", "participant_id", "eaten_on"),
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    meal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)          # σειρά όπως την έστειλε το παιδί
    food_id: Mapped[str] = mapped_column(String(64))
    portion: Mapped[str] = mapped_column(String(8))
    grams: Mapped[float] = mapped_column(Float)
    ai_suggested: Mapped[bool] = mapped_column(default=False)

    meal: Mapped[Meal] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint(check_in("portion", Portion), name="portion"),
        CheckConstraint("grams > 0", name="grams_positive"),
    )


class DayStatus(Base):
    """ΠΡΟΣΧΕΔΙΟ (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: πλήρης ημέρα): την «πλήρη ημέρα» τη δηλώνει το παιδί."""
    __tablename__ = "day_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"))
    day: Mapped[date] = mapped_column(Date)
    completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("participant_id", "day"),)
