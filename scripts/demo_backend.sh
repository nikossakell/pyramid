#!/usr/bin/env bash
# Τοπικό demo του backend με Swagger UI: http://localhost:8000/docs
#
#   scripts/demo_backend.sh                 # φάκελος demo: /tmp/pyramid_demo
#   scripts/demo_backend.sh ~/pyramid_demo  # άλλος φάκελος
#   PORT=8080 HOST=0.0.0.0 scripts/demo_backend.sh   # π.χ. για προβολή από άλλη συσκευή στο ίδιο δίκτυο
#
# Κάθε εκτέλεση: καινούργια βάση SQLite, ΤΥΧΑΙΑ μυστικά, DEMO_MODE=true (demo φίλτρα φωτογραφίας και demo τρόφιμα),
# demo συμμετέχοντες και δοκιμαστικές εικόνες. Δεν διαβάζει ούτε αλλάζει το .env του repo· δεν αγγίζει άλλη βάση.
# Στο τέλος τυπώνει εντολές curl που δείχνουν: /food-groups, alternatives, idempotency του /meals/confirm, system-status.
# ΜΟΝΟ για επίδειξη: ποτέ με πραγματικά δεδομένα παιδιών.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="${1:-${DEMO_DIR:-/tmp/pyramid_demo}}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PY="${PYTHON:-$ROOT/venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

mkdir -p "$DEMO_DIR"
rm -f "$DEMO_DIR/demo.db"
secret() { "$PY" -c 'import secrets; print(secrets.token_urlsafe(48))'; }

# Ρητές τιμές για ΟΛΑ όσα επηρεάζουν το demo, ώστε ένα .env του repo να μην τα αλλάζει.
export ENVIRONMENT=development DEMO_MODE=true API_DOCS=true LOG_LEVEL=INFO
export DATABASE_URL="sqlite:///$DEMO_DIR/demo.db"
export JWT_SECRET="$(secret)" ACCESS_KEY_PEPPER="$(secret)" ADMIN_TOKEN="$(secret)"
export APP_TIMEZONE="${APP_TIMEZONE:-Europe/Athens}" CONTROL_ACCESS_FROM="${CONTROL_ACCESS_FROM:-}"
export STUDY_DURATION_DAYS="${STUDY_DURATION_DAYS:-84}" POST_STUDY_ACCESS="${POST_STUDY_ACCESS:-false}"
export COMPLETE_DAY_MODE="${COMPLETE_DAY_MODE:-declared}" AUTO_COMPLETE_MIN_MEALS="${AUTO_COMPLETE_MIN_MEALS:-2}"
export DATA_DIR="$ROOT/data" FOODS_CSV=demo_foods.csv FOOD_ALIASES_CSV=demo_food_aliases.csv
export DISPLAY_FOOD_GROUPS_CSV=display_food_groups.csv
export LLM_BASE_URL="${LLM_BASE_URL:-}" LLM_MODEL="${LLM_MODEL:-}" CORS_ORIGINS="" ALLOW_MEAL_DELETE=true
# Προαιρετικά πραγματικό OliveGemma με demo φίλτρα: PHOTO_RECOGNIZER=olivegemma scripts/demo_backend.sh
# (θέλει τα βάρη στο models/olivegemma-3b· σε CPU, λεπτά ανά φωτογραφία)
export PHOTO_RECOGNIZER="${PHOTO_RECOGNIZER:-none}" PHOTO_CONTENT_FILTER="${PHOTO_CONTENT_FILTER:-none}"
export OLIVEGEMMA_TIMEOUT_S="${OLIVEGEMMA_TIMEOUT_S:-2400}"

cd "$ROOT/backend"
"$PY" -m alembic upgrade head >/dev/null
"$PY" "$ROOT/scripts/seed_demo.py" --photos "$DEMO_DIR/photos"

cat <<INFO

Admin (Swagger → Authorize → AdminToken):
  X-Admin-Token: $ADMIN_TOKEN

Swagger UI:  http://localhost:$PORT/docs      (Ctrl+C για τερματισμό)
Ομάδα ελέγχου: CONTROL_ACCESS_FROM=$(date +%F) scripts/demo_backend.sh  -> το παιδί Γ μπαίνει κανονικά
Τέλος μελέτης: STUDY_DURATION_DAYS=7 scripts/demo_backend.sh           -> τα παιδιά Α και Δ παίρνουν 403 {"study_ended": true}

Τι να δείξετε (σε δεύτερο τερματικό, με το κλειδί του παιδιού Β από πάνω· ή τα ίδια βήματα στο Swagger):
  API=http://localhost:$PORT/api/v1
  KEY=<κλειδί του παιδιού Β>
  TOKEN=\$(curl -s \$API/auth/login -H 'Content-Type: application/json' -d "{\\"access_key\\": \\"\$KEY\\"}" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  AUTH="Authorization: Bearer \$TOKEN"

  # 1. Ομάδες εμφάνισης (και οι 11· shown=false για αλλαντικά και αλμυρά σνακ) και «Κατηγορίες»
  curl -s \$API/food-groups -H "\$AUTH"
  curl -s "\$API/foods/search?group=legumes" -H "\$AUTH"

  # 2. Προτάσεις με alternatives («Μήπως είναι…» / «Δεν το βρήκα, διάλεξε από αυτά»)
  curl -s \$API/meals/photo -H "\$AUTH" -H 'Content-Type: image/jpeg' --data-binary @$DEMO_DIR/photos/meal.jpg
  curl -s \$API/meals/text -H "\$AUTH" -H 'Content-Type: application/json' -d '{"text": "σπανακόπιτα και φακές"}'

  # 3. Idempotency: το ίδιο σώμα δύο φορές -> 201 (created: true) και μετά 200 (created: false), ένα γεύμα
  MEAL='{"client_meal_id": "'\$("$PY" -c 'import uuid; print(uuid.uuid4())')'", "eaten_on": "$(date +%F)", "meal_slot": "lunch", "source": "camera", "items": [{"food_id": "lentils", "portion": "medium", "ai_suggested": true}]}'
  curl -s -w '  [%{http_code}]\\n' \$API/meals/confirm -H "\$AUTH" -H 'Content-Type: application/json' -d "\$MEAL"
  curl -s -w '  [%{http_code}]\\n' \$API/meals/confirm -H "\$AUTH" -H 'Content-Type: application/json' -d "\$MEAL"

  # 4. Κονσόλα ερευνητή: κατάσταση συστήματος, συμμετέχοντες, χρονολόγιο alert
  ADMIN='X-Admin-Token: $ADMIN_TOKEN'
  curl -s \$API/admin/system-status -H "\$ADMIN"
  curl -s \$API/admin/participants -H "\$ADMIN"
  curl -s "\$API/admin/alerts?status=new" -H "\$ADMIN"      # και: \$API/admin/alerts/<id> για το χρονολόγιο
INFO

exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --no-access-log
