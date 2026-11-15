# Αναφορά: διορθώσεις backend και υλοποίηση του PWA (12–15/11/2026)

> Κατάσταση: ΠΡΟΣΧΕΔΙΟ για την ομάδα. Όλες οι αλλαγές είναι στο working tree, **χωρίς commit** (HEAD `4791854 api fixes`).
> Αιτιολόγηση των αποφάσεων backend: `docs/decisions/2026-11-12_backend_gaps.txt` (Αποφάσεις 25–38).
> Πηγές για το frontend: `docs/design/*.dc.html` (mockups), `docs/design/mockups_delta.md` (υπερισχύει των mockups),
> `docs/api.md`, κανόνες R1–R11 του design brief.

## 1. Σύνοψη

| Τι | Κατάσταση |
|---|---|
| Διορθώσεις backend μετά τα Στάδια 0–5 (Βήματα 1–8) | Εφαρμόστηκαν |
| Τροποποιήσεις Βήματος 3 (analysis_id, suggestion_outcome, ENVIRONMENT υποχρεωτικό, DPIA) | Εφαρμόστηκαν |
| PWA Vue 3 + Vite, Στάδια A–Δ | Υλοποιήθηκαν |
| Backend tests (χωρίς PostgreSQL) | 559 passed, 10 deselected (marker `postgres`) |
| Frontend build (`vue-tsc --noEmit && vite build`) | Χωρίς σφάλματα |
| E2E tests frontend | Δεν ζητήθηκαν σε αυτή τη φάση· δεν υπάρχουν |
| Δοκιμή σε πραγματική συσκευή | Δεν έγινε |

Αλλαγές στο working tree: 41 τροποποιημένα, 21 διαγραμμένα, 39 νέα αρχεία/φάκελοι (backend, docs, frontend).

---

## 2. Backend: τι άλλαξε

### 2.1 Διορθώσεις αποκλίσεων (Αποφάσεις 25–33)

- **DEMO_MODE** (25, 26): επιτρέπεται μόνο με `ENVIRONMENT=development`. Μία γραμμή WARNING στην εκκίνηση
  (`pyramid.startup`, `demo_mode_enabled`). Το `GET /admin/system-status` δείχνει `demo_mode`.
- **Έλεγχος R1 στα tests** (27): το `assert_no_numbers` στο `backend/tests/api/conftest.py` έγινε αυστηρότερο. Ημερομηνίες
  και UUID περνούν μόνο σε γνωστά πεδία και μόνο ως πλήρες ISO/UUID. Νέο `tests/api/test_r1_check.py`.
- **`/food-groups`** (28): επιστρέφει `{code, label_el, shown, sort}`. Το `sort` είναι σειρά εμφάνισης και όχι τιμή
  θρεπτικού, άρα δεν παραβιάζει το R1.
- **Έξοδος μοντέλου στο audit** (29): ετικέτες χωρίς σκορ, `model_id`, `resolved_food_ids`, `pipeline`.
- **Κατώφλια υποψηφίων ως ρυθμίσεις** (30): `CANDIDATE_PREFIX_MIN=4`, `CANDIDATE_MIN_RATIO=0.75` (ΠΡΟΣΧΕΔΙΟ).
- **Κάρτες** (31): μόνο έγγραφο, `docs/card_catalog_proposal.md` ενότητα 10.
- **DPIA / GDPR** (32): ενότητα «Αλλαγές 12–13/11/2026 (ΠΡΟΣΧΕΔΙΟ)» στα `docs/dpia.md`, `docs/gdpr-compliance.md`.
- **PostgreSQL triggers** (33): `tests/api/test_postgres_triggers.py`, marker `postgres`, τρέχει μόνο με `PG_TEST_URL`.

### 2.2 Τροποποιήσεις Βήματος 3 (Αποφάσεις 34–38)

- **`photo_processed` / `text_processed` χωρίς participant_id** (34). Κάθε ανάλυση έχει νέο `analysis_id` (UUID) που
  επιστρέφεται στην απάντηση προτάσεων. Για το κείμενο δεν κρατιούνται ετικέτες (θα ήταν λέξεις του παιδιού), μόνο
  πλήθος τμημάτων και `food_id`.
