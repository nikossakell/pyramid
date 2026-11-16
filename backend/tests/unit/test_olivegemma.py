"""
OliveGemmaRecognizer χωρίς βάρη: ψεύτικο backend. Ελέγχονται beam -> label map -> διπλά -> alternatives, ο κανόνας
«σίγουρο / ίσως» (Απόφαση 6), timeout -> απόρριψη, ουρά -> busy, λάθος sha256 -> unavailable, και ότι καμία τιμή σκορ
ή αριθμός δεν φεύγει από τη μονάδα (R1).
"""
import threading
import time
from dataclasses import dataclass

import pytest

from ai_pipeline.vision.olivegemma import (MAYBE, SURE, OliveGemmaRecognizer, load_label_map, normalize_label,
                                           parse_components)
from ai_pipeline.vision.types import RecognizedFood, RecognizerBusy, RecognizerUnavailable
from app.services.photo_pipeline import PhotoPipeline, PhotoRejected
from tests.api.photos import jpeg


@dataclass(frozen=True)
class Food:
    name_el: str
    food_group: str


FOODS = {"lentils": Food("Φακές", "legumes"), "bean_soup": Food("Φασολάδα", "legumes"),
         "chicken": Food("Κοτόπουλο ψητό", "meat"), "tomato": Food("Ντομάτα", "vegetables")}
LABEL_MAP = {"lentil soup": "lentils", "Lentils": "lentils", "bean soup": "bean_soup", "giant beans": "bean_soup",
             "grilled chicken": "chicken", "tomato": "tomato"}


class FakeBackend:
    def __init__(self, dish=("lentil soup", "lentils", "bean soup"), ingredients="", delay=0.0):
        self.dish, self.ingredients, self.delay, self.calls = list(dish), ingredients, delay, []

    def answer(self, image, question, k):
        self.calls.append((question, k))
        time.sleep(self.delay)
        if "ingredients" in question:
            return [self.ingredients]
        return self.dish[:k]


def recognizer(tmp_path, backend=None, **kw):
    (tmp_path / "model.safetensors").write_bytes(b"not real weights")
    (tmp_path / "REVISION.txt").write_text("abc123\n")
    backend = backend or FakeBackend()
    return OliveGemmaRecognizer(tmp_path, LABEL_MAP, FOODS, timeout_s=kw.pop("timeout_s", 5.0),
                                backend_factory=lambda: backend, **kw), backend


# ---------------------------------------------------------------- αντιστοίχιση

def test_beams_are_mapped_deduplicated_and_become_alternatives(tmp_path):
    rec, backend = recognizer(tmp_path)
    out = rec.recognize(jpeg())
    assert out == [RecognizedFood("lentil soup", "Φακές", SURE, ("Φασολάδα",))]   # lentils = ίδιο food_id: όχι διπλό
    assert backend.calls == [("What is the name of this dish?", 3)]              # ένα beam search, χωρίς ingredients
    assert rec.version == "OliveGemma-3B@abc123"


def test_unmapped_top_label_gives_no_name_but_keeps_mapped_alternatives(tmp_path):
    rec, _ = recognizer(tmp_path, FakeBackend(dish=("moussaka", "pastitsio", "lentil soup")))
    (found,) = rec.recognize(jpeg())
    assert found.label_en == "moussaka" and found.name_el is None and found.confidence == MAYBE
    assert found.alternatives == ("Φακές",)


@pytest.mark.parametrize("dish, expected", [
    (("lentil soup",), SURE),                               # μόνο μία πρόταση
    (("lentil soup", "bean soup"), SURE),                   # 2η ίδιας ομάδας (όσπρια)
    (("lentil soup", "lentils"), SURE),                     # 2η ίδιο τρόφιμο
    (("lentil soup", "pea soup"), SURE),                    # 2η δεν αντιστοιχίζεται: δεν αποδεικνύει διαφορά
    (("lentil soup", "grilled chicken"), MAYBE),            # 2η άλλης ομάδας
    (("pea soup", "lentil soup"), MAYBE),                   # 1η δεν αντιστοιχίζεται
])
def test_confidence_rule(tmp_path, dish, expected):
    rec, _ = recognizer(tmp_path, FakeBackend(dish=dish))
    assert rec.recognize(jpeg())[0].confidence == expected


