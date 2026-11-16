# PYRAMID backend (Φάση 6)

FastAPI + SQLAlchemy 2 (sync) + Alembic. Προδιαγραφή: [`docs/backend_spec_v1.md`](../docs/backend_spec_v1.md)·
αποφάσεις και ανοιχτά θέματα: [`docs/decisions/2026-11-10_backend.txt`](../docs/decisions/2026-11-10_backend.txt) και
[`docs/decisions/2026-11-12_backend_gaps.txt`](../docs/decisions/2026-11-12_backend_gaps.txt) (κενά backend ↔ mockups).
Κάρτες: μόνο πρόταση, [`docs/card_catalog_proposal.md`](../docs/card_catalog_proposal.md).

```
app/
  api/        endpoints (/api/v1/...), docs.py: Swagger UI / OpenAPI
  core/       security (κλειδιά, JWT), audit (append-only), logging (χωρίς σώμα/query/headers), clock, exceptions
  db/         μοντέλα SQLAlchemy (append_only: audit_log, alert_events), session
  schemas/    Pydantic (ό,τι βλέπει το παιδί: ποτέ αριθμοί θρεπτικών ή γραμμάρια)
  services/   λογική: auth, food_catalog, meal, feedback (rule engine + presenter), photo_pipeline, suggestion, card,
              alert (χρονολόγιο), system_status
  jobs/       daily_card_drops (νυχτερινή κατανομή καρτών, αυτόματη «πλήρης ημέρα», job_runs)
alembic/      001 αρχικό σχήμα · 002 meals.client_meal_id · 003 day_status.completed_by · 004 alert_events, job_runs
```

## Endpoints (`/api/v1`)

Πλήρης περιγραφή: [`docs/api.md`](../docs/api.md) και το Swagger UI.

| | |
|---|---|
| Χωρίς token | `GET /health` · `POST /auth/login` (429 με `Retry-After`· 403 `not_yet_available` / `{"study_ended": true}`) |
| Παιδί | `GET` `PATCH /me` (`photo_status`) · `GET /food-groups` · `GET /foods/search?q=&group=` |
| Γεύματα | `POST /meals/photo` · `POST /meals/text` (προτάσεις με `alternatives`) · `POST /meals/confirm` (idempotent με `client_meal_id`) · `GET /meals` · `DELETE /meals/{meal_id}` |
| Ημέρες | `GET /days?from=&to=` · `POST /days/{day}/complete` |
| Ανατροφοδότηση, κάρτες | `GET /feedback/today` · `GET /cards` · `POST /cards/{card_id}/open` · `POST /ask` (501) |
| Admin (`X-Admin-Token`) | `GET /admin/alerts?status=` · `GET /admin/alerts/{id}` (χρονολόγιο) · `POST /admin/alerts/{id}/status` · `GET /admin/participants` · `POST /admin/participants/{id}/deactivate` · `GET /admin/photo-suspensions` · `GET /admin/system-status` |

## Demo με Swagger (μία εντολή)

```bash
scripts/demo_backend.sh            # ή: make demo
```

Φτιάχνει στο `/tmp/pyramid_demo` καινούργια βάση SQLite, τυχαία μυστικά, `DEMO_MODE=true`, τέσσερα demo παιδιά
(τυπώνει τα κλειδιά τους), το `X-Admin-Token` και δοκιμαστικές εικόνες, και ξεκινά τον server. Μετά:

1. Άνοιγμα <http://localhost:8000/docs> (το Swagger UI φορτώνεται από CDN: χρειάζεται internet).
2. `POST /api/v1/auth/login` με κλειδί → **Authorize** → `ChildJWT` → επικόλληση του `access_token`.
3. `/me`, `/food-groups`, `/foods/search` (και `?group=legumes`), `/meals/photo` (Try it out → επιλογή `meal.jpg`:
   προτάσεις με `alternatives`), `/meals/text`, `/meals/confirm` (τα παραδείγματα έχουν ήδη τη σημερινή ημερομηνία
   και νέο `client_meal_id`· δεύτερο Execute με το ίδιο σώμα → `200`, `created: false`), `/days`,
   `/days/{day}/complete`, `/feedback/today`, `/cards`.
4. **Authorize** → `AdminToken` με το `X-Admin-Token` → `/admin/alerts` (και `?status=new`), `/admin/alerts/{id}`
   (χρονολόγιο), `/admin/participants`, `/admin/system-status`, `/admin/photo-suspensions`.

Το script τυπώνει και έτοιμες εντολές `curl` για τα ίδια (ομάδες, alternatives, idempotency, system-status).

