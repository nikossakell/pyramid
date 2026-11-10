"""
/meals — φωτογραφία και κείμενο (προτάσεις, ΔΕΝ αποθηκεύονται), επιβεβαίωση (/meals/confirm), λίστα, διαγραφή.
Κάθε παιδί βλέπει και αγγίζει μόνο τα δικά του γεύματα· για ξένο γεύμα η απάντηση είναι 404, όχι 403.

/meals/photo (R4, Κανόνες 7-8): raw σώμα image/jpeg (ΟΧΙ multipart/UploadFile, που γράφει σε δίσκο πάνω από ~1 MB).
Το σώμα διαβάζεται σε κομμάτια στη RAM και η ανάγνωση σταματά μόλις ξεπεράσει το MAX_PHOTO_BYTES. Πριν διαβαστεί
οτιδήποτε: JWT (και ομάδα ελέγχου), διαθεσιμότητα (503) και αναστολή (403). Για ΚΑΘΕ λόγο απόρριψης η απάντηση είναι
η ίδια: 422 {"rejected": true}· ο λόγος γράφεται μόνο στο audit (photo_rejected, stored_bytes: 0).
"""
import uuid
from datetime import date
from typing import Optional

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.db.models import Meal
from app.dependencies import CatalogDep, CurrentParticipant, DbDep, NowDep, SettingsDep
from app.core import audit
from app.core.clock import local_today
from app.schemas.meal import ConfirmMeal, MealItemOut, MealOut, SuggestionOut, SuggestionsOut, TextRequest
from app.services import meal_service
from app.services.food_catalog import FoodCatalog
from app.services.photo_pipeline import PhotoRejected
from app.services.suggestion_service import (Suggestion, photo_suspended, record_rejection, suggestions_from_photo,
                                             suggestions_from_text)

router = APIRouter(prefix="/meals", tags=["meals"])


def meal_out(meal: Meal, catalog: FoodCatalog) -> MealOut:
    return MealOut(id=meal.id, eaten_on=meal.eaten_on, meal_slot=meal.meal_slot, source=meal.source,
                   items=[MealItemOut(food_id=i.food_id, portion=i.portion,
                                      name_el=f.name_el if (f := catalog.get(i.food_id)) else i.food_id)
                          for i in meal.items])


