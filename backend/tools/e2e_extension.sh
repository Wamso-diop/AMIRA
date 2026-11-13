#!/usr/bin/env bash
# Bout en bout : vrai serveur (gunicorn + modèle) + vraie extension reconstruite avec VITE_AMIRA_API_URL.
# À la fin, l'extension est reconstruite en mode démonstration (front/dist revient à son état initial).
# Usage (depuis backend/) : bash tools/e2e_extension.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/node/bin:$PATH"
PORT=5000 API="http://localhost:5000" WORK="$(mktemp -d)"
export AMIRA_ENV=development AMIRA_ENGINE=nllb AMIRA_DB_PATH="$WORK/amira.sqlite3" AMIRA_RECORDINGS_DIR="$WORK/rec"

.venv/bin/python -m tools.import_gold languages/ff/gold.csv --validator natif-1 --db "$AMIRA_DB_PATH" | head -1
.venv/bin/gunicorn -w 1 --threads 4 -b "127.0.0.1:$PORT" --timeout 30 wsgi:app >"$WORK/server.log" 2>&1 &
SERVER=$!
restore() {
  kill "$SERVER" 2>/dev/null || true
  (cd ../front && npm run build >/dev/null 2>&1) && echo "extension reconstruite en mode démonstration"
}
trap restore EXIT

for _ in $(seq 120); do curl -sf "$API/v1/ready" >/dev/null && break; sleep 1; done
curl -sf "$API/v1/ready" >/dev/null || { echo "serveur pas prêt"; tail -5 "$WORK/server.log"; exit 1; }
echo "serveur prêt"
(cd ../front && VITE_AMIRA_API_URL="$API" npm run build >/dev/null) && echo "extension construite pour $API"
node tools/e2e_extension.mjs "$API"
echo "--- journal du serveur (aucun texte attendu) ---"
grep -E "POST|GET" "$WORK/server.log" | sed 's/^[0-9-]* [0-9:,]* INFO //' | sort | uniq -c | sort -rn | head -12
