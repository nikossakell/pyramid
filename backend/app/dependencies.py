"""
app/dependencies.py — κοινές εξαρτήσεις των endpoints: ρυθμίσεις, session, ρολόι, τρέχων συμμετέχων.

Ο τρέχων συμμετέχων ελέγχεται σε ΚΑΘΕ αίτημα: έγκυρο token, ενεργός, ίδιο token_version (ανάκληση
συγκατάθεσης -> 401), και πρόσβαση ομάδας ελέγχου (-> 403). Το pseudonym_id μπαίνει στο request.state για το log.
"""
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.security import InvalidToken, decode_access_token
from app.db.models import Participant
from app.services.auth_service import may_use_app
from app.services.food_catalog import FoodCatalog

_bearer = HTTPBearer(auto_error=False, scheme_name="ChildJWT",
                     description="Το access_token από το POST /api/v1/auth/login (κλειδί πρόσβασης του παιδιού).")
UNAUTHORIZED = HTTPException(401, "not_authenticated", headers={"WWW-Authenticate": "Bearer"})


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_now(request: Request) -> datetime:
    return request.app.state.clock()


def get_catalog(request: Request) -> FoodCatalog:
    return request.app.state.catalog


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]
NowDep = Annotated[datetime, Depends(get_now)]
CatalogDep = Annotated[FoodCatalog, Depends(get_catalog)]


def get_current_participant(request: Request, db: DbDep, settings: SettingsDep, now: NowDep,
                            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> Participant:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UNAUTHORIZED
    try:
        participant_id, tv = decode_access_token(credentials.credentials, settings.JWT_SECRET.get_secret_value())
    except InvalidToken:
        raise UNAUTHORIZED from None
    participant = db.get(Participant, participant_id)
    if participant is None or not participant.active or participant.token_version != tv:
        raise UNAUTHORIZED
    request.state.pseudonym_id = str(participant.id)
    if not may_use_app(participant, settings, now):
        raise HTTPException(403, "not_yet_available")
    return participant


CurrentParticipant = Annotated[Participant, Depends(get_current_participant)]