- **`POST /meals/confirm` με προαιρετικό `analysis_id`** (35) → audit `suggestion_outcome` με participant:
  `analysis_id`, `meal_id`, έκβαση ανά τρόφιμο ∈ {accepted, portion_changed, alternative_chosen, removed, added}.
  Ποτέ κείμενο παιδιού, ποτέ bytes εικόνας. Μόνο για νέο γεύμα· η επανάληψη idempotency δεν ξαναγράφει.
- **Κανένα endpoint δεν εκθέτει αυτά τα δεδομένα** (36), ούτε admin. Το test ελέγχει το `app.openapi()["paths"]`.
- **`ENVIRONMENT` υποχρεωτικό** (37), χωρίς προεπιλογή. Ενημερώθηκαν `backend/README.md`, `.env.example`, tests.
- **DPIA** (38): σκοπός = αξιολόγηση μοντέλου· πρόσβαση = μόνο ο Κύριος Ερευνητής μέσω εξαγωγής.

Κύρια αρχεία: `backend/app/config.py`, `app/main.py`, `app/api/meals.py`, `app/schemas/meal.py`,
`app/services/analysis_audit.py` (νέο), `ai_pipeline/food_resolver.py`, `docs/api.md`, `docs/backend_spec_v1.md`
(Τροποποιήσεις 34–40).

---

## 3. Frontend: τι φτιάχτηκε

### 3.1 Τεχνολογία και αρχιτεκτονική

- **Vue 3.5 + Vite 5 + TypeScript + vue-router 4 + pinia 2**. Αφαιρέθηκαν `axios` και `@tensorflow/tfjs`.
- **API client** (`src/api/client.ts`) με `fetch`, bearer token, κανονικοποίηση σφαλμάτων:
  - 401 με token → M09 SessionExpired
  - 403 `{"study_ended": true}` σε **οποιοδήποτε** αίτημα → S19
  - 403 `{"detail": "not_yet_available"}` → S21
  - 429 → `retryAfter` από το header `Retry-After`
  - Η φωτογραφία πάει ως raw `image/jpeg` Blob. Δεν γράφεται τίποτα στην κονσόλα.
- **Service worker** (`src/sw/sw.js`, χειροποίητο): cache μόνο του app shell, **ποτέ `/api/`**. Η έκδοση μπαίνει στο
  build από το plugin στο `vite.config.ts` (`dist/sw.js`). Εγγραφή μόνο σε production.
- **Manifest και εικονίδια** στο `public/` (placeholder πυραμίδα, φτιαγμένα με Pillow).
- **Design tokens** (`src/styles/tokens.css`): χρώματα του `Main.dc.html`, σκοτεινό θέμα, 3 μεγέθη κειμένου, μείωση
  κίνησης, safe areas. Κανένα κόκκινο σφάλματος.
- **Γραμματοσειρές** τοπικά με `@font-face` (`public/fonts/fonts.css`), χωρίς Google Fonts.

### 3.2 Στάδια

**Στάδιο A: σκελετός**
- Components C01 HelpButton, C02 BottomNav, C03 TopBar, C04 AppButton, C05 AccessKeyInput, C06 AvatarPicker,
  BottomSheet, CenterDialog, C26 EmptyState, C27 Toast, C28 OfflineBanner, Icon, PyramidMark.
- Router με φύλακες: χωρίς token → S02, χωρίς onboarding → S03.
- M01 HelpSheet, M09 SessionExpired, S19 StudyEnd, S21 NotYetOpen, S20β Error.

**Στάδιο B: είσοδος και Σήμερα**
- S01 Splash (φόρτωση, εκτός σύνδεσης).
- S02 Login α–ε: λάθος κλειδί, κλείδωμα «σε N λεπτά» από `Retry-After`, offline, «Δεν έχω κλειδί».
- S03 Onboarding: 4 βήματα + avatar, κείμενο φωτογραφίας του delta §3.
- S04 Today με C11 MealSlotList, C12 FoodGroupSummary (9 ομάδες από `/food-groups`), C13 WeekDots (από `/meals`),
  C14 FeedbackMessage, C17 CardTeaser, C30 DayCompletePrompt (`POST /days/{day}/complete`).
- `stores/meals.ts`: τοπική cache της τελευταίας φόρτωσης για το S04δ.

