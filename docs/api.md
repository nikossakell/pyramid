# API

> Status: v1 (Φάση 6). Η πλήρης, εκτελέσιμη αναφορά είναι το Swagger UI στο `/docs` (εκτός production·
> `scripts/demo_backend.sh` για demo). Προδιαγραφή: `docs/backend_spec_v1.md` (Τροποποιήσεις 23–40 για όσα
> προστέθηκαν στις 12–14/11/2026· αιτιολόγηση στο `docs/decisions/2026-11-12_backend_gaps.txt`).

Όλα τα endpoints έχουν prefix `/api/v1`. Το παιδί μπαίνει με **κλειδί πρόσβασης** (`POST /auth/login`) και παίρνει
JWT (bearer). Δεν υπάρχει εγγραφή μέσω API: οι συμμετέχοντες δημιουργούνται με `scripts/create_participant.py`.
Καμία απάντηση προς το παιδί δεν περιέχει αριθμητική τιμή θρεπτικού, γραμμαρίων ή ποσοστού (R1).

## Χωρίς token

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Η εφαρμογή και η βάση απαντούν. |
| POST | `/auth/login` | Κλειδί → JWT. Ίδιο `401` για κάθε αποτυχία· `429` μετά από πολλές αποτυχίες ανά IP, με header `Retry-After` (δευτερόλεπτα)· `403 {"detail": "not_yet_available"}` για την ομάδα ελέγχου πριν το `CONTROL_ACCESS_FROM`· `403 {"study_ended": true}` για την ομάδα παρέμβασης μετά το τέλος της μελέτης. |

Το `403 {"study_ended": true}` έρχεται και σε **κάθε** αίτημα με token, από την επομένη της τελευταίας ημέρας μελέτης
(`enrollment_date + STUDY_DURATION_DAYS − 1`), εκτός αν `POST_STUDY_ACCESS=true`.

## Παιδί (JWT)

| Method | Path | Notes |
|---|---|---|
| GET / PATCH | `/me` | Μόνο `{arm, avatar_id, photo_available, photo_status}`. `photo_status`: `available` / `suspended` / `unavailable` (το PWA δείχνει ίδιο κείμενο για τα δύο τελευταία). Avatar από κλειστή λίστα. |
| GET | `/food-groups` | Οι 11 κύριες ομάδες στη σειρά εμφάνισης: `[{code, label_el, shown, sort}]`. `shown=false`: όχι ως «ομάδα που είχες». `sort`: ακέραια σειρά εμφάνισης από το CSV (δεν είναι τιμή θρεπτικού· η μόνη ακέραια τιμή σε απάντηση προς το παιδί). |
| GET | `/foods/search?q=&group=` | `[{food_id, name_el, food_group}]`, χωρίς θρεπτικά. Με `group` και χωρίς `q`: τα τρόφιμα της ομάδας, αλφαβητικά (έως 50). Άγνωστη ομάδα: `422 unknown_group`. |
| POST | `/meals/photo` | Raw `image/jpeg` (όχι multipart), ≤ 1 MB, πλευρά ≤ 448 px. Προτάσεις, **τίποτα δεν αποθηκεύεται**. Κάθε απόρριψη: `422 {"rejected": true}`. Αναστολή: `403`· χωρίς φίλτρα: `503 {"photo_unavailable": true}`. |
| POST | `/meals/text` | `{text ≤ 300}` → ίδια μορφή προτάσεων. Τίποτα δεν αποθηκεύεται. |
| POST | `/meals/confirm` | `{client_meal_id, eaten_on, meal_slot, source, items, analysis_id?}` → `{meal_id, eaten_on, meal_slot, food_groups, created}`. Idempotent (βλ. παρακάτω). Τα γραμμάρια από τη μερίδα (server). |
| GET | `/meals?from=&to=` | Μόνο τα γεύματα του ίδιου παιδιού: `{meal_id, eaten_on, meal_slot, source, created_at, items:[{food_id, name_el, portion, food_group, ai_suggested}]}`. Χωρίς γραμμάρια. |
| DELETE | `/meals/{meal_id}` | Soft delete, μόνο με `ALLOW_MEAL_DELETE=true`· ξένο γεύμα `404`. |
| GET | `/days?from=&to=` | `[{day, completed}]` για κάθε ημέρα του εύρους (έως 31, προεπιλογή σήμερα). |
| POST | `/days/{day}/complete` | Δήλωση «πλήρης ημέρα» (με τουλάχιστον ένα γεύμα). Διαθέσιμη και με `COMPLETE_DAY_MODE=auto`· υπερισχύει. |
| GET | `/feedback/today` | `{messages:[{id, text}], food_groups_today}`· rule engine 7 ημερών + presenter + ασφάλεια. `food_groups_today`: μόνο ομάδες με `shown=true`, στη σειρά εμφάνισης. |
| GET | `/cards` | `[{id, tier, day, opened}]`. |
| POST | `/cards/{id}/open` | Ξένη κάρτα `404`. |
| POST | `/ask` | `501 {"not_implemented": "5.2"}` (RAG Q&A μετά το backend). |

