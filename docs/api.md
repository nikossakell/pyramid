# API

> Status: v1 (Φάση 6). Η πλήρης, εκτελέσιμη αναφορά είναι το Swagger UI στο `/docs` (εκτός production·
> `scripts/demo_backend.sh` για demo). Προδιαγραφή: `docs/backend_spec_v1.md` (Τροποποιήσεις 23–33 για όσα
> προστέθηκαν στις 12–13/11/2026· αιτιολόγηση στο `docs/decisions/2026-11-12_backend_gaps.txt`).

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
| GET | `/food-groups` | Οι 11 κύριες ομάδες στη σειρά εμφάνισης: `[{code, label_el, shown}]`. `shown=false`: όχι ως «ομάδα που είχες». |
| GET | `/foods/search?q=&group=` | `[{food_id, name_el, food_group}]`, χωρίς θρεπτικά. Με `group` και χωρίς `q`: τα τρόφιμα της ομάδας, αλφαβητικά (έως 50). Άγνωστη ομάδα: `422 unknown_group`. |
| POST | `/meals/photo` | Raw `image/jpeg` (όχι multipart), ≤ 1 MB, πλευρά ≤ 448 px. Προτάσεις, **τίποτα δεν αποθηκεύεται**. Κάθε απόρριψη: `422 {"rejected": true}`. Αναστολή: `403`· χωρίς φίλτρα: `503 {"photo_unavailable": true}`. |
| POST | `/meals/text` | `{text ≤ 300}` → ίδια μορφή προτάσεων. Τίποτα δεν αποθηκεύεται. |
| POST | `/meals/confirm` | `{client_meal_id, eaten_on, meal_slot, source, items}` → `{meal_id, eaten_on, meal_slot, food_groups, created}`. Idempotent (βλ. παρακάτω). Τα γραμμάρια από τη μερίδα (server). |
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
{"suggestions": [{"food_id": "lentils", "name_el": "Φακές", "confidence_word": "σίγουρο",
                  "alternatives": [{"food_id": "bean_soup", "name_el": "Φασολάδα"}],
                  "portion": null, "components": null}],
 "needs_confirmation": true}
```

- `food_id: null`: το τρόφιμο δεν βρέθηκε στον πίνακα· το παιδί διαλέγει από τα `alternatives` ή ψάχνει.
- `alternatives` (0–3): χωρίς σκορ. `confidence_word`: μόνο «σίγουρο» / «ίσως», ποτέ ποσοστό.
- `portion` και `components`: πάντα `null` σήμερα (πεδία για το μέλλον· τα `components` είναι ανοιχτή απόφαση).

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
| GET | `/admin/system-status` | `versions` (sha256 των CSV και του `rag_sources.csv`, εκδόσεις prompt/presenter, `foods_is_demo`, μοντέλα) και `services` (`db`, `llm`, `photo_pipeline`, `last_card_job`). Κανένα δεδομένο συμμετέχοντα. |

Κανένα admin endpoint δεν επιστρέφει γεύματα ή κείμενα παιδιών.

## Δεν υπάρχουν ακόμα

Logout (το token λήγει μόνο του· ανάκληση με το admin deactivate), `/game/*` (decks, μάχες), webhooks του Unity.
Τα placeholders `app/api/game.py` και `app/api/webhooks.py` μένουν για αυτά. Κατάλογος καρτών (`/cards/catalog`,
περιεχόμενο κάρτας): μόνο πρόταση, `docs/card_catalog_proposal.md`. Επίσης εκτός: `/ask` (5.2), Αποστολές,
επεξεργασία γεύματος, αποτελέσματα παιχνιδιού.
