"""
app/db/models/feedback.py — κάθε ανατροφοδότηση που υπολογίστηκε (Κανόνας 5).

engine_audit = NutritionRuleEngine.audit_record(): περιέχει τα research_values (αριθμοί πρόσληψης και τιμών
αναφοράς). Μένουν ΜΟΝΟ εδώ, για την έρευνα· δεν επιστρέφονται ποτέ στο παιδί (R1).
presented = PresentedMessage.audit() του KrikriPresenter για κάθε μήνυμα.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    engine_audit: Mapped[dict] = mapped_column(JSON)
    presented: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
