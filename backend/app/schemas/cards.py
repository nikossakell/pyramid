"""app/schemas/cards.py — κάρτες του παιδιού: μόνο id, σπανιότητα, ημέρα, αν άνοιξε. Χωρίς κανόνα ή λόγο."""
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class CardOut(BaseModel):
    id: uuid.UUID
    tier: Literal["common", "rare", "epic"]
    day: date
    opened: bool
