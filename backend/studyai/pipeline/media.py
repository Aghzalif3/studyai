"""FFmpeg : analyse du fichier, extraction audio en segments, extraction d'images.

Tout passe par des flux (pipes) : la vidéo n'est jamais chargée entière en mémoire.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

SAMPLE_RATE = 16000
CHUNK_SECONDS = 600  # 10 minutes par segment audio


class FFmpegMissing(RuntimeError):
    pass


def _find(binary: str) -> str:
    env = os.environ.get(f"STUDYAI_{binary.upper()}")
    if env:
        return env
    found = shutil.which(binary)
    if found:
        return found
    for candidate in (f"/opt/homebrew/bin/{binary}", f"/usr/local/bin/{binary}"):
        if Path(candidate).exists():
            return candidate
    raise FFmpegMissing(
        f"{binary} est introuvable. Lance StudyAI.command (il installe FFmpeg) ou `brew install ffmpeg`."
    )


def ffmpeg() -> str:
    return _find("ffmpeg")


def ffprobe() -> str:
    return _find("ffprobe")


@dataclass
class MediaInfo:
    duration: float
    has_video: bool
    has_audio: bool
    width: int | None = None
    height: int | None = None


def probe(path: str | Path) -> MediaInfo:
    out = subprocess.run(
        [ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise ValueError(f"Fichier illisible par FFmpeg : {out.stderr.strip()[:300]}")
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams", [])
    # Les pochettes d'album (attached_pic) ne sont pas une vraie vidéo.
    video = [s for s in streams if s.get("codec_type") == "video"
             and not s.get("disposition", {}).get("attached_pic")]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(data.get("format", {}).get("duration") or 0)
    if not duration:
        for s in streams:
            if s.get("duration"):
                duration = max(duration, float(s["duration"]))
    return MediaInfo(
        duration=duration,
        has_video=bool(video),
        has_audio=bool(audio),
        width=int(video[0]["width"]) if video and video[0].get("width") else None,
        height=int(video[0]["height"]) if video and video[0].get("height") else None,
    )


def plan_chunks(duration: float, chunk_seconds: float | None = None) -> list[tuple[float, float]]:
    """Découpe la durée en segments ; le dernier segment trop court est fusionné au précédent."""
    chunk_seconds = chunk_seconds or CHUNK_SECONDS
    if duration <= 0:
        return [(0.0, 0.0)]
    bounds: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(start + chunk_seconds, duration)
        bounds.append((start, end))
        start = end
    if len(bounds) > 1 and bounds[-1][1] - bounds[-1][0] < 30:
        last = bounds.pop()
        bounds[-1] = (bounds[-1][0], last[1])
    return bounds


def extract_audio_chunk(src: str | Path, dst: str | Path, start: float, end: float) -> None:
    """Extrait [start, end] en WAV mono 16 kHz (format attendu par Whisper)."""
    dst = Path(dst)
    tmp = dst.with_suffix(".part.wav")
    cmd = [
        ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{max(end - start, 0.1):.3f}",
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Extraction audio impossible : {res.stderr.strip()[:300]}")
    tmp.replace(dst)  # écriture atomique : un segment à moitié écrit n'est jamais pris pour terminé


def load_wav_float32(path: str | Path) -> np.ndarray:
    """Lit un WAV PCM 16 bits mono en float32 (un segment de 10 min ≈ 38 Mo)."""
    import wave

    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def iter_frames(src: str | Path, interval: float, width: int = 160, height: int = 90,
                start: float = 0.0) -> Iterator[tuple[float, np.ndarray]]:
    """Génère (instant, image en niveaux de gris réduite) toutes les `interval` secondes.

    FFmpeg décode et réduit les images ; Python ne reçoit que de petites images 160x90.
    """
    cmd = [
        ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src),
        "-vf", f"fps=1/{interval},scale={width}:{height}:flags=area,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    frame_size = width * height
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None
    i = 0
    try:
        while True:
            buf = proc.stdout.read(frame_size)
            if len(buf) < frame_size:
                break
            yield start + i * interval, np.frombuffer(buf, dtype=np.uint8).reshape(height, width)
            i += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def extract_frame(src: str | Path, ts: float, dst: str | Path, max_width: int = 1600) -> None:
    """Capture une image pleine résolution (limitée à 1600 px de large) à l'instant ts."""
    cmd = [
        ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{ts:.3f}", "-i", str(src), "-frames:v", "1",
        "-vf", f"scale='min({max_width},iw)':-2", "-q:v", "3", str(dst),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not Path(dst).exists():
        raise RuntimeError(f"Capture d'image impossible à {ts:.1f}s : {res.stderr.strip()[:200]}")
