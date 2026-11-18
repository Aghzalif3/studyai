#!/bin/bash
# Installe (une seule fois) tout ce dont StudyAI a besoin. Relançable sans risque.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bold() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok() { printf "  \033[32m✓\033[0m %s\n" "$1"; }

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
STAMP_DIR="$ROOT/data/.setup"
mkdir -p "$STAMP_DIR"

missing=()
command -v ffmpeg >/dev/null 2>&1 || missing+=(ffmpeg)
command -v uv >/dev/null 2>&1 || missing+=(uv)
command -v node >/dev/null 2>&1 || missing+=(node)
# Homebrew n'est installé que s'il manque vraiment un outil (il demande le mot de passe du Mac).
if (( ${#missing[@]} )); then
  if [[ "$(uname)" != "Darwin" ]]; then
    echo "Installe ${missing[*]} puis relance (ex : apt install ffmpeg nodejs)."; exit 1
  fi
  if ! command -v brew >/dev/null 2>&1; then
    bold "Installation de Homebrew (gestionnaire de logiciels pour Mac)…"
    echo "  Ton mot de passe de session Mac peut être demandé (il ne s'affiche pas quand tu tapes)."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
  fi
  bold "Installation de ${missing[*]}…"
  brew install "${missing[@]}"
fi
ok "FFmpeg, uv, Node.js"

# Moteur Python (Whisper, OCR, API Claude) — environnement isolé dans backend/.venv
LOCK_HASH="$(cat backend/pyproject.toml backend/uv.lock 2>/dev/null | shasum | cut -c1-16)"
if [[ ! -f "$STAMP_DIR/python-$LOCK_HASH" ]]; then
  bold "Installation du moteur Python (Whisper, OCR, Claude)… (première fois : quelques minutes)"
  (cd backend && uv sync --no-dev)
  rm -f "$STAMP_DIR"/python-* && touch "$STAMP_DIR/python-$LOCK_HASH"
fi
ok "Moteur Python"

# Interface web
UI_HASH="$( (cat frontend/package-lock.json; find frontend/src -type f -exec cat {} +; cat frontend/next.config.mjs frontend/tailwind.config.ts) | shasum | cut -c1-16)"
if [[ ! -f "$STAMP_DIR/ui-$UI_HASH" || ! -d frontend/out ]]; then
  bold "Préparation de l'interface…"
  (cd frontend && npm ci --no-audit --no-fund --loglevel=error && npm run build >/dev/null)
  rm -f "$STAMP_DIR"/ui-* && touch "$STAMP_DIR/ui-$UI_HASH"
fi
ok "Interface"

[[ -f .env ]] || { cp .env.example .env; chmod 600 .env; }
ok "Configuration (.env)"

# Raccourci « StudyAI » dans le dossier Applications de l'utilisateur (Launchpad, Spotlight).
if [[ "$(uname)" == "Darwin" && ! -d "$HOME/Applications/StudyAI.app" ]] && command -v osacompile >/dev/null; then
  mkdir -p "$HOME/Applications"
  osacompile -o "$HOME/Applications/StudyAI.app" \
    -e "tell application \"Terminal\" to do script \"'$ROOT/StudyAI.command'\"" \
    -e "tell application \"Terminal\" to activate" >/dev/null 2>&1 && ok "Application StudyAI ajoutée dans ~/Applications (Launchpad, Spotlight)"
fi
