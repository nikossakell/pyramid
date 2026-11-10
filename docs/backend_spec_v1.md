# Προδιαγραφή backend v1 (Φάση 6)

Αποθηκεύτηκε: 09/11/2026. Η αρχική προδιαγραφή είναι αυτούσια στο τέλος. Οι **τροποποιήσεις** που
συμφωνήθηκαν μετά το Στάδιο 0 είναι αμέσως παρακάτω και **υπερισχύουν** του αρχικού κειμένου όπου
διαφέρουν. Η αιτιολόγηση των αποφάσεων γράφεται στο `docs/decisions/2026-11-xx_backend.txt`.

## Τροποποιήσεις μετά το Στάδιο 0 (09/11/2026)

1. **Ρυθμίσεις: κρατιούνται τα ονόματα του υπάρχοντος `.env.example` / docker-compose.**
   - `ENV` → `ENVIRONMENT` με τιμές `development | test | production`.
   - `KEY_PEPPER` → `ACCESS_KEY_PEPPER`.
   - `TOKEN_TTL_HOURS=24` → `ACCESS_TOKEN_TTL_MINUTES=720` (ΠΡΟΣΧΕΔΙΟ).
   - Όριο σώματος φωτογραφίας: `MAX_PHOTO_BYTES=1048576` (αντί για 1.000.000).
   - Μεγαλύτερη πλευρά: `PHOTO_MAX_EDGE_PX=448`, **αυστηρά** στον server (> 448 px → απόρριψη), ίδιο με το
     όριο του browser στο DPIA.
   - Νέα: `ADMIN_TOKEN`, `DEMO_MODE`, `CONTROL_ACCESS_FROM`, `APP_TIMEZONE`.
   - `FIELD_ENCRYPTION_KEY` αφαιρείται: κανένα `docs/*.md` δεν υπόσχεται κρυπτογράφηση πεδίων.
2. **Εξαρτήσεις.** Ακριβείς εκδόσεις (`==`) για όσα είναι εγκατεστημένα στο venv (web stack, Pillow). Το numpy
   όχι: η εγκατεστημένη 2.5.4 θέλει Python ≥ 3.12, ενώ το Dockerfile χτίζει με 3.11. ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ, με
   σύσταση: ίδια Python 3.12 σε venv και Docker (το RAG δεν χρειάζεται rebuild αν μείνει `chromadb==1.5.9`).
3. **Deployment.** `docker-compose.prod.yml`: `--workers 1` (το όριο αποτυχιών login είναι in-memory),
   `--proxy-headers --forwarded-allow-ips='*'` (το backend είναι μόνο στο εσωτερικό δίκτυο, πίσω από τον Nginx),
   `--no-access-log` (R6: το access log του uvicorn γράφει το query string).
4. **Alerts.** Νέο πεδίο `kind = safety | operational`. Μόνο τα ανοιχτά (`status ≠ closed`) alerts με
   `kind = safety` δίνουν `SafetySignals(RiskLevel.HIGH, category)` στο `/feedback/today`. **Κανένα αυτόματο
   alert.** Τα alerts δημιουργούνται μόνο με CLI: `scripts/create_alert.py --participant … --kind … --category …`.
5. **Αναστολή φωτογραφίας.** Μετά από 5 απορρίψεις σε 24 ώρες (ΠΡΟΣΧΕΔΙΟ): αναστολή για
   `PHOTO_SUSPENSION_HOURS=24` (ΠΡΟΣΧΕΔΙΟ), με `participants.photo_suspended_until`. Οι απορρίψεις μετριούνται από
   τα `photo_rejected` του audit_log. Κατά την αναστολή το upload παίρνει 403 `{"photo_unavailable": true}`,
   χωρίς επεξεργασία, και δεν μετρά ως απόρριψη· το `/me` δίνει `photo_available: false`. Η αναστολή **δεν**
   δημιουργεί alert: γράφεται μόνο στο audit (`photo_suspended`) και φαίνεται στο νέο admin endpoint
   `GET /admin/photo-suspensions` (μόνο κωδικός, έως πότε, πλήθος απορρίψεων).
