# Rule 7 -- ephemeral photo processing

**Claim.** A meal photograph is never written to persistent storage anywhere in
the system.

This document lists what has to be true for that claim to hold, and how each
condition is checked.

## Preconditions

| # | Condition | Where it is enforced |
|---|---|---|
| 1 | The request body is read into memory and never spooled to a file | `app/api/meals.py` -- raw `bytes`, no `UploadFile` spooling above the cap |
| 2 | The body is capped below Nginx's buffer size, so Nginx never writes a temp file | `nginx/sites-available/pyramid.conf`: `client_max_body_size 1m`, `client_body_buffer_size 1m` |
| 3 | `proxy_request_buffering` does not spool to disk | same file |
| 4 | Containers' `/tmp` is tmpfs | `docker-compose.prod.yml` |
| 5 | Swap is disabled on the host and in the containers | host `swapoff -a`; `memswap_limit: 0`, `mem_swappiness: 0` |
| 6 | No logger ever records a request body | `app/core/logging.py`; Nginx access log format excludes bodies |
| 7 | No model client caches the image | `ai_pipeline/vision/*` take `bytes`, write nothing |
| 8 | Nothing in the schema can hold an image | migration `001` has no image table or column |
| 9 | Audit entries record the event, not the image | `photo_processed` / `photo_rejected`, always `stored_bytes: 0` |
| 10 | No core dumps | `ulimit -c 0` / container setting |

## Checks

- `backend/tests/integration/test_photo_ephemeral.py` -- 1000 uploads, asserts
  no new file appears anywhere under the writable paths.
- `scripts/check_ephemeral.sh` -- inspects Nginx temp directories, container
  `/tmp` mounts, swap status and log contents. Run by `make check-ephemeral`
  and as the last step of `make deploy`.

## If a precondition is broken

Treat it as a reportable incident: the claim in the DPIA and the consent forms
no longer holds. Stop enrolment, restore the control, and document it.
