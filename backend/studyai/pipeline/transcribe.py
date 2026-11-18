"""Transcription locale avec Whisper.

Trois moteurs, mêmes modèles OpenAI Whisper :
- mlx       : mlx-whisper, accéléré par la puce Apple (M1/M2/M3/M4). Le plus rapide sur Mac.
- faster    : faster-whisper (CTranslate2), rapide sur processeur (Mac Intel, Linux).
- openai    : paquet officiel openai-whisper (PyTorch). Optionnel, plus lent sur Mac.
"""
from __future__ import annotations

import importlib.util
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np

from .. import config

MLX_REPOS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "tiny": "mlx-community/whisper-tiny",
}

# Phrases que Whisper invente souvent sur du silence (bien connues en français).
HALLUCINATIONS = [
    r"sous-titr(age|es?) (réalisés? )?(par|st'?)", r"amara\.org", r"merci d'avoir regardé",
    r"abonnez-vous", r"radio-canada", r"^\W*\.\.\.\W*$",
]
_HALLU_RE = re.compile("|".join(HALLUCINATIONS), re.IGNORECASE)

ACCOUNTING_PROMPT = (
    "Cours de comptabilité en français (Belgique). Vocabulaire : bilan, compte de résultats, PCMN, "
    "écriture comptable, débit, crédit, TVA, facture, note de crédit, RRR, remise, rabais, ristourne, "
    "escompte, amortissement, intérêts, stocks, fournisseurs, clients."
)


@dataclass
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None

    @property
    def uncertain(self) -> bool:
        """Passage dont la transcription est peut-être fausse (à signaler à l'étudiant)."""
        if self.avg_logprob is not None and self.avg_logprob < -0.8:
            return True
        if self.compression_ratio is not None and self.compression_ratio > 2.4:
            return True
        if self.no_speech_prob is not None and self.no_speech_prob > 0.5 and (self.avg_logprob or 0) < -0.4:
            return True
        return False


@dataclass
class TranscriptResult:
    language: str | None
    segments: list[Segment] = field(default_factory=list)


class Engine(Protocol):
    name: str

    def transcribe(self, audio: np.ndarray, language: str | None, prompt: str | None) -> TranscriptResult: ...


def is_hallucination(seg: Segment) -> bool:
    text = seg.text.strip()
    if not text:
        return True
    return bool(_HALLU_RE.search(text)) and (seg.no_speech_prob or 0) > 0.3


def _clean(segments: list[Segment], offset: float) -> list[Segment]:
    out = []
    for s in segments:
        if is_hallucination(s):
            continue
        s.start += offset
        s.end += offset
        s.text = s.text.strip()
        out.append(s)
    return out


class MLXEngine:
    name = "mlx"

    def __init__(self, model: str):
        self.repo = MLX_REPOS.get(model, model)

    def transcribe(self, audio, language, prompt):
        import mlx_whisper  # type: ignore

        r = mlx_whisper.transcribe(
            audio, path_or_hf_repo=self.repo, language=language, initial_prompt=prompt,
            condition_on_previous_text=False, hallucination_silence_threshold=2.0, word_timestamps=False,
        )
        segs = [Segment(s["start"], s["end"], s["text"], s.get("avg_logprob"), s.get("no_speech_prob"),
                        s.get("compression_ratio")) for s in r.get("segments", [])]
        return TranscriptResult(r.get("language"), segs)


class FasterEngine:
    name = "faster"

    def __init__(self, model: str):
        from faster_whisper import WhisperModel  # type: ignore

        self.model = WhisperModel(model, device="auto", compute_type="int8")

    def transcribe(self, audio, language, prompt):
        segments, info = self.model.transcribe(
            audio, language=language, initial_prompt=prompt, beam_size=5, vad_filter=True,
            condition_on_previous_text=False,
        )
        segs = [Segment(s.start, s.end, s.text, s.avg_logprob, s.no_speech_prob, s.compression_ratio)
                for s in segments]
        return TranscriptResult(info.language, segs)


class OpenAIEngine:
    name = "openai"

    def __init__(self, model: str):
        import whisper  # type: ignore

        self.model = whisper.load_model(model)

    def transcribe(self, audio, language, prompt):
        r = self.model.transcribe(audio, language=language, initial_prompt=prompt, fp16=False,
                                  condition_on_previous_text=False)
        segs = [Segment(s["start"], s["end"], s["text"], s.get("avg_logprob"), s.get("no_speech_prob"),
                        s.get("compression_ratio")) for s in r.get("segments", [])]
        return TranscriptResult(r.get("language"), segs)


ENGINES: dict[str, Callable[[str], Any]] = {"mlx": MLXEngine, "faster": FasterEngine, "openai": OpenAIEngine}
_MODULES = {"mlx": "mlx_whisper", "faster": "faster_whisper", "openai": "whisper"}


def available_engines() -> list[str]:
    out = []
    for name, mod in _MODULES.items():
        if name == "mlx" and not config.IS_APPLE_SILICON:
            continue
        if importlib.util.find_spec(mod) is not None:
            out.append(name)
    return out


def resolve_engine_name(requested: str) -> str:
    avail = available_engines()
    if requested != "auto":
        if requested not in avail:
            raise RuntimeError(f"Le moteur Whisper « {requested} » n'est pas installé sur cet ordinateur.")
        return requested
    for pref in ("mlx", "faster", "openai"):
        if pref in avail:
            return pref
    raise RuntimeError("Aucun moteur Whisper installé. Relance StudyAI.command pour l'installer.")


_cache: dict[tuple[str, str], Any] = {}
_cache_lock = threading.Lock()
_factory_override: Callable[[str, str], Engine] | None = None  # utilisé par les tests


def get_engine(engine: str, model: str) -> Engine:
    if _factory_override is not None:
        return _factory_override(engine, model)
    name = resolve_engine_name(engine)
    key = (name, model)
    with _cache_lock:
        if key not in _cache:
            _cache.clear()  # un seul modèle en mémoire à la fois
            _cache[key] = ENGINES[name](model)
        return _cache[key]


def transcribe_chunk(audio: np.ndarray, offset: float, engine: str, model: str,
                     language: str | None, prompt: str | None) -> TranscriptResult:
    eng = get_engine(engine, model)
    res = eng.transcribe(audio, language, prompt)
    res.segments = _clean(res.segments, offset)
    return res