**Στάδιο C: καταγραφή**
- S05 NewLogSheet, S06 Camera (getUserMedia), S07 Analysis, S08 Confirm, S09 TextLog, S10 Search, S11 Saved.
- M02 PortionPicker, M04 CameraPermission, M05 NotFoodDetected, M06 LowConfidence.
- C09 FoodItemRow, C10 PortionSelector, SlotChips, SlotPicker.
- `ml/imagePrep.ts`: τετράγωνη περικοπή στο κέντρο, ≤ 448 px, JPEG ≤ 1 MB μέσω canvas (άρα χωρίς EXIF).
- `stores/log.ts`: πρόχειρο **μόνο στη μνήμη**, με `client_meal_id` και `analysis_id`.
- `stores/queue.ts`: ουρά εκτός σύνδεσης μόνο για καταγραφές από αναζήτηση.

**Στάδιο Δ: ιστορικό και προφίλ**
- S12 History (Ημέρα / Εβδομάδα, «ολοκληρωμένη μέρα»), S12β MealDetail με M07 DeleteMeal.
- S17 Profile, S18 Privacy, S20α offline στο S05.
- M08 AIDisclosure (πρώτο άνοιγμα Βοηθού), M10 LeaveStudyInfo.

### 3.3 Χάρτης οθονών

| Οθόνη | Αρχείο | API |
|---|---|---|
| S01 Splash | `views/SplashView.vue` | GET /me |
| S02 Login | `views/LoginView.vue` | POST /auth/login |
| S03 Onboarding | `views/OnboardingView.vue` | GET / PATCH /me |
| S04 Σήμερα + S05 | `views/TodayView.vue`, `components/log/NewLogSheet.vue` | /meals, /days, /feedback/today, /food-groups, /cards, /days/{day}/complete, /me |
| S06 Κάμερα | `views/CameraView.vue` | — |
| S07 Ανάλυση | `views/AnalysisView.vue` | POST /meals/photo |
| S08 Επιβεβαίωση | `views/ConfirmView.vue` | POST /meals/confirm |
| S09 Κείμενο | `views/TextLogView.vue` | POST /meals/text |
| S10 Αναζήτηση | `views/SearchView.vue` | GET /foods/search, GET /meals |
| S11 Αποθηκεύτηκε | `views/SavedView.vue` | — (από την απάντηση του confirm) |
| S12 Ιστορικό | `views/HistoryView.vue`, `views/MealDetailView.vue` | GET /meals, GET /days, DELETE /meals/{id} |
| S17 Προφίλ | `views/ProfileView.vue` | GET / PATCH /me |
| S18 Απόρρητο | `views/PrivacyView.vue` | — |
| S19 / S21 | `views/StudyEndView.vue`, `views/NotYetOpenView.vue` | 403 οποιουδήποτε αιτήματος |
| S20β | `views/ErrorView.vue` | — |
| Βοηθός / Κάρτες | `views/PlaceholderView.vue` | — (εκτός φάσης) |

### 3.4 Κανόνες και πώς τηρούνται

- **R1, κανένας αριθμός θρεπτικού / βάρους / γραμμαρίων / ποσοστού.** Μερίδα μόνο ως λέξη. Βεβαιότητα μόνο «σίγουρο» /
  «ίσως». Οι μόνοι αριθμοί προς το παιδί: πλήθος καρτών, «σε N λεπτά» στο κλείδωμα, μετρητής χαρακτήρων 0/300,
  «Βήμα 1 από 4».
- **R5, τίποτα δεν αποθηκεύεται χωρίς «Σωστό».** Οι προτάσεις μένουν στο πρόχειρο στη μνήμη· αποθήκευση μόνο από το S08.
- **R6, πάντα διαθέσιμη καταγραφή με κείμενο ή αναζήτηση.** Κάθε αδιέξοδο της φωτογραφίας οδηγεί σε S09 / S10.
- **R7, HelpButton σε κάθε οθόνη.** Είναι μέσα στο TopBar, που υπάρχει σε όλες τις οθόνες. Τα sheets ξεκινούν το
  scrim κάτω από το TopBar, ώστε το κουμπί να μένει ορατό.
