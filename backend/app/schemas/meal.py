"""
app/schemas/meal.py — γεύματα και ημέρες. Καμία έξοδος δεν περιέχει γραμμάρια ή θρεπτικά (R1): μόνο όνομα τροφίμου
και μερίδα ως λέξη (small | medium | large).
"""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import MealSlot, MealSource, Portion
from app.services.meal_service import MAX_ITEMS_PER_MEAL


class ConfirmItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_id: str = Field(min_length=1, max_length=64)
    portion: Portion
    ai_suggested: bool = False


class ConfirmMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")       # π.χ. "grams" από τον client απορρίπτεται
    eaten_on: date
    meal_slot: MealSlot
    source: MealSource
    items: list[ConfirmItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)


class MealItemOut(BaseModel):
    food_id: str
    name_el: str
    portion: Portion


class MealOut(BaseModel):
    id: uuid.UUID
    eaten_on: date
    meal_slot: MealSlot
    source: MealSource
    items: list[MealItemOut]


class DayOut(BaseModel):
    day: date
    completed: bool


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"text": "φακές με ψωμί και ένα μήλο"}]})
    text: str = Field(min_length=1, max_length=300)


class SuggestionOut(BaseModel):
    food_id: Optional[str]                       # null: δεν βρέθηκε στον πίνακα τροφίμων (το παιδί ψάχνει)
    name_el: str
    label_en: Optional[str] = None
    confidence_word: Literal["σίγουρο", "ίσως"]  # ποτέ αριθμός (R1)


class SuggestionsOut(BaseModel):
    suggestions: list[SuggestionOut]
    needs_confirmation: Literal[True] = True     # τίποτα δεν αποθηκεύεται χωρίς /meals/confirm (R3)
