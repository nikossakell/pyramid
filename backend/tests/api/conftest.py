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
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _nutrient_names_with_digits() -> list[str]:
    import csv
    with (DATA / "nutrient_names_el.csv").open(encoding="utf-8", newline="") as f:
        return [r["name_el"] for r in csv.DictReader(f) if re.search(r"\d", r["name_el"])]


# Το όνομα θρεπτικού «βιταμίνη B12» δεν είναι αριθμητική τιμή· ο validator του 4.2 το εξαιρεί ρητά (V-NUM).
NAMES_WITH_DIGITS = _nutrient_names_with_digits()


def assert_no_numbers(obj: Any, path: str = "$") -> None:
    """R1: σε απάντηση προς το παιδί κανένας αριθμός (int/float) και κανένα ψηφίο σε κείμενο, εκτός από
    αναγνωριστικά (UUID), ημερομηνίες ISO και ονόματα θρεπτικών του λεξικού (μόνο «βιταμίνη B12»)."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        raise AssertionError(f"number at {path}: {obj!r}")
    if isinstance(obj, str):
        if _ISO_DATE.match(obj):
            return
        try:
            uuid.UUID(obj)
            return
        except ValueError:
            pass
        text = obj
        for name in NAMES_WITH_DIGITS:
            text = re.sub(re.escape(name), " ", text, flags=re.IGNORECASE)
        assert not re.search(r"\d", text), f"digit in text at {path}: {obj!r}"
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in {"grams", "research_values", "usual_intake", "nutrients"}, f"forbidden key {path}.{k}"
            assert_no_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_no_numbers(v, f"{path}[{i}]")


def make_settings(**overrides) -> Settings:
    values = {"ENVIRONMENT": "test", "DATABASE_URL": "sqlite://", **SECRETS, **overrides}
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
