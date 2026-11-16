"""
Επιλογή component ανά κομμάτι (2026-11-16): PHOTO_RECOGNIZER / PHOTO_CONTENT_FILTER, φραγμός development, DEMO_MODE ως
συντόμευση, 503 photo_unavailable / photo_busy χωρίς απόρριψη, audit pipeline demo | mixed | real, system-status.
"""
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ai_pipeline.vision.types import RecognizedFood, RecognizerBusy, RecognizerUnavailable
from app.db.models import AuditLog
from app.main import create_app
from app.services.photo_pipeline import PhotoPipeline, build_photo_pipeline
from tests.api.conftest import SECRETS, add_participant, build_app, login, make_settings
from tests.api.photos import jpeg

PHOTO = "/api/v1/meals/photo"
ADMIN = {"X-Admin-Token": SECRETS["ADMIN_TOKEN"]}


class RealRecognizer:                      # «πραγματικό» = χωρίς is_demo
    version = "real-test"

    def __init__(self, result=None):
        self.result = result

    def recognize(self, jpeg_bytes):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result or [RecognizedFood("lentil soup", "φακές", 1.0)]


def post(client, headers, body=jpeg()):
    return client.post(PHOTO, content=body, headers={**headers, "Content-Type": "image/jpeg"})


# ---------------------------------------------------------------- ρυθμίσεις

def test_defaults_are_none_and_demo_mode_fills_them():
    s = make_settings()
    assert (s.PHOTO_RECOGNIZER, s.PHOTO_CONTENT_FILTER) == ("none", "none")
    assert (s.photo_recognizer, s.photo_content_filter) == ("none", "none") and s.photo_demo_components == []
    s = make_settings(DEMO_MODE=True)
    assert (s.photo_recognizer, s.photo_content_filter) == ("demo", "demo")
    s = make_settings(DEMO_MODE=True, PHOTO_RECOGNIZER="olivegemma")          # ρητή τιμή υπερισχύει
    assert (s.photo_recognizer, s.photo_content_filter) == ("olivegemma", "demo")
    assert s.photo_demo_components == ["content_filter"]


@pytest.mark.parametrize("environment", ["test", "production"])
@pytest.mark.parametrize("overrides", [{"PHOTO_RECOGNIZER": "demo"}, {"PHOTO_CONTENT_FILTER": "demo"},
                                       {"PHOTO_RECOGNIZER": "demo", "PHOTO_CONTENT_FILTER": "demo"}])
def test_demo_component_refused_outside_development(environment, overrides):
    extra = {"CORS_ORIGINS": "https://pyramid.example.org", "JWT_SECRET": "j" * 40, "ACCESS_KEY_PEPPER": "p" * 40,
             "ADMIN_TOKEN": "a" * 40} if environment == "production" else {}
    with pytest.raises(ValidationError) as e:
        make_settings(ENVIRONMENT=environment, **extra, **overrides)
    assert "demo" in str(e.value) and "none" not in json.dumps(overrides).replace("none", "")


def test_demo_components_allowed_in_development():
    s = make_settings(ENVIRONMENT="development", PHOTO_RECOGNIZER="demo", PHOTO_CONTENT_FILTER="demo")
    assert s.DEMO_MODE is False and s.photo_demo_components == ["recognizer", "content_filter"]


def test_real_components_allowed_everywhere_and_olivegemma_needs_no_weights_to_configure(tmp_path):
    """Ο recognizer olivegemma ρυθμίζεται χωρίς βάρη (lazy)· χωρίς φάκελο η φωτογραφία είναι 503, όχι σφάλμα εκκίνησης."""
    s = make_settings(PHOTO_RECOGNIZER="olivegemma", PHOTO_CONTENT_FILTER="real", OLIVEGEMMA_DIR=tmp_path / "none")
    assert s.photo_demo_components == []
    app = create_app(s)
    pipeline = app.state.photo_pipeline
    assert pipeline.components == {"nsfw": "missing", "food_gate": "missing", "recognizer": "real"}
    assert pipeline.available is False and pipeline.versions["recognizer"] == "OliveGemma-3B@unknown"


def test_preload_failure_marks_recognizer_not_ready(tmp_path, caplog):
    empty_map = tmp_path / "map.csv"
    empty_map.write_text("olivegemma_label,food_id\n", encoding="utf-8")
    s = make_settings(ENVIRONMENT="development", PHOTO_RECOGNIZER="olivegemma", PHOTO_CONTENT_FILTER="demo",
                      OLIVEGEMMA_DIR=tmp_path / "none", OLIVEGEMMA_PRELOAD=True, OLIVEGEMMA_LABEL_MAP_CSV=empty_map)
    pipeline = build_photo_pipeline(s, {})
    assert pipeline.recognizer.ready is False and pipeline.available is False
    assert any(r.getMessage() == "olivegemma_load_failed" for r in caplog.records)


