# API

> Status: v1 (Φάση 6). Η πλήρης, εκτελέσιμη αναφορά είναι το Swagger UI στο `/docs` (εκτός production·
> `scripts/demo_backend.sh` για demo). Προδιαγραφή: `docs/backend_spec_v1.md`.

Όλα τα endpoints έχουν prefix `/api/v1`. Το παιδί μπαίνει με **κλειδί πρόσβασης** (`POST /auth/login`) και παίρνει
JWT (bearer). Δεν υπάρχει εγγραφή μέσω API: οι συμμετέχοντες δημιουργούνται με `scripts/create_participant.py`.
Καμία απάντηση προς το παιδί δεν περιέχει αριθμητική τιμή θρεπτικού, γραμμαρίων ή ποσοστού (R1).

## Χωρίς token

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Η εφαρμογή και η βάση απαντούν. |
| POST | `/auth/login` | Κλειδί → JWT. Ίδιο `401` για κάθε αποτυχία· `429` μετά από πολλές αποτυχίες ανά IP· `403` για την ομάδα ελέγχου πριν το `CONTROL_ACCESS_FROM`. |

## Παιδί (JWT)

| Method | Path | Notes |
|---|---|---|
| GET / PATCH | `/me` | Μόνο `{arm, avatar_id, photo_available}`. Avatar από κλειστή λίστα. |
| GET | `/foods/search?q=` | `[{food_id, name_el, food_group}]`, χωρίς θρεπτικά. |
| POST | `/meals/photo` | Raw `image/jpeg` (όχι multipart), ≤ 1 MB, πλευρά ≤ 448 px. Προτάσεις, **τίποτα δεν αποθηκεύεται**. Κάθε απόρριψη: `422 {"rejected": true}`. Αναστολή: `403`· χωρίς φίλτρα: `503 {"photo_unavailable": true}`. |
| POST | `/meals/text` | `{text ≤ 300}` → ίδια μορφή προτάσεων. Τίποτα δεν αποθηκεύεται. |
| POST | `/meals/confirm` | Η λίστα που επιβεβαίωσε το παιδί· τα γραμμάρια από τη μερίδα (server). |
| GET | `/meals?from=&to=` | Μόνο τα γεύματα του ίδιου παιδιού: όνομα και μερίδα ως λέξη. |
| DELETE | `/meals/{id}` | Soft delete, μόνο με `ALLOW_MEAL_DELETE=true`· ξένο γεύμα `404`. |
| POST | `/days/{day}/complete` | Δήλωση «πλήρης ημέρα» (με τουλάχιστον ένα γεύμα). |
| GET | `/feedback/today` | `{messages:[{id, text}], food_groups_today}`· rule engine 7 ημερών + presenter + ασφάλεια. |
| GET | `/cards` | `[{id, tier, day, opened}]`. |
| POST | `/cards/{id}/open` | Ξένη κάρτα `404`. |
| POST | `/ask` | `501 {"not_implemented": "5.2"}` (RAG Q&A μετά το backend). |

## Admin (`X-Admin-Token`, μόνο από το VPN του ΑΠΘ μέσω Nginx)

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/alerts` | Κωδικός, είδος (`safety` / `operational`), κατηγορία, κατάσταση. |
| POST | `/admin/alerts/{id}/status` | `{status, note}`· κλείσιμο ενός safety alert επαναφέρει την ανατροφοδότηση. |
| POST | `/admin/participants/{id}/deactivate` | Ανάκληση συγκατάθεσης: `active=false`, ακύρωση όλων των tokens. |
| GET | `/admin/photo-suspensions` | Κωδικός, έως πότε, πλήθος απορρίψεων. |

Κανένα admin endpoint δεν επιστρέφει γεύματα ή κείμενα παιδιών.

## Δεν υπάρχουν ακόμα

Logout (το token λήγει μόνο του· ανάκληση με το admin deactivate), `/game/*` (decks, μάχες), webhooks του Unity,
admin monitoring. Τα placeholders `app/api/game.py` και `app/api/webhooks.py` μένουν για αυτά.
