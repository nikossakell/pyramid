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
    assert all(set(s) == {"food_id", "name_el", "confidence_word", "alternatives", "portion", "components"}
               for s in body["suggestions"])
    assert all(s["portion"] is None and s["components"] is None for s in body["suggestions"])   # πεδία για το μέλλον
    assert body["suggestions"][2]["name_el"] == "χωριάτικη σαλάτα"
    assert [[a["food_id"] for a in s["alternatives"]] for s in body["suggestions"]] == [
        ["bean_soup", "chickpeas"], ["oats"], ["tomato", "feta"]]              # M06 «Μήπως είναι…», S08β «διάλεξε»
    assert body["suggestions"][0]["alternatives"][0] == {"food_id": "bean_soup", "name_el": "Φασολάδα"}   # χωρίς σκορ
    assert_no_numbers(body)                                                      # R1: ούτε confidence
    assert db.query(Meal).count() == 0 and db.query(MealItem).count() == 0       # R3
    a = db.query(AuditLog).filter_by(event="photo_processed").one()
    assert a.payload["stored_bytes"] == 0 and len(a.payload["shown"]) == 3      # n_suggestions -> shown (Απόφαση 34)
    # Έξοδος του μοντέλου για την αξιολόγησή του, ΧΩΡΙΣ κωδικό παιδιού (Απόφαση 34): νέο analysis_id στην απάντηση.
    assert a.participant_id is None
    assert set(a.payload) == {"stored_bytes", "analysis_id", "model_id", "model_labels", "resolved_food_ids",
                              "pipeline", "shown"}
    assert a.payload["analysis_id"] == body["analysis_id"] and str(p.id) not in json.dumps(a.payload)
    assert a.payload["model_labels"] == ["lentil soup", "bread", "greek salad"]
    assert a.payload["resolved_food_ids"] == ["lentils", "wholegrain_bread", None]
    assert a.payload["model_id"] == "demo-1" and a.payload["pipeline"] == "demo"
    assert a.payload["shown"] == [
        {"food_id": "lentils", "portion": None, "alternatives": ["bean_soup", "chickpeas"]},
        {"food_id": "wholegrain_bread", "portion": None, "alternatives": ["oats"]},
        {"food_id": None, "portion": None, "alternatives": ["tomato", "feta"]}]      # χωρίς όνομα («χωριάτικη σαλάτα»)
    dumped = json.dumps(a.payload, ensure_ascii=False).lower()
    assert "χωριάτικη" not in dumped
    assert_no_numbers({k: v for k, v in a.payload.items() if k not in ("stored_bytes", "model_id")})   # ούτε σκορ, διαστάσεις
    for forbidden in ("0.92", "0.61", "confidence", "width", "height", "exif", "sha", "hash", "jfif", "/9j/"):
        assert forbidden not in dumped                                           # ούτε base64 JPEG, ούτε hash εικόνας


