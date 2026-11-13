"""
GET /foods/search?q=&group= — αυτόματη συμπλήρωση και «Κατηγορίες» (S10). ΜΟΝΟ food_id, όνομα, ομάδα (R1).
GET /food-groups — οι κύριες ομάδες όπως τις βλέπει το παιδί (data/display_food_groups.csv, ΠΡΟΣΧΕΔΙΟ).
Το q δεν γράφεται στο log (R6).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import CatalogDep, CurrentParticipant
from app.schemas.food import FoodGroupOut, FoodOut

router = APIRouter(tags=["foods"])
SEARCH_LIMIT = 10
GROUP_LIMIT = 50       # ΠΡΟΣΧΕΔΙΟ: τρόφιμα μιας ομάδας χωρίς q (και όριο του resolver.search)


@router.get("/foods/search", response_model=list[FoodOut],
            summary="Αναζήτηση τροφίμου (q=φακ) ή τρόφιμα μιας ομάδας (group=legumes, αλφαβητικά)")
def search_foods(_: CurrentParticipant, catalog: CatalogDep, q: str = Query("", max_length=100),
                 group: Optional[str] = Query(None, max_length=64, description="Κωδικός ομάδας από το /food-groups")):
    if group is not None and group not in catalog.group_codes:
        raise HTTPException(422, "unknown_group")
    if group is not None and not q.strip():
        foods = catalog.foods_in_group(group)[:GROUP_LIMIT]
    else:
        found = (catalog.foods[fid] for fid in catalog.resolver.search(q, GROUP_LIMIT if group else SEARCH_LIMIT))
        foods = [f for f in found if group is None or f.food_group == group][:SEARCH_LIMIT]
    return [FoodOut(food_id=f.food_id, name_el=f.name_el, food_group=f.food_group) for f in foods]


@router.get("/food-groups", response_model=list[FoodGroupOut],
            summary="Ομάδες τροφίμων για εμφάνιση, στη σειρά εμφάνισης (shown=false: όχι ως «ομάδα που είχες»)")
def food_groups(_: CurrentParticipant, catalog: CatalogDep):
    return [FoodGroupOut(code=g.code, label_el=g.label_el, shown=g.shown) for g in catalog.display_groups]
