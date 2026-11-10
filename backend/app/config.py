"""
app/config.py — ρυθμίσεις της εφαρμογής (pydantic-settings: μεταβλητές περιβάλλοντος ή .env στη ρίζα του repo).

Τα ονόματα ακολουθούν το υπάρχον .env.example / docker-compose (docs/backend_spec_v1.md, Τροποποίηση 1).
Όλα τα όρια είναι ΠΡΟΣΧΕΔΙΟ (R7) μέχρι το πάγωμα της πιλοτικής μελέτης.

Μυστικά (JWT_SECRET, ACCESS_KEY_PEPPER, ADMIN_TOKEN) και DATABASE_URL (περιέχει κωδικό) είναι SecretStr και
τα σφάλματα επικύρωσης δεν τυπώνουν τιμές (hide_input_in_errors), ώστε μια αποτυχημένη εκκίνηση να μη
γράψει μυστικό στο log.

Σε ENVIRONMENT=production η εφαρμογή ΑΡΝΕΙΤΑΙ να ξεκινήσει αν: DEMO_MODE=true, κάποιο μυστικό έχει
λιγότερους από MIN_SECRET_LENGTH χαρακτήρες, ή το CORS_ORIGINS περιέχει "*". (Ο έλεγχος «demo τρόφιμα»
γίνεται στο create_app, όταν φορτώνεται ο πίνακας τροφίμων.)

DATA_DIR: τοπικά <repo>/data· στο container (κώδικας στο /app) είναι το /data, όπου το docker-compose κάνει mount
το ./data — το ίδιο σημείο που περιμένει και το ai_pipeline/presentation/lexicon.py. Σχετικά paths των CSV
λύνονται ως προς το DATA_DIR.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
MIN_SECRET_LENGTH = 32
SECRET_FIELDS = ("JWT_SECRET", "ACCESS_KEY_PEPPER", "ADMIN_TOKEN")
DEFAULT_AVATAR_IDS = ",".join(f"avatar_{i:02d}" for i in range(1, 13))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore",
                                      case_sensitive=True, hide_input_in_errors=True)

    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DATABASE_URL: SecretStr
    LOG_LEVEL: str = "INFO"

    # --- πρόσβαση ---
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: Literal["HS256"] = "HS256"          # μόνο HS256: κανένα άλλο αλγόριθμο δεν δέχεται το decode
    ACCESS_TOKEN_TTL_MINUTES: int = Field(720, ge=5, le=7 * 24 * 60)   # ΠΡΟΣΧΕΔΙΟ (ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: TTL token)
    ACCESS_KEY_PEPPER: SecretStr
    ADMIN_TOKEN: SecretStr
    # ΠΡΟΣΧΕΔΙΟ: αποτυχίες ανά IP σε LOGIN_WINDOW_MINUTES (in-memory, ένας worker). Χαλαρό σκόπιμα: πολλά παιδιά
    # μπορεί να μοιράζονται IP (ακαδημίες, σχολεία). Με κλειδιά 60 bit, 30 δοκιμές / 15 λεπτά (~10^6 τον χρόνο)
    # από μία IP βρίσκουν οποιοδήποτε από 200 κλειδιά κατά μέσο όρο σε ~3·10^9 χρόνια: η ασφάλεια δεν αλλάζει.
    LOGIN_MAX_FAILURES: int = Field(30, ge=1)
    LOGIN_WINDOW_MINUTES: int = Field(15, ge=1)       # ΠΡΟΣΧΕΔΙΟ
    # Ομάδα ελέγχου: σύμφωνα με το πρωτόκολλο δεν χρησιμοποιεί την εφαρμογή κατά τη μελέτη.
    CONTROL_ACCESS_FROM: Optional[date] = None        # ΠΡΟΣΧΕΔΙΟ: από αυτή την ημέρα (APP_TIMEZONE)· κενό = ποτέ

    # --- εφαρμογή ---
    DEMO_MODE: bool = True
    # Swagger UI (/docs) και /openapi.json. Κενό = ανοιχτά εκτός production. Σε production δεν επιτρέπονται.
    API_DOCS: Optional[bool] = None
    CORS_ORIGINS: str = ""                            # λίστα χωρισμένη με κόμμα
    APP_TIMEZONE: str = "Europe/Athens"               # ΠΡΟΣΧΕΔΙΟ: «σήμερα», ημέρες, νυχτερινή εργασία
    AVATAR_IDS: str = DEFAULT_AVATAR_IDS              # ΠΡΟΣΧΕΔΙΟ: κλειστή λίστα, ώστε το avatar_id να μη γίνει ελεύθερο κείμενο (R2)

    # --- τρόφιμα και γεύματα ---
    DATA_DIR: Path = ROOT / "data"
    FOODS_CSV: Path = Path("demo_foods.csv")          # ΜΟΝΟ demo μέχρι να υπάρξει πραγματικός πίνακας σύνθεσης
    FOOD_ALIASES_CSV: Path = Path("demo_food_aliases.csv")
    MEAL_BACKDATE_DAYS: int = Field(1, ge=0, le=7)    # ΠΡΟΣΧΕΔΙΟ: γεύμα από σήμερα έως τόσες ημέρες πριν
    ALLOW_MEAL_DELETE: bool = False                   # ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ M07: διαγραφή γεύματος από το παιδί

    # --- ανατροφοδότηση ---
    EVALUATION_WINDOW_DAYS: int = Field(7, ge=3, le=28)   # ΠΡΟΣΧΕΔΙΟ: συνήθης πρόσληψη στις τελευταίες τόσες ημέρες
    # Krikri (προαιρετικό): χωρίς LLM_BASE_URL ΚΑΙ LLM_MODEL ο presenter δίνει μόνο τα σταθερά κείμενα.
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    PRESENTER_TIMEOUT_SECONDS: float = Field(20.0, gt=0, le=120)   # ΠΡΟΣΧΕΔΙΟ: ανά μήνυμα, μετά σταθερό κείμενο

    # --- φωτογραφία (R4, Κανόνες 7-8) ---
    MAX_PHOTO_BYTES: int = Field(1_048_576, ge=1, le=1_048_576)   # ≤ client_max_body_size του Nginx (1m)
    PHOTO_MAX_EDGE_PX: int = Field(448, ge=64, le=448)            # αυστηρά στον server, ίδιο με τον browser (DPIA)
    PHOTO_REJECT_LIMIT: int = Field(5, ge=1)                       # ΠΡΟΣΧΕΔΙΟ: απορρίψεις ...
    PHOTO_REJECT_WINDOW_HOURS: int = Field(24, ge=1)               # ΠΡΟΣΧΕΔΙΟ: ... σε τόσες ώρες -> αναστολή
    PHOTO_SUSPENSION_HOURS: int = Field(24, ge=1)                  # ΠΡΟΣΧΕΔΙΟ: διάρκεια αναστολής φωτογραφίας
    PHOTO_CONFIDENT_MIN: float = Field(0.80, gt=0, le=1)           # ΠΡΟΣΧΕΔΙΟ: από εδώ «σίγουρο», αλλιώς «ίσως»

    @field_validator("LLM_BASE_URL", "LLM_MODEL", mode="before")
    @classmethod
    def _empty_str(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("CONTROL_ACCESS_FROM", "API_DOCS", mode="before")
    @classmethod
    def _empty_date(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("APP_TIMEZONE")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown time zone {v!r}") from e
        return v

    @property
    def docs_enabled(self) -> bool:
        return self.API_DOCS if self.API_DOCS is not None else self.ENVIRONMENT != "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def avatar_ids(self) -> frozenset[str]:
        return frozenset(a.strip() for a in self.AVATAR_IDS.split(",") if a.strip())

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.APP_TIMEZONE)

    def data_path(self, path: Path) -> Path:
        return path if path.is_absolute() else self.DATA_DIR / path

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self
        problems = []
        if self.DEMO_MODE:
            problems.append("DEMO_MODE must be false")
        problems += [f"{name} shorter than {MIN_SECRET_LENGTH} characters" for name in SECRET_FIELDS
                     if len(getattr(self, name).get_secret_value()) < MIN_SECRET_LENGTH]
        if "*" in self.cors_origins:
            problems.append('CORS_ORIGINS must not contain "*"')
        if self.API_DOCS:
            problems.append("API_DOCS must not be true (Swagger only outside production)")
        if problems:
            raise ValueError("refusing to start in production: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
