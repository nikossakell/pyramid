"""app/schemas/food.py — αναζήτηση τροφίμων: ΜΟΝΟ food_id, όνομα, ομάδα. Ποτέ θρεπτικά ή γραμμάρια (R1)."""
from pydantic import BaseModel


class FoodOut(BaseModel):
    food_id: str
    name_el: str
    food_group: str
