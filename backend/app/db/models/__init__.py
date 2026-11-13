"""Όλα τα μοντέλα, ώστε το Base.metadata (και το Alembic autogenerate) να τα βλέπει."""
from .alert import Alert, AlertEvent
from .audit import AuditLog
from .card import CardDrop
from .feedback import FeedbackRecord
from .job import JobRun
from .meal import DayStatus, Meal, MealItem
from .participant import Participant

__all__ = ["Alert", "AlertEvent", "AuditLog", "CardDrop", "DayStatus", "FeedbackRecord", "JobRun", "Meal", "MealItem",
           "Participant"]
