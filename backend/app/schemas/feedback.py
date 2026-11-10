"""app/schemas/feedback.py — ό,τι βλέπει το παιδί: ΜΟΝΟ κείμενα και κωδικοί ομάδων τροφίμων. Χωρίς rule_id, status, αριθμούς (R1)."""
import uuid

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: uuid.UUID
    text: str


class FeedbackOut(BaseModel):
    messages: list[MessageOut]
    food_groups_today: list[str]
