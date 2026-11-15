"""Κοινά fixtures των tests του API: εφαρμογή με SQLite in-memory, συμμετέχοντες, login, έλεγχος R1."""
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.security import generate_access_key, key_hmac, normalize_access_key
from app.db.base import Base
from app.db.models import Participant
from app.main import create_app

SECRETS = {"JWT_SECRET": "j" * 40, "ACCESS_KEY_PEPPER": "p" * 40, "ADMIN_TOKEN": "a" * 40}
DATA = Path(__file__).resolve().parents[3] / "data"
# Ολόκληρη η τιμή πρέπει να είναι ISO 8601 (fullmatch), και μόνο σε πεδία ημερομηνίας με γνωστό όνομα.
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")   # π.χ. created_at
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
DATE_FIELDS = frozenset({"created_at", "updated_at", "eaten_on", "day", "at", "enrolled_on", "opened_at",
                         "completed_at"})
# Κείμενο που διαβάζει το παιδί: καμία εξαίρεση για ημερομηνία, ώρα ή αναγνωριστικό.
TEXT_FIELDS = frozenset({"text", "name_el", "label_el", "message", "title", "detail"})


def _nutrient_names_with_digits() -> list[str]:
    import csv
    with (DATA / "nutrient_names_el.csv").open(encoding="utf-8", newline="") as f:
        return [r["name_el"] for r in csv.DictReader(f) if re.search(r"\d", r["name_el"])]


# Το όνομα θρεπτικού «βιταμίνη B12» δεν είναι αριθμητική τιμή· ο validator του 4.2 το εξαιρεί ρητά (V-NUM).
NAMES_WITH_DIGITS = _nutrient_names_with_digits()


def assert_no_numbers(obj: Any, path: str = "$", *, allow_int_keys: frozenset = frozenset(),
                      _key: Optional[str] = None) -> None:
    """R1: σε απάντηση προς το παιδί κανένας αριθμός (int/float) και κανένα ψηφίο σε κείμενο. Εξαιρέσεις, μόνο αυτές:
      - ημερομηνία / χρονοσφραγίδα: ΜΟΝΟ σε πεδίο του DATE_FIELDS και ΜΟΝΟ αν ολόκληρη η τιμή είναι ISO 8601·
      - αναγνωριστικό: ολόκληρη η τιμή κανονικό UUID, σε πεδίο που ΔΕΝ είναι κείμενο προς το παιδί (TEXT_FIELDS)·
      - όνομα θρεπτικού του λεξικού με ψηφίο (μόνο «βιταμίνη B12», Απόφαση 23 του 2026-11-10)·
      - allow_int_keys: ακέραιος σε ρητά ονομασμένο πεδίο, ΜΟΝΟ όπου το ζητά ο καλών (σήμερα: `sort` του
        /food-groups, σειρά εμφάνισης — Απόφαση 28 του 2026-11-12). Ποτέ γενική εξαίρεση.
    Ψηφία μέσα σε κείμενο (text, name_el, label_el, μηνύματα) πιάνονται πάντα, ακόμα κι αν μοιάζουν με ημερομηνία."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if isinstance(obj, int) and _key is not None and _key in allow_int_keys:
            return
        raise AssertionError(f"number at {path}: {obj!r}")
    if isinstance(obj, str):
        if _key in DATE_FIELDS and (_ISO_DATE.fullmatch(obj) or _ISO_DATETIME.fullmatch(obj)):
            return
        if _key not in TEXT_FIELDS and _UUID.fullmatch(obj):
            return
        text = obj
        for name in NAMES_WITH_DIGITS:
            text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
        assert not re.search(r"\d", text), f"digit in text at {path}: {obj!r}"
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in {"grams", "research_values", "usual_intake", "nutrients"}, f"forbidden key {path}.{k}"
            assert_no_numbers(v, f"{path}.{k}", allow_int_keys=allow_int_keys, _key=k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):                      # λίστα: ισχύει το όνομα του πεδίου που την περιέχει
            assert_no_numbers(v, f"{path}[{i}]", allow_int_keys=allow_int_keys, _key=_key)


def make_settings(**overrides) -> Settings:
    """ENVIRONMENT=test, εκτός αν το test ζητά DEMO_MODE=True: το DEMO_MODE επιτρέπεται μόνο με ρητό
    ENVIRONMENT=development (Απόφαση 25 του 2026-11-12), άρα τα demo tests τρέχουν ως development."""
    environment = "development" if overrides.get("DEMO_MODE") is True else "test"
    values = {"ENVIRONMENT": environment, "DATABASE_URL": "sqlite://", **SECRETS, **overrides}
    return Settings(_env_file=None, **values)


def build_app(**overrides):
    app = create_app(make_settings(**overrides))
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def settings_overrides() -> dict:
    """Τα tests που θέλουν άλλες ρυθμίσεις το ξαναορίζουν (π.χ. DEMO_MODE=True)."""
    return {}


@pytest.fixture
def app(settings_overrides):
    application = build_app(**settings_overrides)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    with app.state.sessionmaker() as session:
        yield session


def add_participant(app, arm: str = "intervention", sex: str = "F", age: int = 12, active: bool = True,
                    enrollment_date: Optional[date] = None) -> tuple[Participant, str]:
    key = generate_access_key()
    pepper = app.state.settings.ACCESS_KEY_PEPPER.get_secret_value()
    with app.state.sessionmaker() as s:
        p = Participant(key_hmac=key_hmac(normalize_access_key(key), pepper), sex=sex, age_years_at_enrollment=age,
                        arm=arm, active=active, enrollment_date=enrollment_date or date(2026, 11, 2))
        s.add(p)
        s.commit()
        return p, key


def login(client, key: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"access_key": key})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def child(app, client):
    """Ενεργός συμμετέχων της ομάδας παρέμβασης, με headers για αιτήματα."""
    p, key = add_participant(app)
    return p, key, login(client, key)
