# Rule 8 -- content safety

Two gates stand between a camera and OliveGemma. The first runs in the browser
so that non-food never leaves the device; the second runs on the server so that
the API cannot be bypassed.

## Gate 1 -- in-browser food gate

- Model: MobileNetV2 binary classifier, trained by `scripts/train_food_gate.py`
  on Food-5K plus our own samples, converted to TF.js 8-bit by
  `scripts/convert_food_gate_tfjs.sh`.
- Served from `frontend/public/models/food_gate/`, run by
  `frontend/src/ml/foodGate.ts`.
- Threshold: `FOOD_GATE_THRESHOLD` (default 0.60).
- Below threshold: the upload is never made, and the child is asked to retake.

## Gate 2 -- server side

Applied in `ai_pipeline/vision/content_filter.py`, in order:

1. **NSFW detection** -- Falconsai/nsfw_image_detection. At or above
   `NSFW_THRESHOLD` (default 0.70) the request is rejected with no further
   processing, an audit entry `photo_rejected` is written (`stored_bytes: 0`),
   and the researcher-facing counter is incremented.
2. **Food re-check** -- the same gate model server-side. Below
   `SERVER_FOOD_RECHECK_THRESHOLD` (default 0.50) the request is rejected as
   non-food.

Only images passing both gates reach OliveGemma.

## Thresholds and versions

Thresholds live in `.env` / `app/config.py`; model versions in
`ai_pipeline/config.py`. Both are recorded in the audit log with every
decision, so a pilot result can always be traced to the exact configuration
that produced it.

| Setting | Default | Rationale |
|---|---|---|
| `FOOD_GATE_THRESHOLD` | 0.60 | Tuned for recall on real food photos |
| `SERVER_FOOD_RECHECK_THRESHOLD` | 0.50 | Looser, as the browser already filtered |
| `NSFW_THRESHOLD` | 0.70 | Tuned against false positives on food photos |

## False positives

Food photographs misflagged as NSFW are the main usability risk. Tracked in
`notebooks/07_nsfw_false_positives.ipynb` and guarded by
`backend/tests/unit/test_content_filter.py`.

## Bypass attempts

`backend/tests/integration/test_photo_bypass.py` posts non-food straight to the
API and asserts rejection.
