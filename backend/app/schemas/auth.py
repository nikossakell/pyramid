"""app/schemas/auth.py — login."""
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"access_key": "XXXX-XXXX-XXXX"}]})
    # Ελεύθερο κείμενο έως 64 χαρακτήρες: η μορφή ελέγχεται στο service, ώστε κάθε λάθος να παίρνει την ίδια γενική απάντηση (401).
    access_key: str = Field(max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
