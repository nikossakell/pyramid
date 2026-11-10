# Rule 7 -- ephemeral photo processing

**Claim.** A meal photograph is never written to persistent storage anywhere in
the system.

This document lists what has to be true for that claim to hold, and how each
condition is checked.

## Preconditions

| # | Condition | Where it is enforced |
|---|---|---|
| 1 | The request body is read into memory and never spooled to a file | `app/api/meals.py` (`POST /api/v1/meals/photo`) -- raw `bytes` read in chunks, reading stops above `MAX_PHOTO_BYTES`; no `UploadFile`. `python-multipart` is deliberately **not** a dependency, so FastAPI refuses to load any `UploadFile`/`Form` endpoint |
| 2 | The body is capped below Nginx's buffer size, so Nginx never writes a temp file | `nginx/sites-available/pyramid.conf`: `location = /api/v1/meals/photo` with `client_max_body_size 1m`, `client_body_buffer_size 1m` (the path must match the backend prefix) |
| 3 | `proxy_request_buffering` does not spool to disk | same file |
| 4 | Containers' `/tmp` is tmpfs | `docker-compose.prod.yml` |
| 5 | Swap is disabled on the host and in the containers | host `swapoff -a`; `memswap_limit: 0`, `mem_swappiness: 0` |
| 6 | No logger ever records a request body | `app/core/logging.py` (method, path without query, status, duration, pseudonym); uvicorn runs with `--no-access-log`; the Nginx log format uses `$uri` (no body, no query string) |
| 7 | No model client caches the image | `app/services/photo_pipeline.py`: the `ContentFilter` / `FoodRecognizer` protocols take `bytes` and write nothing; the image is re-encoded in RAM (no EXIF). Real models (future `ai_pipeline/vision/*`) must keep the same contract |
| 8 | Nothing in the schema can hold an image | migration `001` has no image table or column |
| 9 | Audit entries record the event, not the image | `photo_processed` / `photo_rejected` (reason only), always `stored_bytes: 0`; `app/core/audit.py` refuses any `bytes` value or image/key/token field |
| 10 | No core dumps | `ulimit -c 0` / container setting |

## Checks

- `backend/tests/integration/test_photo_ephemeral.py` -- 1000 uploads, asserts
  no new file appears in `tempfile.gettempdir()` (pointed at a private, empty
  directory for the test) or in the application directory, and that every audit
  entry has `stored_bytes: 0`.
- `backend/tests/api/test_photo_text.py` -- every rejection (wrong type, bad
  signature, PNG, > 1 MB, > 448 px, decompression bomb, filter exception) gets
  the same `422 {"rejected": true}`; no image byte in the audit log or logs.
- `backend/tests/api/test_deployment.py` -- Nginx locations use `/api/v1`, the
  Nginx and uvicorn logs carry no query string.
- `scripts/check_ephemeral.sh` -- inspects Nginx temp directories, container
  `/tmp` mounts, swap status and log contents. Run by `make check-ephemeral`
  and as the last step of `make deploy`.

## If a precondition is broken

Treat it as a reportable incident: the claim in the DPIA and the consent forms
no longer holds. Stop enrolment, restore the control, and document it.
