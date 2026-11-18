"""Détection des changements de diapositives + OCR."""
from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np


@dataclass
class SlideCandidate:
    ts: float  # instant où la diapo est stable à l'écran


def change_ratio(a: np.ndarray, b: np.ndarray, pixel_delta: int = 28) -> float:
    """Part des pixels qui ont nettement changé entre deux petites images en niveaux de gris."""
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float((diff > pixel_delta).mean())


def detect_slides(frames: Iterable[tuple[float, np.ndarray]], threshold: float = 0.012,
                  min_gap: float = 4.0, stable_ratio: float | None = None,
                  on_progress: Callable[[float], None] | None = None) -> list[SlideCandidate]:
    """Repère les instants où une nouvelle image stable apparaît.

    - une diapo est retenue quand l'image change de plus de `threshold` par rapport à la
      diapo précédente ET reste stable sur l'image suivante (évite les transitions, les gestes) ;
    - au moins `min_gap` secondes entre deux diapos ;
    - les images presque uniformes (écran noir, fondu) sont ignorées.
    """
    if stable_ratio is None:
        stable_ratio = threshold / 2
    slides: list[SlideCandidate] = []
    ref: np.ndarray | None = None  # image de la dernière diapo retenue
    pending: tuple[float, np.ndarray] | None = None
    last_ts = -1e9
    for ts, img in frames:
        if on_progress:
            on_progress(ts)
        if img.std() < 4:  # écran uni
            pending = None
            continue
        if ref is None:
            if pending is not None and change_ratio(pending[1], img) < stable_ratio:
                slides.append(SlideCandidate(pending[0]))
                ref, last_ts, pending = pending[1], pending[0], None
            else:
                pending = (ts, img)
            continue
        if pending is not None:
            if change_ratio(pending[1], img) < stable_ratio:
                if change_ratio(ref, pending[1]) >= threshold and pending[0] - last_ts >= min_gap:
                    slides.append(SlideCandidate(pending[0]))
                    ref, last_ts = pending[1], pending[0]
                pending = None
                continue
            pending = (ts, img)  # encore en mouvement
            continue
        if change_ratio(ref, img) >= threshold:
            pending = (ts, img)
    if ref is None and pending is not None:
        slides.append(SlideCandidate(pending[0]))
    return slides


def detect_slides_adaptive(frames: list[tuple[float, np.ndarray]], threshold: float = 0.012,
                           max_per_minute: float = 2.0) -> list[SlideCandidate]:
    """Si la vidéo filme le professeur (beaucoup de mouvement), trop de « diapos » sont trouvées :
    on relève alors le seuil jusqu'à un rythme réaliste (2 diapos par minute au plus en moyenne)."""
    duration_min = max((frames[-1][0] - frames[0][0]) / 60, 10) if frames else 10
    found: list[SlideCandidate] = []
    for factor in (1, 2, 4, 8, 16):
        found = detect_slides(iter(frames), threshold=min(threshold * factor, 0.5))
        if len(found) / duration_min <= max_per_minute:
            break
    return found


# --- OCR -----------------------------------------------------------------------

def ocr_backend() -> str | None:
    if importlib.util.find_spec("ocrmac") is not None:
        return "vision"
    if shutil.which("tesseract") or Path("/opt/homebrew/bin/tesseract").exists() or Path("/usr/local/bin/tesseract").exists():
        return "tesseract"
    return None


def _ocr_vision(path: Path) -> str:
    from ocrmac import ocrmac  # type: ignore

    items = ocrmac.OCR(str(path), recognition_level="accurate", language_preference=["fr-FR", "en-US"]).recognize()
    # bbox = (x, y, w, h) normalisés, origine en bas à gauche : on lit de haut en bas, de gauche à droite.
    lines: list[tuple[float, float, str]] = [(1 - (b[1] + b[3]), b[0], t) for t, _c, b in items]
    lines.sort(key=lambda r: (round(r[0] * 40), r[1]))
    out, current_row, buf = [], None, []
    for y, _x, text in lines:
        row = round(y * 40)
        if current_row is not None and row != current_row:
            out.append(" ".join(buf))
            buf = []
        buf.append(text)
        current_row = row
    if buf:
        out.append(" ".join(buf))
    return "\n".join(out)


def _ocr_tesseract(path: Path) -> str:
    import pytesseract  # type: ignore
    from PIL import Image

    for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if not shutil.which("tesseract") and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
    langs = pytesseract.get_languages(config="")
    lang = "+".join(l for l in ("fra", "eng") if l in langs) or None
    with Image.open(path) as im:
        return pytesseract.image_to_string(im, lang=lang).strip()


def ocr_image(path: str | Path) -> str:
    backend = ocr_backend()
    if backend == "vision":
        return _ocr_vision(Path(path))
    if backend == "tesseract":
        return _ocr_tesseract(Path(path))
    return ""


def slide_ranges(slide_ts: list[float], duration: float) -> list[tuple[float, float]]:
    """Chaque diapo reste « à l'écran » jusqu'à la suivante."""
    out = []
    for i, ts in enumerate(slide_ts):
        end = slide_ts[i + 1] if i + 1 < len(slide_ts) else duration
        out.append((ts, max(end, ts)))
    return out
