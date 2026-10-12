# Data Protection Impact Assessment

> Status: outline. Children's data plus AI processing -- a DPIA is mandatory.

## 1. Description of the processing

## 2. The photograph: what happens to it

1. Captured in the browser.
2. Downscaled to 448 px and re-encoded as a fresh JPEG; EXIF is dropped
   (`frontend/src/ml/imagePrep.ts`).
3. Screened in the browser by the food gate; non-food never leaves the device
   (`frontend/src/ml/foodGate.ts`).
4. Transmitted over TLS as a raw body, capped at 1 MB.
5. Held in process memory only, screened again server-side (NSFW + food
   re-check), passed to OliveGemma, then discarded.
6. Only the dish name, the resolved `food_id` and the child's confirmation are
   persisted.

Residual risk is addressed by the controls in `docs/ephemeral-processing.md`
(no disk, no swap, no request-body logging) and verified by
`backend/tests/integration/test_photo_ephemeral.py` and
`scripts/check_ephemeral.sh`.

## 3. Necessity and proportionality

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A photograph persists on disk | low | high | Rule 7 controls, tmpfs, no swap, automated check |
| An inappropriate image is uploaded | low | high | Rule 8: browser food gate + server NSFW + food re-check |
| Re-identification from meal data | low | medium | Pseudonymisation, key kept off-server |
| The LLM invents a nutritional claim | medium | medium | Safety validator; engine output is authoritative |
| Harm from stigmatising feedback | low | high | No calories, no BMI, no leaderboards; ED safety rules |

## 5. Consultation

## 6. Sign-off
