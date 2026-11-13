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
| `ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `DATABASE_URL` | — | `postgresql+psycopg://...` (production), `sqlite:///...` (τοπικά) |
| `JWT_SECRET`, `ACCESS_KEY_PEPPER`, `ADMIN_TOKEN` | — | ≥ 32 χαρακτήρες σε production |
| `ACCESS_TOKEN_TTL_MINUTES` | 720 | ΠΡΟΣΧΕΔΙΟ |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_MINUTES` | 30 / 15 | ανά IP, in-memory (ένας worker) |
| `CONTROL_ACCESS_FROM` | κενό | ομάδα ελέγχου: 403 μέχρι αυτή την ημέρα |
| `STUDY_DURATION_DAYS` | 84 | ΠΡΟΣΧΕΔΙΟ· μετά: 403 `{"study_ended": true}` για την ομάδα παρέμβασης |
| `POST_STUDY_ACCESS` | `false` | ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: πρόσβαση μετά το τέλος της μελέτης |
| `APP_TIMEZONE` | `Europe/Athens` | «σήμερα», ημέρες, νυχτερινή εργασία |
| `DEMO_MODE` | `false` | demo φίλτρα/αναγνώριση φωτογραφίας· απαγορεύεται σε production |
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

## Tests

```bash
cd backend && python -m pytest -q tests                 # όλα (unit, api, integration)
python -m pytest -q tests/integration/test_photo_ephemeral.py   # 1000 uploads, κανένα αρχείο (Κανόνας 7)
```

Τα tests του API τρέχουν με SQLite in-memory και `TestClient`· δεν χρειάζονται `.env`.
