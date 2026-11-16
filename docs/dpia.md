# Data Protection Impact Assessment

> Status: outline. Children's data plus AI processing -- a DPIA is mandatory.

## 1. Description of the processing

## 2. The photograph: what happens to it

1. Captured in the browser.
2. Downscaled to 448 px and re-encoded as a fresh JPEG; EXIF is dropped
   (`frontend/src/ml/imagePrep.ts`).
3. Screened in the browser by the food gate; non-food never leaves the device
   (`frontend/src/ml/foodGate.ts`).
4. Transmitted over TLS as a raw body, capped at 1 MB.
5. Held in process memory only, screened again server-side (NSFW + food
   re-check), passed to OliveGemma, then discarded.
6. Only the dish name, the resolved `food_id` and the child's confirmation are
   persisted.

Residual risk is addressed by the controls in `docs/ephemeral-processing.md`
(no disk, no swap, no request-body logging) and verified by
`backend/tests/integration/test_photo_ephemeral.py` and
`scripts/check_ephemeral.sh`.

## 3. Necessity and proportionality

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A photograph persists on disk | low | high | Rule 7 controls, tmpfs, no swap, automated check |
| An inappropriate image is uploaded | low | high | Rule 8: browser food gate + server NSFW + food re-check |
| Re-identification from meal data | low | medium | Pseudonymisation, key kept off-server |
| The LLM invents a nutritional claim | medium | medium | Safety validator; engine output is authoritative |
| Harm from stigmatising feedback | low | high | No calories, no BMI, no leaderboards; ED safety rules |

## 5. Consultation

## 6. Sign-off

## Αλλαγές 12–13/11/2026 (ΠΡΟΣΧΕΔΙΟ, προς έγκριση)

Νέες επεξεργασίες του backend (`docs/decisions/2026-11-12_backend_gaps.txt`). Νομική βάση: όπως ορίζεται στο
`docs/gdpr-compliance.md`, ενότητα 2 (δεν εισάγεται καινούργια). Διατήρηση: όπως τα υπόλοιπα δεδομένα της μελέτης.
Κανένα από τα παρακάτω δεν περιέχει όνομα, email, ημερομηνία γέννησης ή φωτογραφία.

| Επεξεργασία | Τι αποθηκεύεται | Σκοπός | Πρόσβαση |
|---|---|---|---|
| `meals.client_meal_id` | Τυχαίο UUID που φτιάχνει η συσκευή για κάθε γεύμα | Να μην αποθηκευτεί δύο φορές το ίδιο γεύμα όταν η συσκευή το ξαναστέλνει (ουρά εκτός σύνδεσης) | Ερευνητική ομάδα (βάση)· δεν επιστρέφεται από το API |
| `day_status.completed_by` και αυτόματη πλήρης ημέρα | `child` ή `auto` για κάθε πλήρη ημέρα | Να ξεχωρίζει στην ανάλυση η ημέρα που δήλωσε το παιδί από εκείνη που σημείωσε η νυχτερινή εργασία (μόνο αν `COMPLETE_DAY_MODE=auto`· προεπιλογή `declared`) | Ερευνητική ομάδα (βάση)· το παιδί βλέπει μόνο «πλήρης / όχι» |
| Τέλος μελέτης | Γεγονός audit `login_denied_study_ended` (κωδικός συμμετέχοντα, χρόνος) | Τεκμηρίωση ότι η πρόσβαση έκλεισε μετά τις `STUDY_DURATION_DAYS` ημέρες· κανένα νέο δεδομένο υγείας | Ερευνητική ομάδα (audit) |
| `alert_events` | Για κάθε alert: είδος γεγονότος, καταστάσεις, χρόνος. Ποτέ το κείμενο της σημείωσης | Χρονολόγιο χειρισμού των alerts ασφάλειας (ποιος χρόνος, ποια ενέργεια)· append-only | Ερευνητής / εφημερεύων μέσω κονσόλας (`X-Admin-Token`, VPN) |
| `job_runs` | Εκτελέσεις της νυχτερινής εργασίας: ημέρα, χρόνοι, κατάσταση, πλήθος καρτών συνολικά | Λειτουργικός έλεγχος. Δεν είναι προσωπικό δεδομένο (κανένας κωδικός συμμετέχοντα) | Ερευνητής μέσω κονσόλας |
| Έξοδος μοντέλου στο audit (`photo_processed`, `text_processed`) | Τυχαίο `analysis_id` ανά ανάλυση, ετικέτες του μοντέλου (έως 10, χωρίς σκορ, μόνο φωτογραφία), έκδοση μοντέλου, `food_id` που αντιστοιχίστηκαν και που είδε το παιδί, `demo`/`real`, χρόνος. **Χωρίς κωδικό συμμετέχοντα**, χωρίς εικόνα και χωρίς το κείμενο του παιδιού | **Αξιολόγηση του μοντέλου** (OliveGemma, food resolver) | **Μόνο ο Κύριος Ερευνητής, μέσω εξαγωγής** από τη βάση. Κανένα endpoint, ούτε η κονσόλα |
| Έκβαση προτάσεων (`suggestion_outcome`) | Με κωδικό συμμετέχοντα, μόνο για **επιβεβαιωμένο** γεύμα που προήλθε από ανάλυση: `analysis_id`, `meal_id` και ανά τρόφιμο `accepted` / `portion_changed` / `alternative_chosen` / `removed` / `added` με `food_id` | **Αξιολόγηση του μοντέλου**: τι κράτησε, άλλαξε ή πρόσθεσε το παιδί | **Μόνο ο Κύριος Ερευνητής, μέσω εξαγωγής** από τη βάση. Κανένα endpoint, ούτε η κονσόλα |
| `GET /admin/participants` | Τίποτα νέο: προβολή υπαρχόντων πεδίων (κωδικός, ομάδα, ενεργός, ημερομηνία ένταξης, τέλος μελέτης, αναστολή φωτογραφίας) | Διαχείριση της μελέτης από την κονσόλα | Ερευνητής μέσω κονσόλας (`X-Admin-Token`, VPN) |

