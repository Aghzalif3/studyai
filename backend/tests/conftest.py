import subprocess
from pathlib import Path

import pytest

from studyai import config, db
from studyai.pipeline import transcribe
from studyai.analysis import llm

FONT = next((p for p in ["/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"] if Path(p).exists()), None)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db._local.__dict__.clear()
    yield tmp_path / "data"
    transcribe._factory_override = None
    llm._call_override = None


def make_video(path: Path, slides=("Le bilan", "La TVA", "Les amortissements"), seconds=25, audio=True) -> Path:
    """Vidéo de test : une « diapo » différente toutes les `seconds` secondes + un son."""
    inputs, filters = [], []
    colors = ["white", "lightyellow", "lightblue", "mistyrose"]
    for i, text in enumerate(slides):
        inputs += ["-f", "lavfi", "-i", f"color=c={colors[i % 4]}:s=640x360:d={seconds}:r=10"]
        dt = f"drawtext=text='{text}':fontsize=48:x=(w-tw)/2:y=80:fontcolor=black"
        dt2 = f"drawtext=text='Diapo {i + 1}':fontsize=32:x=40:y=280:fontcolor=navy"
        if FONT:
            dt += f":fontfile={FONT}"
            dt2 += f":fontfile={FONT}"
        filters.append(f"[{i}:v]{dt},{dt2}[v{i}]")
    n = len(slides)
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds * n}"]
    cmd += ["-filter_complex", ";".join(filters + [concat]), "-map", "[v]"]
    if audio:
        cmd += ["-map", f"{n}:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(seconds * n), str(path)]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture
def video(tmp_path):
    return make_video(tmp_path / "cours.mp4")


class FakeEngine:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def transcribe(self, audio, language, prompt):
        self.calls += 1
        dur = len(audio) / 16000
        segs = []
        t = 0.0
        while t < dur:
            end = min(t + 5, dur)
            segs.append(transcribe.Segment(t, end, f"Phrase à {int(t)} secondes sur le bilan.",
                                           avg_logprob=-0.2 if int(t) % 20 else -1.2, no_speech_prob=0.01))
            t = end
        return transcribe.TranscriptResult("fr", segs)


@pytest.fixture
def fake_engine():
    eng = FakeEngine()
    transcribe._factory_override = lambda e, m: eng
    return eng