def test_label_map_with_unknown_food_stops_startup(tmp_path):
    bad = tmp_path / "map.csv"
    bad.write_text("olivegemma_label,food_id\nsoup,not_a_food\n", encoding="utf-8")
    s = make_settings(PHOTO_RECOGNIZER="olivegemma", OLIVEGEMMA_DIR=tmp_path, OLIVEGEMMA_LABEL_MAP_CSV=bad)
    with pytest.raises(ValueError, match="unknown food_id"):
        create_app(s)


# ---------------------------------------------------------------- pipeline kinds

def test_pipeline_kind_and_components():
    from app.services.photo_pipeline import DemoBrightnessFilter, DemoNsfwFilter, DemoRecognizer
    demo = PhotoPipeline(DemoNsfwFilter(), DemoBrightnessFilter(), DemoRecognizer(), 1, 448)
    assert demo.kind == "demo" and demo.has_demo and demo.components["recognizer"] == "demo"
    mixed = PhotoPipeline(DemoNsfwFilter(), DemoBrightnessFilter(), RealRecognizer(), 1, 448)
    assert mixed.kind == "mixed" and mixed.has_demo and mixed.components["recognizer"] == "real"
    real = PhotoPipeline(RealRecognizer(), RealRecognizer(), RealRecognizer(), 1, 448)
    assert real.kind == "real" and not real.has_demo
    missing = PhotoPipeline(None, None, RealRecognizer(), 1, 448)
    assert missing.available is False and missing.components["nsfw"] == "missing"


# ---------------------------------------------------------------- API

def _mixed_app(recognizer):
    app = build_app(ENVIRONMENT="development", PHOTO_CONTENT_FILTER="demo")
    from dataclasses import replace
    app.state.photo_pipeline = replace(app.state.photo_pipeline, recognizer=recognizer)
    return app


def test_mixed_pipeline_audits_mixed_and_status_shows_components():
    app = _mixed_app(RealRecognizer())
    with TestClient(app) as client:
        headers = login(client, add_participant(app)[1])
        assert client.get("/api/v1/me", headers=headers).json()["photo_status"] == "available"
        r = post(client, headers)
        assert r.status_code == 200 and r.json()["suggestions"][0]["food_id"] == "lentils"
        status = client.get("/api/v1/admin/system-status", headers=ADMIN).json()
    assert status["demo_mode"] is False
    assert status["photo_components"] == {"nsfw": "demo", "food_gate": "demo", "recognizer": "real"}
    assert status["services"]["photo_pipeline"] == "demo"                         # demo αν οποιοδήποτε component είναι demo
    assert status["versions"]["models"]["recognizer"] == "real-test"
    with app.state.sessionmaker() as s:
        a = s.query(AuditLog).filter_by(event="photo_processed").one()
        assert a.payload["pipeline"] == "mixed" and a.payload["model_id"] == "real-test"


@pytest.mark.parametrize("error, body", [(RecognizerUnavailable("load_failed"), {"photo_unavailable": True}),
                                         (RecognizerBusy(), {"photo_busy": True})])
def test_unavailable_and_busy_are_503_not_rejections(error, body):
    app = _mixed_app(RealRecognizer(error))
    with TestClient(app) as client:
        headers = login(client, add_participant(app)[1])
        r = post(client, headers)
        assert r.status_code == 503 and r.json() == body
    with app.state.sessionmaker() as s:
        assert s.query(AuditLog).filter(AuditLog.event.like("photo_%")).count() == 0   # δεν μετρά στην αναστολή


def test_recognizer_timeout_is_a_rejection_with_reason_in_audit_only():
    app = _mixed_app(RealRecognizer(TimeoutError("olivegemma_timeout")))
    with TestClient(app) as client:
        headers = login(client, add_participant(app)[1])
        r = post(client, headers)
        assert r.status_code == 422 and r.json() == {"rejected": True}
    with app.state.sessionmaker() as s:
        assert s.query(AuditLog).filter_by(event="photo_rejected").one().payload["reason"] == "recognizer_timeout"


def test_components_in_response_only_when_recognizer_gives_them():
    found = [RecognizedFood("lentil soup", "φακές", 1.0, (), ("lentils", "onion", "3 carrots"))]
    app = _mixed_app(RealRecognizer(found))
    with TestClient(app) as client:
        headers = login(client, add_participant(app)[1])
        body = post(client, headers).json()
    assert body["suggestions"][0]["components"] == ["lentils", "onion"]          # το «3 carrots» δεν περνά (R1)
    app = _mixed_app(RealRecognizer())
    with TestClient(app) as client:
        headers = login(client, add_participant(app)[1])
        assert post(client, headers).json()["suggestions"][0]["components"] is None
