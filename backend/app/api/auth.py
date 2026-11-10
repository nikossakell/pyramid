"""POST /auth/login — κλειδί πρόσβασης -> JWT. Δεν υπάρχει εγγραφή μέσω API (μόνο scripts/create_participant.py)."""
from fastapi import APIRouter, HTTPException, Request

from app.dependencies import DbDep, NowDep, SettingsDep
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Κλειδί πρόσβασης -> JWT",
             responses={401: {"description": "Ίδια απάντηση για κάθε αποτυχία",
                              "content": {"application/json": {"example": {"detail": "invalid_credentials"}}}},
                        403: {"description": "Ομάδα ελέγχου πριν το CONTROL_ACCESS_FROM",
                              "content": {"application/json": {"example": {"detail": "not_yet_available"}}}},
                        429: {"description": "Πολλές αποτυχίες από την ίδια IP",
                              "content": {"application/json": {"example": {"detail": "too_many_attempts"}}}}})
def login(body: LoginRequest, request: Request, db: DbDep, settings: SettingsDep, now: NowDep):
    client_ip = request.client.host if request.client else "unknown"
    try:
        result = auth_service.login(db, settings, request.app.state.login_limiter, client_ip, body.access_key, now)
    except auth_service.LoginError as e:
        raise HTTPException(e.status_code, e.detail) from None
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)