6. **Ομάδα ελέγχου.** Κατά το πρωτόκολλο δεν χρησιμοποιεί την εφαρμογή κατά τη μελέτη: login με `arm=control`
   → 403 `{"detail": "not_yet_available"}` μέχρι το `CONTROL_ACCESS_FROM` (ημερομηνία στη ζώνη `APP_TIMEZONE`,
   ΠΡΟΣΧΕΔΙΟ· κενό = πάντα 403). Από εκείνη την ημερομηνία: πλήρεις λειτουργίες. Ο ίδιος έλεγχος γίνεται σε
   κάθε αίτημα με token. Tests και για τις δύο περιπτώσεις.
7. **Ζώνη ώρας και ημέρες.** `APP_TIMEZONE=Europe/Athens` (ΠΡΟΣΧΕΔΙΟ) για το «σήμερα», το backdate, τις ημέρες
   και το job. Το `/days/{day}/complete` έχει το ίδιο παράθυρο με το `MEAL_BACKDATE_DAYS`. Το
   `/feedback/today` ξαναχρησιμοποιεί το σημερινό feedback_record αν δεν άλλαξαν γεύματα ή ημέρες από τότε.
8. **Δομή αρχείων.** Ονόματα της προδιαγραφής. Τα κενά placeholders του σκελετού (12/10) που αντικαθίστανται
   διαγράφονται· όσα αφορούν μελλοντικές λειτουργίες μένουν ανέγγιχτα (`api/webhooks.py`,
   `services/notification_service.py`, `jobs/scheduler.py`, `jobs/safety_monitoring.py`,
   `ai_pipeline/vision/*`, `ai_pipeline/pipeline.py`, `ai_pipeline/config.py`). Tests: συμπληρώνονται τα
   placeholders `tests/unit/test_food_resolver.py`, `tests/unit/test_access_keys.py`,
   `tests/integration/test_photo_ephemeral.py`, `tests/integration/test_photo_bypass.py` (τα παραθέτουν τα docs
   και το DPIA)· τα υπόλοιπα tests στο `tests/api/`.
9. **Test ephemeral:** 1000 uploads, όπως γράφει το `docs/ephemeral-processing.md` (όχι 200).
10. **Audit events φωτογραφίας:** `photo_processed` / `photo_rejected`, πάντα με `stored_bytes: 0`
    (`docs/ephemeral-processing.md`).
11. **Ηλικία:** `age_years_at_enrollment` + ολόκληρα έτη από την εγγραφή· μέσα σε 12 εβδομάδες είναι πάντα η
    ηλικία εγγραφής (αναπόφευκτο χωρίς ημερομηνία γέννησης, R2). Το CLI δέχεται μόνο 10–16.
12. **Τρόφιμα:** μία κύρια ομάδα ανά τρόφιμο (`vegetables, fruit, legumes, whole_grains, dairy, fish, nuts, meat,
    eggs, processed_meat, salty_snacks`)· οι υποομάδες του `food_groups.csv` μόνο στα μηνύματα.
13. **Docs:** στο Στάδιο 5 ενημερώνονται τα `docs/api.md` και `docs/ephemeral-processing.md`. Στο τέλος: λίστα
    των σημείων του DPIA / GDPR που διαφέρουν πλέον από τον κώδικα.
14. **Alembic:** το placeholder `001_initial_schema.py` αντικαθίσταται από το autogenerate, με revision `001` και
    χωρίς πίνακα ή στήλη εικόνας (το παραθέτει το `docs/ephemeral-processing.md`).
15. **IP πίσω από τον Nginx (10/11/2026).** Όχι `--forwarded-allow-ips=*`: το backend εμπιστεύεται X-Forwarded-For
    μόνο από `FORWARDED_ALLOW_IPS` (`.env`, προεπιλογή το σταθερό subnet του δικτύου του compose, `172.28.0.0/24`).
    Το backend δεν κάνει publish θύρα. Ο Nginx **αντικαθιστά** το header: `proxy_set_header X-Forwarded-For
    $remote_addr;` (όχι `$proxy_add_x_forwarded_for`). Test: ψεύτικο X-Forwarded-For δεν αλλάζει την IP του ορίου.
16. **Όριο αποτυχιών login (10/11/2026):** `LOGIN_MAX_FAILURES=30` ανά `LOGIN_WINDOW_MINUTES=15` (ΠΡΟΣΧΕΔΙΟ, αντί
    για 5): κοινή IP σε ακαδημίες/σχολεία· με κλειδιά ≥ 60 bit οι δοκιμές είναι μη ρεαλιστικές και με χαλαρό όριο.
