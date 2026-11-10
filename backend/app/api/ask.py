"""POST /ask — εκπαιδευτικές ερωτήσεις από τη βάση γνώσης (RAG, Βήμα 5.2). Δεν έχει υλοποιηθεί ακόμα: 501."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.dependencies import CurrentParticipant

router = APIRouter(tags=["ask"])
NOT_IMPLEMENTED = {"not_implemented": "5.2"}


@router.post("/ask", status_code=501, summary="Ερώτηση στη βάση γνώσης (δεν υπάρχει ακόμα: 501)",
             responses={501: {"description": "Το RAG Q&A (5.2) έρχεται μετά το backend",
                              "content": {"application/json": {"example": NOT_IMPLEMENTED}}}})
def ask(_: CurrentParticipant):
    return JSONResponse(NOT_IMPLEMENTED, status_code=501)