### Προτάσεις (`/meals/photo`, `/meals/text`)

```json
{"analysis_id": "3f2b8a1c-9d4e-4f6a-8b7c-1a2b3c4d5e6f",
 "suggestions": [{"food_id": "lentils", "name_el": "Φακές", "confidence_word": "σίγουρο",
                  "alternatives": [{"food_id": "bean_soup", "name_el": "Φασολάδα"}],
                  "portion": null, "components": null}],
 "needs_confirmation": true}
```

- `analysis_id`: νέο σε κάθε ανάλυση. Ο client το στέλνει στο `/meals/confirm` αν το γεύμα προέκυψε από αυτές τις
  προτάσεις (προαιρετικό· δεν αλλάζει το γεύμα, δεν μετρά στο idempotency). Μόνο για την αξιολόγηση του μοντέλου.
- `food_id: null`: το τρόφιμο δεν βρέθηκε στον πίνακα· το παιδί διαλέγει από τα `alternatives` ή ψάχνει.
- `alternatives` (0–3): χωρίς σκορ. `confidence_word`: μόνο «σίγουρο» / «ίσως», ποτέ ποσοστό.
- `portion`: πάντα `null` σήμερα (δεν υπάρχει μοντέλο μερίδας). `components`: `null`, εκτός αν
  `OLIVEGEMMA_INGREDIENTS=true` (ΠΡΟΣΧΕΔΙΟ, ανοιχτή απόφαση διαιτολόγου): τότε έως 10 λέξεις στα αγγλικά, υλικά
  συνταγής κατά το μοντέλο, ΟΧΙ επιβεβαιωμένα από τη φωτογραφία, ποτέ ποσότητες.
- `503 {"photo_unavailable": true}`: δεν υπάρχει ρυθμισμένη διαδρομή φωτογραφίας ή το μοντέλο δεν φόρτωσε.
  `503 {"photo_busy": true}`: η ουρά του μοντέλου είναι γεμάτη· ο client ξαναδοκιμάζει. Καμία από τις δύο δεν είναι
  απόρριψη και δεν μετρά στην αναστολή.

### Idempotency του `/meals/confirm`

Ο client φτιάχνει ένα `client_meal_id` (UUID) ανά γεύμα και το ξαναστέλνει όπως είναι αν δεν πάρει απάντηση (ουρά
offline).

| Περίπτωση | Απάντηση |
|---|---|
| Νέο `client_meal_id` | `201`, `created: true` |
| Ίδιο `client_meal_id`, ίδιο σώμα | `200`, το υπάρχον γεύμα, `created: false` (και αν πέρασε το παράθυρο ημερομηνίας) |
| Ίδιο `client_meal_id`, άλλο σώμα, ή το γεύμα διαγράφηκε | `409 {"detail": "client_meal_id_conflict"}` |

## Admin (`X-Admin-Token`, μόνο από το VPN του ΑΠΘ μέσω Nginx)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/alerts?status=` | Κωδικός, είδος (`safety` / `operational`), κατηγορία, κατάσταση. `status=new\|in_progress\|closed` για τις καρτέλες. |
| GET | `/admin/alerts/{id}` | Το alert και το χρονολόγιό του: `events:[{event, from_status, to_status, at}]`, `event = created \| status_changed \| note_updated`. Χωρίς το κείμενο της σημείωσης. |
| POST | `/admin/alerts/{id}/status` | `{status, note}`· κλείσιμο ενός safety alert επαναφέρει την ανατροφοδότηση. Γράφει γεγονός στο χρονολόγιο. |
| GET | `/admin/participants` | `[{participant_id, arm, active, enrolled_on, study_ended, photo_suspended_until}]`. |
| POST | `/admin/participants/{id}/deactivate` | Ανάκληση συγκατάθεσης: `active=false`, ακύρωση όλων των tokens. |
| GET | `/admin/photo-suspensions` | Κωδικός, έως πότε, πλήθος απορρίψεων. |
| GET | `/admin/system-status` | `demo_mode` (η ρύθμιση `DEMO_MODE`), `versions` (sha256 των CSV και του `rag_sources.csv`, εκδόσεις prompt/presenter, `foods_is_demo`, μοντέλα) και `services` (`db`, `llm`, `photo_pipeline`, `last_card_job`). Κανένα δεδομένο συμμετέχοντα. |

