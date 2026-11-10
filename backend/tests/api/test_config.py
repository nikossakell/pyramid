"""Ρυθμίσεις: σε ENVIRONMENT=production η εφαρμογή αρνείται να ξεκινήσει με επικίνδυνες ρυθμίσεις."""
import pytest
from pydantic import ValidationError

from app.main import StartupError, create_app

from .conftest import DATA, SECRETS, make_settings

PROD = {"ENVIRONMENT": "production", "CORS_ORIGINS": "https://pyramid.example.org"}


@pytest.fixture
def real_foods(tmp_path):
    """Μικρός πίνακας χωρίς demo γραμμές (σαν πραγματικός), για να ξεκινήσει η εφαρμογή σε production."""
    src = (DATA / "demo_foods.csv").read_text(encoding="utf-8").splitlines()
    rows = [src[0]] + [l.replace("DEMO — ΟΧΙ πραγματικές τιμές", "TEST table v1").replace(",true", ",false")
                       for l in src[1:3]]
    (tmp_path / "foods.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (tmp_path / "aliases.csv").write_text("food_id,alias\n", encoding="utf-8")
    return {"FOODS_CSV": tmp_path / "foods.csv", "FOOD_ALIASES_CSV": tmp_path / "aliases.csv"}


def test_valid_production_settings_start(real_foods):
    app = create_app(make_settings(**PROD, **real_foods))
    assert app.state.settings.ENVIRONMENT == "production"
    assert app.openapi_url is None and app.docs_url is None          # χωρίς /docs εκτός development


@pytest.mark.parametrize("overrides, problem", [
    ({"DEMO_MODE": True}, "DEMO_MODE must be false"),
    ({"JWT_SECRET": "Qz7-weak-jwt"}, "JWT_SECRET shorter than 32"),
    ({"ACCESS_KEY_PEPPER": "Pq9-weak-pepper"}, "ACCESS_KEY_PEPPER shorter than 32"),
    ({"ADMIN_TOKEN": "Ad3" + "x" * 28}, "ADMIN_TOKEN shorter than 32"),
    ({"CORS_ORIGINS": "https://a.example.org, *"}, 'CORS_ORIGINS must not contain "*"'),
])
def test_production_refuses_to_start(overrides, problem):
    with pytest.raises(ValidationError) as e:
        create_app(make_settings(**{**PROD, **overrides}))
    assert problem in str(e.value)
    for value in [*SECRETS.values(), *overrides.values()]:      # κανένα μυστικό στο μήνυμα σφάλματος
        if isinstance(value, str) and len(value) >= 5 and value != "https://a.example.org, *":
            assert value not in str(e.value)


def test_production_refuses_demo_foods():
    with pytest.raises(StartupError, match="demo rows"):
        create_app(make_settings(**PROD))                       # προεπιλογή: data/demo_foods.csv


def test_development_allows_demo_and_short_secrets():
    s = make_settings(ENVIRONMENT="development", DEMO_MODE=True, JWT_SECRET="dev")
    assert s.DEMO_MODE


def test_empty_control_access_from_means_never_and_bad_timezone_rejected():
    assert make_settings(CONTROL_ACCESS_FROM="").CONTROL_ACCESS_FROM is None
    with pytest.raises(ValidationError, match="unknown time zone"):
        make_settings(APP_TIMEZONE="Mars/Olympus")


def test_secrets_hidden_in_repr():
    s = make_settings()
    assert SECRETS["JWT_SECRET"] not in repr(s) and "sqlite://" not in repr(s)