- **Εικόνα μόνο στη μνήμη.** Το Blob ζει στο pinia store και μηδενίζεται μετά την απάντηση του S07 ή σε κάθε έξοδο.
  Δεν πηγαίνει ποτέ σε localStorage, IndexedDB, Cache ή ουρά. Το SW δεν κάνει cache το `/api/`.
- **Κείμενα `[*…]` μένουν placeholders.** Τα κοινά κείμενα που περιμένουν έγκριση είναι στο `src/lib/copy.ts`.
- **Η φράση «δεν φεύγει από το κινητό»** δεν υπάρχει σε κείμενο προς το παιδί (delta §3).

### 3.5 Τι μένει στη συσκευή

| Κλειδί | Περιεχόμενο | Καθαρίζει |
|---|---|---|
| `pyramid.token`, `pyramid.token_expires_at` | JWT και λήξη | Έξοδος, 401, τέλος μελέτης |
| `pyramid.onboarded` | σημάδι «έγινε onboarding» | — |
| `pyramid.prefs` | μέγεθος κειμένου, θέμα, μείωση κίνησης | — |
| `pyramid.cache.v1` | τελευταία φόρτωση Σήμερα: ονόματα τροφίμων, κωδικοί ομάδων, ημέρες, μηνύματα, κάρτες | Έξοδος |
| `pyramid.queue.v1` | σώματα `/meals/confirm` της ουράς (κωδικοί, μερίδες ως λέξεις) και ονόματα | Έξοδος, μετά την αποστολή |
| `pyramid.camera_intro_seen`, `pyramid.ai_disclosure_seen` | «είδα το M04 / M08» | — |
| `pyramid.day_prompt_dismissed` (sessionStorage) | «Όχι ακόμα» στο C30 για σήμερα | κλείσιμο καρτέλας |

Το κλειδί πρόσβασης, το κείμενο του παιδιού και η εικόνα **δεν αποθηκεύονται ποτέ**.

---

## 4. Αποφάσεις που πάρθηκαν

### 4.1 Εγκεκριμένες στο σχέδιο (πριν το Στάδιο A)

1. Χειροποίητο service worker αντί για `vite-plugin-pwa`, για πλήρη έλεγχο ότι το `/api/` δεν μπαίνει σε cache.
2. Τοπικές γραμματοσειρές· τα αρχεία τα δίνει η ομάδα.
3. JWT σε localStorage, ώστε η PWA να μη ζητά το κλειδί σε κάθε άνοιγμα. Ο server το ακυρώνει με `token_version`.
4. Αφαίρεση `@tensorflow/tfjs`. Το food gate του browser είναι εκτός φάσης.
5. Tabs Βοηθός / Κάρτες ως ουδέτερη οθόνη placeholder· M08 στο πρώτο άνοιγμα του Βοηθού.
6. Ουρά offline μόνο για επιβεβαιώσεις από αναζήτηση, σε localStorage.
7. S12 «Διόρθωσε» δεν υλοποιείται. M07 συνδέεται με το DELETE· 403 → μαύρο toast.
8. WeekDots από `/meals` (≥ 2 καταγραφές = γεμάτη)· «ολοκληρωμένη μέρα» από `/days`.
9. S21 κρατά `[*ημερομηνία]`, επειδή το 403 `not_yet_available` δεν φέρνει ημερομηνία.

### 4.2 Αποφάσεις υλοποίησης που πήρα κατά τη διάρκεια

**Είσοδος και Σήμερα**
- Αν το `/me` έχει ήδη `avatar_id`, το onboarding θεωρείται ότι έγινε. Νέα συσκευή δεν ξαναδείχνει το S03.
- Στο 429 η είσοδος ξεκλειδώνει αυτόματα μετά το `Retry-After`, χωρίς αντίστροφη μέτρηση (delta §6).
- C30 εμφανίζεται με τουλάχιστον ένα γεύμα **και** (απογευματινό ή βραδινό καταγεγραμμένο ή ώρα ≥ 18:00).
  `422 day_has_no_meals` → ήπιο toast.
- «Η πρώτη σου μέρα» = καμία καταγραφή στην εβδομάδα και καμία πλήρης μέρα. Το API δεν δίνει ημερομηνία εγγραφής.
- C12: πλέγμα 3 στηλών για τις 9 ομάδες. Παρούσες = ένωση του `food_groups_today` και των ομάδων των σημερινών
  γευμάτων, ώστε να δουλεύει και εκτός σύνδεσης.