def test_photo_audit_caps_model_labels_and_never_holds_image_data(app, client, child, db):
    from app.core import audit
    from app.services.photo_pipeline import RecognizedFood

    class Many:
        version = "test-many"

        def recognize(self, jpeg):
            return [RecognizedFood(f"label {'x' * 100} {chr(97 + i)}", "φακές", 0.9 - i / 100) for i in range(14)]

    from dataclasses import replace
    app.state.photo_pipeline = replace(app.state.photo_pipeline, recognizer=Many())
    p, _, headers = child
    sent = jpeg()
    assert post_photo(client, headers, sent).status_code == 200
    a = db.query(AuditLog).filter_by(event="photo_processed").one()
    assert len(a.payload["model_labels"]) == 10 == len(a.payload["resolved_food_ids"])      # έως 10
    assert all(len(label) <= 60 for label in a.payload["model_labels"])
    assert a.payload["model_id"] == "test-many" and a.participant_id is None
    audit._check(a.payload, "photo_processed")                                    # ο έλεγχος payload δεν χαλάρωσε
    assert not audit.FORBIDDEN_KEYS & {k.lower() for k in a.payload}

    def no_bytes(value):
        assert not isinstance(value, (bytes, bytearray, memoryview))
        for v in (value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()):
            no_bytes(v)
    import base64
    for row in db.query(AuditLog).all():
        no_bytes(row.payload)
        text = json.dumps(row.payload)
        assert base64.b64encode(sent[:30]).decode()[:24] not in text and sent[:16].hex() not in text
        assert str(len(sent)) not in text                                         # ούτε το μέγεθος του αρχείου


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
    for s in body["suggestions"]:
        assert len(s["alternatives"]) <= 3 and s["food_id"] not in [a["food_id"] for a in s["alternatives"]]
        assert s["portion"] is None and s["components"] is None
        if s["confidence_word"] == "σίγουρο":
            assert s["alternatives"] == []
    assert_no_numbers(body)
    assert db.query(Meal).count() == 0                                        # R3
    audit_row = db.query(AuditLog).filter_by(event="text_processed").one()
    assert text not in json.dumps(audit_row.payload, ensure_ascii=False)       # ποτέ το κείμενο
    assert audit_row.participant_id is None and audit_row.payload["analysis_id"] == body["analysis_id"]
    assert set(audit_row.payload) == {"analysis_id", "model_id", "n_segments", "resolved_food_ids", "pipeline", "shown"}
    assert [x["food_id"] for x in audit_row.payload["shown"]] == [fid for fid, _ in expected]


def test_text_audit_has_counts_and_food_ids_but_never_the_childs_text(client, child, db):
    _, _, headers = child
    sent = "ξυλοπόδαρο με μυστικό, φακές και σπανακόπιτα"
    body = client.post(TEXT, json={"text": sent}, headers=headers).json()
    assert [s["food_id"] for s in body["suggestions"]] == [None, None, "lentils", None]
    row = db.query(AuditLog).filter_by(event="text_processed").one()
    payload = row.payload
    assert row.participant_id is None
    assert payload == {"analysis_id": body["analysis_id"], "model_id": "deterministic-0", "n_segments": 4,
                       "resolved_food_ids": [None, None, "lentils", None], "pipeline": "real",
                       "shown": [{"food_id": None, "portion": None, "alternatives": []},
                                 {"food_id": None, "portion": None, "alternatives": []},
                                 {"food_id": "lentils", "portion": None, "alternatives": []},
                                 {"food_id": None, "portion": None, "alternatives": ["spinach"]}]}
    dumped = json.dumps(payload, ensure_ascii=False)
    for word in ("ξυλοπόδαρο", "μυστικό", "σπανακόπιτα", "φακές"):               # κανένα τμήμα του κειμένου
        assert word not in dumped
    # Τα food_id των alternatives (εδώ spinach) γράφονται πλέον στο shown: χρειάζονται για το alternative_chosen
    # (Απόφαση 35). Είναι κωδικοί του πίνακα, όχι λέξεις του παιδιού.


@pytest.mark.parametrize("body", [{"text": "x" * 301}, {"text": ""}, {"text": "φακές", "extra": 1}, {}])
def test_text_validation(client, child, body):
    _, _, headers = child
    assert client.post(TEXT, json=body, headers=headers).status_code == 422


def test_text_requires_token(client):
    assert client.post(TEXT, json={"text": "φακές"}).status_code == 401


def test_text_alternatives_for_unknown_and_fuzzy(client, child):
    _, _, headers = child
    by_name = lambda text: {s["name_el"]: s for s in client.post(TEXT, json={"text": text}, headers=headers).json()["suggestions"]}
    unknown = by_name("σπανακόπιτα, πίτσα")
    assert unknown["σπανακόπιτα"]["food_id"] is None                            # S08β: «Δεν το βρήκα, διάλεξε από αυτά»
    assert unknown["σπανακόπιτα"]["alternatives"] == [{"food_id": "spinach", "name_el": "Σπανάκι"}]
    assert unknown["πίτσα"] == {"food_id": None, "name_el": "πίτσα", "confidence_word": "ίσως", "alternatives": [],
                                "portion": None, "components": None}
    assert_no_numbers(unknown)


