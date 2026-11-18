"""Stockage local SQLite (une base par installation, dans data/studyai.db)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  media_path TEXT NOT NULL,
  has_video INTEGER NOT NULL DEFAULT 0,
  duration REAL,
  language TEXT,
  status TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | error | cancelled
  stage TEXT,                               -- étape en cours
  progress REAL NOT NULL DEFAULT 0,         -- 0..1 sur l'ensemble du traitement
  eta_seconds REAL,
  steps TEXT NOT NULL DEFAULT '{}',         -- état de chaque étape (reprise après interruption)
  options TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  cost_usd REAL NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  course_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  start REAL NOT NULL,
  end REAL NOT NULL,
  path TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0,
  seconds_taken REAL,
  PRIMARY KEY (course_id, idx)
);
CREATE TABLE IF NOT EXISTS segments (
  course_id TEXT NOT NULL,
  chunk_idx INTEGER NOT NULL,
  start REAL NOT NULL,
  end REAL NOT NULL,
  text TEXT NOT NULL,
  avg_logprob REAL,
  no_speech_prob REAL,
  uncertain INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS segments_course ON segments(course_id, start);
CREATE TABLE IF NOT EXISTS slides (
  course_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  ts REAL NOT NULL,
  end_ts REAL,
  image_path TEXT NOT NULL,
  ocr_text TEXT,
  vision TEXT,
  PRIMARY KEY (course_id, idx)
);
CREATE TABLE IF NOT EXISTS analysis (
  course_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  data TEXT NOT NULL,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd REAL,
  created_at REAL NOT NULL,
  PRIMARY KEY (course_id, kind)
);
CREATE TABLE IF NOT EXISTS flashcards (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  front TEXT NOT NULL,
  back TEXT NOT NULL,
  notion TEXT,
  ease REAL NOT NULL DEFAULT 2.5,
  interval_days REAL NOT NULL DEFAULT 0,
  reps INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0,
  due REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  mode TEXT NOT NULL,                  -- qcm | exam
  score REAL NOT NULL,
  total REAL NOT NULL,
  duration_seconds REAL,
  details TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
  attempt_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  notion TEXT,
  correct INTEGER NOT NULL,
  created_at REAL NOT NULL
);
"""

_local = threading.local()
_init_lock = threading.Lock()
_initialized: set[str] = set()


def db_path() -> Path:
    return config.DATA_DIR / "studyai.db"


def connect() -> sqlite3.Connection:
    path = str(db_path())
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "path", None) == path:
        return conn
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    with _init_lock:
        if path not in _initialized:
            conn.executescript(SCHEMA)
            _initialized.add(path)
    _local.conn = conn
    _local.path = path
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> float:
    return time.time()


def row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    for k in ("steps", "options", "data", "details"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def rows(rs: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row(r) for r in rs]  # type: ignore[misc]


# --- cours -----------------------------------------------------------------

def create_course(title: str, filename: str, media_path: str, options: dict) -> str:
    cid = new_id()
    t = now()
    with tx() as c:
        c.execute(
            "INSERT INTO courses(id,title,filename,media_path,options,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (cid, title, filename, media_path, json.dumps(options), t, t),
        )
    return cid


def get_course(cid: str) -> dict | None:
    return row(connect().execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone())


def list_courses() -> list[dict]:
    return rows(connect().execute("SELECT * FROM courses ORDER BY created_at DESC").fetchall())


def update_course(cid: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now()
    for k in ("steps", "options"):
        if k in fields and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k])
    cols = ",".join(f"{k}=?" for k in fields)
    with tx() as c:
        c.execute(f"UPDATE courses SET {cols} WHERE id=?", (*fields.values(), cid))


def set_step(cid: str, step: str, state: str) -> None:
    course = get_course(cid)
    if not course:
        return
    steps = course["steps"] or {}
    steps[step] = state
    update_course(cid, steps=steps)


def delete_course(cid: str) -> None:
    with tx() as c:
        for t in ("chunks", "segments", "slides", "analysis", "flashcards", "attempts", "answers"):
            c.execute(f"DELETE FROM {t} WHERE course_id=?", (cid,))
        c.execute("DELETE FROM courses WHERE id=?", (cid,))


def add_cost(cid: str, usd: float) -> None:
    with tx() as c:
        c.execute("UPDATE courses SET cost_usd = cost_usd + ? WHERE id=?", (usd, cid))


# --- analyse -----------------------------------------------------------------

def save_analysis(cid: str, kind: str, data: Any, model: str | None = None,
                  input_tokens: int = 0, output_tokens: int = 0, cost: float = 0.0) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR REPLACE INTO analysis(course_id,kind,data,model,input_tokens,output_tokens,cost_usd,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (cid, kind, json.dumps(data, ensure_ascii=False), model, input_tokens, output_tokens, cost, now()),
        )


def get_analysis(cid: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in connect().execute("SELECT kind, data FROM analysis WHERE course_id=?", (cid,)).fetchall():
        out[r["kind"]] = json.loads(r["data"])
    return out