- C14: το API δεν ξεχωρίζει ενθάρρυνση από πρόταση. Το πρώτο μήνυμα είναι σε surface, τα επόμενα με περίγραμμα.
- Εικονίδια για τους 9 κωδικούς ομάδων: δικός μου σχεδιασμός (τα mockups έχουν μόνο κενά svg).

**Καταγραφή**
- Προεπιλεγμένη θέση γεύματος από την ώρα: <10 πρωινό, <12 δεκατιανό, <16 μεσημεριανό, <19 απογευματινό,
  <23 βραδινό, αλλιώς σνακ.
- Tag «Προπόνηση» του S05 (ΑΠΟΦΑΣΗ): δεν υλοποιήθηκε, γιατί το backend δεν έχει πεδίο.
- M04 εμφανίζεται μόνο πριν την πρώτη χρήση της κάμερας.
- Η φωτογραφία κόβεται τετράγωνη στο κέντρο, όπως το πλαίσιο πιάτου του S06.
- Υπόδειξη «Λίγο σκοτεινά» όταν η μέση φωτεινότητα δείγματος 16×16 πέσει κάτω από 48/255.
- S07: «Λίγο ακόμα…» μετά από 8 s, λήξη στα 25 s → «Άργησε πολύ». Και τα δύο όρια είναι εκτιμήσεις.
- M06 ενεργοποιείται όταν η απάντηση έχει **ακριβώς μία** πρόταση «ίσως» με εναλλακτικές. Αλλιώς όλα πάνε στο S08.
- Μερίδα χωρίς προεπιλογή (delta §5). Το «Σωστό, αποθήκευσε» ενεργοποιείται μόνο όταν κάθε γραμμή έχει τρόφιμο και
  μερίδα. Ένα κείμενο κάτω από το κουμπί λέει τι λείπει.
- Αφαίρεση τροφίμου με «Αναίρεση», όπως το C09.
- Confirm εκτός σύνδεσης από φωτογραφία ή κείμενο: δεν μπαίνει στην ουρά, μένει στο S08 με toast.
- 409 στο confirm: toast «Αυτή η καταγραφή δεν στάλθηκε. Γράψ' τη ξανά.» και επιστροφή στο Σήμερα. Δεν ξαναστέλνεται
  με νέο id, για να μη γραφτεί διπλό γεύμα.
- Το πρόχειρο επιβιώνει στο «Πίσω» από S08 προς S05. Καθαρίζει με «Ακύρωση» ή μετά το S11.
- S09 «Συνηθισμένα»: τα 4 παραδείγματα του mockup ως placeholder chips.
- S10: debounce 250 ms. «Πρόσφατα» = έως 5 μοναδικά τρόφιμα από τα αποθηκευμένα γεύματα.

**Ουρά εκτός σύνδεσης**
- Αποστολή στην εκκίνηση και σε κάθε επανασύνδεση, με το ίδιο `client_meal_id` (idempotent).
- 422 / 409 → η εγγραφή αφαιρείται με το ήπιο μήνυμα του delta §7. Offline, 5xx, 401, 403 → μένει στην ουρά.
- Η καταγραφή της ουράς φαίνεται στο S04 και στο S12 ως «σε αναμονή αποστολής».

**Ιστορικό και προφίλ**
- S12 ξεκινά σε προβολή Εβδομάδα, με την πιο πρόσφατη ημέρα πρώτη. Το «μπροστά» είναι ανενεργό στο σήμερα.
- M07: `403 meal_delete_disabled` → «Η διαγραφή δεν είναι διαθέσιμη τώρα. Αν θες να αλλάξει κάτι, μίλα με την ομάδα.»
- M10 «Επικοινωνία με την ομάδα» ανοίγει το M01, όπου είναι τα στοιχεία επικοινωνίας.
- Έξοδος από το S17: καθαρίζει token, cache του Σήμερα και ουρά. Αν η ουρά έχει μη σταλμένες καταγραφές, χάνονται.
- S20β: κάθε σφάλμα πλοήγησης (π.χ. αποτυχία φόρτωσης chunk) οδηγεί στο ErrorView.