def test_labels_are_normalized_and_capped(tmp_path):
    rec, _ = recognizer(tmp_path, FakeBackend(dish=("  Lentil   SOUP ", "x" * 200)))
    (found,) = rec.recognize(jpeg())
    assert found.label_en == "lentil soup" and found.name_el == "Φακές"
    assert normalize_label("  Giant\tBeans ") == "giant beans"


def test_empty_model_output_is_an_error_hence_rejection(tmp_path):
    rec, _ = recognizer(tmp_path, FakeBackend(dish=("", "  ")))
    pipeline = PhotoPipeline(None, None, rec, 1_048_576, 448)
    with pytest.raises(PhotoRejected) as e:
        pipeline.recognize(jpeg())
    assert e.value.reason == "recognizer_error"


# ---------------------------------------------------------------- R1

def test_no_scores_or_digits_leave_the_module(tmp_path):
    rec, _ = recognizer(tmp_path, FakeBackend(
        dish=("lentil soup", "bean soup", "grilled chicken"),
        ingredients="Visible-typical ingredients: lentils, 2 carrots, onion. Commonly-present: olive oil, salt."),
        ingredients=True)
    (found,) = rec.recognize(jpeg())
    assert found.confidence in (SURE, MAYBE)                                     # μόνο οι δύο σταθερές, ποτέ σκορ
    assert found.components == ("lentils", "onion", "olive oil", "salt")        # «2 carrots» έξω (ψηφίο)
    text = " ".join([found.label_en, *found.alternatives, *found.components])
    assert not any(ch.isdigit() for ch in text)


def test_ingredients_off_by_default_means_no_second_question(tmp_path):
    rec, backend = recognizer(tmp_path)
    rec.recognize(jpeg())
    assert all("ingredients" not in q for q, _ in backend.calls)


def test_parse_components_drops_frame_phrases_and_quantities():
    assert parse_components("Visible-typical ingredients: tomato, feta cheese and olives; 200 g rice, etc.") == (
        "tomato", "feta cheese", "olives")
    assert parse_components("") == ()


# ---------------------------------------------------------------- ακεραιότητα, ουρά, timeout

def test_wrong_sha256_means_unavailable_not_rejected(tmp_path, caplog):
    rec, _ = recognizer(tmp_path, sha256="0" * 64)
    assert rec.ready
    with pytest.raises(RecognizerUnavailable):
        rec.recognize(jpeg())
    assert not rec.ready and not rec.loaded
    pipeline = PhotoPipeline(None, None, rec, 1_048_576, 448)
    assert pipeline.available is False                                           # /me: unavailable, /meals/photo: 503
    with pytest.raises(RecognizerUnavailable):
        pipeline.recognize(jpeg())                                               # περνά ως έχει, ΟΧΙ PhotoRejected
    assert any(r.getMessage() == "olivegemma_load_failed" for r in caplog.records)


def test_missing_weights_means_unavailable(tmp_path):
    rec = OliveGemmaRecognizer(tmp_path / "nowhere", LABEL_MAP, FOODS, backend_factory=FakeBackend)
    assert rec.version == "OliveGemma-3B@unknown"
    with pytest.raises(RecognizerUnavailable):
        rec.load()


def test_correct_sha256_loads(tmp_path):
    import hashlib
    rec, _ = recognizer(tmp_path, sha256=hashlib.sha256(b"not real weights").hexdigest().upper())
    rec.load()
    assert rec.loaded and rec.ready