Κανένα admin endpoint δεν επιστρέφει γεύματα ή κείμενα παιδιών.

## DEMO_MODE

Προεπιλογή `false`. Το `ENVIRONMENT` είναι υποχρεωτικό (καμία προεπιλογή). `DEMO_MODE=true` επιτρέπεται **μόνο**
με `ENVIRONMENT=development`· με `production`, `test`, άγνωστη ή κενή τιμή, ή χωρίς `ENVIRONMENT`, η εφαρμογή δεν
ξεκινά· το μήνυμα δεν περιέχει τιμές ρυθμίσεων. Όταν είναι ενεργό: μία γραμμή
`WARNING` (`demo_mode_enabled`, logger `pyramid.startup`) σε κάθε εκκίνηση και `demo_mode: true` στο
`GET /admin/system-status`. Το παιδί δεν βλέπει τίποτα σχετικό.

Όλα τα σημεία που διαβάζουν τη ρύθμιση (14/11/2026):

| Σημείο | Τι κάνει |
|---|---|
| `backend/app/config.py:64` | Ορισμός, προεπιλογή `false`. |
| `backend/app/config.py:146` | Σε `ENVIRONMENT=production`: άρνηση εκκίνησης («DEMO_MODE must be false»). |
| `backend/app/config.py:161` | Εκτός production: άρνηση εκκίνησης αν το `ENVIRONMENT` δεν είναι `development`. |
| `backend/app/main.py:60` | Γραμμή `WARNING` στην εκκίνηση. |
| `backend/app/config.py` (`photo_recognizer`, `photo_content_filter`) | Η μόνη αλλαγή συμπεριφοράς: με `true` κάθε component που είναι `none` γίνεται `demo` (βλ. παρακάτω)· με `false` και χωρίς ρητά components η φωτογραφία είναι «μη διαθέσιμη» (`503`, `photo_status: unavailable`). |
| `backend/app/services/system_status.py` | `services.photo_pipeline`: `demo` αν οποιοδήποτε component είναι demo· `photo_components` ανά component. |
| `backend/app/services/system_status.py` | Πεδίο `demo_mode` του `/admin/system-status`. |
| `backend/app/api/meals.py` | Audit `photo_processed`: `pipeline` = `demo` (όλα demo), `mixed` (κάποια demo) ή `real`. |
| `scripts/seed_demo.py:61` | Αρνείται να γράψει δεδομένα επίδειξης χωρίς `DEMO_MODE=true` ή σε production. |
| `scripts/demo_backend.sh:26` (`make demo`, `Makefile:72`) | Το ορίζει ρητά μαζί με `ENVIRONMENT=development`, σε προσωρινή βάση SQLite. |
| `.env.example:37` | `DEMO_MODE=false`. |

Δεν το διαβάζουν: `backend/Dockerfile`, `docker-compose.yml` (παίρνει ό,τι έχει το `.env`), `docker-compose.prod.yml`
(ορίζει `ENVIRONMENT: production`, άρα `DEMO_MODE=true` σταματά την εκκίνηση). Το `backend/app/api/docs.py:41` είναι
μόνο κείμενο προειδοποίησης στο Swagger. Το κείμενο (`/meals/text`), η αναζήτηση και τα demo τρόφιμα **δεν**
εξαρτώνται από το `DEMO_MODE` (τα demo τρόφιμα τα σταματά ο έλεγχος `is_demo` σε production).

## Components της φωτογραφίας (2026-11-16)

