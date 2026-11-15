"""
app/schemas/meal.py — γεύματα και ημέρες. Καμία έξοδος δεν περιέχει γραμμάρια ή θρεπτικά (R1): μόνο όνομα τροφίμου,
κωδικός ομάδας και μερίδα ως λέξη (small | medium | large).
"""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import aware
from app.db.models.enums import MealSlot, MealSource, Portion
from app.services.meal_service import MAX_ITEMS_PER_MEAL


class ConfirmItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_id: str = Field(min_length=1, max_length=64)
    portion: Portion
    ai_suggested: bool = False


class ConfirmMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")       # π.χ. "grams" από τον client απορρίπτεται
    # Κλειδί idempotency που φτιάχνει ο client (UUID) μία φορά ανά γεύμα: η ουρά offline μπορεί να ξαναστείλει το ίδιο.
    client_meal_id: uuid.UUID
    eaten_on: date
    meal_slot: MealSlot
    source: MealSource
    items: list[ConfirmItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_MEAL)
    # Προαιρετικό: το analysis_id της απάντησης προτάσεων από την οποία προέκυψε το γεύμα. Μόνο για την αξιολόγηση του
    # μοντέλου (audit suggestion_outcome)· δεν αλλάζει τίποτα στο γεύμα και δεν μετρά στη σύγκριση idempotency.
    analysis_id: Optional[uuid.UUID] = None


class ConfirmOut(BaseModel):
    """Απάντηση του /meals/confirm: ό,τι χρειάζεται το S11 («Το μεσημεριανό σου είχε όσπρια»). Χωρίς γραμμάρια."""
    meal_id: uuid.UUID
    eaten_on: date
    meal_slot: MealSlot
    food_groups: list[str]                       # κωδικοί με shown=true, στη σειρά εμφάνισης
    created: bool                                # false: το client_meal_id υπήρχε ήδη (επανάληψη), κανένα νέο γεύμα


class MealItemOut(BaseModel):
    food_id: str
    name_el: str
    portion: Portion
    food_group: Optional[str]                    # null μόνο αν το τρόφιμο δεν υπάρχει πια στον πίνακα
    ai_suggested: bool


class MealOut(BaseModel):
    meal_id: uuid.UUID
    eaten_on: date
    meal_slot: MealSlot
    source: MealSource
    created_at: datetime
    items: list[MealItemOut]

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:      # το SQLite δεν κρατά ζώνη: πάντα UTC με offset στην έξοδο
        return aware(v)


class DayOut(BaseModel):
    day: date
    completed: bool


class TextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"text": "φακές με ψωμί και ένα μήλο"}]})
    text: str = Field(min_length=1, max_length=300)


class AlternativeOut(BaseModel):
    food_id: str
    name_el: str


class SuggestionOut(BaseModel):
    food_id: Optional[str]                       # null: δεν βρέθηκε στον πίνακα (το παιδί διαλέγει από τα alternatives ή ψάχνει)
    name_el: str
    confidence_word: Literal["σίγουρο", "ίσως"]  # ποτέ αριθμός (R1)
    alternatives: list[AlternativeOut] = Field(default_factory=list, max_length=3)   # χωρίς σκορ
    portion: Optional[Portion] = None            # πάντα null σήμερα: δεν υπάρχει μοντέλο μερίδας (πεδίο για το μέλλον)
    # Πάντα null. ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ (διαιτολόγος): υλικά σύνθετου πιάτου. ΜΟΝΟ schema· καμία υλοποίηση.
    components: None = None


class SuggestionsOut(BaseModel):
    # Νέο σε κάθε ανάλυση. Ο client το ξαναστέλνει στο /meals/confirm (analysis_id) αν το γεύμα προέκυψε από αυτές τις
    # προτάσεις. Δεν συνδέεται με το παιδί στον server μέχρι την επιβεβαίωση.
    analysis_id: uuid.UUID
    suggestions: list[SuggestionOut]
    needs_confirmation: Literal[True] = True     # τίποτα δεν αποθηκεύεται χωρίς /meals/confirm (R3)
