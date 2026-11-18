#!/bin/bash
# Installation automatique (si nécessaire) puis lancement de StudyAI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${STUDYAI_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
cd "$ROOT"

bold() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok() { printf "  \033[32m✓\033[0m %s\n" "$1"; }

# Déjà lancé ? On ouvre simplement le navigateur.
if curl -fsS "$URL/api/status" >/dev/null 2>&1; then
  ok "StudyAI tourne déjà : ouverture du navigateur."
  open "$URL" 2>/dev/null || true
  exit 0
fi

bash "$ROOT/scripts/setup.sh"

bold "Lancement de StudyAI…"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
cd "$ROOT/backend"
uv run --no-sync uvicorn studyai.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; exit 0' INT TERM HUP

for _ in $(seq 1 60); do
  if curl -fsS "$URL/api/status" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || true
cat <<MSG

  StudyAI est ouvert dans ton navigateur : $URL
  Laisse cette fenêtre ouverte pendant que tu utilises StudyAI.
  Pour quitter : ferme cette fenêtre (ou Ctrl+C). Les analyses en cours reprendront au prochain lancement.

MSG
wait $SERVER