### Προσθήκη 16/11/2026 (ΠΡΟΣΧΕΔΙΟ): πραγματικό μοντέλο αναγνώρισης (OliveGemma-3B)

- **Τοπική εκτέλεση.** Το μοντέλο (`JamesZar/OliveGemma-3B`, άδεια Gemma) φορτώνεται από φάκελο του server
  (`OLIVEGEMMA_DIR`) με `HF_HUB_OFFLINE=1`, `local_files_only=True`, `trust_remote_code=False`. **Καμία κλήση σε τρίτους**
  κατά τη φόρτωση ή την εκτέλεση· η φωτογραφία δεν φεύγει από τον server.
- **Είσοδος / έξοδος.** Είσοδος μόνο το ξανακωδικοποιημένο JPEG (≤ 448 px, χωρίς EXIF) στη RAM· εικόνα και tensors
  διαγράφονται μετά την απάντηση. Έξοδος μόνο ετικέτες (λέξεις), που αντιστοιχίζονται σε `food_id`. Προς το παιδί
  μόνο «σίγουρο» / «ίσως», ποτέ σκορ. Αν ενεργοποιηθούν τα `components` (`OLIVEGEMMA_INGREDIENTS`, προεπιλογή όχι), είναι
  υλικά συνταγής κατά την κάρτα του μοντέλου, όχι επιβεβαιωμένα από τη φωτογραφία, και χρειάζονται έγκριση διαιτολόγου.
- **Έκδοση στο audit.** Το `model_id` κάθε `photo_processed` είναι `OliveGemma-3B@<commit>` (από `REVISION.txt`), ώστε η
  αξιολόγηση να ξέρει ποια έκδοση έδωσε κάθε ετικέτα. Προαιρετικός έλεγχος `sha256` των βαρών πριν τη φόρτωση· διαφορά =
  το μοντέλο δεν φορτώνεται και η φωτογραφία είναι μη διαθέσιμη.
- **Ανά component.** NSFW και food gate #2 δεν υπάρχουν ακόμα· η εκτέλεση του πραγματικού μοντέλου με demo φίλτρα
  επιτρέπεται μόνο σε περιβάλλον ανάπτυξης (`ENVIRONMENT=development`) και φαίνεται στο audit (`pipeline: mixed`) και στην
  κονσόλα (`photo_components`). Σε production χωρίς πραγματικά φίλτρα η φωτογραφία παραμένει μη διαθέσιμη (503).
- **Νέες καταστάσεις χωρίς νέα δεδομένα:** `503 photo_busy` (ουρά γεμάτη) και `503 photo_unavailable` (μοντέλο δεν
  φόρτωσε) δεν γράφουν τίποτα με κωδικό παιδιού. Το timeout γράφει `photo_rejected` με λόγο `recognizer_timeout` (όπως
  κάθε απόρριψη).

Σημεία που χρειάζονται ρητή έγκριση:

1. **Έξοδος μοντέλου πριν την επιβεβαίωση.** Η ενότητα 2 (βήμα 6) λέει ότι αποθηκεύονται μόνο το όνομα του πιάτου, το
   `food_id` και η επιβεβαίωση του παιδιού. Το audit κρατά πλέον τι αναγνώρισε το μοντέλο και για αναλύσεις που το
   παιδί δεν επιβεβαίωσε ποτέ, αλλά **χωρίς κωδικό συμμετέχοντα** (απόφαση 14/11/2026). Σύνδεση με παιδί υπάρχει
   μόνο μέσω της έκβασης, δηλαδή μόνο για γεύμα που το παιδί επιβεβαίωσε. Σκοπός: αξιολόγηση του μοντέλου. Πρόσβαση:
   μόνο ο Κύριος Ερευνητής μέσω εξαγωγής (η εξαγωγή δεν έχει υλοποιηθεί ακόμα). Δεν αποθηκεύεται εικόνα, διαστάσεις,
   EXIF ή hash εικόνας, ούτε το κείμενο που έγραψε το παιδί.
   **Υπολειπόμενος κίνδυνος:** το access log της εφαρμογής γράφει τον κωδικό συμμετέχοντα, τη διαδρομή και τον χρόνο
   κάθε αιτήματος. Όποιος έχει και τα logs και το audit μπορεί να αντιστοιχίσει με τον χρόνο μια ανάλυση που δεν
   επιβεβαιώθηκε σε παιδί. Μετριασμός: τα logs δεν εξάγονται μαζί με το audit· να αποφασιστεί αν χρειάζεται και
   στρογγυλοποίηση του χρόνου των αναλύσεων.
2. **Αυτόματη πλήρης ημέρα.** Απενεργοποιημένη (`declared`). Αν ενεργοποιηθεί, μια ημέρα χαρακτηρίζεται πλήρης
   χωρίς ενέργεια του παιδιού και επηρεάζει την ανατροφοδότηση· ανοιχτή απόφαση διαιτολόγου.
3. **Ποιος έχει πρόσβαση στη βάση και στο audit** δεν ορίζεται ακόμα σε αυτό το έγγραφο· οι γραμμές «Ερευνητική
   ομάδα» παραπάνω θέλουν συγκεκριμένους ρόλους.
