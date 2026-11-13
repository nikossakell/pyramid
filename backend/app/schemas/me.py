"""app/schemas/me.py — ό,τι μαθαίνει το παιδί για τον εαυτό του: ΜΟΝΟ ομάδα, avatar, διαθεσιμότητα φωτογραφίας."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MeResponse(BaseModel):
    arm: str
    avatar_id: Optional[str]
    photo_available: bool                     # = (photo_status == "available")· μένει για συμβατότητα
    # Μόνο για τον client (π.χ. να μην ξαναδοκιμάζει): το PWA δείχνει ΙΔΙΟ ουδέτερο κείμενο για suspended και
    # unavailable. Ποτέ ημερομηνία λήξης αναστολής προς το παιδί.
    photo_status: Literal["available", "suspended", "unavailable"]


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"avatar_id": "avatar_03"}]})
    avatar_id: Optional[str] = Field(max_length=32)