17. **Υποδομή για το `/api/v1` (Στάδιο 2).** Nginx: `location = /api/v1/meals/photo` και `location /api/v1/admin/`
    (χωρίς το `/v1` ούτε το buffer του Κανόνα 7 ούτε το allow/deny του VPN έπιαναν)· access log με `$uri`, χωρίς
    query string (R6). Dockerfile: `HEALTHCHECK` στο `/api/v1/health`, `CMD` με `--workers 1 --no-access-log`.
    docker-compose: επιπλέον mount `./data:/data:ro`, γιατί στο container ο κώδικας είναι στο `/app` και το
    `ai_pipeline/presentation/lexicon.py` διαβάζει από το `parents[3]/data` = `/data`.
18. **Πίνακας τροφίμων (Στάδιο 2).** Στήλες θρεπτικών `<nutrient_id>__<μονάδα>` (π.χ. `sodium__g`), ώστε ο loader και
    το test να ελέγχουν τη μονάδα έναντι του `efsa_drv.csv`. «Πλήρης ημέρα» μόνο με τουλάχιστον ένα γεύμα
    (ΠΡΟΣΧΕΔΙΟ). `GET /meals`: προεπιλογή σήμερα, εύρος έως 31 ημέρες (ΠΡΟΣΧΕΔΙΟ). Διαγραφή κλειστή: 403
    `meal_delete_disabled`· ανοιχτή: ξένο γεύμα 404.
19. **Ανατροφοδότηση (Στάδιο 3).** Παράθυρο: σήμερα και οι `EVALUATION_WINDOW_DAYS − 1` προηγούμενες ημέρες. Το `id`
    κάθε μηνύματος είναι UUID (uuid5 του feedback_record και της θέσης), ώστε να μην αποκαλύπτει κανόνα ή κατάσταση.
    Krikri μόνο με `LLM_BASE_URL` και `LLM_MODEL`· αναμονή ανά μήνυμα `PRESENTER_TIMEOUT_SECONDS=20` (ΠΡΟΣΧΕΔΙΟ).
    Ημέρα με τρόφιμο που δεν υπάρχει πια στον πίνακα: όχι πλήρης. Ηλικία εκτός 10–16: καμία ανατροφοδότηση
    (audit `feedback_unavailable`). Test R1: κανένα ψηφίο στα κείμενα **εκτός από το όνομα θρεπτικού «βιταμίνη B12»**,
    που ο validator του 4.2 εξαιρεί ρητά (δεν είναι αριθμητική τιμή).
20. **Φωτογραφία και κείμενο (Στάδιο 4).** Αν λείπει έστω ένα από NSFW / food gate #2 / αναγνώριση: 503
    `{"photo_unavailable": true}` (δεν επεξεργάζεται τίποτα, δεν μετρά ως απόρριψη). Κάθε άλλο σφάλμα ή άρνηση
    φίλτρου: 422 `{"rejected": true}`, και **κάθε** λόγος μετρά στο όριο αναστολής. «σίγουρο» μόνο με βεβαιότητα ≥
    `PHOTO_CONFIDENT_MIN=0.80` (ΠΡΟΣΧΕΔΙΟ) **και** αντιστοίχιση exact/alias. Κείμενο: η ντετερμινιστική υλοποίηση δεν
    είναι μοντέλο, άρα ισχύει και χωρίς DEMO_MODE· αγνοεί αρχικές λέξεις ποσότητας/άρθρα («ένα μήλο»)· ό,τι δεν
    βρίσκεται επιστρέφεται με `food_id: null`. Demo: NSFW που επιτρέπει τα πάντα, food gate φωτεινότητας < 10,
    σταθερή αναγνώριση.
21. **Κάρτες και admin (Στάδιο 5).** Νυχτερινή εργασία: προεπιλογή η χθεσινή ημέρα. `/cards` χωρίς κανόνα ή λόγο.
    `/ask` απαιτεί JWT και δίνει 501. Οι ημερομηνίες του admin σε UTC με ζώνη. Τα placeholders `app/api/game.py`,
    `app/api/webhooks.py` (decks, μάχες, Unity) μένουν για μελλοντική φάση.
