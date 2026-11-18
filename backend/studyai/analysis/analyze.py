"""Analyse du cours avec Claude : structure, notions, matériel de révision, diapositives (vision)."""
from __future__ import annotations

import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from .. import db
from . import accounting, llm, prompts, schemas

MAX_COURSE_CHARS = 2_400_000  # ≈ 600k tokens : bien au-delà de 10 h de cours


def hms(seconds: float) -> str:
    s = int(max(seconds, 0))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def build_course_document(segments: list[dict], slides: list[dict]) -> str:
    """Transcription + diapositives intercalées dans l'ordre chronologique."""
    events: list[tuple[float, int, str]] = []
    for s in segments:
        mark = " (?)" if s.get("uncertain") else ""
        events.append((s["start"], 1, f"[{hms(s['start'])}]{mark} {s['text'].strip()}"))
    for sl in slides:
        parts = [f"[{hms(sl['ts'])}] ===== DIAPO {sl['idx']} ====="]
        if sl.get("vision"):
            try:
                v = json.loads(sl["vision"]) if isinstance(sl["vision"], str) else sl["vision"]
            except ValueError:
                v = {}
            for label, key in (("Texte", "text"), ("Tableaux", "tables"), ("Formules", "formulas"), ("Figures", "figures")):
                if v.get(key):
                    parts.append(f"{label} : {v[key]}")
        elif sl.get("ocr_text"):
            parts.append(f"Texte (OCR) : {sl['ocr_text']}")
        else:
            parts.append("(aucun texte lisible)")
        parts.append("===== fin diapo =====")
        events.append((sl["ts"], 0, "\n".join(parts)))
    events.sort(key=lambda e: (e[0], e[1]))
    return "\n".join(e[2] for e in events)


def _system(accounting_mode: bool) -> str:
    return prompts.SYSTEM + (prompts.ACCOUNTING if accounting_mode else "")


def _course_blocks(document: str, task: str) -> list[dict]:
    # Le cours est identique pour les 3 appels : il est mis en cache (≈ 90 % moins cher à la relecture).
    return [
        {"type": "text", "text": f"<cours>\n{document}\n</cours>", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": task},
    ]


def _image_block(path: str, max_side: int = 1280) -> dict:
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()}}


def estimate(document_chars: int, n_slides: int, model: str, vision: bool) -> dict:
    """Estimation du coût avant l'analyse (≈ 3,5 caractères par token en français)."""
    doc_tokens = int(document_chars / 3.5)
    inp = doc_tokens * 1.25 + doc_tokens * 0.1 * 2 + 3 * 1500  # écriture cache + 2 relectures + consignes
    out = 45_000  # 3 réponses détaillées (réflexion comprise)
    if vision and n_slides:
        inp += n_slides * 1700
        out += n_slides * 400
    usd = llm.estimate_cost(model, int(inp), int(out))
    return {"input_tokens": int(inp), "output_tokens": out, "usd": round(usd, 2)}


def analyze_slides_with_vision(course_id: str, slides: list[dict], model: str, effort: str,
                               on_progress: Callable[[float], None] | None = None, batch: int = 8) -> llm.Usage:
    total = llm.Usage()
    todo = [s for s in slides if not s.get("vision")]
    for i in range(0, len(todo), batch):
        group = todo[i:i + batch]
        content: list[dict] = []
        for s in group:
            content.append({"type": "text", "text": f"DIAPO {s['idx']} :"})
            content.append(_image_block(s["image_path"]))
        content.append({"type": "text", "text": prompts.VISION_TASK})
        data, usage = llm.structured_call(prompts.SYSTEM, content, schemas.VISION, model=model, effort="low")
        total.add(usage)
        by_idx = {d["index"]: d for d in data.get("slides", [])}
        with db.tx() as c:
            for s in group:
                d = by_idx.get(s["idx"])
                if d:
                    s["vision"] = json.dumps(d, ensure_ascii=False)
                    c.execute("UPDATE slides SET vision=? WHERE course_id=? AND idx=?", (s["vision"], course_id, s["idx"]))
        db.add_cost(course_id, usage.cost(model))
        if on_progress:
            on_progress(min(1.0, (i + len(group)) / max(len(todo), 1)))
    return total


def postprocess_revision(data: dict) -> dict:
    data = dict(data)
    data["exercises"] = [accounting.verify_exercise(e) for e in data.get("exercises", [])]
    mcq = []
    for i, q in enumerate(data.get("mcq", [])):
        choices = q.get("choices") or []
        if len(choices) < 2 or not 0 <= int(q.get("correct_index", -1)) < len(choices):
            continue  # QCM mal formé : on l'écarte plutôt que d'afficher une mauvaise correction
        mcq.append({**q, "id": f"q{i}"})
    data["mcq"] = mcq
    data["open_questions"] = [{**q, "id": f"o{i}"} for i, q in enumerate(data.get("open_questions", []))]
    return data


