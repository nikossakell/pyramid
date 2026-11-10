"""
app/api/docs.py — Swagger UI (/docs) και OpenAPI (/openapi.json), για δοκιμή και επίδειξη του API.

Ανοιχτά μόνο εκτός production (Settings.docs_enabled· API_DOCS=true σε production: η εφαρμογή δεν ξεκινά). Δεν
περνούν από τον Nginx (που σερβίρει το PWA στο /): το demo τρέχει το backend απευθείας (scripts/demo_backend.sh).
Τα αρχεία του Swagger UI φορτώνονται από το CDN του FastAPI (cdn.jsdelivr.net): το demo θέλει σύνδεση στο internet.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.config import Settings
from app.core.clock import local_today

APP_VERSION = "0.4.0"

DESCRIPTION = """
API του **PYRAMID** (διπλωματική ΑΠΘ): καταγραφή γευμάτων για παιδιά 10–16 ετών, πιλοτική μελέτη 12 εβδομάδων.

### Demo σε πέντε βήματα
1. Τρέξτε `scripts/demo_backend.sh`: φτιάχνει βάση SQLite με demo συμμετέχοντες και τυπώνει τα **κλειδιά πρόσβασης**,
   το **X-Admin-Token** και δοκιμαστικές φωτογραφίες (`meal.jpg`, `dark.jpg`, `too_big.jpg`).
2. `POST /api/v1/auth/login` με το κλειδί ενός παιδιού → αντιγράψτε το `access_token`.
3. **Authorize** → `ChildJWT`: επικολλήστε το token (μένει αποθηκευμένο στη σελίδα).
4. Δοκιμάστε: `/me` → `/foods/search?q=φακ` → `/meals/photo` (επιλέξτε `meal.jpg`) ή `/meals/text` →
   `/meals/confirm` → `/days/{day}/complete` → `/feedback/today` → `/cards`.
5. Ερευνητής: **Authorize** → `AdminToken` με το X-Admin-Token → `/admin/alerts`, `/admin/photo-suspensions`.

### Κανόνες που φαίνονται στο demo
- **R1:** καμία αριθμητική τιμή θρεπτικού, γραμμαρίων ή ποσοστού σε απάντηση προς το παιδί.
- **R3:** οι προτάσεις φωτογραφίας/κειμένου δεν αποθηκεύονται· μόνο το `/meals/confirm`.
- **R4:** φωτογραφία ως raw `image/jpeg` (όχι multipart), μόνο στη RAM· κάθε απόρριψη: ίδιο `422 {"rejected": true}`.
  Το `dark.jpg` απορρίπτεται από το demo φίλτρο· μετά από 5 απορρίψεις η φωτογραφία αναστέλλεται (403).
- Ομάδα ελέγχου: `403 not_yet_available` μέχρι το `CONTROL_ACCESS_FROM`.

⚠️ Με `DEMO_MODE=true` τα φίλτρα και η αναγνώριση είναι **demo** (όχι μοντέλα) και οι τιμές τροφίμων **ενδεικτικές**.
"""

TAGS = [
    {"name": "health", "description": "Χωρίς token."},
    {"name": "auth", "description": "Κλειδί πρόσβασης → JWT. Δεν υπάρχει εγγραφή μέσω API (scripts/create_participant.py)."},
    {"name": "me", "description": "Μόνο ομάδα, avatar και αν η φωτογραφία είναι διαθέσιμη."},
    {"name": "foods", "description": "Αναζήτηση στον πίνακα τροφίμων (χωρίς θρεπτικά)."},
    {"name": "meals", "description": "Προτάσεις από φωτογραφία/κείμενο (δεν αποθηκεύονται) και επιβεβαιωμένα γεύματα."},
    {"name": "days", "description": "Δήλωση πλήρους ημέρας (μετρά στη συνήθη πρόσληψη)."},
    {"name": "feedback", "description": "Rule engine + KrikriPresenter + ασφάλεια. Μόνο κείμενα, χωρίς αριθμούς."},
    {"name": "cards", "description": "Κάρτες της νυχτερινής εργασίας (python -m app.jobs.daily_card_drops)."},
    {"name": "ask", "description": "Ερωτήσεις στη βάση γνώσης (5.2): δεν υπάρχει ακόμα (501)."},
    {"name": "admin", "description": "Για τον ερευνητή (X-Admin-Token, μόνο από το VPN). Χωρίς γεύματα ή κείμενα παιδιών."},
]

SWAGGER_UI_PARAMETERS = {
    "persistAuthorization": True,     # το token μένει μετά από ανανέωση της σελίδας
    "displayRequestDuration": True,
    "tryItOutEnabled": True,
    "docExpansion": "list",
    "defaultModelsExpandDepth": -1,
    "filter": True,
}

CONFIRM_PATH = "/api/v1/meals/confirm"


def install_openapi(app: FastAPI, settings: Settings) -> None:
    """OpenAPI με περιγραφή demo· τα παραδείγματα του /meals/confirm παίρνουν τη σημερινή ημερομηνία."""
    def openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = get_openapi(title=app.title, version=app.version, description=app.description,
                                             routes=app.routes, tags=TAGS)
        today = local_today(settings.tz, app.state.clock()).isoformat()
        examples = (app.openapi_schema["paths"].get(CONFIRM_PATH, {}).get("post", {}).get("requestBody", {})
                    .get("content", {}).get("application/json", {}).get("examples", {}))
        for ex in examples.values():
            ex["value"]["eaten_on"] = today
        return app.openapi_schema
    app.openapi = openapi