---

## 5. Κενά και ανοιχτά θέματα

### 5.1 Περιμένουν υλικό από την ομάδα
- **Γραμματοσειρές**: τα `.woff2` για Commissioner, DM Serif Display, Noto Serif Display λείπουν. Οδηγίες μέσα στο
  `public/fonts/fonts.css`. Μέχρι τότε fallback σε Georgia / system-ui.
- **Λογότυπο**: τα blobs του canvas δεν υπάρχουν. Το `PyramidMark`, το `mark.svg` και τα εικονίδια PWA είναι
  placeholders.
- **Avatars `avatar_09–12`**: υπάρχουν στο backend, χωρίς σχέδιο. Δεν προσφέρονται στο C06.

### 5.2 Κείμενα προς έγκριση (μένουν `[*…]`)

| Κείμενο | Πού | Ποιος εγκρίνει |
|---|---|---|
| Φωτογραφία κρυπτογραφημένη στον server (D1) | S03, M04, S18 (`lib/copy.ts`) | Επιτροπή Ηθικής |
| Διάρκεια τήρησης (D8) | S18 | Ομάδα |
| Κείμενο κινδύνου (D10) | S18, M08 | Επιτροπή Ηθικής |
| Περιγραφές γραμμών 112 / 1056 / 1018 / 10306 | M01 | Ομάδα |
| Στοιχεία επικοινωνίας ομάδας | M01, M10, S18 | Ομάδα |
| «Η φωτογραφία δεν είναι διαθέσιμη τώρα…» | S05, S07 | Ομάδα |
| Πρότυπα «Σήμερα είχες…», «Το μεσημεριανό σου είχε…» | C12, S11 | Διαιτολόγος |
| Εικονογράφηση μερίδας (χέρι / πιάτο) | C10, M02 | Διαιτολόγος |
| «Συνηθισμένες φράσεις» | S09 | Ομάδα |
| Ημερομηνία ανοίγματος | S21 | Ομάδα (και backend) |
| Συνάντηση τέλους, πρόσβαση μετά τη μελέτη | S19 | Ομάδα |
| «Αυτή η ενότητα δεν είναι διαθέσιμη ακόμα» | Βοηθός, Κάρτες | Ομάδα |

### 5.3 Αποφάσεις σχεδιασμού που περιμένουν (σήμανση ΑΠΟΦΑΣΗ)
- Tag «Προπόνηση» στο S05: χρειάζεται πεδίο στο backend αν εγκριθεί.
- «Διόρθωσε» στο S12: δεν υπάρχει endpoint επεξεργασίας γεύματος.
- Διαγραφή γεύματος από το παιδί: `ALLOW_MEAL_DELETE` είναι `false` από προεπιλογή.
- Σύνθετο πιάτο με «Τι είχε μέσα» (S08στ): το `components` είναι πάντα `null` στο backend.
- Μερίδα «εκτίμηση» (S08ε): δεν υπάρχει μοντέλο μερίδας, το `portion` είναι πάντα `null`.
- Όρια χρόνου ανάλυσης (8 s / 25 s): `[*όριο να μετρηθεί]` σε πραγματικές συνθήκες.
- Κανόνας ενεργοποίησης M06: να επιβεβαιωθεί με τη συμπεριφορά του πραγματικού μοντέλου.
- «Πλήρης ημέρα»: δήλωση ή αυτόματα (`COMPLETE_DAY_MODE`), και πότε ακριβώς εμφανίζεται το C30.

### 5.4 Τεχνικά κενά
- **S21 χωρίς ημερομηνία**: το 403 `not_yet_available` δεν φέρνει `CONTROL_ACCESS_FROM`. Αν η ομάδα θέλει ημερομηνία,
  το backend πρέπει να τη δώσει στο σώμα της απάντησης.
- **Αναζήτηση εκτός σύνδεσης**: δουλεύουν μόνο τα «Πρόσφατα». Αναζήτηση και Κατηγορίες θέλουν server. Μια τοπική λίστα
  τροφίμων θα το έλυνε, αλλά δεν συζητήθηκε.
