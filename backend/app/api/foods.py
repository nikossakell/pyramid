"""GET /foods/search?q= — αυτόματη συμπλήρωση. ΜΟΝΟ food_id, όνομα, ομάδα (R1). Το q δεν γράφεται στο log (R6)."""
from fastapi import APIRouter, Query

from app.dependencies import CatalogDep, CurrentParticipant
from app.schemas.food import FoodOut

router = APIRouter(prefix="/foods", tags=["foods"])
SEARCH_LIMIT = 10


@router.get("/search", response_model=list[FoodOut], summary="Αναζήτηση τροφίμου (π.χ. q=φακ)")
def search_foods(_: CurrentParticipant, catalog: CatalogDep, q: str = Query("", max_length=100)):
    return [FoodOut(food_id=f.food_id, name_el=f.name_el, food_group=f.food_group)
            for f in (catalog.foods[fid] for fid in catalog.resolver.search(q, SEARCH_LIMIT))]
