#!/usr/bin/env bash
# Τοπικό demo του backend με Swagger UI: http://localhost:8000/docs
#
#   scripts/demo_backend.sh                 # φάκελος demo: /tmp/pyramid_demo
#   scripts/demo_backend.sh ~/pyramid_demo  # άλλος φάκελος
#   PORT=8080 HOST=0.0.0.0 scripts/demo_backend.sh   # π.χ. για προβολή από άλλη συσκευή στο ίδιο δίκτυο
#
# Κάθε εκτέλεση: καινούργια βάση SQLite, ΤΥΧΑΙΑ μυστικά, DEMO_MODE=true (demo φίλτρα φωτογραφίας και demo τρόφιμα),
# demo συμμετέχοντες και δοκιμαστικές εικόνες. Δεν διαβάζει ούτε αλλάζει το .env του repo· δεν αγγίζει άλλη βάση.
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
export DATA_DIR="$ROOT/data" FOODS_CSV=demo_foods.csv FOOD_ALIASES_CSV=demo_food_aliases.csv
export LLM_BASE_URL="${LLM_BASE_URL:-}" LLM_MODEL="${LLM_MODEL:-}" CORS_ORIGINS="" ALLOW_MEAL_DELETE=true

cd "$ROOT/backend"
"$PY" -m alembic upgrade head >/dev/null
"$PY" "$ROOT/scripts/seed_demo.py" --photos "$DEMO_DIR/photos"

cat <<INFO

Admin (Swagger → Authorize → AdminToken):
  X-Admin-Token: $ADMIN_TOKEN

Swagger UI:  http://localhost:$PORT/docs      (Ctrl+C για τερματισμό)
Ομάδα ελέγχου: CONTROL_ACCESS_FROM=$(date +%F) scripts/demo_backend.sh  -> το παιδί Γ μπαίνει κανονικά
INFO

exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --no-access-log
