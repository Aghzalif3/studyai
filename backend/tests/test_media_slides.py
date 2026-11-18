import numpy as np

from studyai.pipeline import media, slides
from conftest import make_video


def test_probe_and_chunks(video):
    info = media.probe(video)
    assert info.has_video and info.has_audio
    assert abs(info.duration - 75) < 1
    assert media.plan_chunks(75, 30) == [(0, 30), (30, 75)]  # dernier morceau < 30 s fusionné
    assert media.plan_chunks(3600 * 2.5)[-1][1] == 9000
    assert len(media.plan_chunks(3600 * 2.5)) == 15


def test_extract_audio_chunk(video, tmp_path):
    out = tmp_path / "a.wav"
    media.extract_audio_chunk(video, out, 10, 40)
    audio = media.load_wav_float32(out)
    assert abs(len(audio) / media.SAMPLE_RATE - 30) < 0.1
    assert audio.dtype == np.float32 and np.abs(audio).max() > 0.1


def test_detect_three_slides(video):
    found = slides.detect_slides(media.iter_frames(video, 2.0))
    ts = [f.ts for f in found]
    assert len(ts) == 3, ts
    assert ts[0] < 5 and 24 <= ts[1] <= 30 and 49 <= ts[2] <= 55


def test_no_slide_on_audio_only(tmp_path):
    v = make_video(tmp_path / "same.mp4", slides=("Titre", "Titre"), seconds=10)
    found = slides.detect_slides(media.iter_frames(v, 2.0))
    assert len(found) == 1  # deux fois la même diapo = une seule diapo


def test_transitions_ignored():
    rng = np.random.default_rng(0)
    a = np.full((90, 160), 200, np.uint8)
    a[20:40, 20:140] = 0
    b = np.full((90, 160), 200, np.uint8)
    b[50:80, 10:150] = 0
    noisy = [rng.integers(0, 255, (90, 160), dtype=np.uint8) for _ in range(3)]
    frames = [(0, a), (2, a), (4, noisy[0]), (6, noisy[1]), (8, b), (10, b), (12, b)]
    ts = [s.ts for s in slides.detect_slides(iter(frames), min_gap=1)]
    assert ts == [0, 8]


def test_adaptive_threshold_on_camera_footage():
    rng = np.random.default_rng(1)
    # « professeur filmé » : chaque image change un peu (5 % des pixels), pendant 10 minutes
    base = np.full((90, 160), 128, np.uint8)
    frames = []
    for i in range(300):
        img = base.copy()
        mask = rng.random((90, 160)) < 0.05
        img[mask] = 255
        frames.append((i * 2.0, img))
    found = slides.detect_slides_adaptive(frames)
    assert len(found) <= 20


def test_frame_capture(video, tmp_path):
    out = tmp_path / "f.jpg"
    media.extract_frame(video, 30, out)
    assert out.stat().st_size > 1000


def test_slide_ranges():
    assert slides.slide_ranges([0, 10, 30], 50) == [(0, 10), (10, 30), (30, 50)]