def run_analysis(course_id: str, document: str, *, model: str, effort: str, accounting_mode: bool,
                 on_progress: Callable[[float, str], None] | None = None,
                 only: list[str] | None = None) -> llm.Usage:
    if len(document) > MAX_COURSE_CHARS:
        raise llm.ClaudeError("Ce cours est trop long pour une seule analyse (plus de ~10 h). Découpe la vidéo en deux.")
    system = _system(accounting_mode)
    total = llm.Usage()
    tasks: dict[str, tuple[str, dict]] = {
        "course": (prompts.COURSE_TASK, schemas.COURSE),
        "notions": (prompts.NOTIONS_TASK, schemas.NOTIONS),
        "revision": (prompts.REVISION_TASK, schemas.REVISION),
    }
    existing = db.get_analysis(course_id)
    wanted = [k for k in tasks if (only is None or k in only) and (only is not None or k not in existing)]
    done_count = 0

    def run(kind: str) -> tuple[str, dict, llm.Usage]:
        task, schema = tasks[kind]
        data, usage = llm.structured_call(system, _course_blocks(document, task), schema, model=model, effort=effort)
        return kind, data, usage

    def store(kind: str, data: dict, usage: llm.Usage) -> None:
        nonlocal done_count
        if kind == "revision":
            data = postprocess_revision(data)
            replace_flashcards(course_id, data.get("flashcards", []))
        cost = usage.cost(model)
        db.save_analysis(course_id, kind, data, model, usage.input_tokens + usage.cache_read + usage.cache_write,
                         usage.output_tokens, cost)
        db.add_cost(course_id, cost)
        total.add(usage)
        done_count += 1
        if on_progress:
            on_progress(done_count / max(len(wanted), 1), kind)

    if not wanted:
        return total
    if llm.is_local(model):
        return _run_local(course_id, document, system, model, wanted, store, total)
    # Le premier appel écrit le cours dans le cache ; les suivants le relisent en parallèle.
    first, rest = wanted[0], wanted[1:]
    store(*run(first))
    if rest:
        with ThreadPoolExecutor(max_workers=len(rest)) as pool:
            for kind, data, usage in pool.map(run, rest):
                store(kind, data, usage)
    return total


LOCAL_PIECE_CHARS = 24_000  # ≈ 7 000 tokens : tient dans le contexte d'un petit modèle local


def split_document(document: str, max_chars: int = LOCAL_PIECE_CHARS) -> list[str]:
    pieces, buf, size = [], [], 0
    for line in document.splitlines():
        if size + len(line) > max_chars and buf:
            pieces.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        pieces.append("\n".join(buf))
    return pieces


def merge_results(kind: str, parts: list[dict]) -> dict:
    """Fusionne les résultats partie par partie (les listes sont mises bout à bout)."""
    merged: dict[str, Any] = {}
    for p in parts:
        for k, v in p.items():
            if isinstance(v, list):
                merged.setdefault(k, []).extend(v)
            elif k not in merged or not merged[k]:
                merged[k] = v
    return merged


SUMMARY_SCHEMA = schemas.obj(title=schemas.S, subject=schemas.S, general_summary=schemas.S)


def _run_local(course_id, document, system, model, wanted, store, total):
    """Modèle local : le cours est traité par morceaux, puis les résultats sont fusionnés."""
    pieces = split_document(document)
    tasks = {"course": (prompts.COURSE_TASK, schemas.COURSE), "notions": (prompts.NOTIONS_TASK, schemas.NOTIONS),
             "revision": (prompts.REVISION_TASK, schemas.REVISION)}
    for kind in wanted:
        task, schema = tasks[kind]
        parts, usage = [], llm.Usage()
        for i, piece in enumerate(pieces, start=1):
            note = f"(Partie {i}/{len(pieces)} du cours. Ne traite que cette partie.)\n" if len(pieces) > 1 else ""
            data, u = llm.structured_call(system, [{"type": "text", "text": f"<cours>\n{piece}\n</cours>"},
                                                   {"type": "text", "text": note + task}], schema, model=model)
            parts.append(data)
            usage.add(u)
        merged = merge_results(kind, parts)
        if kind == "course" and len(pieces) > 1:
            outline = "\n\n".join(f"### {c['title']}\n{c['summary']}" for c in merged.get("chapters", []))
            data, u = llm.structured_call(system, [{"type": "text", "text": outline}, {"type": "text", "text":
                "Voici les résumés des chapitres d'un cours. Donne le titre du cours, la matière et un résumé général "
                "(10 à 20 lignes) fidèle à ces résumés."}], SUMMARY_SCHEMA, model=model)
            merged.update(data)
            usage.add(u)
        store(kind, merged, usage)
    return total


def replace_flashcards(course_id: str, cards: list[dict]) -> None:
    t = db.now()
    with db.tx() as c:
        c.execute("DELETE FROM flashcards WHERE course_id=?", (course_id,))
        for card in cards:
            c.execute(
                "INSERT INTO flashcards(id,course_id,front,back,notion,due) VALUES(?,?,?,?,?,?)",
                (db.new_id(), course_id, card["front"], card["back"], card.get("notion"), t),
            )


def grade_open_answer(question: dict, answer: str, *, model: str) -> tuple[dict, llm.Usage]:
    text = prompts.GRADE_TASK.format(
        question=question.get("question", ""), model_answer=question.get("model_answer", ""),
        points=question.get("points", 5), answer=answer or "(pas de réponse)",
    )
    return llm.structured_call(prompts.SYSTEM, [{"type": "text", "text": text}], schemas.GRADE, model=model, effort="medium",
                               max_tokens=16000)