- **Ουρά και Έξοδος**: η Έξοδος σβήνει μη σταλμένες καταγραφές χωρίς προειδοποίηση.
- **Ημερομηνία γεύματος**: πάντα «σήμερα» της συσκευής. Το backend επιτρέπει έως `MEAL_BACKDATE_DAYS`, αλλά δεν
  υπάρχει UI για χθεσινό γεύμα. Συσκευή με λάθος ώρα ή ζώνη μπορεί να πάρει 422.
- **«Η πρώτη σου μέρα»**: προσέγγιση, επειδή το `/me` δεν δίνει ημερομηνία εγγραφής.
- **`vite.config.ts`** είναι εκτός `vue-tsc`, γιατί θα χρειαζόταν `@types/node`.
- **`package-lock.json`** είναι νέο αρχείο και πρέπει να μπει στο commit.
- **Προσβασιμότητα**: δεν έγινε έλεγχος με screen reader ή με εργαλείο αντίθεσης χρωμάτων.

### 5.5 Τι δεν δοκιμάστηκε
- Καμία δοκιμή σε πραγματικό κινητό: κάμερα, άδειες, safe areas, εγκατάσταση PWA, iOS Safari.
- Καμία ροή από άκρη σε άκρη με το backend να τρέχει. Το build περνά, αλλά οι ροές δεν έχουν ελεγχθεί οπτικά.
- Τα PostgreSQL tests (10) δεν έτρεξαν σε αυτή την αναφορά· θέλουν `PG_TEST_URL`.

---

## 6. Τι απομένει να υλοποιηθεί

### 6.1 Εκτός φάσης κατά τη συμφωνία
- **S13 Βοηθός** (Βήμα 5.2): RAG Q&A. Το `POST /ask` απαντά σήμερα `501`.
- **S14 Κάρτες, S15 Παιχνίδι, S16 Αποστολές, M03 DailyCardDrop**: εκκρεμεί ο σχεδιασμός του παιχνιδιού (D6).
- **A01–A04 κονσόλα ερευνητή**: τα admin endpoints υπάρχουν, δεν υπάρχει UI.
- **Food gate στον browser** (S01β λήψη φίλτρου, προέλεγχος στο S06): το `src/ml/foodGate.ts` είναι κενό stub και ο
  φάκελος `public/models/food_gate/` άδειος.

### 6.2 Προτεινόμενα επόμενα βήματα
1. Τρέξιμο με backend σε `ENVIRONMENT=development` και `DEMO_MODE=true` για οπτικό έλεγχο όλων των ροών.
2. Δοκιμή σε Android Chrome και iOS Safari: κάμερα, εγκατάσταση, offline, safe areas.
3. Commit σε ξεχωριστό branch, χωρισμένο σε backend, docs και frontend.
4. Παράδοση γραμματοσειρών, λογότυπου και εγκεκριμένων κειμένων.
5. Απόφαση για όσα του §5.3 και προσαρμογή backend όπου χρειάζεται (π.χ. ημερομηνία στο S21).
6. E2E tests (π.χ. Playwright) για τις κρίσιμες ροές: είσοδος, καταγραφή με αναζήτηση, ουρά offline, R1.
7. Έλεγχος προσβασιμότητας.

---

## 7. Πού είναι τι

| Θέμα | Αρχείο |
|---|---|
| Αιτιολόγηση αποφάσεων backend | `docs/decisions/2026-11-12_backend_gaps.txt` |
| Endpoints | `docs/api.md` |
| Προδιαγραφή backend | `docs/backend_spec_v1.md` |
| Προσχέδια DPIA / GDPR | `docs/dpia.md`, `docs/gdpr-compliance.md` |
| Mockups και αλλαγές σχεδίου | `docs/design/*.dc.html`, `docs/design/mockups_delta.md` |
| API client και διαχείριση 401 / 403 | `frontend/src/api/client.ts`, `frontend/src/router/index.ts` |
| Πρόχειρο καταγραφής | `frontend/src/stores/log.ts` |
| Ουρά εκτός σύνδεσης | `frontend/src/stores/queue.ts` |
| Προετοιμασία εικόνας | `frontend/src/ml/imagePrep.ts` |
| Κείμενα προς έγκριση | `frontend/src/lib/copy.ts` και τα `[*…]` στα views |
| Service worker | `frontend/src/sw/sw.js`, `frontend/vite.config.ts` |
