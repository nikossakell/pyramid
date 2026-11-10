"""GET /cards, POST /cards/{id}/open — μόνο οι κάρτες του ίδιου παιδιού· ξένη ή άγνωστη κάρτα: 404."""
import uuid

from fastapi import APIRouter, HTTPException

from app.db.models import CardDrop
from app.dependencies import CurrentParticipant, DbDep, NowDep
from app.schemas.cards import CardOut
from app.services import card_service

router = APIRouter(prefix="/cards", tags=["cards"])


def card_out(c: CardDrop) -> CardOut:
    return CardOut(id=c.id, tier=c.tier, day=c.day, opened=c.opened_at is not None)


@router.get("", response_model=list[CardOut], summary="Οι κάρτες μου")
def list_cards(participant: CurrentParticipant, db: DbDep):
    return [card_out(c) for c in card_service.list_cards(db, participant)]


@router.post("/{card_id}/open", response_model=CardOut, summary="Άνοιγμα κάρτας")
def open_card(card_id: uuid.UUID, participant: CurrentParticipant, db: DbDep, now: NowDep):
    card = card_service.open_card(db, participant, card_id, now)
    if card is None:
        raise HTTPException(404, "not_found")
    return card_out(card)
