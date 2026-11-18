"""API locale de StudyAI (FastAPI). Sert aussi l'interface web construite (frontend/out)."""
from __future__ import annotations

import json
import logging
import mimetypes
import re
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from . import config, db, exports, revision
from .analysis import accounting, analyze, llm
from .pipeline import media, slides as slides_mod, transcribe
from .pipeline.runner import STAGE_LABELS, course_dir, runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".ts"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.connect()
    runner.start()
    yield


app = FastAPI(title="StudyAI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])


def _course_or_404(cid: str) -> dict:
    c = db.get_course(cid)
    if not c:
        raise HTTPException(404, "Cours introuvable")
    return c


def _public_course(c: dict) -> dict:
    c = dict(c)
    c.pop("media_path", None)
    c["stage_label"] = STAGE_LABELS.get(c.get("stage") or "", None)
    conn = db.connect()
    c["counts"] = {
        "segments": conn.execute("SELECT COUNT(*) FROM segments WHERE course_id=?", (c["id"],)).fetchone()[0],
        "slides": conn.execute("SELECT COUNT(*) FROM slides WHERE course_id=?", (c["id"],)).fetchone()[0],
        "flashcards": conn.execute("SELECT COUNT(*) FROM flashcards WHERE course_id=?", (c["id"],)).fetchone()[0],
    }
    c["analysis_kinds"] = [r[0] for r in conn.execute("SELECT kind FROM analysis WHERE course_id=?", (c["id"],))]
    return c


# --- état & réglages -----------------------------------------------------------

@app.get("/api/status")
def status() -> dict:
    try:
        media.ffmpeg()
        ffmpeg_ok = True
    except media.FFmpegMissing:
        ffmpeg_ok = False
    key = config.api_key()
    s = config.load_settings()
    return {
        "ffmpeg": ffmpeg_ok,
        "whisper_engines": transcribe.available_engines(),
        "apple_silicon": config.IS_APPLE_SILICON,
        "ocr": slides_mod.ocr_backend(),
        "api_key": bool(key),
        "api_key_hint": f"…{key[-4:]}" if key else None,
        "ollama_models": llm.ollama_models(),
        "pulling": sorted(_pulls),
        "settings": asdict(s),
        "claude_models": config.CLAUDE_MODELS,
        "local_models": config.LOCAL_MODELS,
        "whisper_models": config.WHISPER_MODELS,
        "current_job": runner.current,
    }


class SettingsIn(BaseModel):
    whisper_engine: str | None = None
    whisper_model: str | None = None
    language: str | None = None
    provider: str | None = None
    claude_model: str | None = None
    local_model: str | None = None
    effort: str | None = None
    slide_interval: float | None = None
    slide_threshold: float | None = None
    vision_default: bool | None = None
    accounting_default: bool | None = None


@app.put("/api/settings")
def put_settings(body: SettingsIn) -> dict:
    s = config.load_settings()
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    if s.provider not in ("claude", "local"):
        raise HTTPException(400, "Fournisseur inconnu")
    if s.claude_model not in config.CLAUDE_MODELS:
        raise HTTPException(400, "Modèle Claude inconnu")
    if s.effort not in ("low", "medium", "high", "xhigh", "max"):
        raise HTTPException(400, "Niveau d'effort inconnu")
    config.save_settings(s)
    return asdict(s)


class KeyIn(BaseModel):
    key: str


@app.put("/api/settings/api-key")
def put_key(body: KeyIn) -> dict:
    key = body.key.strip()
    if key and not key.startswith("sk-ant-"):
        raise HTTPException(400, "Une clé API Anthropic commence par « sk-ant- ».")
    config.save_api_key(key)
    return {"api_key": bool(key)}


_pulls: set[str] = set()


class PullIn(BaseModel):
    model: str


@app.post("/api/ollama/pull")
def ollama_pull(body: PullIn) -> dict:
    if llm.ollama_models() is None:
        raise HTTPException(503, "Ollama n'est pas lancé. Ouvre l'application Ollama puis réessaie.")
    if not re.fullmatch(r"[\w.\-:/]+", body.model):
        raise HTTPException(400, "Nom de modèle invalide")

    def work() -> None:
        try:
            llm.ollama_pull(body.model)
        except Exception:  # noqa: BLE001
            logging.exception("téléchargement Ollama")
        finally:
            _pulls.discard(body.model)

    _pulls.add(body.model)
    threading.Thread(target=work, daemon=True).start()
    return {"pulling": body.model}


# --- cours ---------------------------------------------------------------------

@app.get("/api/courses")
def courses() -> list[dict]:
    return [_public_course(c) for c in db.list_courses()]


@app.post("/api/courses/upload")
async def upload(request: Request) -> dict:
    """Envoi du fichier en flux (pas de chargement en mémoire), par morceaux de 1 Mo."""
    filename = unquote(request.headers.get("x-filename", "")).strip() or "cours"
    filename = Path(filename).name
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXT | VIDEO_EXT:
        raise HTTPException(400, f"Format non pris en charge ({ext or 'sans extension'}).")
    try:
        options = json.loads(unquote(request.headers.get("x-options", "{}")) or "{}")
    except ValueError:
        options = {}
    title = options.pop("title", None) or Path(filename).stem.replace("_", " ")
    cid = db.new_id()
    d = course_dir(cid)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"source{ext}"
    tmp = d / f"source{ext}.part"
    size = 0
    try:
        with tmp.open("wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                size += len(chunk)
    except Exception as e:  # noqa: BLE001 - client parti en cours d'envoi
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "Envoi interrompu") from e
    if size == 0:
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "Fichier vide")
    tmp.replace(dst)
    t = db.now()
    with db.tx() as c:
        c.execute("INSERT INTO courses(id,title,filename,media_path,options,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                  (cid, title, filename, str(dst), json.dumps(options), t, t))
    runner.enqueue(cid)
    return _public_course(db.get_course(cid))


@app.get("/api/courses/{cid}")
def course(cid: str) -> dict:
    return _public_course(_course_or_404(cid))


class CoursePatch(BaseModel):
    title: str | None = None


@app.patch("/api/courses/{cid}")
def patch_course(cid: str, body: CoursePatch) -> dict:
    _course_or_404(cid)
    if body.title:
        db.update_course(cid, title=body.title.strip())
    return _public_course(db.get_course(cid))


@app.delete("/api/courses/{cid}")
def delete_course(cid: str) -> dict:
    _course_or_404(cid)
    runner.cancel(cid)
    db.delete_course(cid)
    import shutil

    shutil.rmtree(course_dir(cid), ignore_errors=True)
    return {"deleted": cid}


@app.post("/api/courses/{cid}/retry")
def retry(cid: str) -> dict:
    _course_or_404(cid)
    runner.enqueue(cid)
    return _public_course(db.get_course(cid))


@app.post("/api/courses/{cid}/cancel")
def cancel(cid: str) -> dict:
    _course_or_404(cid)
    runner.cancel(cid)
    return _public_course(db.get_course(cid))


class ReanalyzeIn(BaseModel):
    only: list[str] | None = None
    provider: str | None = None
    claude_model: str | None = None
    local_model: str | None = None
    accounting: bool | None = None
    vision: bool | None = None


@app.post("/api/courses/{cid}/analyze")
def reanalyze(cid: str, body: ReanalyzeIn) -> dict:
    c = _course_or_404(cid)
    if c["status"] == "running":
        raise HTTPException(409, "Le cours est en cours de traitement.")
    opts = c["options"] or {}
    for k in ("provider", "claude_model", "local_model", "accounting", "vision"):
        v = getattr(body, k)
        if v is not None:
            opts[k] = v
    opts["analyze"] = True
    opts["reanalyze_only"] = body.only or ["course", "notions", "revision"]
    steps = c["steps"] or {}
    steps["analysis"] = "pending"
    db.update_course(cid, options=opts, steps=steps)
    runner.enqueue(cid)
    return _public_course(db.get_course(cid))


@app.get("/api/courses/{cid}/estimate")
def estimate(cid: str) -> dict:
    _course_or_404(cid)
    s = config.load_settings()
    doc = runner.document(cid)
    n = db.connect().execute("SELECT COUNT(*) FROM slides WHERE course_id=?", (cid,)).fetchone()[0]
    return {m: analyze.estimate(len(doc), n, m, s.vision_default) for m in config.CLAUDE_MODELS}


@app.get("/api/estimate")
def estimate_duration(minutes: float = 60, slides: int = 40) -> dict:
    """Estimation avant import : ~150 mots/min de parole, ~6,5 caractères par mot."""
    chars = int(minutes * 150 * 6.5)
    return {m: analyze.estimate(chars, slides, m, True) for m in config.CLAUDE_MODELS}


@app.get("/api/courses/{cid}/media")
def course_media(cid: str) -> FileResponse:
    c = _course_or_404(cid)
    path = Path(c["media_path"])
    if not path.exists():
        raise HTTPException(404, "Fichier source supprimé")
    mt = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() in (".mov", ".m4v"):
        mt = "video/mp4" if path.suffix.lower() == ".m4v" else "video/quicktime"
    return FileResponse(path, media_type=mt)


@app.get("/api/courses/{cid}/transcript")
def transcript(cid: str) -> list[dict]:
    _course_or_404(cid)
    return db.rows(db.connect().execute(
        "SELECT rowid AS id, start, end, text, uncertain FROM segments WHERE course_id=? ORDER BY start", (cid,)).fetchall())


class SegmentEdit(BaseModel):
    text: str


@app.put("/api/courses/{cid}/transcript/{seg_id}")
def edit_segment(cid: str, seg_id: int, body: SegmentEdit) -> dict:
    """Corriger un mot mal reconnu : le texte corrigé n'est plus marqué incertain."""
    with db.tx() as c:
        c.execute("UPDATE segments SET text=?, uncertain=0 WHERE rowid=? AND course_id=?", (body.text.strip(), seg_id, cid))
    return {"ok": True}


@app.get("/api/courses/{cid}/slides")
def course_slides(cid: str) -> list[dict]:
    _course_or_404(cid)
    out = []
    for s in db.rows(db.connect().execute("SELECT * FROM slides WHERE course_id=? ORDER BY idx", (cid,)).fetchall()):
        s.pop("image_path", None)
        if s.get("vision"):
            try:
                s["vision"] = json.loads(s["vision"])
            except ValueError:
                s["vision"] = None
        out.append(s)
    return out


@app.get("/api/courses/{cid}/slides/{idx}/image")
def slide_image(cid: str, idx: int) -> FileResponse:
    r = db.connect().execute("SELECT image_path FROM slides WHERE course_id=? AND idx=?", (cid, idx)).fetchone()
    if not r or not Path(r[0]).exists():
        raise HTTPException(404, "Image introuvable")
    return FileResponse(r[0], media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/courses/{cid}/analysis")
def course_analysis(cid: str) -> dict:
    _course_or_404(cid)
    return db.get_analysis(cid)


def _segments(cid: str) -> list[dict]:
    return db.rows(db.connect().execute("SELECT * FROM segments WHERE course_id=? ORDER BY start", (cid,)).fetchall())


def _safe_name(title: str) -> str:
    return re.sub(r"[^\w\- ]+", "", title).strip().replace(" ", "_")[:80] or "cours"


@app.get("/api/courses/{cid}/export/{fmt}")
def export(cid: str, fmt: str) -> Response:
    c = _course_or_404(cid)
    name = _safe_name(c["title"])
    disp = lambda ext: {"Content-Disposition": f'attachment; filename="{name}.{ext}"'}  # noqa: E731
    if fmt == "txt":
        return PlainTextResponse(exports.to_txt(_segments(cid)), headers=disp("txt"))
    if fmt == "srt":
        return PlainTextResponse(exports.to_srt(_segments(cid)), headers=disp("srt"), media_type="application/x-subrip")
    if fmt == "pdf":
        return Response(exports.transcript_pdf(c["title"], _segments(cid)), media_type="application/pdf", headers=disp("pdf"))
    analysis = db.get_analysis(cid)
    if fmt in ("course.pdf", "course.md") and not analysis:
        raise HTTPException(400, "Le cours n'a pas encore été analysé.")
    if fmt == "course.md":
        return PlainTextResponse(exports.course_markdown(c, analysis), headers=disp("md"), media_type="text/markdown")
    if fmt == "course.pdf":
        return Response(exports.course_pdf(c, analysis), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}_cours.pdf"'})
    raise HTTPException(404, "Format inconnu")


# --- révision ------------------------------------------------------------------

@app.get("/api/flashcards")
def flashcards(course_id: str | None = None, due: bool = False) -> list[dict]:
    q, args = "SELECT * FROM flashcards WHERE 1=1", []
    if course_id:
        q += " AND course_id=?"
        args.append(course_id)
    if due:
        q += " AND due<=?"
        args.append(db.now())
    q += " ORDER BY due"
    return db.rows(db.connect().execute(q, args).fetchall())


class ReviewIn(BaseModel):
    grade: int


@app.post("/api/flashcards/{card_id}/review")
def review(card_id: str, body: ReviewIn) -> dict:
    if body.grade not in revision.GRADES:
        raise HTTPException(400, "Note entre 0 et 3")
    try:
        return revision.review_card(card_id, body.grade)
    except KeyError as e:
        raise HTTPException(404, "Carte introuvable") from e


class AttemptIn(BaseModel):
    course_id: str
    mode: str
    score: float
    total: float
    duration_seconds: float | None = None
    details: list[dict[str, Any]] = []


@app.post("/api/attempts")
def attempt(body: AttemptIn) -> dict:
    _course_or_404(body.course_id)
    aid = revision.record_attempt(body.course_id, body.mode, body.score, body.total, body.duration_seconds, body.details)
    return {"id": aid}


@app.get("/api/stats")
def stats(course_id: str | None = None) -> dict:
    return revision.stats(course_id)


class GradeIn(BaseModel):
    course_id: str
    question_id: str
    answer: str


@app.post("/api/grade")
def grade(body: GradeIn) -> dict:
    _course_or_404(body.course_id)
    rev = db.get_analysis(body.course_id).get("revision", {})
    q = next((q for q in rev.get("open_questions", []) if q.get("id") == body.question_id), None)
    if not q:
        raise HTTPException(404, "Question introuvable")
    s = config.load_settings()
    course = db.get_course(body.course_id) or {}
    model = config.analysis_model(s, course.get("options"))
    try:
        result, usage = analyze.grade_open_answer(q, body.answer, model=model)
    except llm.NoApiKey as e:
        raise HTTPException(400, str(e)) from e
    except llm.ClaudeError as e:
        raise HTTPException(502, str(e)) from e
    db.add_cost(body.course_id, usage.cost(model))
    return result


# --- outils comptables ---------------------------------------------------------

class InvoiceIn(BaseModel):
    gross: float
    discount_rate: float = 0
    rebate_rate: float = 0
    cash_discount_rate: float = 0
    vat_rate: float = 0.21
    transport: float = 0


@app.post("/api/tools/invoice")
def tool_invoice(b: InvoiceIn) -> dict:
    return accounting.invoice(**b.model_dump())


class DepIn(BaseModel):
    cost: float
    years: int
    method: str = "lineaire"
    residual: float = 0
    coefficient: float = 2.0
    first_year_prorata: float = 1.0


@app.post("/api/tools/depreciation")
def tool_dep(b: DepIn) -> dict:
    try:
        return accounting.depreciation(**b.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class InterestIn(BaseModel):
    capital: float
    annual_rate: float
    days: int = 0
    years: float = 0
    kind: str = "simple"
    day_basis: int = 365


@app.post("/api/tools/interest")
def tool_interest(b: InterestIn) -> dict:
    if b.kind == "compose":
        return accounting.compound_interest(b.capital, b.annual_rate, b.years)
    return accounting.simple_interest(b.capital, b.annual_rate, b.days, b.day_basis)


class VatIn(BaseModel):
    ttc: float
    vat_rate: float = 0.21


@app.post("/api/tools/vat")
def tool_vat(b: VatIn) -> dict:
    return accounting.vat_from_ttc(b.ttc, b.vat_rate)


class CalcIn(BaseModel):
    expression: str


@app.post("/api/tools/calc")
def tool_calc(b: CalcIn) -> dict:
    try:
        return {"result": round(accounting.safe_eval(b.expression), 6)}
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        raise HTTPException(400, f"Calcul invalide : {e}") from e


# --- interface web -------------------------------------------------------------

@app.exception_handler(404)
async def not_found(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", "Introuvable")
        return JSONResponse({"detail": detail}, status_code=404)
    return _frontend("/404.html") or JSONResponse({"detail": "Introuvable"}, status_code=404)


def _frontend(path: str) -> FileResponse | None:
    root = config.FRONTEND_DIR.resolve()
    if not root.exists():
        return None
    rel = path.lstrip("/") or "index.html"
    for candidate in (rel, f"{rel}.html", f"{rel}/index.html"):
        p = (root / candidate).resolve()
        if p.is_file() and root in p.parents:
            return FileResponse(p)
    return None


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    resp = _frontend("/" + path)
    if resp:
        return resp
    if not config.FRONTEND_DIR.exists():
        return PlainTextResponse("Interface non construite : lance `npm run build` dans frontend/ (StudyAI.command le fait).", 503)
    return _frontend("/index.html")
