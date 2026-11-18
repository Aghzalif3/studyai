"""File de traitement : une tâche à la fois, reprise automatique après interruption.

Étapes : probe → transcription (segment par segment) → diapositives → OCR → vision → analyse.
Chaque étape terminée est enregistrée dans SQLite ; au redémarrage on reprend là où on s'était arrêté.
"""
from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
from pathlib import Path

from .. import config, db
from ..analysis import analyze, llm
from . import media, slides as slides_mod, transcribe

log = logging.getLogger("studyai.runner")

WEIGHTS = {"probe": 0.01, "transcribe": 0.62, "slides": 0.12, "ocr": 0.05, "vision": 0.05, "analysis": 0.15}
STAGE_LABELS = {
    "probe": "Lecture du fichier",
    "transcribe": "Transcription (Whisper)",
    "slides": "Détection des diapositives",
    "ocr": "Lecture du texte des diapositives",
    "vision": "Analyse visuelle des diapositives (Claude)",
    "analysis": "Analyse du cours (Claude)",
}


class Cancelled(Exception):
    pass


def course_dir(cid: str) -> Path:
    return config.DATA_DIR / "courses" / cid


class Runner:
    def __init__(self) -> None:
        self.q: queue.Queue[str] = queue.Queue()
        self.queued: set[str] = set()
        self.cancel_flags: set[str] = set()
        self.current: str | None = None
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()

    # --- file d'attente ----------------------------------------------------
    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        # Reprise : tout ce qui était en cours ou en attente repart.
        for c in db.list_courses():
            if c["status"] in ("queued", "running"):
                db.update_course(c["id"], status="queued")
                self.enqueue(c["id"])
        self.thread = threading.Thread(target=self._loop, name="studyai-runner", daemon=True)
        self.thread.start()

    def enqueue(self, cid: str) -> None:
        with self.lock:
            if cid in self.queued:
                return
            self.queued.add(cid)
            self.cancel_flags.discard(cid)
        db.update_course(cid, status="queued", error=None)
        self.q.put(cid)

    def cancel(self, cid: str) -> None:
        with self.lock:
            self.cancel_flags.add(cid)
        c = db.get_course(cid)
        if c and c["status"] == "queued":
            db.update_course(cid, status="cancelled", stage=None, eta_seconds=None)

    def _check(self, cid: str) -> None:
        if cid in self.cancel_flags:
            raise Cancelled()

    def _loop(self) -> None:
        while True:
            cid = self.q.get()
            with self.lock:
                self.queued.discard(cid)
                if cid in self.cancel_flags:
                    continue
            self.current = cid
            try:
                self.process(cid)
            except Exception:  # noqa: BLE001 - déjà enregistré dans process
                log.exception("échec du traitement %s", cid)
            finally:
                self.current = None

    def run_sync(self, cid: str) -> None:
        """Traitement immédiat (tests)."""
        self.process(cid)

    # --- traitement ---------------------------------------------------------
    def process(self, cid: str) -> None:
        course = db.get_course(cid)
        if not course:
            return
        db.update_course(cid, status="running", error=None)
        try:
            self._process(course)
            db.update_course(cid, status="done", stage=None, progress=1.0, eta_seconds=0)
        except Cancelled:
            db.update_course(cid, status="cancelled", stage=None, eta_seconds=None)
        except Exception as e:  # noqa: BLE001
            log.exception("erreur")
            db.update_course(cid, status="error", error=str(e) or e.__class__.__name__, eta_seconds=None)
            raise

    def _progress(self, cid: str, stage: str, frac: float, eta: float | None = None) -> None:
        order = list(WEIGHTS)
        base = sum(WEIGHTS[s] for s in order[: order.index(stage)])
        db.update_course(cid, stage=stage, progress=round(base + WEIGHTS[stage] * max(0.0, min(frac, 1.0)), 4),
                         eta_seconds=eta)

    def _process(self, course: dict) -> None:
        cid = course["id"]
        opts = course["options"] or {}
        settings = config.load_settings()
        steps = course["steps"] or {}
        src = course["media_path"]
        workdir = course_dir(cid)
        workdir.mkdir(parents=True, exist_ok=True)
        if not Path(src).exists():
            raise FileNotFoundError("Le fichier du cours est introuvable (supprimé ou déplacé). Réimporte-le.")

        # 1. probe
        if steps.get("probe") != "done":
            self._progress(cid, "probe", 0)
            info = media.probe(src)
            if not info.has_audio and not info.has_video:
                raise ValueError("Ce fichier ne contient ni son ni image.")
            db.update_course(cid, duration=info.duration, has_video=int(info.has_video))
            db.set_step(cid, "probe", "done")
            if not info.has_audio:
                db.set_step(cid, "transcribe", "skipped")
        course = db.get_course(cid) or course
        duration = course["duration"] or 0.0
        has_video = bool(course["has_video"])

        # 2. transcription
        if (course["steps"] or {}).get("transcribe") not in ("done", "skipped"):
            self._transcribe(cid, src, duration, workdir, opts, settings)

        # 3-4. diapositives + OCR
        want_slides = has_video and opts.get("slides", True)
        if want_slides and (db.get_course(cid)["steps"] or {}).get("slides") != "done":
            self._detect_slides(cid, src, duration, workdir, opts, settings)
        if want_slides and (db.get_course(cid)["steps"] or {}).get("ocr") != "done":
            self._ocr(cid)

        # 5-6. Claude
        analyze_on = opts.get("analyze", True)
        if not analyze_on:
            return
        model = config.analysis_model(settings, opts)
        local = llm.is_local(model)
        if not local and not config.api_key():
            db.set_step(cid, "analysis", "no_key")
            return
        if local and llm.ollama_models() is None:
            raise llm.ClaudeError("Ollama ne répond pas : ouvre l'application Ollama, puis clique sur Relancer.")
        effort = opts.get("effort") or settings.effort
        steps = db.get_course(cid)["steps"] or {}
        if (want_slides and not local and opts.get("vision", settings.vision_default)
                and steps.get("vision") != "done"):
            self._check(cid)
            sl = db.rows(db.connect().execute("SELECT * FROM slides WHERE course_id=? ORDER BY idx", (cid,)).fetchall())
            self._progress(cid, "vision", 0)
            analyze.analyze_slides_with_vision(cid, sl, model, effort,
                                               on_progress=lambda f: self._progress(cid, "vision", f))
            db.set_step(cid, "vision", "done")
        if steps.get("analysis") != "done":
            self._check(cid)
            est = 240 if not local else 120 + len(self.document(cid)) / 20000 * 360
            self._progress(cid, "analysis", 0.02, eta=est)
            document = self.document(cid)
            if not document.strip():
                raise ValueError("Rien à analyser : la transcription est vide (vidéo sans parole ?).")
            analyze.run_analysis(
                cid, document, model=model, effort=effort,
                accounting_mode=opts.get("accounting", settings.accounting_default),
                on_progress=lambda f, _k: self._progress(cid, "analysis", f, eta=max(0, (1 - f) * est)),
                only=opts.pop("reanalyze_only", None),
            )
            db.update_course(cid, options=opts)
            db.set_step(cid, "analysis", "done")

    @staticmethod
    def document(cid: str) -> str:
        conn = db.connect()
        segs = db.rows(conn.execute("SELECT * FROM segments WHERE course_id=? ORDER BY start", (cid,)).fetchall())
        sl = db.rows(conn.execute("SELECT * FROM slides WHERE course_id=? ORDER BY idx", (cid,)).fetchall())
        return analyze.build_course_document(segs, sl)

    def _transcribe(self, cid, src, duration, workdir: Path, opts, settings) -> None:
        conn = db.connect()
        plan = media.plan_chunks(duration)
        existing = {r["idx"]: dict(r) for r in conn.execute("SELECT * FROM chunks WHERE course_id=?", (cid,))}
        if len(existing) != len(plan):
            with db.tx() as c:
                c.execute("DELETE FROM chunks WHERE course_id=?", (cid,))
                c.execute("DELETE FROM segments WHERE course_id=?", (cid,))
                for i, (s, e) in enumerate(plan):
                    c.execute("INSERT INTO chunks(course_id,idx,start,end,path) VALUES(?,?,?,?,?)",
                              (cid, i, s, e, str(workdir / f"audio_{i:03d}.wav")))
            existing = {r["idx"]: dict(r) for r in conn.execute("SELECT * FROM chunks WHERE course_id=?", (cid,))}

        engine = opts.get("whisper_engine") or settings.whisper_engine
        model = opts.get("whisper_model") or settings.whisper_model
        language = opts.get("language") or settings.language
        language = None if language in (None, "", "auto") else language
        course = db.get_course(cid)
        if language is None and course and course.get("language"):
            language = course["language"]  # langue détectée sur le premier segment
        prompt = transcribe.ACCOUNTING_PROMPT if opts.get("accounting", settings.accounting_default) else None

        rtf_samples: list[float] = [r["seconds_taken"] / max(r["end"] - r["start"], 1) for r in existing.values()
                                    if r["done"] and r["seconds_taken"]]
        for i in range(len(plan)):
            ch = existing[i]
            if ch["done"]:
                continue
            self._check(cid)
            done_audio = sum(c["end"] - c["start"] for c in existing.values() if c["done"])
            remaining_audio = duration - done_audio
            rtf = sum(rtf_samples) / len(rtf_samples) if rtf_samples else None
            eta = remaining_audio * rtf + self._post_eta(duration) if rtf else None
            self._progress(cid, "transcribe", done_audio / max(duration, 1), eta)

            t0 = time.time()
            wav = Path(ch["path"])
            media.extract_audio_chunk(src, wav, ch["start"], ch["end"])
            audio = media.load_wav_float32(wav)
            res = transcribe.transcribe_chunk(audio, ch["start"], engine, model, language, prompt)
            if language is None and res.language:
                language = res.language
                db.update_course(cid, language=language)
            taken = time.time() - t0
            with db.tx() as c:
                c.execute("DELETE FROM segments WHERE course_id=? AND chunk_idx=?", (cid, i))
                for s in res.segments:
                    c.execute(
                        "INSERT INTO segments(course_id,chunk_idx,start,end,text,avg_logprob,no_speech_prob,uncertain)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (cid, i, s.start, s.end, s.text, s.avg_logprob, s.no_speech_prob, int(s.uncertain)),
                    )
                c.execute("UPDATE chunks SET done=1, seconds_taken=? WHERE course_id=? AND idx=?", (taken, cid, i))
            existing[i]["done"] = 1
            rtf_samples.append(taken / max(ch["end"] - ch["start"], 1))
            wav.unlink(missing_ok=True)  # l'audio temporaire n'est plus utile
        db.set_step(cid, "transcribe", "done")

    @staticmethod
    def _post_eta(duration: float) -> float:
        return duration * 0.02 + 240  # diapos (rapide) + analyse Claude

    def _detect_slides(self, cid, src, duration, workdir: Path, opts, settings) -> None:
        interval = float(opts.get("slide_interval") or settings.slide_interval)
        threshold = float(opts.get("slide_threshold") or settings.slide_threshold)
        self._progress(cid, "slides", 0)
        last = [0.0]

        def prog(ts: float) -> None:
            self._check(cid)
            if ts - last[0] >= 60:
                last[0] = ts
                self._progress(cid, "slides", ts / max(duration, 1), eta=(duration - ts) * 0.02 + 240)

        frames = []  # petites images 160x90 (≈ 14 Ko) : ~50 Mo pour 2 h de vidéo
        for ts, img in media.iter_frames(src, interval):
            prog(ts)
            frames.append((ts, img))
        found = slides_mod.detect_slides_adaptive(frames, threshold=threshold)
        del frames
        slide_dir = workdir / "slides"
        if slide_dir.exists():
            shutil.rmtree(slide_dir)
        slide_dir.mkdir(parents=True)
        ts_list = [f.ts for f in found]
        ranges = slides_mod.slide_ranges(ts_list, duration)
        with db.tx() as c:
            c.execute("DELETE FROM slides WHERE course_id=?", (cid,))
        for i, (ts, end) in enumerate(ranges, start=1):
            self._check(cid)
            path = slide_dir / f"slide_{i:03d}.jpg"
            media.extract_frame(src, min(ts + 0.5, max(duration - 0.1, 0)), path)
            with db.tx() as c:
                c.execute("INSERT INTO slides(course_id,idx,ts,end_ts,image_path) VALUES(?,?,?,?,?)",
                          (cid, i, ts, end, str(path)))
        db.set_step(cid, "slides", "done")
        db.set_step(cid, "ocr", "pending")

    def _ocr(self, cid: str) -> None:
        conn = db.connect()
        sl = db.rows(conn.execute("SELECT * FROM slides WHERE course_id=? ORDER BY idx", (cid,)).fetchall())
        backend = slides_mod.ocr_backend()
        for n, s in enumerate(sl):
            self._check(cid)
            self._progress(cid, "ocr", n / max(len(sl), 1))
            if s.get("ocr_text") is not None or backend is None:
                continue
            try:
                text = slides_mod.ocr_image(s["image_path"])
            except Exception as e:  # noqa: BLE001 - une diapo illisible ne bloque pas le cours
                log.warning("OCR impossible pour la diapo %s : %s", s["idx"], e)
                text = ""
            with db.tx() as c:
                c.execute("UPDATE slides SET ocr_text=? WHERE course_id=? AND idx=?", (text, cid, s["idx"]))
        db.set_step(cid, "ocr", "done" if backend else "no_ocr")


runner = Runner()
