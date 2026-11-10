"""/meals/photo (R4, 7.1 του πλάνου) και /meals/text: προτάσεις χωρίς αποθήκευση (R3), ίδια απόρριψη για κάθε λόγο,
αναστολή μετά από 5 απορρίψεις, 503 χωρίς φίλτρα, κανένα byte εικόνας σε audit ή log."""
import json
import logging
from datetime import timedelta

import pytest

from app.core.clock import utcnow
from app.db.models import AuditLog, Meal, MealItem, Participant
from app.services.photo_pipeline import (DemoBrightnessFilter, DemoNsfwFilter, DemoRecognizer, PhotoPipeline)

from .conftest import add_participant, assert_no_numbers, login
from .photos import bomb_jpeg, dark_jpeg, jpeg, png

PHOTO, TEXT = "/api/v1/meals/photo", "/api/v1/meals/text"
JPEG_HEADERS = {"Content-Type": "image/jpeg"}


@pytest.fixture
def settings_overrides():
    return {"DEMO_MODE": True}


def post_photo(client, headers, body, content_type="image/jpeg"):
    return client.post(PHOTO, content=body, headers={**headers, "Content-Type": content_type})


def test_valid_photo_gives_suggestions_and_stores_nothing(client, child, db):
    p, _, headers = child
    r = post_photo(client, headers, jpeg())
    assert r.status_code == 200
    body = r.json()
    assert body["needs_confirmation"] is True
    assert [(s["food_id"], s["confidence_word"]) for s in body["suggestions"]] == [
        ("lentils", "σίγουρο"), ("wholegrain_bread", "ίσως"), (None, "ίσως")]
    assert body["suggestions"][2]["name_el"] == "χωριάτικη σαλάτα" and body["suggestions"][0]["label_en"] == "lentil soup"
    assert_no_numbers(body)                                                      # R1: ούτε confidence
    assert db.query(Meal).count() == 0 and db.query(MealItem).count() == 0       # R3
    a = db.query(AuditLog).filter_by(event="photo_processed").one()
    assert a.payload["stored_bytes"] == 0 and a.payload["n_suggestions"] == 3


def _rejection_cases():
    big = b"\xff\xd8\xff" + b"0" * 1_048_576
    return {
        "content_type_png_header": (jpeg(), "image/png"),
        "no_content_type": (jpeg(), ""),
        "multipart": (jpeg(), "multipart/form-data; boundary=x"),
        "fake_signature": (b"\xff\xd8\xff" + b"not really a jpeg" * 20, "image/jpeg"),
        "png_body": (png(), "image/jpeg"),
        "too_large": (big, "image/jpeg"),
        "too_wide": (jpeg(449, 200), "image/jpeg"),
        "too_tall": (jpeg(200, 600), "image/jpeg"),
        "bomb": (bomb_jpeg(), "image/jpeg"),
        "dark_non_food": (dark_jpeg(), "image/jpeg"),
        "empty": (b"", "image/jpeg"),
    }


def test_every_rejection_has_identical_status_and_body(app, client):
    responses, reasons = [], []
    for name, (body, ctype) in _rejection_cases().items():
        _, key = add_participant(app)                       # νέος κωδικός κάθε φορά: όχι αναστολή
        headers = login(client, key)
        r = post_photo(client, headers, body, ctype)
        responses.append((name, r.status_code, r.content))
    assert {(s, c) for _, s, c in responses} == {(422, b'{"rejected":true}')}, responses
    with app.state.sessionmaker() as s:
        reasons = [a.payload["reason"] for a in s.query(AuditLog).filter_by(event="photo_rejected").order_by(AuditLog.id)]
        assert s.query(Meal).count() == 0
    assert reasons == ["content_type", "content_type", "content_type", "decode", "signature", "too_large",
                       "dimensions", "dimensions", "decode", "food_gate", "signature"]
    # bomb: το Pillow σηκώνει DecompressionBombError ήδη στο open() (κεφαλίδα 60000 x 60000): απόρριψη χωρίς αποσυμπίεση


def test_streamed_body_over_the_limit_is_rejected(client, child):
    _, _, headers = child
    def chunks():                                           # χωρίς Content-Length (chunked)
        yield b"\xff\xd8\xff"
        for _ in range(20):
            yield b"x" * 65536
    r = client.post(PHOTO, content=chunks(), headers={**headers, **JPEG_HEADERS})
    assert r.status_code == 422 and r.json() == {"rejected": True}


def test_pillow_pixel_limit_is_set(app):
    from PIL import Image
    assert Image.MAX_IMAGE_PIXELS == 448 * 448


class Boom:
    name, version = "boom", "test"

    def allows(self, jpeg_bytes):
        raise RuntimeError("model crashed")


class Deny:
    name, version = "deny", "test"

    def allows(self, jpeg_bytes):
        return False


