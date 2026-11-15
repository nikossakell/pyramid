# GDPR compliance

> Status: outline -- Ethics Board submission document.

## 1. Controller and processors

## 2. Lawful basis

## 3. Categories of data

| Category | Stored? | Retention |
|---|---|---|
| Access key (hashed) | yes | duration of the study |
| Pseudonymised profile (sex, age, height, weight, activity) | yes | duration of the study |
| Meal entries (confirmed food items and portions) | yes | duration of the study |
| Recommendations and rule executions | yes | duration of the study |
| Game state | yes | duration of the study |
| Audit log | yes | duration of the study |
| **Meal photographs** | **no -- never written to disk** | n/a |

## 4. Data minimisation

## 5. Data-subject rights and how they are exercised

## 6. Security measures

## 7. International transfers

None. All processing is on-premise.

## 8. Related documents

`docs/dpia.md`, `docs/ephemeral-processing.md`, `docs/content-safety.md`.

## Αλλαγές 12–13/11/2026 (ΠΡΟΣΧΕΔΙΟ, προς έγκριση)

Νέες κατηγορίες και επεξεργασίες του backend. Νομική βάση: της ενότητας 2 (δεν έχει συμπληρωθεί ακόμα· εδώ δεν
εισάγεται καινούργια). Διατήρηση: «duration of the study», όπως οι υπόλοιπες κατηγορίες της ενότητας 3.
Αναλυτικά (σκοπός, σημεία προς έγκριση): `docs/dpia.md`, ίδια ενότητα.

| Κατηγορία | Αποθηκεύεται; | Σκοπός | Διατήρηση | Πρόσβαση |
|---|---|---|---|---|
| Κλειδί idempotency γεύματος (`client_meal_id`, τυχαίο UUID της συσκευής) | ναι | Αποφυγή διπλής αποθήκευσης γεύματος | όπως τα υπόλοιπα δεδομένα της μελέτης | ερευνητική ομάδα |
| Τρόπος ολοκλήρωσης ημέρας (`completed_by`: `child` / `auto`) | ναι | Διάκριση δήλωσης παιδιού από αυτόματη σήμανση | όπως τα υπόλοιπα δεδομένα της μελέτης | ερευνητική ομάδα |
| Άρνηση πρόσβασης μετά το τέλος της μελέτης (audit `login_denied_study_ended`) | ναι, στο audit log | Τεκμηρίωση λήξης πρόσβασης | όπως το audit log | ερευνητική ομάδα |
| Χρονολόγιο alerts (`alert_events`: γεγονός, καταστάσεις, χρόνος· χωρίς κείμενο) | ναι, append-only | Ιχνηλασιμότητα χειρισμού alerts ασφάλειας | όπως τα υπόλοιπα δεδομένα της μελέτης | ερευνητής / εφημερεύων (κονσόλα) |
| Εκτελέσεις εργασιών (`job_runs`) | ναι | Λειτουργικός έλεγχος· χωρίς κωδικό συμμετέχοντα | όπως τα υπόλοιπα δεδομένα της μελέτης | ερευνητής (κονσόλα) |
| Έξοδος μοντέλου αναγνώρισης (τυχαίο `analysis_id`, ετικέτες χωρίς σκορ, `food_id`, έκδοση μοντέλου· για κείμενο μόνο πλήθη και `food_id`) | ναι, στο audit log, **χωρίς κωδικό συμμετέχοντα**, και για αναλύσεις που δεν επιβεβαιώθηκαν | Αξιολόγηση του μοντέλου | όπως το audit log | μόνο ο Κύριος Ερευνητής, μέσω εξαγωγής |
| Έκβαση προτάσεων (`suggestion_outcome`: ανά τρόφιμο accepted / portion_changed / alternative_chosen / removed / added) | ναι, στο audit log, με κωδικό συμμετέχοντα, μόνο για επιβεβαιωμένο γεύμα | Αξιολόγηση του μοντέλου | όπως το audit log | μόνο ο Κύριος Ερευνητής, μέσω εξαγωγής |
| Λίστα συμμετεχόντων στην κονσόλα (`GET /admin/participants`) | καμία νέα αποθήκευση | Διαχείριση της μελέτης | — | ερευνητής (κονσόλα, `X-Admin-Token`, VPN) |

Οι φωτογραφίες εξακολουθούν να μην αποθηκεύονται· ούτε το ελεύθερο κείμενο του παιδιού.