def test_timeout_becomes_rejection_and_worker_keeps_the_lock(tmp_path):
    rec, backend = recognizer(tmp_path, FakeBackend(delay=0.6), timeout_s=0.1, max_queue=0)
    pipeline = PhotoPipeline(None, None, rec, 1_048_576, 448)
    with pytest.raises(PhotoRejected) as e:
        pipeline.recognize(jpeg())
    assert e.value.reason == "recognizer_timeout"
    with pytest.raises(RecognizerBusy):                                          # το νήμα τρέχει ακόμα: ουρά 0 → busy
        rec.recognize(jpeg())
    time.sleep(0.8)
    backend.delay, rec.timeout_s = 0.0, 5.0                                      # ανεκτικό στον φόρτο του μηχανήματος
    assert rec.recognize(jpeg())[0].name_el == "Φακές"                           # μετά το τέλος του, ξανά διαθέσιμο


def test_queue_limit_gives_busy_without_rejection(tmp_path):
    rec, _ = recognizer(tmp_path, FakeBackend(delay=0.4), max_queue=1)
    results, errors = [], []

    def call():
        try:
            results.append(rec.recognize(jpeg()))
        except Exception as e:                                                   # noqa: BLE001
            errors.append(type(e))

    threads = [threading.Thread(target=call) for _ in range(3)]
    for t in threads:
        t.start()
        time.sleep(0.05)
    for t in threads:
        t.join()
    assert len(results) == 2 and errors == [RecognizerBusy]                      # 1 τρέχει + 1 περιμένει· ο 3ος busy


def test_one_inference_at_a_time(tmp_path):
    running, overlap = [0], [False]

    class Serial(FakeBackend):
        def answer(self, image, question, k):
            running[0] += 1
            overlap[0] |= running[0] > 1
            time.sleep(0.1)
            running[0] -= 1
            return super().answer(image, question, k)

    rec, _ = recognizer(tmp_path, Serial(), max_queue=5)
    threads = [threading.Thread(target=rec.recognize, args=(jpeg(),)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert overlap[0] is False


# ---------------------------------------------------------------- label map

def test_label_map_reads_only_label_and_food_id(tmp_path):
    p = tmp_path / "map.csv"
    p.write_text("olivegemma_label,food_id,default_portion_g,confidence_floor,notes\n"
                 "Lentil  Soup,lentils,250,0.9,ΠΡΟΣΧΕΔΙΟ demo\n"
                 "unmapped label,,,,\n"
                 "giant beans,bean_soup,,,\n", encoding="utf-8")
    assert load_label_map(p, FOODS) == {"lentil soup": "lentils", "giant beans": "bean_soup"}


def test_label_map_rejects_unknown_food_and_conflicts(tmp_path):
    p = tmp_path / "map.csv"
    p.write_text("olivegemma_label,food_id\nsoup,nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown food_id"):
        load_label_map(p, FOODS)
    p.write_text("olivegemma_label,food_id\nsoup,lentils\nSOUP,bean_soup\n", encoding="utf-8")
    with pytest.raises(ValueError, match="maps to both"):
        load_label_map(p, FOODS)
    p.write_text("label,food_id\nsoup,lentils\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_label_map(p)


def test_repo_label_map_matches_demo_foods():
    """Το data/olivegemma_label_map.csv (ΠΡΟΣΧΕΔΙΟ demo) αναφέρεται μόνο σε food_id του demo πίνακα."""
    from pathlib import Path
    from app.services.food_catalog import load_catalog
    root = Path(__file__).resolve().parents[3]
    catalog = load_catalog(root / "data/demo_foods.csv", root / "data/demo_food_aliases.csv",
                           root / "data/efsa_drv.csv", root / "data/food_groups.csv",
                           root / "data/display_food_groups.csv")
    m = load_label_map(root / "data/olivegemma_label_map.csv", catalog.foods)
    assert m["lentil soup"] == "lentils" and len(m) >= 20
