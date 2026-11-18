"""Appels à l'API Claude (clé dans ANTHROPIC_API_KEY, jamais dans le code)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .. import config

# Modèles qui acceptent le repli automatique côté serveur en cas de refus.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class NoApiKey(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Aucune clé API Claude configurée. Ajoute-la dans Réglages (ou dans le fichier .env). "
            "Attention : l'abonnement Claude Pro ne donne pas accès à l'API, la clé se crée sur console.anthropic.com."
        )


class ClaudeError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write: int = 0
    cache_read: int = 0

    def cost(self, model: str) -> float:
        if model.startswith("ollama:"):
            return 0.0
        p = config.CLAUDE_MODELS.get(model, config.CLAUDE_MODELS["claude-opus-5-5"])
        return (
            self.input_tokens * p["input"]
            + self.cache_write * p["input"] * 1.25
            + self.cache_read * p["input"] * 0.1
            + self.output_tokens * p["output"]
        ) / 1_000_000

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_write += other.cache_write
        self.cache_read += other.cache_read


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens).cost(model)


# Remplaçable dans les tests : fn(system, content_blocks, schema, model, effort) -> (dict, Usage)
_call_override: Callable[..., tuple[dict, Usage]] | None = None


def structured_call(system: str, content: list[dict[str, Any]], schema: dict, *, model: str,
                    effort: str = "high", max_tokens: int = 64000) -> tuple[dict, Usage]:
    """Un appel Claude dont la réponse respecte le schéma JSON donné (sorties structurées)."""
    if _call_override is not None:
        return _call_override(system, content, schema, model, effort)
    if is_local(model):
        return ollama_call(system, content, schema, model=model.split(":", 1)[1])
    key = config.api_key()
    if not key:
        raise NoApiKey()
    import anthropic

    client = anthropic.Anthropic(api_key=key, max_retries=4)
    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if model in _FALLBACK_MODELS:
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    try:
        with client.beta.messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ClaudeError("Clé API refusée par Anthropic : vérifie-la dans Réglages.") from e
    except anthropic.PermissionDeniedError as e:
        raise ClaudeError(f"Accès refusé par l'API Claude : {e.message}") from e
    except anthropic.RateLimitError as e:
        raise ClaudeError("Limite d'utilisation de l'API atteinte. Réessaie dans quelques minutes.") from e
    except anthropic.BadRequestError as e:
        if "credit" in str(e.message).lower():
            raise ClaudeError("Crédit API insuffisant : ajoute du crédit sur console.anthropic.com.") from e
        raise ClaudeError(f"Requête refusée par l'API Claude : {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ClaudeError("Impossible de joindre l'API Claude (connexion Internet ?).") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Erreur de l'API Claude ({e.status_code}) : {e.message}") from e

    u = msg.usage
    usage = Usage(
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
        cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
    )
    if msg.stop_reason == "refusal":
        raise ClaudeError("Claude a refusé de traiter ce contenu.")
    if msg.stop_reason == "max_tokens":
        raise ClaudeError("La réponse de Claude a été coupée (cours trop long pour un seul appel).")
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    try:
        return json.loads(text), usage
    except ValueError as e:
        raise ClaudeError("Réponse de Claude illisible (JSON invalide).") from e


# --- Modèle local gratuit (Ollama) ---------------------------------------------

def is_local(model: str) -> bool:
    return model.startswith("ollama:")


def ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def ollama_models() -> list[str] | None:
    """Modèles installés dans Ollama, ou None si Ollama ne tourne pas."""
    try:
        with urllib.request.urlopen(f"{ollama_host()}/api/tags", timeout=2) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except (OSError, ValueError):
        return None


def ollama_call(system: str, content: list[dict[str, Any]], schema: dict, *, model: str,
                num_ctx: int = 16384) -> tuple[dict, Usage]:
    """Appel à un modèle local via Ollama, avec la même sortie JSON imposée (gratuit, hors ligne)."""
    text = "\n\n".join(b["text"] for b in content if b.get("type") == "text")
    images = [b["source"]["data"] for b in content if b.get("type") == "image"]
    user: dict[str, Any] = {"role": "user", "content": text}
    if images:
        user["images"] = images
    body = json.dumps({
        "model": model, "stream": False, "format": schema, "think": False,
        "messages": [{"role": "system", "content": system}, user],
        "options": {"num_ctx": num_ctx, "temperature": 0.2},
    }).encode()
    req = urllib.request.Request(f"{ollama_host()}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code == 404:
            raise ClaudeError(f"Le modèle local « {model} » n'est pas installé. Installe-le depuis Réglages.") from e
        raise ClaudeError(f"Erreur du modèle local : {detail}") from e
    except OSError as e:
        raise ClaudeError("Ollama ne répond pas. Ouvre l'application Ollama (ou relance StudyAI.command).") from e
    usage = Usage(input_tokens=int(data.get("prompt_eval_count") or 0), output_tokens=int(data.get("eval_count") or 0))
    try:
        return json.loads(data["message"]["content"]), usage
    except (KeyError, ValueError) as e:
        raise ClaudeError("Le modèle local a renvoyé une réponse illisible. Essaie un modèle plus grand.") from e


def ollama_pull(model: str) -> None:
    """Télécharge un modèle dans Ollama (peut prendre plusieurs minutes)."""
    req = urllib.request.Request(f"{ollama_host()}/api/pull", data=json.dumps({"model": model, "stream": False}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=7200) as r:
        r.read()
