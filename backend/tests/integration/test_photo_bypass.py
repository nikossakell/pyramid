"""
Κανόνας 8 (docs/content-safety.md): ό,τι στέλνεται απευθείας στο API, παρακάμπτοντας το food gate του browser, περνά
ξανά από NSFW και food gate #2 στον server. Η σειρά είναι NSFW -> food gate -> αναγνώριση, και μια απόρριψη σταματά
την επεξεργασία (το επόμενο βήμα δεν καλείται).
"""
import pytest
from fastapi.testclient import TestClient

from app.db.models import AuditLog
from app.services.photo_pipeline import PhotoPipeline, RecognizedFood
from tests.api.conftest import add_participant, build_app, login
from tests.api.photos import dark_jpeg, jpeg


class Recorder:
    def __init__(self, name, verdict):
        self.name, self.version, self.verdict, self.calls = name, "test", verdict, 0

    def allows(self, jpeg_bytes):
        self.calls += 1
        return self.verdict


class CountingRecognizer:
    version = "test"

    def __init__(self):
        self.calls = 0

    def recognize(self, jpeg_bytes):
        self.calls += 1
        return [RecognizedFood("lentil soup", "φακές", 0.9)]


@pytest.mark.parametrize("nsfw_ok, food_ok, reason, calls", [
    (False, True, "nsfw", (1, 0, 0)),          # NSFW: δεν φτάνει ούτε στο food gate
    (True, False, "food_gate", (1, 1, 0)),     # μη φαγητό: δεν φτάνει στην αναγνώριση
    (True, True, None, (1, 1, 1)),
])
def test_server_side_gates_and_order(nsfw_ok, food_ok, reason, calls):
    app = build_app(DEMO_MODE=True)
    nsfw, food, recognizer = Recorder("nsfw", nsfw_ok), Recorder("food", food_ok), CountingRecognizer()
    app.state.photo_pipeline = PhotoPipeline(nsfw, food, recognizer, max_bytes=1_048_576, max_edge_px=448)
    with TestClient(app) as client:
        headers = {**login(client, add_participant(app)[1]), "Content-Type": "image/jpeg"}
        r = client.post("/api/v1/meals/photo", content=jpeg(), headers=headers)
    assert (nsfw.calls, food.calls, recognizer.calls) == calls
    if reason is None:
        assert r.status_code == 200
    else:
        assert r.status_code == 422 and r.json() == {"rejected": True}
        with app.state.sessionmaker() as s:
            assert s.query(AuditLog).filter_by(event="photo_rejected").one().payload["reason"] == reason


def test_non_food_straight_to_api_is_rejected_by_demo_gate():
    app = build_app(DEMO_MODE=True)
    with TestClient(app) as client:
        headers = {**login(client, add_participant(app)[1]), "Content-Type": "image/jpeg"}
        r = client.post("/api/v1/meals/photo", content=dark_jpeg(), headers=headers)
    assert r.status_code == 422 and r.json() == {"rejected": True}