@pytest.mark.parametrize("pipeline_args, reason", [
    ((Boom(), DemoBrightnessFilter(), DemoRecognizer()), "nsfw_error"),
    ((DemoNsfwFilter(), Boom(), DemoRecognizer()), "food_gate_error"),
    ((Deny(), DemoBrightnessFilter(), DemoRecognizer()), "nsfw"),
])
def test_filter_exception_or_denial_rejects(app, client, child, pipeline_args, reason):
    _, _, headers = child
    app.state.photo_pipeline = PhotoPipeline(*pipeline_args, max_bytes=1_048_576, max_edge_px=448)
    r = post_photo(client, headers, jpeg())
    assert r.status_code == 422 and r.json() == {"rejected": True}
    with app.state.sessionmaker() as s:
        assert s.query(AuditLog).filter_by(event="photo_rejected").one().payload["reason"] == reason


def test_suspension_after_five_rejections(app, client, child, db):
    p, _, headers = child
    for _ in range(5):
        assert post_photo(client, headers, dark_jpeg()).status_code == 422
    r = post_photo(client, headers, jpeg())                                  # ακόμα και έγκυρη: δεν επεξεργάζεται
    assert r.status_code == 403 and r.json() == {"photo_unavailable": True}
    assert client.get("/api/v1/me", headers=headers).json()["photo_available"] is False
    assert client.post(TEXT, json={"text": "φακές"}, headers=headers).status_code == 200   # κείμενο: κανονικά
    assert client.get("/api/v1/foods/search", params={"q": "φακ"}, headers=headers).status_code == 200
    events = [a.event for a in db.query(AuditLog).filter(AuditLog.event.like("photo_%")).order_by(AuditLog.id)]
    assert events == ["photo_rejected"] * 5 + ["photo_suspended"]
    suspended = db.query(AuditLog).filter_by(event="photo_suspended").one().payload
    assert suspended["n_rejections"] == 5

    # Η αναστολή έληξε (στην πράξη 24 ώρες μετά την 5η απόρριψη, άρα μετά από όλες τις παλιές απορρίψεις).
    db.get(Participant, p.id).photo_suspended_until = utcnow()
    db.commit()
    assert post_photo(client, headers, jpeg()).status_code == 200
    assert post_photo(client, headers, dark_jpeg()).status_code == 422       # οι παλιές απορρίψεις δεν ξαναμετρούν
    assert post_photo(client, headers, jpeg()).status_code == 200


@pytest.mark.parametrize("settings_overrides", [{"DEMO_MODE": False}])
def test_no_filters_without_demo_mode_means_503(client, child, db):
    _, _, headers = child
    r = post_photo(client, headers, jpeg())
    assert r.status_code == 503 and r.json() == {"photo_unavailable": True}
    assert client.get("/api/v1/me", headers=headers).json()["photo_available"] is False
    assert db.query(AuditLog).filter(AuditLog.event.like("photo_%")).count() == 0   # δεν μετρά ως απόρριψη
    assert client.post(TEXT, json={"text": "φακές"}, headers=headers).status_code == 200


def test_photo_requires_token(client):
    assert client.post(PHOTO, content=jpeg(), headers=JPEG_HEADERS).status_code == 401


def test_no_image_bytes_in_audit_or_log(app, client, child, db, caplog):
    caplog.set_level(logging.DEBUG)
    _, _, headers = child
    good, dark = jpeg(), dark_jpeg()
    post_photo(client, headers, good)
    post_photo(client, headers, dark)
    dump = json.dumps([[a.event, a.payload] for a in db.query(AuditLog).all()]) + caplog.text
    for body in (good, dark):
        for fragment in (body[:16].hex(), body[100:132].hex(), body[100:132].decode("latin-1")):
            assert fragment not in dump
    assert "ffd8ff" not in dump.lower() and "\\xff\\xd8" not in dump
    assert all(a.payload["stored_bytes"] == 0 for a in db.query(AuditLog).filter(AuditLog.event.like("photo_%"))
               if a.event != "photo_suspended")


# ---------- /meals/text ----------

@pytest.mark.parametrize("text, expected", [
    ("φακές με ψωμί και ένα μήλο", [("lentils", "σίγουρο"), ("wholegrain_bread", "σίγουρο"), ("apple", "σίγουρο")]),
    ("μακαρόνια με κιμά, σαλάτα", [("spaghetti_meat_sauce", "σίγουρο"), (None, "ίσως")]),
    ("ΓΙΑΟΥΡΤΙ και σπανακκι", [("yogurt", "σίγουρο"), ("spinach", "ίσως")]),
    ("φακές και φακές", [("lentils", "σίγουρο")]),
])
def test_text_suggestions(client, child, db, text, expected):
    _, _, headers = child
    r = client.post(TEXT, json={"text": text}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert [(s["food_id"], s["confidence_word"]) for s in body["suggestions"]] == expected
    assert body["needs_confirmation"] is True
    assert_no_numbers(body)
    assert db.query(Meal).count() == 0                                        # R3
    audit_row = db.query(AuditLog).filter_by(event="text_processed").one()
    assert text not in json.dumps(audit_row.payload, ensure_ascii=False)       # ποτέ το κείμενο


@pytest.mark.parametrize("body", [{"text": "x" * 301}, {"text": ""}, {"text": "φακές", "extra": 1}, {}])
def test_text_validation(client, child, body):
    _, _, headers = child
    assert client.post(TEXT, json=body, headers=headers).status_code == 422


def test_text_requires_token(client):
    assert client.post(TEXT, json={"text": "φακές"}).status_code == 401
