"""GET /health — χωρίς JWT. Ελέγχει μόνο ότι η βάση απαντά· δεν δίνει εκδόσεις ή ρυθμίσεις."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import DbDep

router = APIRouter(tags=["health"])


@router.get("/health", summary="Η εφαρμογή και η βάση απαντούν")
def health(db: DbDep):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}
