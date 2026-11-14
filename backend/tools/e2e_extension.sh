#!/usr/bin/env bash
# Bout en bout : vrai serveur (gunicorn + modèle) + vraie extension reconstruite avec VITE_AMIRA_API_URL.
# À la fin, l'extension est reconstruite en mode démonstration (front/dist revient à son état initial).
# Usage (depuis backend/) : bash tools/e2e_extension.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/node/bin:$PATH"
PORT=5000 API="http://localhost:5000" WORK="$(mktemp -d)"
export AMIRA_ENV=development AMIRA_ENGINE=m2m100 AMIRA_DB_PATH="$WORK/amira.sqlite3" AMIRA_RECORDINGS_DIR="$WORK/rec"

.venv/bin/python -m tools.import_gold languages/ff/gold.csv --validator natif-1 --db "$AMIRA_DB_PATH" | head -1
.venv/bin/python -m tools.import_audio languages/ff/audio languages/ff/gold.csv --validator natif-1 --db "$AMIRA_DB_PATH" --recordings "$AMIRA_RECORDINGS_DIR" | head -1
.venv/bin/gunicorn -w 1 --threads 4 -b "127.0.0.1:$PORT" --timeout 30 wsgi:app >"$WORK/server.log" 2>&1 &
SERVER=$!
# Surveille les connexions du serveur : toute connexion dont le port local n'est pas le port du service est SORTANTE.
# (Dossier du modèle : AMIRA_MODEL_DIR, hérité de l'environnement ; défaut models/m2m_ff.)
watch_conns() {
  : >"$WORK/outgoing.log"; : >"$WORK/incoming.log"; echo 0 >"$WORK/samples"; n=0
  while kill -0 "$SERVER" 2>/dev/null; do
    pids="$SERVER|$(pgrep -P "$SERVER" | paste -sd'|' || true)"
    ss -tunpH 2>/dev/null | grep -E "pid=($pids)[,)]" | awk -v p=":$PORT" '$5 ~ p"$" {print >> "'"$WORK"'/incoming.log"; next} {print >> "'"$WORK"'/outgoing.log"}' || true  # grep sans résultat ne doit pas arrêter la surveillance (set -e)
    n=$((n+1)); echo $n >"$WORK/samples"; sleep 0.05
  done
}
watch_conns &
WATCH=$!
restore() {
  kill "$WATCH" 2>/dev/null || true
  kill "$SERVER" 2>/dev/null || true
  (cd ../front && npm run build >/dev/null 2>&1) && echo "extension reconstruite en mode démonstration"
}
trap restore EXIT

for _ in $(seq 120); do curl -sf "$API/v1/ready" >/dev/null && break; sleep 1; done
curl -sf "$API/v1/ready" >/dev/null || { echo "serveur pas prêt"; tail -5 "$WORK/server.log"; exit 1; }
echo "serveur prêt"
(cd ../front && VITE_AMIRA_API_URL="$API" npm run build >/dev/null) && echo "extension construite pour $API"
node tools/e2e_extension.mjs "$API"
echo "--- connexions du serveur : $(cat "$WORK/samples") échantillons ; entrantes vues : $(wc -l <"$WORK/incoming.log") ; SORTANTES : $(wc -l <"$WORK/outgoing.log") (0 attendu) ---"
cat "$WORK/outgoing.log" | head -5
echo "--- journal du serveur (aucun texte attendu) ---"
grep -E "POST|GET" "$WORK/server.log" | sed 's/^[0-9-]* [0-9:,]* INFO //' | sort | uniq -c | sort -rn | head -12
# le journal ne doit contenir aucun texte de la page
if grep -qiE "paiement|carte|historique|code secret|demande est|solde" "$WORK/server.log"; then echo "ÉCHEC : du texte dans le journal"; exit 1; else echo "journal : aucun texte de page trouvé"; fi
