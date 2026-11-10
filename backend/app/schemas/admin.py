"""app/schemas/admin.py — admin: ΜΟΝΟ κωδικοί, κατηγορίες, καταστάσεις, ημερομηνίες. Ποτέ γεύματα ή κείμενα παιδιών."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import aware

from app.db.models.alert import MAX_NOTE_CHARS
from app.db.models.enums import AlertKind, AlertStatus


class AlertOut(BaseModel):
    id: uuid.UUID
    participant_id: uuid.UUID
    kind: AlertKind
    category: str
    status: AlertStatus
    note: Optional[str]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:       # το SQLite δεν κρατά ζώνη: πάντα UTC με offset στην έξοδο
        return aware(v)


class AlertStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [{"status": "in_progress", "note": "ενημερώθηκε ο παιδίατρος"}]})
    status: AlertStatus
    note: Optional[str] = Field(None, max_length=MAX_NOTE_CHARS)   # σημείωση ερευνητή, ΟΧΙ κείμενο παιδιού


class DeactivatedOut(BaseModel):
    participant_id: uuid.UUID
    active: bool


class PhotoSuspensionOut(BaseModel):
    participant_id: uuid.UUID
    suspended_until: datetime
    n_rejections: int
