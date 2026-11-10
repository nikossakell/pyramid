"""scripts/seed_demo.py: τα δεδομένα επίδειξης δουλεύουν από άκρη σε άκρη (login, feedback, κάρτες, ασφάλεια, ομάδα
ελέγχου, φωτογραφίες)· αρνείται χωρίς DEMO_MODE ή σε production."""
import importlib.util
import re
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import assert_no_numbers, make_settings
from .test_cli_alembic import alembic_config

ROOT = Path(__file__).resolve().parents[3]


def _seed():
    spec = importlib.util.spec_from_file_location("seed_demo", ROOT / "scripts" / "seed_demo.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_demo_end_to_end(tmp_path, capsys):
    db_file = tmp_path / "demo.db"
    command.upgrade(alembic_config(f"sqlite:///{db_file}"), "head")
    settings = make_settings(DATABASE_URL=f"sqlite:///{db_file}", DEMO_MODE=True)
    assert _seed().main(["--photos", str(tmp_path / "photos")], settings=settings) == 0
    out = capsys.readouterr().out
    keys = dict(re.findall(r"^\s+(Α|Β|Γ|Δ) \(.*?\)\s+([0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4})", out, re.M))
    assert set(keys) == {"Α", "Β", "Γ", "Δ"}
    photos = tmp_path / "photos"

    app = create_app(settings)
    with TestClient(app) as client:
        def login(key):
            r = client.post("/api/v1/auth/login", json={"access_key": key})
            return r.status_code, {"Authorization": f"Bearer {r.json().get('access_token', '')}"}

        status, a = login(keys["Α"])
        assert status == 200
        feedback = client.get("/api/v1/feedback/today", headers=a).json()
        assert feedback["messages"]
        assert_no_numbers(feedback)
        cards = client.get("/api/v1/cards", headers=a).json()
        assert cards and {"rare"} <= {c["tier"] for c in cards}               # streak 3 ημερών

        _, d = login(keys["Δ"])
        assert client.get("/api/v1/feedback/today", headers=d).json()["messages"] == []   # ανοιχτό safety alert

        assert login(keys["Γ"])[0] == 403                                    # ομάδα ελέγχου

        _, b = login(keys["Β"])
        jpeg = {**b, "Content-Type": "image/jpeg"}
        assert client.post("/api/v1/meals/photo", content=(photos / "meal.jpg").read_bytes(), headers=jpeg).status_code == 200
        for bad in ("dark.jpg", "too_big.jpg", "not_jpeg.png"):
            r = client.post("/api/v1/meals/photo", content=(photos / bad).read_bytes(), headers=jpeg)
            assert r.status_code == 422 and r.json() == {"rejected": True}, bad
    app.state.engine.dispose()


@pytest.mark.parametrize("overrides", [{"DEMO_MODE": False}])
def test_seed_refuses_without_demo_mode(tmp_path, overrides, capsys):
    settings = make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'x.db'}", **overrides)
    assert _seed().main([], settings=settings) == 2
    assert "DEMO_MODE" in capsys.readouterr().err


def test_seed_refuses_without_tables(tmp_path, capsys):
    settings = make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'empty.db'}", DEMO_MODE=True)
    assert _seed().main([], settings=settings) == 2
    assert "alembic upgrade head" in capsys.readouterr().err
