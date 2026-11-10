"""app/db/models/card.py — κάρτες που κέρδισε το παιδί (rule_engine.card_rules, νυχτερινή εργασία). Μία ανά (παιδί, ημέρα, κανόνα)."""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base
from .enums import CardTier, check_in


class CardDrop(Base):
    __tablename__ = "card_drops"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    rule_id: Mapped[str] = mapped_column(String(32))
    rule_version: Mapped[str] = mapped_column(String(16))
    tier: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(String(200))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("participant_id", "day", "rule_id"),   # idempotent νυχτερινή εργασία
        CheckConstraint(check_in("tier", CardTier), name="tier"),
    )
