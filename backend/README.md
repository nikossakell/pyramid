# PYRAMID backend (Φάση 6)

FastAPI + SQLAlchemy 2 (sync) + Alembic. Προδιαγραφή: [`docs/backend_spec_v1.md`](../docs/backend_spec_v1.md)·
αποφάσεις και ανοιχτά θέματα: [`docs/decisions/2026-11-10_backend.txt`](../docs/decisions/2026-11-10_backend.txt).

```
app/
  api/        endpoints (/api/v1/...), docs.py: Swagger UI / OpenAPI
  core/       security (κλειδιά, JWT), audit (append-only), logging (χωρίς σώμα/query/headers), clock
  db/         μοντέλα SQLAlchemy, session
  schemas/    Pydantic (ό,τι βλέπει το παιδί: ποτέ αριθμοί θρεπτικών ή γραμμάρια)
  services/   λογική: auth, food_catalog, meal, feedback (rule engine + presenter), photo_pipeline, suggestion, card
  jobs/       daily_card_drops (νυχτερινή κατανομή καρτών)
```

## Demo με Swagger (μία εντολή)

```bash
scripts/demo_backend.sh            # ή: make demo
```

Φτιάχνει στο `/tmp/pyramid_demo` καινούργια βάση SQLite, τυχαία μυστικά, `DEMO_MODE=true`, τέσσερα demo παιδιά
(τυπώνει τα κλειδιά τους), το `X-Admin-Token` και δοκιμαστικές εικόνες, και ξεκινά τον server. Μετά:

1. Άνοιγμα <http://localhost:8000/docs> (το Swagger UI φορτώνεται από CDN: χρειάζεται internet).
2. `POST /api/v1/auth/login` με κλειδί → **Authorize** → `ChildJWT` → επικόλληση του `access_token`.
3. `/me`, `/foods/search`, `/meals/photo` (Try it out → επιλογή `meal.jpg`), `/meals/text`, `/meals/confirm`
   (τα παραδείγματα έχουν ήδη τη σημερινή ημερομηνία), `/days/{day}/complete`, `/feedback/today`, `/cards`.
4. **Authorize** → `AdminToken` με το `X-Admin-Token` → `/admin/alerts`, `/admin/photo-suspensions`.

| Παιδί | Τι δείχνει |
|---|---|
| Α (παρέμβαση, με ιστορικό) | `/feedback/today` με μηνύματα (χωρίς αριθμούς), κάρτες με streak |
| Β (παρέμβαση, χωρίς ιστορικό) | ζωντανή καταγραφή: φωτογραφία, κείμενο, επιβεβαίωση. `dark.jpg` / `too_big.jpg` → ίδιο `422`· μετά από 5 → `403` |
| Γ (ομάδα ελέγχου) | `403 not_yet_available` (με `CONTROL_ACCESS_FROM=$(date +%F) scripts/demo_backend.sh` μπαίνει κανονικά) |
| Δ (ανοιχτό safety alert) | `/feedback/today` χωρίς μηνύματα· κλείσιμο του alert από το admin → μηνύματα |

Επιλογές: `PORT=8080`, `HOST=0.0.0.0` (προβολή από άλλη συσκευή), `LLM_BASE_URL=... LLM_MODEL=...` (Krikri),
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
παρέμβασης. Προγραμματισμός (π.χ. 03:00): cron ή systemd timer στον host, με
`docker compose exec backend python -m app.jobs.daily_card_drops`.

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
| `APP_TIMEZONE` | `Europe/Athens` | «σήμερα», ημέρες, νυχτερινή εργασία |
| `DEMO_MODE` | `false` | demo φίλτρα/αναγνώριση φωτογραφίας· απαγορεύεται σε production |
| `API_DOCS` | κενό | Swagger/OpenAPI εκτός production· απαγορεύεται σε production |
| `FOODS_CSV`, `FOOD_ALIASES_CSV` | demo αρχεία | σε production η εφαρμογή δεν ξεκινά με demo τρόφιμα |
| `MEAL_BACKDATE_DAYS` | 1 | ΠΡΟΣΧΕΔΙΟ |
| `ALLOW_MEAL_DELETE` | `false` | ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ M07 |
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
