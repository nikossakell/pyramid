"""
app/db/models/enums.py — οι επιτρεπτές τιμές των στηλών-κειμένων. Αποθηκεύονται ως κείμενο με CHECK constraint
(ίδιο σχήμα σε SQLite και PostgreSQL, χωρίς native ENUM types στις μεταβάσεις).
"""
from enum import Enum

from rule_engine.models import MealSource as _EngineMealSource


class Arm(str, Enum):
    INTERVENTION = "intervention"
    CONTROL = "control"


class Sex(str, Enum):           # ίδιες τιμές με rule_engine.models.Sex
    MALE = "M"
    FEMALE = "F"


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    MORNING_SNACK = "morning_snack"
    LUNCH = "lunch"
    AFTERNOON_SNACK = "afternoon_snack"
    DINNER = "dinner"
    SNACK = "snack"


MealSource = _EngineMealSource   # camera | text | manual (ίδιος τύπος με τον rule engine)


class Portion(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class CompletedBy(str, Enum):
    CHILD = "child"                # δήλωση του παιδιού (POST /days/{day}/complete)· υπερισχύει
    AUTO = "auto"                  # νυχτερινή εργασία, μόνο με COMPLETE_DAY_MODE=auto


class CardTier(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"


class AlertKind(str, Enum):
    SAFETY = "safety"              # μόνο αυτά (ανοιχτά) κρατούν την ανατροφοδότηση πρόσληψης (/feedback/today)
    OPERATIONAL = "operational"


class AlertStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class AlertEventType(str, Enum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    NOTE_UPDATED = "note_updated"      # άλλαξε η σημείωση του ερευνητή· το κείμενό της ΔΕΝ γράφεται στο event


class JobStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"


def check_in(column: str, enum: type[Enum]) -> str:
    """SQL για CHECK constraint: column IN ('a', 'b', ...)."""
    return f"{column} IN ({', '.join(repr(e.value) for e in enum)})"
