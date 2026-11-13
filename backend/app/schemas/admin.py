"""app/schemas/admin.py — admin: ΜΟΝΟ κωδικοί, κατηγορίες, καταστάσεις, ημερομηνίες. Ποτέ γεύματα ή κείμενα παιδιών."""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import aware

from app.db.models.alert import MAX_NOTE_CHARS
from app.db.models.enums import AlertEventType, AlertKind, AlertStatus, Arm, JobStatus


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


class AlertEventOut(BaseModel):
    """Γεγονός του χρονολογίου (A02). Χωρίς το κείμενο της σημείωσης."""
    event: AlertEventType
    from_status: Optional[AlertStatus]
    to_status: Optional[AlertStatus]
    at: datetime

    @field_validator("at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return aware(v)


class AlertDetailOut(AlertOut):
    events: list[AlertEventOut]               # από το παλαιότερο· κενό για alerts πριν από τη μετάβαση 004


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


class ParticipantOut(BaseModel):
    """Λίστα συμμετεχόντων (A04): μόνο κωδικός και κατάσταση. Τίποτα για γεύματα, κείμενα, φύλο ή ηλικία."""
    participant_id: uuid.UUID
    arm: Arm
    active: bool
    enrolled_on: date
    study_ended: bool                         # ομάδα παρέμβασης μετά το STUDY_DURATION_DAYS (και POST_STUDY_ACCESS=false)
    photo_suspended_until: Optional[datetime]   # μόνο αν η αναστολή ισχύει τώρα


class ModelVersionsOut(BaseModel):
    llm: Optional[str]
    nsfw: Optional[str]
    food_gate: Optional[str]
    recognizer: Optional[str]


class VersionsOut(BaseModel):
    app: Optional[str]
    data_versions: dict[str, str]             # όνομα CSV -> sha256
    rag_sources_sha256: Optional[str]
    prompt_version: str
    presenter_version: str
    foods_is_demo: bool
    models: ModelVersionsOut


class LastJobOut(BaseModel):
    day: Optional[date]
    run_at: datetime
    finished_at: Optional[datetime]
    status: JobStatus
    drops: Optional[int]


class ServicesOut(BaseModel):
    db: Literal["ok", "unavailable"]
    llm: Literal["ok", "unavailable", "not_configured"]
    photo_pipeline: Literal["available", "demo", "unavailable"]
    last_card_job: Optional[LastJobOut]       # null: η εργασία δεν έχει τρέξει ποτέ


class SystemStatusOut(BaseModel):
    """Κατάσταση συστήματος (A03). Κανένα δεδομένο συμμετέχοντα, κανένα URL ή μυστικό."""
    versions: VersionsOut
    services: ServicesOut
