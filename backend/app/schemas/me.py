"""app/schemas/me.py — ό,τι μαθαίνει το παιδί για τον εαυτό του: ΜΟΝΟ ομάδα, avatar, διαθεσιμότητα φωτογραφίας."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MeResponse(BaseModel):
    arm: str
    avatar_id: Optional[str]
    photo_available: bool


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"avatar_id": "avatar_03"}]})
    avatar_id: Optional[str] = Field(max_length=32)
