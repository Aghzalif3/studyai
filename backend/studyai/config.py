"""Configuration : variables d'environnement (.env) + réglages modifiables dans l'interface."""
from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]  # racine du dépôt
ENV_FILE = Path(os.environ.get("STUDYAI_ENV_FILE", ROOT_DIR / ".env"))
load_dotenv(ENV_FILE, override=False)

DATA_DIR = Path(os.environ.get("STUDYAI_DATA_DIR", ROOT_DIR / "data")).expanduser()
FRONTEND_DIR = Path(os.environ.get("STUDYAI_FRONTEND_DIR", ROOT_DIR / "frontend" / "out"))

IS_APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"

CLAUDE_MODELS = {
    "claude-opus-5-5": {"label": "Claude Opus 5.5 (meilleure qualité)", "input": 4.0, "output": 20.0},
    "claude-sonnet-5-5": {"label": "Claude Sonnet 5.5 (équilibré)", "input": 2.0, "output": 10.0},
    "claude-haiku-5-5": {"label": "Claude Haiku 5.5 (le moins cher)", "input": 0.10, "output": 0.50},
}

# Modèles locaux gratuits conseillés (Ollama). Qualité inférieure à Claude.
LOCAL_MODELS = {
    "qwen3:8b": "Qwen3 8B (≈ 5 Go, 16 Go de RAM conseillés)",
    "gemma3:12b": "Gemma 3 12B (≈ 8 Go, 16 Go de RAM minimum)",
    "mistral-small3.2": "Mistral Small 3.2 24B (≈ 15 Go, 32 Go de RAM, meilleur en français)",
    "qwen3:4b": "Qwen3 4B (≈ 3 Go, pour les Mac 8 Go, qualité limitée)",
}

WHISPER_MODELS = ["turbo", "large-v3", "medium", "small", "base", "tiny"]


@dataclass
class Settings:
    whisper_engine: str = "auto"  # auto | mlx | faster | openai
    whisper_model: str = "turbo"
    language: str = "auto"  # auto ou code ISO (fr, en, nl...)
    provider: str = "claude"  # claude (API payante) | local (Ollama, gratuit)
    claude_model: str = "claude-opus-5-5"
    local_model: str = "qwen3:8b"
    effort: str = "high"
    slide_interval: float = 2.0  # secondes entre deux images analysées
    slide_threshold: float = 0.012  # part de pixels modifiés pour compter un changement de diapo
    vision_default: bool = True  # analyser les diapos avec Claude (vision) si une clé existe
    accounting_default: bool = True
    extra: dict = field(default_factory=dict)


def settings_path() -> Path:
    return DATA_DIR / "settings.json"


def load_settings() -> Settings:
    p = settings_path()
    s = Settings()
    if p.exists():
        try:
            raw = json.loads(p.read_text("utf-8"))
            for k, v in raw.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except (OSError, ValueError):
            pass
    return s


def save_settings(s: Settings) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False), "utf-8")


def api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None


def save_api_key(key: str) -> None:
    """Écrit la clé dans le fichier .env local (ignoré par git) et dans l'environnement courant."""
    key = key.strip()
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = [ln for ln in ENV_FILE.read_text("utf-8").splitlines() if not ln.startswith("ANTHROPIC_API_KEY=")]
    if key:
        lines.append(f"ANTHROPIC_API_KEY={key}")
        os.environ["ANTHROPIC_API_KEY"] = key
    else:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    ENV_FILE.write_text("\n".join(lines) + "\n", "utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass


def analysis_model(s: Settings, opts: dict | None = None) -> str:
    """Identifiant du modèle d'analyse : 'claude-…' ou 'ollama:<modèle>'."""
    opts = opts or {}
    provider = opts.get("provider") or s.provider
    if provider == "local":
        return "ollama:" + (opts.get("local_model") or s.local_model)
    return opts.get("claude_model") or s.claude_model
