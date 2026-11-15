"""app/schemas/food.py — αναζήτηση τροφίμων και ομάδες: ΜΟΝΟ κωδικοί και ονόματα. Ποτέ θρεπτικά ή γραμμάρια (R1)."""
from pydantic import BaseModel


class FoodOut(BaseModel):
    food_id: str
    name_el: str
    food_group: str


class FoodGroupOut(BaseModel):
    """Η λίστα επιστρέφεται ήδη στη σειρά εμφάνισης. sort: η στήλη του CSV, ακέραια σειρά εμφάνισης — δεν είναι τιμή
    θρεπτικού, ενέργειας, βάρους ή ποσοστό, άρα το R1 δεν εφαρμόζεται (Απόφαση 28 του 2026-11-12)."""
    code: str
    label_el: str
    shown: bool          # false: το UI δεν τη δείχνει ως «ομάδα που είχες» (μένει στις «Κατηγορίες»)
    sort: int
