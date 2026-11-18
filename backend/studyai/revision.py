"""Répétition espacée (SM-2 simplifié) et statistiques de révision."""
from __future__ import annotations

import json
from collections import defaultdict

from . import db

DAY = 86400.0
# 0 = à revoir, 1 = difficile, 2 = bien, 3 = facile
GRADES = {0: "À revoir", 1: "Difficile", 2: "Bien", 3: "Facile"}


def schedule(card: dict, grade: int, now: float | None = None) -> dict:
    now = db.now() if now is None else now
    ease = float(card.get("ease") or 2.5)
    interval = float(card.get("interval_days") or 0)
    reps = int(card.get("reps") or 0)
    lapses = int(card.get("lapses") or 0)
    if grade == 0:
        reps, lapses, interval = 0, lapses + 1, 0
        ease = max(1.3, ease - 0.2)
        due = now + 10 * 60  # revoir dans 10 minutes
    else:
        if reps == 0:
            interval = 1 if grade < 3 else 3
        elif reps == 1:
            interval = 3 if grade == 1 else 6
        else:
            factor = {1: 1.2, 2: ease, 3: ease * 1.3}[grade]
            interval = max(interval * factor, interval + 1)
        ease = max(1.3, ease + {1: -0.15, 2: 0.0, 3: 0.15}[grade])
        reps += 1
        due = now + interval * DAY
    return {"ease": round(ease, 3), "interval_days": round(interval, 2), "reps": reps, "lapses": lapses, "due": due}


def review_card(card_id: str, grade: int) -> dict:
    conn = db.connect()
    card = db.row(conn.execute("SELECT * FROM flashcards WHERE id=?", (card_id,)).fetchone())
    if not card:
        raise KeyError(card_id)
    upd = schedule(card, grade)
    with db.tx() as c:
        c.execute("UPDATE flashcards SET ease=?, interval_days=?, reps=?, lapses=?, due=? WHERE id=?",
                  (upd["ease"], upd["interval_days"], upd["reps"], upd["lapses"], upd["due"], card_id))
        c.execute("INSERT INTO answers(attempt_id,course_id,question_id,notion,correct,created_at) VALUES(?,?,?,?,?,?)",
                  ("flashcard", card["course_id"], card_id, card.get("notion"), int(grade >= 2), db.now()))
    return {**card, **upd}


def record_attempt(course_id: str, mode: str, score: float, total: float, duration: float | None,
                   details: list[dict]) -> str:
    aid = db.new_id()
    t = db.now()
    with db.tx() as c:
        c.execute("INSERT INTO attempts(id,course_id,mode,score,total,duration_seconds,details,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (aid, course_id, mode, score, total, duration, json.dumps(details, ensure_ascii=False), t))
        for d in details:
            c.execute("INSERT INTO answers(attempt_id,course_id,question_id,notion,correct,created_at) VALUES(?,?,?,?,?,?)",
                      (aid, course_id, str(d.get("question_id")), d.get("notion"), int(bool(d.get("correct"))), t))
    return aid


def stats(course_id: str | None = None) -> dict:
    conn = db.connect()
    where, args = ("WHERE course_id=?", (course_id,)) if course_id else ("", ())
    attempts = db.rows(conn.execute(f"SELECT id,course_id,mode,score,total,duration_seconds,created_at FROM attempts {where} ORDER BY created_at", args).fetchall())
    answers = conn.execute(f"SELECT course_id, notion, correct FROM answers {where}", args).fetchall()
    per_notion: dict[tuple[str, str], list[int]] = defaultdict(list)
    for a in answers:
        if a["notion"]:
            per_notion[(a["course_id"], a["notion"])].append(a["correct"])
    weak = []
    for (cid, notion), res in per_notion.items():
        if len(res) >= 2 or (res and res[-1] == 0):
            rate = sum(res) / len(res)
            if rate < 0.7:
                weak.append({"course_id": cid, "notion": notion, "success_rate": round(rate, 2), "answers": len(res)})
    weak.sort(key=lambda w: (w["success_rate"], -w["answers"]))
    now = db.now()
    due = conn.execute(f"SELECT COUNT(*) FROM flashcards {where + (' AND' if where else 'WHERE')} due<=?", (*args, now)).fetchone()[0]
    cards = conn.execute(f"SELECT COUNT(*) FROM flashcards {where}", args).fetchone()[0]
    total_answers = len(answers)
    correct = sum(a["correct"] for a in answers)
    return {
        "attempts": attempts,
        "weak_notions": weak[:15],
        "flashcards_due": due,
        "flashcards_total": cards,
        "answers": total_answers,
        "success_rate": round(correct / total_answers, 3) if total_answers else None,
    }