def test_recognizer_alternatives_are_resolved_deduplicated_and_capped(app, client, child):
    from app.services.photo_pipeline import RecognizedFood

    class Rec:
        version = "test"

        def recognize(self, jpeg_bytes):
            return [RecognizedFood("x", "φακές", 0.9, ("φακές", "φακόσουπα", "άγνωστο πιάτο", "ρεβίθια", "φασολάδα",
                                                       "μήλο", "μπανάνα"))]

    _, _, headers = child
    app.state.photo_pipeline = PhotoPipeline(DemoNsfwFilter(), DemoBrightnessFilter(), Rec(), 1_048_576, 448)
    s = post_photo(client, headers, jpeg()).json()["suggestions"][0]
    assert s["food_id"] == "lentils"
    assert [a["food_id"] for a in s["alternatives"]] == ["chickpeas", "bean_soup", "apple"]   # όχι το ίδιο, όχι άγνωστα, έως 3


def test_recognizer_with_malformed_alternatives_is_rejected(app, client, child):
    from app.services.photo_pipeline import RecognizedFood

    class Rec:
        version = "test"

        def recognize(self, jpeg_bytes):
            return [RecognizedFood("x", "φακές", 0.9, [("lentils", 0.9)])]       # σκορ μέσα στα alternatives: όχι

    _, _, headers = child
    app.state.photo_pipeline = PhotoPipeline(DemoNsfwFilter(), DemoBrightnessFilter(), Rec(), 1_048_576, 448)
    r = post_photo(client, headers, jpeg())
    assert r.status_code == 422 and r.json() == {"rejected": True}              # fail-closed (R4)


# ------------------------------------------------------------------ analysis_id και suggestion_outcome (Απόφαση 35)

CONFIRM = "/api/v1/meals/confirm"


def _confirm(client, headers, items, analysis_id=None, client_meal_id=None):
    import uuid as _uuid
    from datetime import datetime
    from zoneinfo import ZoneInfo
    body = {"client_meal_id": client_meal_id or str(_uuid.uuid4()),
            "eaten_on": datetime.now(ZoneInfo("Europe/Athens")).date().isoformat(), "meal_slot": "lunch",
            "source": "camera", "items": [{"food_id": f, "portion": portion, "ai_suggested": True} for f, portion in items]}
    if analysis_id is not None:
        body["analysis_id"] = analysis_id
    return client.post(CONFIRM, json=body, headers=headers), body


def test_each_analysis_gets_a_new_analysis_id(client, child):
    _, _, headers = child
    ids = {post_photo(client, headers, jpeg()).json()["analysis_id"] for _ in range(2)}
    ids |= {client.post(TEXT, json={"text": "φακές"}, headers=headers).json()["analysis_id"] for _ in range(2)}
    assert len(ids) == 4


def test_photo_outcome_per_food(client, child, db):
    p, _, headers = child
    analysis_id = post_photo(client, headers, jpeg()).json()["analysis_id"]
    # φακές: δεκτή· ψωμί: αφαιρέθηκε· σαλάτα (null): διάλεξε φέτα από τα alternatives· γάλα: προστέθηκε
    r, _ = _confirm(client, headers, [("lentils", "medium"), ("feta", "small"), ("milk", "medium")], analysis_id)
    assert r.status_code == 201
    row = db.query(AuditLog).filter_by(event="suggestion_outcome").one()
    assert row.participant_id == p.id
    assert row.payload == {"analysis_id": analysis_id, "meal_id": r.json()["meal_id"], "analysis_found": True,
                           "items": [{"outcome": "accepted", "food_id": "lentils"},
                                     {"outcome": "alternative_chosen", "food_id": "feta", "instead_of": None},
                                     {"outcome": "added", "food_id": "milk"},
                                     {"outcome": "removed", "food_id": "wholegrain_bread"}]}
    assert "analysis_id" not in r.json()                                         # τίποτα νέο προς το παιδί