| Ρύθμιση | Τιμές | Σημείωση |
|---|---|---|
| `PHOTO_CONTENT_FILTER` | `none` (προεπιλογή) \| `demo` \| `real` | NSFW + food gate #2. Το `real` δεν υπάρχει ακόμα (Βήματα 3.1b/3.1c): `WARNING` και 503. |
| `PHOTO_RECOGNIZER` | `none` (προεπιλογή) \| `demo` \| `olivegemma` | `olivegemma`: `backend/ai_pipeline/vision/olivegemma.py`, τοπικά βάρη, εκτός σύνδεσης. |
| `OLIVEGEMMA_DIR` | `models/olivegemma-3b` | φάκελος με `model.safetensors`, processor/tokenizer, `REVISION.txt` |
| `OLIVEGEMMA_DTYPE` | `bfloat16` \| `float32` | float32 θέλει ~12 GB μόνο για βάρη |
| `OLIVEGEMMA_THREADS` | κενό | `torch.set_num_threads` |
| `OLIVEGEMMA_TIMEOUT_S` | 600 (ΠΡΟΣΧΕΔΙΟ) | μετά: απόρριψη `recognizer_timeout` (μόνο στο audit) |
| `OLIVEGEMMA_TOPK` | 3 | beams = η πρόταση + alternatives |
| `OLIVEGEMMA_INGREDIENTS` | `false` | ΑΝΟΙΧΤΗ ΑΠΟΦΑΣΗ: γεμίζει τα `components` |
| `OLIVEGEMMA_SHA256` | κενό | του `model.safetensors`· διαφορά = δεν φορτώνεται (503) |
| `OLIVEGEMMA_MAX_QUEUE` | 2 (ΠΡΟΣΧΕΔΙΟ) | αιτήματα σε αναμονή· παραπάνω → `503 photo_busy` |
| `OLIVEGEMMA_PRELOAD` | `false` | `true`: φόρτωση στην εκκίνηση |
| `OLIVEGEMMA_LABEL_MAP_CSV` | `olivegemma_label_map.csv` | ετικέτα → `food_id` (ΠΡΟΣΧΕΔΙΟ demo) |

Κάθε `demo` επιτρέπεται **μόνο** με `ENVIRONMENT=development` (ίδιος φραγμός με το `DEMO_MODE`): αλλιώς η εφαρμογή δεν
ξεκινά. `model_id` στο audit: `OliveGemma-3B@<REVISION.txt>`.

## Audit: τι κρατά για την αναγνώριση

| Γεγονός | Κωδικός παιδιού | Περιεχόμενο |
|---|---|---|
| `photo_processed` | **όχι** | `analysis_id`, `stored_bytes: 0`, `model_id`, `model_labels` (έως 10 ετικέτες του μοντέλου, χωρίς σκορ), `resolved_food_ids` (στην ίδια σειρά, `null` όπου δεν βρέθηκε τρόφιμο), `pipeline` (`demo` / `mixed` / `real`), `shown` (ό,τι είδε το παιδί: `food_id`, μερίδα, `food_id` των alternatives). |
| `text_processed` | **όχι** | `analysis_id`, `model_id` (έκδοση extractor), `n_segments`, `resolved_food_ids` (ανά τμήμα, `null` όπου δεν βρέθηκε), `pipeline: "real"`, `shown`. Χωρίς `model_labels` (θα ήταν λέξεις του παιδιού). |
| `suggestion_outcome` | ναι | Μόνο όταν το `/meals/confirm` έχει `analysis_id` και δημιουργεί νέο γεύμα: `analysis_id`, `meal_id`, `analysis_found`, `items: [{outcome, food_id, instead_of?}]`, `outcome ∈ accepted \| portion_changed \| alternative_chosen \| removed \| added`. |
| `photo_rejected` | ναι | `reason`, `stored_bytes: 0` (χρειάζεται για την αναστολή φωτογραφίας). |

Ποτέ bytes εικόνας, διαστάσεις, EXIF ή hash εικόνας, ποτέ το κείμενο του παιδιού ή όνομα που δεν βρέθηκε στον πίνακα.
Μια ανάλυση συνδέεται με παιδί **μόνο** μέσω `suggestion_outcome`, δηλαδή μόνο αν κατέληξε σε επιβεβαιωμένο γεύμα.
Κανένα endpoint (ούτε admin) δεν διαβάζει αυτές τις εγγραφές· πρόσβαση μόνο με εξαγωγή από τη βάση από τον Κύριο
Ερευνητή (`docs/dpia.md`, «Αλλαγές 12–13/11/2026»).

## Δεν υπάρχουν ακόμα

Logout (το token λήγει μόνο του· ανάκληση με το admin deactivate), `/game/*` (decks, μάχες), webhooks του Unity.
Τα placeholders `app/api/game.py` και `app/api/webhooks.py` μένουν για αυτά. Κατάλογος καρτών (`/cards/catalog`,
περιεχόμενο κάρτας): μόνο πρόταση, `docs/card_catalog_proposal.md`. Επίσης εκτός: `/ask` (5.2), Αποστολές,
επεξεργασία γεύματος, αποτελέσματα παιχνιδιού.