22. **Swagger για demo.** `/docs` και `/openapi.json` εκτός production (`API_DOCS`· σε production δεν επιτρέπεται).
    Authorize με `ChildJWT` (bearer) και `AdminToken` (`X-Admin-Token`), upload `image/jpeg` στο `/meals/photo`,
    παραδείγματα του `/meals/confirm` με τη σημερινή ημερομηνία. Demo με μία εντολή: `scripts/demo_backend.sh`
    (`make demo`), δεδομένα από το `scripts/seed_demo.py` (μόνο με DEMO_MODE).

## Αρχική προδιαγραφή (αυτούσια)

```text
Πλαίσιο: PYRAMID (διπλωματική, ΑΠΘ). PWA διατροφικής καταγραφής για παιδιά 10–16 ετών, πιλοτική μελέτη 12 εβδομάδων.
Υπάρχουν ήδη στο repo:
- backend/rule_engine/ (Φάση 2, ντετερμινιστική μηχανή κανόνων, frozen dataclasses)
- backend/ai_pipeline/presentation/ (4.1 KrikriPresenter, 4.2 safety_validator, templates)
- backend/ai_pipeline/text/krikri_client.py (OpenAI-compatible client + ScriptedClient)
- backend/ai_pipeline/rag/ (5.1)
- docs/decisions/*.txt (αποφάσεις με αιτιολόγηση)
ΔΙΑΒΑΣΕ ΠΡΩΤΑ: backend/rule_engine/{models,evaluation,engine,card_rules,safety_rules}.py,
backend/ai_pipeline/presentation/krikri_presenter.py, data/efsa_drv.csv (στήλη unit), data/food_groups.csv,
docs/decisions/*.txt.

ΣΤΟΧΟΣ: Φάση 6 του πλάνου, το backend (FastAPI), στη δομή backend/app/ (api/, core/, db/, schemas/, services/, jobs/).
Τα μοντέλα AI (OliveGemma, Krikri-extractor, NSFW, food gate #2) ΔΕΝ υπάρχουν ακόμα: μπαίνουν ως interfaces
(typing.Protocol) με demo υλοποιήσεις που ενεργοποιούνται ΜΟΝΟ με DEMO_MODE=true.

========================================================================================================
ΑΜΕΤΑΚΙΝΗΤΟΙ ΚΑΝΟΝΕΣ (αν κάτι παρακάτω συγκρούεται με αυτούς, σταμάτα και ρώτα με)
R1  Καμία αριθμητική τιμή θρεπτικού, ενέργειας, βάρους, γραμμαρίων ή ποσοστού σε απάντηση προς το παιδί.
    Τα research_values του rule engine μένουν μόνο στη βάση (audit). Test: καμία απάντηση των endpoints
    του παιδιού (εκτός από ids/ημερομηνίες) δεν περιέχει θρεπτικές τιμές.
R2  Ο server γνωρίζει ΜΟΝΟ κωδικό συμμετέχοντα (UUID). Κανένα όνομα, email, τηλέφωνο, ημερομηνία γέννησης.
R3  Μόνο επιβεβαιωμένα από το παιδί γεύματα αποθηκεύονται (Κανόνας 3). Οι προτάσεις AI δεν αποθηκεύονται ποτέ.
R4  Φωτογραφίες (Κανόνες 7-8): raw body image/jpeg ≤ 1.000.000 bytes, ΟΧΙ multipart/UploadFile (γράφει σε δίσκο
    πάνω από ~1 MB), μόνο στη RAM, ποτέ σε δίσκο, βάση ή log. Σειρά: πρόσβαση → μορφή (υπογραφή FF D8 FF, Pillow
    με MAX_IMAGE_PIXELS, μεγαλύτερη πλευρά ≤ 460 px, νέα κωδικοποίηση στη RAM) → NSFW → food/non-food #2 →
    αναγνώριση. Fail-closed σε κάθε σφάλμα ή απουσία φίλτρου. ΙΔΙΟ status (422) και ΙΔΙΟ σώμα {"rejected": true}
    για κάθε λόγο απόρριψης. Ο λόγος μόνο στο audit. Μετρητής απορρίψεων: μετά από 5 σε 24 ώρες (ΠΡΟΣΧΕΔΙΟ),
    αναστολή φωτογραφίας για τον κωδικό (κείμενο και αναζήτηση μένουν).
R5  Audit (Κανόνας 5): append-only πίνακας. Ποτέ bytes εικόνας, ποτέ access key, ποτέ token.
R6  Logging χωρίς σώμα αιτήματος και χωρίς headers Authorization.
R7  Όλα τα κατώφλια/όρια είναι σταθερές ή settings με σχόλιο «ΠΡΟΣΧΕΔΙΟ».
R8  ΜΗΝ αλλάξεις τίποτα στα backend/rule_engine/, backend/ai_pipeline/ (εκτός από νέο αρχείο food_resolver.py),
    data/efsa_drv.csv, data/rag_sources.csv, backend/rag_db/. Αν κάτι εκεί χρειάζεται αλλαγή, ρώτα με.
R9  Δείξε μου diff πριν γράψεις στο repo. ΜΗΝ κάνεις commit.

========================================================================================================
ΤΕΧΝΟΛΟΓΙΑ
FastAPI, SQLAlchemy 2.x (sync), Alembic, pydantic-settings, PyJWT, Pillow, uvicorn. Για tests: pytest, httpx
(TestClient), SQLite in-memory. Για παραγωγή: PostgreSQL (psycopg). Πρόσθεσε τις εξαρτήσεις στο pyproject.toml με
ΑΚΡΙΒΕΙΣ εκδόσεις (==) όπως εγκαθίστανται στο venv (πάγωμα για τις 12 εβδομάδες).

========================================================================================================
ΣΧΕΔΙΑΣΜΟΣ

Ρυθμίσεις (app/config.py, pydantic-settings, από env/.env):
ENV (dev|test|prod), DATABASE_URL, JWT_SECRET, KEY_PEPPER, ADMIN_TOKEN, TOKEN_TTL_HOURS=24 (ΠΡΟΣΧΕΔΙΟ),
DEMO_MODE=false, FOODS_CSV, FOOD_ALIASES_CSV, EVALUATION_WINDOW_DAYS=7 (ΠΡΟΣΧΕΔΙΟ), LLM_BASE_URL/LLM_MODEL
(προαιρετικά· αν λείπουν, ο presenter δίνει μόνο σταθερά κείμενα), CORS_ORIGINS, MEAL_BACKDATE_DAYS=1 (ΠΡΟΣΧΕΔΙΟ).
Στο ENV=prod η εφαρμογή ΑΡΝΕΙΤΑΙ να ξεκινήσει αν: DEMO_MODE=true, μυστικά < 32 χαρακτήρες, υπάρχουν demo τρόφιμα,
CORS="*". Το .env.example χωρίς πραγματικά μυστικά. Το .env στο .gitignore.

Πρόσβαση (app/core/security.py):
- Κλειδί πρόσβασης: τυχαίο, ≥ 60 bit, π.χ. 12 χαρακτήρες Crockford base32 σε μορφή XXXX-XXXX-XXXX.
- Στη βάση μόνο HMAC-SHA256(KEY_PEPPER, κανονικοποιημένο κλειδί), για αναζήτηση. Τα κλειδιά είναι τυχαία με υψηλή
  εντροπία, άρα δεν χρειάζεται αργό hash τύπου argon2. Το κλειδί εμφανίζεται ΜΙΑ φορά, στη δημιουργία.
- POST /api/v1/auth/login → JWT (sub = pseudonym_id, tv = token_version, exp). Γενικό μήνυμα σφάλματος.
  Όριο: 5 αποτυχίες ανά IP σε 15 λεπτά (ΠΡΟΣΧΕΔΙΟ, in-memory· σημείωσε ότι απαιτεί έναν worker).
- Ανάκληση: participants.active=false ή αύξηση token_version (ανάκληση συγκατάθεσης, M10) → 401.
- Δημιουργία συμμετεχόντων ΜΟΝΟ με CLI (scripts/create_participant.py), όχι με API.
  Ορίσματα: --sex, --age-years, --arm intervention|control. Τυπώνει pseudonym_id και κλειδί μία φορά.

Βάση (app/db/models/):
- participants: id (UUID), key_hmac (unique), sex, age_years_at_enrollment, enrollment_date, arm, active,
  token_version, avatar_id (nullable), photo_suspended_until (nullable), created_at.
  ΟΧΙ βάρος/ύψος: η Αρχιτεκτονική v0.4 κρατά τα βιομετρικά στο χαρτί. Άρα ο κανόνας πρωτεΐνης δίνει
  insufficient_data, και αυτό είναι αναμενόμενο. Βάλε σχόλιο ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ.
- meals: id, participant_id, eaten_on (date), meal_slot (breakfast|morning_snack|lunch|afternoon_snack|dinner|snack),
  source (camera|text|manual), created_at, deleted_at (nullable).
- meal_items: id, meal_id, food_id, portion (small|medium|large), grams (υπολογίζει ο server), ai_suggested (bool).
- day_status: participant_id, day, completed, completed_at (unique participant+day).
- feedback_records: id, participant_id, as_of, engine_audit (JSON), presented (JSON), created_at.
- card_drops: id, participant_id, day, rule_id, rule_version, tier, reason, opened_at (unique participant+day+rule_id).
- alerts: id, participant_id, category, status (new|in_progress|closed), created_at, updated_at, note.
  Μόνο κωδικός και κατηγορία, ποτέ κείμενο συνομιλίας.
- audit_log: id, ts, participant_id (nullable), event, payload (JSON). Η εφαρμογή ΔΕΝ κάνει update/delete εδώ.

Τρόφιμα (στατικά δεδομένα, όχι πίνακας DB):
- ΔΕΝ υπάρχει ακόμα πραγματική βάση σύνθεσης. Δημιούργησε data/demo_foods.csv με ~20 κοινά τρόφιμα.
  Στήλες: food_id, name_el, food_group (κωδικοί από data/food_groups.csv, π.χ. legumes, dairy, meat, fish,
  vegetables, fruit, whole_grains, processed_meat, salty_snacks), portion_small_g, portion_medium_g,
  portion_large_g, θρεπτικά ανά 100 g για iron, calcium, sodium, fibre, protein, vitamin_a, vitamin_c,
  folate, vitamin_d, vitamin_b12, source, is_demo.
  Οι ΜΟΝΑΔΕΣ ΠΡΕΠΕΙ να ταιριάζουν με τον αριθμητή της στήλης unit του data/efsa_drv.csv: π.χ. sodium σε g,
  vitamin_a σε ug_RE, folate σε ug_DFE, protein σε g. Γράψε test που το ελέγχει.
  Κάθε γραμμή: source="DEMO — ΟΧΙ πραγματικές τιμές", is_demo=true.
  Στο docstring του loader: οι τιμές είναι ενδεικτικές, δεν χρησιμοποιούνται ποτέ για την έρευνα.
- data/demo_food_aliases.csv: food_id, alias (ελληνικά συνώνυμα, π.χ. «μακαρόνια με κιμά»).
- Loader με sha256 κάθε αρχείου (μπαίνει στα data_versions του engine και στο audit).
- backend/ai_pipeline/food_resolver.py (Βήμα 3.3, ντετερμινιστικό): κανονικοποίηση (πεζά, χωρίς τόνους, ς→σ·
  ξαναχρησιμοποίησε το normalize του presentation/lexicon.py) → ακριβές όνομα → alias →
  fuzzy (difflib ratio ≥ 0.85, ΠΡΟΣΧΕΔΙΟ, όπως το final_plan) → None.
  Υποστήριξε και search(q, limit=10) για αυτόματη συμπλήρωση.

Endpoints παιδιού (prefix /api/v1, όλα με JWT εκτός από login/health):
- GET  /health
- POST /auth/login
- GET  /me → {arm, avatar_id, photo_available}. ΚΑΜΙΑ άλλη πληροφορία.
- PATCH /me {avatar_id}
- GET  /foods/search?q= → [{food_id, name_el, food_group}]. ΟΧΙ θρεπτικά.
- POST /meals/photo (raw image/jpeg) → {suggestions:[{food_id|null, name_el, label_en?, confidence_word: "σίγουρο"|"ίσως"}], needs_confirmation:true}
  ή απόρριψη κατά R4. Pipeline με Protocols ContentFilter και FoodRecognizer (app/services/photo_pipeline.py).
  Αν δεν έχουν ρυθμιστεί και DEMO_MODE=false: 503 {"photo_unavailable": true}. Demo: φίλτρο που απορρίπτει όταν
  ο μέσος όρος φωτεινότητας είναι < 10 (για να δοκιμάζεται η απόρριψη)· recognizer που επιστρέφει σταθερή πρόταση.
- POST /meals/text {text ≤ 300 χαρακτήρες} → ίδια μορφή προτάσεων. Interface TextExtractor (μελλοντικά Krikri, 3.2).
  Demo / προσωρινή υλοποίηση: ντετερμινιστική, με το food_resolver πάνω σε τμήματα του κειμένου
  (χωρίζονται με «και», «με», κόμμα). Δεν αποθηκεύει τίποτα.
- POST /meals/confirm {eaten_on, meal_slot, source, items:[{food_id, portion, ai_suggested}]} → αποθήκευση.
  Έλεγχοι: food_id υπάρχει· 1–10 items· eaten_on από σήμερα έως MEAL_BACKDATE_DAYS πριν· portion έγκυρο.
  Τα grams από τις στήλες portion_*_g του τροφίμου. Audit "meal_confirmed".
- GET  /meals?from=&to= → τα γεύματα ΜΟΝΟ του ίδιου παιδιού (όνομα τροφίμου + μερίδα ως λέξη, ΟΧΙ γραμμάρια).
- DELETE /meals/{id} → soft delete + audit, ΜΟΝΟ αν ALLOW_MEAL_DELETE=true (προεπιλογή false, ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ M07).
- POST /days/{day}/complete → day_status (ΠΡΟΣΧΕΔΙΟ: η «πλήρης ημέρα» τη δηλώνει το παιδί).
- GET  /feedback/today → εκτελεί NutritionRuleEngine σε EVALUATION_WINDOW_DAYS ημέρες (συνήθης πρόσληψη, ΟΧΙ
  μόνο σήμερα), περνά από KrikriPresenter και επιστρέφει:
  {messages:[{id, text}], food_groups_today:[κωδικοί ομάδων που εμφανίστηκαν σήμερα]}.
  ΧΩΡΙΣ rule_id, status, αριθμούς. Αποθηκεύει feedback_record (engine.audit_record() + presenter audit) και audit.
  Χτίσιμο EvaluationContext:
  · UserProfile(pseudonym_id, sex, ηλικία = age_years_at_enrollment + ολόκληρα έτη από enrollment_date,
    weight_kg=None);
  · MealEntry με logged_at = eaten_on στις 12:00, γιατί το evaluation ομαδοποιεί με βάση την ημερομηνία
    του logged_at· επιβεβαίωσέ το διαβάζοντας το evaluation.py·
  · is_complete από day_status;
  · data_versions = sha256 των CSV.
  Ασφάλεια: αν ο συμμετέχων έχει alert με status ≠ closed → SafetySignals(RiskLevel.HIGH, category). Έτσι
  καμία ανατροφοδότηση πρόσληψης δεν φτάνει στο παιδί μέχρι να κλείσει το alert (ΠΡΟΣΧΕΔΙΟ, έγκριση παιδίατρου).
- GET  /cards → οι κάρτες του παιδιού {id, tier, day, opened}. POST /cards/{id}/open.
- POST /ask → 501 {"not_implemented": "5.2"} (το RAG Q&A έρχεται μετά το backend).

Admin (prefix /api/v1/admin, header X-Admin-Token = ADMIN_TOKEN· σχόλιο ότι το Nginx τα επιτρέπει μόνο από VPN ΑΠΘ):
- GET /alerts, POST /alerts/{id}/status {status, note}
- POST /participants/{id}/deactivate (ανάκληση συγκατάθεσης: active=false, token_version += 1)
Τίποτα που να επιστρέφει γεύματα ή κείμενα παιδιών.

Νυχτερινή εργασία app/jobs/daily_card_drops.py (`python -m app.jobs.daily_card_drops --date YYYY-MM-DD`):
για κάθε ενεργό συμμετέχοντα της ομάδας παρέμβασης φτιάχνει DayActivity (επιβεβαιωμένα γεύματα, completed,
ομάδες τροφίμων) με ιστορικό, καλεί rule_engine.card_rules.card_drops, και κάνει idempotent εισαγωγή
(δεύτερη εκτέλεση = καμία διπλή κάρτα).

Logging (app/core/logging.py): μέθοδος, path, status, διάρκεια, pseudonym_id αν υπάρχει. Ποτέ body, query
του /foods/search ή του /meals/text, Authorization.

Alembic: αρχική μετάβαση με autogenerate, που ελέγχεις χειροκίνητα. Test: `alembic upgrade head` σε καινούργια SQLite.

========================================================================================================
TESTS (backend/tests/api/, SQLite in-memory, TestClient)
- auth: σωστό/λάθος κλειδί, ανενεργός, ληγμένο token, token_version, όριο αποτυχιών, κλειδί όχι σε audit/log.
- απομόνωση: το παιδί Α δεν βλέπει, δεν διαγράφει και δεν ανοίγει δεδομένα του Β (404, όχι 403).
- meals: επικύρωση εισόδου, grams από μερίδα, R3 (το /meals/photo και το /meals/text δεν γράφουν στη βάση).
- feedback: με συνθετικά γεύματα δίνει μηνύματα. Κανένα ψηφίο στα text (R1). Ανοιχτό alert → κανένα μήνυμα.
  feedback_record με research_values μόνο στη βάση.
- photo, όλα από το 7.1 του πλάνου:
  · χωρίς token → 401· λάθος Content-Type· ψεύτικη υπογραφή· PNG· > 1 MB· > 460 px· decompression bomb·
    φίλτρο που πετά exception → απόρριψη·
  · το σώμα και το status είναι ΙΔΙΑ για κάθε λόγο απόρριψης·
  · μετά από 5 απορρίψεις → αναστολή·
  · DEMO_MODE=false χωρίς φίλτρα → 503·
  · 200 uploads χωρίς νέο αρχείο στο tempfile.gettempdir() και στον φάκελο της εφαρμογής·
  · κανένα byte εικόνας σε audit/log.
- cards job: idempotent, μόνο για την ομάδα παρέμβασης.
- config: το ENV=prod με DEMO_MODE=true ή αδύναμα μυστικά ή demo τρόφιμα αποτυγχάνει στην εκκίνηση.
- admin: χωρίς/λάθος token → 401· καμία απάντηση δεν περιέχει γεύματα.
- food_resolver: ακριβές, alias, fuzzy, None· μονάδες demo_foods έναντι efsa_drv.
Όλα τα υπάρχοντα tests (backend/tests/unit/) πρέπει να συνεχίσουν να περνούν.

========================================================================================================
ΕΚΤΕΛΕΣΗ ΣΕ ΣΤΑΔΙΑ — μετά από κάθε στάδιο: τρέξε ΟΛΑ τα tests, δείξε σύνοψη diff και έξοδο tests, ΣΤΑΜΑΤΑ και
περίμενε «συνέχισε».
  0. Διάβασε τα αρχεία. Αποθήκευσε αυτή την προδιαγραφή στο docs/backend_spec_v1.md. Πες μου αν κάτι
     συγκρούεται με τον υπάρχοντα κώδικα (π.χ. υπογραφές συναρτήσεων, μονάδες).
  1. Σκελετός: config, db, models, alembic, security/login, audit, logging, /health, /me, CLI δημιουργίας + tests.
  2. Τρόφιμα: demo CSV, loader, food_resolver, /foods/search, /meals/confirm, /meals, /days + tests.
  3. Feedback: /feedback/today με engine + presenter + safety από alerts + tests.
  4. Φωτογραφία και κείμενο: photo_pipeline (Protocols, demo), /meals/photo, /meals/text, όρια, αναστολή + tests.
  5. Κάρτες και admin: job, /cards, admin endpoints, /ask 501 + tests. README backend (εκκίνηση με uvicorn,
     δημιουργία συμμετέχοντα, εκτέλεση job, μεταβλητές env).
Στο τέλος γράψε docs/decisions/2026-11-xx_backend.txt με τις αποφάσεις και τις ΑΝΟΙΧΤΕΣ ΑΠΟΦΑΣΕΙΣ:
βάρος, μερίδες σε γραμμάρια, πλήρης ημέρα, διαγραφή γεύματος, TTL token, όρια, ειδοποιήσεις.
```
