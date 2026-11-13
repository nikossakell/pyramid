"""
app/db/models/job.py — εκτελέσεις των εργασιών (σήμερα μόνο η νυχτερινή κατανομή καρτών), για το /admin/system-status.

Μόνο όνομα εργασίας, ημέρα-στόχος, χρόνοι, κατάσταση και πλήθος· κανένα στοιχείο συμμετέχοντα. Η γραμμή γράφεται ως
running στην αρχή και γίνεται ok / failed στο τέλος, ώστε μια εκτέλεση που «έπεσε» να φαίνεται.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow

from ..base import Base
from .enums import JobStatus, check_in


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(32))
    day: Mapped[Optional[date]] = mapped_column(Date)                  # ημέρα-στόχος της εκτέλεσης
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(8), default=JobStatus.RUNNING.value)
    count: Mapped[Optional[int]] = mapped_column()                     # κάρτες που δόθηκαν (NULL αν απέτυχε)

    __table_args__ = (
        CheckConstraint(check_in("status", JobStatus), name="status"),
        Index("ix_job_runs_job_started_at", "job", "started_at"),
    )
