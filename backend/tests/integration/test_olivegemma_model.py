"""
Πραγματικό OliveGemma-3B (marker `model`): τρέχει ΜΟΝΟ αν υπάρχουν τα βάρη στο OLIVEGEMMA_DIR (προεπιλογή
<repo>/models/olivegemma-3b), αλλιώς skip με μήνυμα. Φορτώνει ~6 GB και σε CPU θέλει λεπτά· εκτός από το προεπιλεγμένο
τρέξιμο με `-m "not model"` (backend/README.md). Δεν ελέγχει ακρίβεια (βλ. scripts/bench_olivegemma.py), μόνο ότι το
pipeline δίνει έγκυρη έξοδο χωρίς αριθμούς και χωρίς αρχείο στον δίσκο.
"""
import os
from pathlib import Path

import pytest

from ai_pipeline.vision.olivegemma import MAYBE, SURE, OliveGemmaRecognizer, load_label_map
from app.services.photo_pipeline import PhotoPipeline
from tests.api.photos import jpeg

ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = Path(os.environ.get("OLIVEGEMMA_DIR", ROOT / "models" / "olivegemma-3b"))

pytestmark = [pytest.mark.model, pytest.mark.slow,
              pytest.mark.skipif(not (MODEL_DIR / "model.safetensors").is_file(),
                                 reason=f"no OliveGemma weights in {MODEL_DIR} (set OLIVEGEMMA_DIR)")]


def test_real_model_recognizes_synthetic_image_without_numbers(tmp_path, monkeypatch):
    from app.services.food_catalog import load_catalog
    catalog = load_catalog(ROOT / "data/demo_foods.csv", ROOT / "data/demo_food_aliases.csv",
                           ROOT / "data/efsa_drv.csv", ROOT / "data/food_groups.csv",
                           ROOT / "data/display_food_groups.csv")
    rec = OliveGemmaRecognizer(MODEL_DIR, load_label_map(ROOT / "data/olivegemma_label_map.csv", catalog.foods),
                               catalog.foods, timeout_s=1800, topk=3)
    monkeypatch.setenv("TMPDIR", str(tmp_path))                 # αν κάτι γράψει προσωρινό αρχείο, θα φανεί εδώ
    pipeline = PhotoPipeline(None, None, rec, 1_048_576, 448)
    found = pipeline.recognize(pipeline.prepare(jpeg()))
    assert len(found) == 1 and found[0].label_en and found[0].confidence in (SURE, MAYBE)
    assert not any(ch.isdigit() for ch in " ".join([found[0].label_en, *found[0].alternatives]))
    assert rec.loaded and rec.ready and list(tmp_path.iterdir()) == []
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