def test_text_outcome_never_holds_the_childs_text(client, child, db):
    _, _, headers = child
    sent = "σπανακόπιτα με μυστικό"
    analysis_id = client.post(TEXT, json={"text": sent}, headers=headers).json()["analysis_id"]
    r, _ = _confirm(client, headers, [("spinach", "small")], analysis_id)
    assert r.status_code == 201
    payload = db.query(AuditLog).filter_by(event="suggestion_outcome").one().payload
    assert [i["outcome"] for i in payload["items"]] == ["alternative_chosen", "removed"]
    for row in db.query(AuditLog).all():
        dumped = json.dumps(row.payload, ensure_ascii=False)
        assert "σπανακόπιτα" not in dumped and "μυστικό" not in dumped


def test_outcome_rules():
    from app.services.analysis_audit import OUTCOMES, outcomes
    shown = [{"food_id": "a", "portion": "small", "alternatives": ["x"]},
             {"food_id": "b", "portion": None, "alternatives": ["a", "y"]},
             {"food_id": None, "portion": None, "alternatives": []}]
    got = outcomes(shown, [{"food_id": "a", "portion": "large"}, {"food_id": "a", "portion": "small"},
                           {"food_id": "z", "portion": "small"}])
    assert got == [{"outcome": "portion_changed", "food_id": "a"},              # η πρόταση είχε μερίδα και άλλαξε
                   {"outcome": "alternative_chosen", "food_id": "a", "instead_of": "b"},
                   {"outcome": "added", "food_id": "z"},
                   {"outcome": "removed", "food_id": None}]
    assert {o["outcome"] for o in got} <= set(OUTCOMES)
    assert outcomes([], [{"food_id": "a", "portion": "small"}]) == [{"outcome": "added", "food_id": "a"}]


def test_outcome_not_repeated_on_replay_and_unknown_analysis_does_not_block_meal(client, child, db):
    import uuid as _uuid
    _, _, headers = child
    analysis_id = client.post(TEXT, json={"text": "φακές"}, headers=headers).json()["analysis_id"]
    r, body = _confirm(client, headers, [("lentils", "medium")], analysis_id)
    assert r.status_code == 201
    assert client.post(CONFIRM, json=body, headers=headers).status_code == 200   # επανάληψη
    assert db.query(AuditLog).filter_by(event="suggestion_outcome").count() == 1
    unknown = str(_uuid.uuid4())
    r2, _ = _confirm(client, headers, [("apple", "small")], unknown)
    assert r2.status_code == 201                                                 # το γεύμα αποθηκεύεται
    rows = db.query(AuditLog).filter_by(event="suggestion_outcome").all()
    assert rows[-1].payload == {"analysis_id": unknown, "meal_id": r2.json()["meal_id"], "analysis_found": False,
                                "items": []}
    r3, _ = _confirm(client, headers, [("apple", "small")])                      # χωρίς analysis_id: καμία έκβαση
    assert r3.status_code == 201 and db.query(AuditLog).filter_by(event="suggestion_outcome").count() == 2
    bad, _ = _confirm(client, headers, [("apple", "small")], "not-a-uuid")
    assert bad.status_code == 422


def test_no_admin_endpoint_exposes_model_output(app, client, child, db):
    _, _, headers = child
    photo = post_photo(client, headers, jpeg()).json()
    text = client.post(TEXT, json={"text": "φακές"}, headers=headers).json()
    _confirm(client, headers, [("lentils", "medium")], photo["analysis_id"])
    admin = {"X-Admin-Token": "a" * 40}
    paths = [path for path, ops in app.openapi()["paths"].items()                 # όλα τα GET του admin
             if path.startswith("/api/v1/admin") and "get" in ops]
    assert "/api/v1/admin/system-status" in paths
    checked = 0
    for path in paths:
        if "{" in path:
            continue
        resp = client.get(path, headers=admin)
        assert resp.status_code == 200, path
        checked += 1
        for secret in (photo["analysis_id"], text["analysis_id"], "lentil soup", "model_labels", "resolved_food_ids",
                       "suggestion_outcome", "alternative_chosen", "shown"):
            assert secret not in resp.text, (path, secret)
    assert checked >= 4