def _http(e: meal_service.MealError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


def _suggestions(items: list[Suggestion]) -> SuggestionsOut:
    return SuggestionsOut(suggestions=[SuggestionOut(food_id=s.food_id, name_el=s.name_el, label_en=s.label_en,
                                                     confidence_word=s.confidence_word) for s in items])


REJECTED = {"rejected": True}                  # ΙΔΙΟ σώμα για κάθε λόγο απόρριψης (R4)
PHOTO_UNAVAILABLE = {"photo_unavailable": True}
PHOTO_OPENAPI = {
    "requestBody": {"required": True, "description": "Raw JPEG (όχι multipart), ≤ MAX_PHOTO_BYTES, μεγαλύτερη πλευρά ≤ "
                                                      "PHOTO_MAX_EDGE_PX. Στο Swagger: «Try it out» και επιλογή αρχείου.",
                    "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}},
}
PHOTO_RESPONSES = {
    422: {"description": "Απόρριψη για ΟΠΟΙΟΝΔΗΠΟΤΕ λόγο (ίδιο σώμα· ο λόγος μόνο στο audit)",
          "content": {"application/json": {"example": REJECTED}}},
    403: {"description": "Αναστολή φωτογραφίας για τον κωδικό (κείμενο και αναζήτηση μένουν)",
          "content": {"application/json": {"example": PHOTO_UNAVAILABLE}}},
    503: {"description": "Η φωτογραφία δεν είναι ρυθμισμένη (χωρίς μοντέλα και DEMO_MODE=false)",
          "content": {"application/json": {"example": PHOTO_UNAVAILABLE}}},
}


async def _read_limited(request: Request, limit: int) -> Optional[bytes]:
    """Το σώμα στη RAM, ή None μόλις ξεπεράσει το όριο (δεν διαβάζεται παραπέρα)."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        return None
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > limit:
            return None
    return bytes(buf)


@router.post("/photo", response_model=SuggestionsOut, openapi_extra=PHOTO_OPENAPI, responses=PHOTO_RESPONSES,
             summary="Προτάσεις τροφίμων από φωτογραφία (τίποτα δεν αποθηκεύεται)")
async def photo(request: Request, participant: CurrentParticipant, db: DbDep, catalog: CatalogDep,
                settings: SettingsDep, now: NowDep):
    pipeline = request.app.state.photo_pipeline
    if not pipeline.available:
        return JSONResponse(PHOTO_UNAVAILABLE, status_code=503)
    if photo_suspended(participant, now):
        return JSONResponse(PHOTO_UNAVAILABLE, status_code=403)

    def reject(reason: str) -> JSONResponse:
        return JSONResponse(REJECTED, status_code=422)

    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    reason, raw = None, None
    if content_type != "image/jpeg":
        reason = "content_type"
    else:
        raw = await _read_limited(request, pipeline.max_bytes)
        if raw is None:
            reason = "too_large"
    if reason is None:
        def process():
            jpeg = pipeline.prepare(raw)
            pipeline.screen(jpeg)
            return pipeline.recognize(jpeg)
        try:
            found = await run_in_threadpool(process)
        except PhotoRejected as e:
            reason = e.reason
        except Exception:                                   # fail-closed
            reason = "error"
        finally:
            raw = None                                      # καμία αναφορά στα bytes μετά την επεξεργασία
    if reason is not None:
        await run_in_threadpool(record_rejection, db, participant, reason, settings, now)
        return reject(reason)

    items = suggestions_from_photo(catalog, found, settings.PHOTO_CONFIDENT_MIN)
    audit.record(db, "photo_processed", participant.id, stored_bytes=0, n_suggestions=len(items),
                 versions=pipeline.versions)
    await run_in_threadpool(db.commit)
    return _suggestions(items)


@router.post("/text", response_model=SuggestionsOut, summary="Προτάσεις τροφίμων από ελεύθερο κείμενο (τίποτα δεν αποθηκεύεται)")
def text(body: TextRequest, request: Request, participant: CurrentParticipant, db: DbDep, catalog: CatalogDep):
    extractor = request.app.state.text_extractor
    items = suggestions_from_text(catalog, extractor, body.text)
    audit.record(db, "text_processed", participant.id, n_suggestions=len(items), extractor=extractor.version)
    db.commit()                                             # μόνο το γεγονός· ποτέ το κείμενο
    return _suggestions(items)


# Η ημερομηνία των παραδειγμάτων γίνεται «σήμερα» σε κάθε φόρτωση του Swagger (app/api/docs.py).
CONFIRM_EXAMPLES = {
    "lunch": {"summary": "Μεσημεριανό από πρόταση φωτογραφίας", "value": {
        "eaten_on": "TODAY", "meal_slot": "lunch", "source": "camera",
        "items": [{"food_id": "lentils", "portion": "medium", "ai_suggested": True},
                  {"food_id": "wholegrain_bread", "portion": "small", "ai_suggested": True},
                  {"food_id": "feta", "portion": "small", "ai_suggested": False}]}},
    "breakfast": {"summary": "Πρωινό με χειροκίνητη καταχώριση", "value": {
        "eaten_on": "TODAY", "meal_slot": "breakfast", "source": "manual",
        "items": [{"food_id": "milk", "portion": "medium", "ai_suggested": False},
                  {"food_id": "oats", "portion": "small", "ai_suggested": False},
                  {"food_id": "banana", "portion": "medium", "ai_suggested": False}]}},
}


@router.post("/confirm", response_model=MealOut, status_code=201,
             summary="Αποθήκευση γεύματος που επιβεβαίωσε το παιδί (τα γραμμάρια τα υπολογίζει ο server)")
def confirm(body: Annotated[ConfirmMeal, Body(openapi_examples=CONFIRM_EXAMPLES)], participant: CurrentParticipant,
            db: DbDep, catalog: CatalogDep,
            settings: SettingsDep, now: NowDep):
    try:
        meal = meal_service.confirm_meal(
            db, catalog, participant, eaten_on=body.eaten_on, meal_slot=body.meal_slot.value,
            source=body.source.value, items=[i.model_dump(mode="json") for i in body.items],
            settings=settings, now=now)
    except meal_service.MealError as e:
        raise _http(e) from None
    return meal_out(meal, catalog)


@router.get("", response_model=list[MealOut], summary="Τα γεύματά μου (προεπιλογή: σήμερα, έως 31 ημέρες)")
def list_meals(participant: CurrentParticipant, db: DbDep, catalog: CatalogDep, settings: SettingsDep, now: NowDep,
               from_: Optional[date] = Query(None, alias="from"), to: Optional[date] = Query(None)):
    today = local_today(settings.tz, now)
    try:
        meals = meal_service.list_meals(db, participant, from_ or to or today, to or from_ or today)
    except meal_service.MealError as e:
        raise _http(e) from None
    return [meal_out(m, catalog) for m in meals]


@router.delete("/{meal_id}", status_code=204, summary="Διαγραφή γεύματος (μόνο αν ALLOW_MEAL_DELETE=true)")
def delete(meal_id: uuid.UUID, participant: CurrentParticipant, db: DbDep, settings: SettingsDep, now: NowDep):
    try:
        meal_service.delete_meal(db, participant, meal_id, settings, now)
    except meal_service.MealError as e:
        raise _http(e) from None
    return Response(status_code=204)