| Παιδί | Τι δείχνει |
|---|---|
| Α (παρέμβαση, με ιστορικό) | `/feedback/today` με μηνύματα (χωρίς αριθμούς), κάρτες με streak |
| Β (παρέμβαση, χωρίς ιστορικό) | ζωντανή καταγραφή: φωτογραφία, κείμενο, επιβεβαίωση. `dark.jpg` / `too_big.jpg` → ίδιο `422`· μετά από 5 → `403` |
| Γ (ομάδα ελέγχου) | `403 not_yet_available` (με `CONTROL_ACCESS_FROM=$(date +%F) scripts/demo_backend.sh` μπαίνει κανονικά) |
| Δ (ανοιχτό safety alert) | `/feedback/today` χωρίς μηνύματα· κλείσιμο του alert από το admin → μηνύματα |

Επιλογές: `PORT=8080`, `HOST=0.0.0.0` (προβολή από άλλη συσκευή), `LLM_BASE_URL=... LLM_MODEL=...` (Krikri),
`STUDY_DURATION_DAYS=7` (τα Α και Δ, εγγεγραμμένα πριν από 7 ημέρες, παίρνουν `403 {"study_ended": true}`),
`COMPLETE_DAY_MODE=auto`,
πρώτο όρισμα = άλλος φάκελος demo. Στο demo το `ALLOW_MEAL_DELETE=true`, ώστε να φαίνεται και η διαγραφή.
⚠️ Demo φίλτρα (όχι μοντέλα) και **ενδεικτικές** τιμές τροφίμων· ποτέ με πραγματικά δεδομένα παιδιών.

## Εκκίνηση (ανάπτυξη)

```bash
cp .env.example .env          # στη ρίζα του repo· συμπληρώστε τα μυστικά (≥ 32 χαρακτήρες σε production)
cd backend
alembic upgrade head          # DATABASE_URL από το .env / το περιβάλλον
uvicorn app.main:app --reload --no-access-log
```

Πάντα `--no-access-log`: το access log του uvicorn γράφει το query string (R6). Η εφαρμογή γράφει μία γραμμή JSON
ανά αίτημα (μέθοδος, path, status, διάρκεια, pseudonym_id). Σε production: `docker compose -f docker-compose.yml
-f docker-compose.prod.yml up -d` (ένας worker, `--proxy-headers` μόνο από το `FORWARDED_ALLOW_IPS`).

## Συμμετέχοντες, alerts, κάρτες

```bash
python scripts/create_participant.py --sex F --age-years 12 --arm intervention   # τυπώνει κλειδί ΜΙΑ φορά
python scripts/create_alert.py --participant <pseudonym_id> --kind safety --category disordered_eating
cd backend && python -m app.jobs.daily_card_drops                 # για χθες· --date YYYY-MM-DD για άλλη ημέρα
```

Η νυχτερινή εργασία είναι idempotent (ξανά την ίδια ημέρα = καμία διπλή κάρτα) και αφορά μόνο ενεργούς της ομάδας
παρέμβασης που ήταν ακόμα στη μελέτη την ημέρα-στόχο. Με `COMPLETE_DAY_MODE=auto` σημειώνει πρώτα πλήρη την ημέρα
όσων έχουν ≥ `AUTO_COMPLETE_MIN_MEALS` γεύματα. Κάθε εκτέλεση γράφεται στο `job_runs` και φαίνεται στο
`/admin/system-status`. Προγραμματισμός (π.χ. 03:00): cron ή systemd timer στον host, με
`docker compose exec backend python -m app.jobs.daily_card_drops`.
Τα alerts δημιουργούνται μόνο με το CLI· κάθε δημιουργία και αλλαγή γράφει γεγονός στο χρονολόγιο (`alert_events`).

## Μεταβλητές περιβάλλοντος

Όλες με σχόλια στο [`.env.example`](../.env.example). Οι κυριότερες:

| Μεταβλητή | Προεπιλογή | |
|---|---|---|
| `ENVIRONMENT` | — (**υποχρεωτικό**) | `development` / `test` / `production`. Χωρίς αυτό η εφαρμογή, τα scripts (`create_participant.py`, `create_alert.py`, `seed_demo.py`) και η νυχτερινή εργασία δεν ξεκινούν |
| `DATABASE_URL` | — | `postgresql+psycopg://...` (production), `sqlite:///...` (τοπικά) |
| `JWT_SECRET`, `ACCESS_KEY_PEPPER`, `ADMIN_TOKEN` | — | ≥ 32 χαρακτήρες σε production |
| `ACCESS_TOKEN_TTL_MINUTES` | 720 | ΠΡΟΣΧΕΔΙΟ |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_MINUTES` | 30 / 15 | ανά IP, in-memory (ένας worker) |
| `CONTROL_ACCESS_FROM` | κενό | ομάδα ελέγχου: 403 μέχρι αυτή την ημέρα |
| `STUDY_DURATION_DAYS` | 84 | ΠΡΟΣΧΕΔΙΟ· μετά: 403 `{"study_ended": true}` για την ομάδα παρέμβασης |
| `POST_STUDY_ACCESS` | `false` | ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: πρόσβαση μετά το τέλος της μελέτης |
| `APP_TIMEZONE` | `Europe/Athens` | «σήμερα», ημέρες, νυχτερινή εργασία |
| `DEMO_MODE` | `false` | συντόμευση «όλα demo» για τη φωτογραφία· `true` μόνο με `ENVIRONMENT=development`, αλλιώς η εφαρμογή δεν ξεκινά |
| `PHOTO_RECOGNIZER` / `PHOTO_CONTENT_FILTER` | `none` / `none` | ανά component: `demo` \| `olivegemma` και `demo` \| `real` (το `real` δεν υπάρχει ακόμα → 503). Κάθε `demo` μόνο με `ENVIRONMENT=development`· το `DEMO_MODE` γεμίζει όσα είναι `none` |
| `OLIVEGEMMA_DIR`, `_DTYPE`, `_THREADS`, `_TIMEOUT_S`, `_TOPK`, `_INGREDIENTS`, `_SHA256`, `_MAX_QUEUE`, `_PRELOAD`, `_LABEL_MAP_CSV` | βλ. `.env.example` | OliveGemma-3B από τοπικό φάκελο, εκτός σύνδεσης· βλ. «OliveGemma τοπικά» |
| `CANDIDATE_PREFIX_MIN` / `CANDIDATE_MIN_RATIO` | 4 / 0.75 | ΠΡΟΣΧΕΔΙΟ: κατώφλια των `alternatives` (ποτέ αυτόματη επιλογή) |
| `API_DOCS` | κενό | Swagger/OpenAPI εκτός production· απαγορεύεται σε production |
| `FOODS_CSV`, `FOOD_ALIASES_CSV` | demo αρχεία | σε production η εφαρμογή δεν ξεκινά με demo τρόφιμα |
| `DISPLAY_FOOD_GROUPS_CSV` | `display_food_groups.csv` | ΠΡΟΣΧΕΔΙΟ: ετικέτες, `shown`, σειρά των 11 ομάδων |
| `MEAL_BACKDATE_DAYS` | 1 | ΠΡΟΣΧΕΔΙΟ |
| `ALLOW_MEAL_DELETE` | `false` | ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ M07 |
| `COMPLETE_DAY_MODE` / `AUTO_COMPLETE_MIN_MEALS` | `declared` / 2 | ΠΡΟΣΧΕΔΙΟ, ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: `auto` = και η νυχτερινή εργασία |
| `EVALUATION_WINDOW_DAYS` | 7 | ΠΡΟΣΧΕΔΙΟ (ο rule engine θέλει ≥ 3 πλήρεις ημέρες) |
| `LLM_BASE_URL` + `LLM_MODEL` | κενά | Krikri· χωρίς αυτά μόνο σταθερά κείμενα |
| `MAX_PHOTO_BYTES` / `PHOTO_MAX_EDGE_PX` | 1048576 / 448 | αυστηρά στον server |
| `PHOTO_REJECT_LIMIT` / `..._WINDOW_HOURS` / `PHOTO_SUSPENSION_HOURS` | 5 / 24 / 24 | ΠΡΟΣΧΕΔΙΟ |
| `FORWARDED_ALLOW_IPS` | `172.28.0.0/24` | από πού εμπιστευόμαστε X-Forwarded-For (ο Nginx)· ποτέ `*` |

## OliveGemma τοπικά (πραγματική αναγνώριση, CPU)

Τα βάρη (`JamesZar/OliveGemma-3B`, 6,07 GB BF16, άδεια Gemma) μπαίνουν στο `models/olivegemma-3b/` (εκτός git· το
`.gitignore` αγνοεί `models/` και `*.safetensors`). Το commit της έκδοσης γράφεται στο `models/olivegemma-3b/REVISION.txt`
και μπαίνει στο audit ως `model_id` (`OliveGemma-3B@<rev>`). Το μοντέλο φορτώνεται **μόνο** από τον τοπικό φάκελο
(`HF_HUB_OFFLINE=1`, `local_files_only=True`, `trust_remote_code=False`): καμία κλήση δικτύου.

```bash
ENVIRONMENT=development PHOTO_RECOGNIZER=olivegemma PHOTO_CONTENT_FILTER=demo uvicorn app.main:app
PHOTO_RECOGNIZER=olivegemma scripts/demo_backend.sh      # ίδιο, μέσα στο demo
```

- Τα demo φίλτρα (NSFW που επιτρέπει τα πάντα, φίλτρο φωτεινότητας) μένουν γιατί τα πραγματικά δεν υπάρχουν ακόμα·
  γι' αυτό επιτρέπεται μόνο σε `development`. Το audit γράφει `pipeline: "mixed"` και το `/admin/system-status`
  δείχνει `photo_components: {nsfw: demo, food_gate: demo, recognizer: real}`.
- Φόρτωση στο πρώτο αίτημα (ή στην εκκίνηση με `OLIVEGEMMA_PRELOAD=true`). Αν τα βάρη λείπουν ή το
  `OLIVEGEMMA_SHA256` δεν ταιριάζει: `WARNING` στο log και η φωτογραφία δίνει `503 photo_unavailable`, όχι απόρριψη.
- Ένα inference τη φορά. Με πάνω από `OLIVEGEMMA_MAX_QUEUE` σε αναμονή: `503 {"photo_busy": true}` (δεν μετρά στην
  αναστολή). Timeout (`OLIVEGEMMA_TIMEOUT_S`): απόρριψη με λόγο `recognizer_timeout` μόνο στο audit.
- **Χρόνος:** σε CPU χωρίς AVX-512 (Ryzen 7 3700U, BF16) μετρήθηκαν **~26 λεπτά ανά φωτογραφία** και 7,5 GB RSS
  (16/11/2026, ίδιο top-1 με την T4 του Colab σε 6/6), πολύ πάνω από τον στόχο των λίγων δευτερολέπτων· ο πιλότος
  τρέχει σε GPU του ΑΠΘ. Τοπικά βάλε `OLIVEGEMMA_TIMEOUT_S=2400`. Μέτρηση:
  `scripts/bench_olivegemma.py --images <φάκελος> --out <csv> [--results olivegemma_results.csv]` (ελέγχει πρώτα τη
  διαθέσιμη μνήμη· χρειάζονται ≥ 7 GiB).
- Το `data/olivegemma_label_map.csv` είναι ΠΡΟΣΧΕΔΙΟ για τον demo πίνακα (ετικέτα → `food_id`)· διαβάζονται μόνο οι
  στήλες `olivegemma_label` και `food_id`.

## Tests

```bash
cd backend && python -m pytest -q tests -m "not model"  # όλα (unit, api, integration) χωρίς το πραγματικό μοντέλο
python -m pytest -q tests -m model                      # φορτώνει το OliveGemma (λεπτά, ~7 GB)· skip χωρίς βάρη
python -m pytest -q tests/integration/test_photo_ephemeral.py   # 1000 uploads, κανένα αρχείο (Κανόνας 7)
```

Τα tests του API τρέχουν με SQLite in-memory και `TestClient`· δεν χρειάζονται `.env` (ορίζουν μόνα τους
`ENVIRONMENT=test`, ή `development` όσα ζητούν `DEMO_MODE=true`).

### Tests σε PostgreSQL (append-only triggers)

Τα triggers του `audit_log` και του `alert_events` ελέγχονται και σε πραγματική PostgreSQL
(`tests/api/test_postgres_triggers.py`, marker `postgres`): `alembic upgrade head` + `alembic check` σε κενή βάση και
μετά `UPDATE`, `DELETE`, `TRUNCATE` με ακατέργαστο SQL, που πρέπει να αποτύχουν. Χωρίς `PG_TEST_URL` τα tests αυτά
παραλείπονται (skip με μήνυμα). Δεν χρειάζεται νέα εξάρτηση: το `psycopg` είναι ήδη στο `pyproject.toml`.

```bash
PW=$(openssl rand -hex 12)
podman run -d --rm --name pyramid_pg_test -e POSTGRES_PASSWORD=$PW -p 127.0.0.1:5433:5432 postgres:16-alpine   # ή docker
export PG_TEST_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:5433/postgres"
cd backend && python -m pytest -q -m postgres tests
podman stop pyramid_pg_test
```

Η βάση του `PG_TEST_URL` πρέπει να είναι **κενή**: αν έχει πίνακες, τα tests αρνούνται να τρέξουν. Ποτέ τη βάση της
μελέτης.
