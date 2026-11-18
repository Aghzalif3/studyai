import json

import pytest
from fastapi.testclient import TestClient

from studyai import config, db
from studyai.analysis import llm, schemas
from studyai.main import app
from studyai.pipeline import media
from studyai.pipeline.runner import Runner


def fake_llm(calls):
    def call(system, content, schema, model, effort):
        calls.append({"schema": schema, "content": content, "model": model})
        doc = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        assert "DIAPO" in doc or schema is schemas.VISION or schema is schemas.GRADE
        if schema is schemas.COURSE:
            data = {"title": "Le bilan", "subject": "Comptabilité", "general_summary": "Résumé **général**.",
                    "chapters": [{"title": "Intro", "start": 0, "end": 75, "summary": "### Détail\n- point",
                                  "key_points": ["actif = passif"], "slides": [1, 2]}],
                    "uncertainties": [{"timestamp": 0, "excerpt": "Phrase à 0", "issue": "mot douteux"}]}
        elif schema is schemas.NOTIONS:
            data = {k: [] for k in schemas.NOTIONS["properties"]}
            data["definitions"] = [{"term": "Bilan", "definition": "Photo du patrimoine", "timestamp": 3, "source": "oral"}]
        elif schema is schemas.REVISION:
            data = {
                "sheets": [{"title": "Bilan", "content": "- Actif\n- Passif"}],
                "flashcards": [{"front": "Bilan ?", "back": "Photo du patrimoine", "notion": "Bilan"}],
                "mcq": [
                    {"question": "TVA normale ?", "choices": ["6 %", "21 %"], "correct_index": 1, "explanation": "cours",
                     "notion": "TVA", "timestamp": 10},
                    {"question": "cassé", "choices": ["a"], "correct_index": 3, "explanation": "", "notion": "", "timestamp": 0},
                ],
                "open_questions": [{"question": "Définir le bilan", "model_answer": "Photo", "notion": "Bilan", "points": 4}],
                "exercises": [{"title": "Facture", "statement": "...", "notion": "TVA", "from_course": True,
                               "steps": [{"explanation": "TVA", "expression": "1000*0.21", "result": 210, "unit": "€"},
                                         {"explanation": "Total", "expression": "1000+210", "result": 1200, "unit": "€"}],
                               "journal_entries": [{"label": "Vente", "lines": [
                                   {"account": "400", "account_name": "Clients", "debit": 1210, "credit": 0},
                                   {"account": "700", "account_name": "Ventes", "debit": 0, "credit": 1000},
                                   {"account": "451", "account_name": "TVA à payer", "debit": 0, "credit": 210}]}],
                               "final_answer": "1210 €"}],
            }
        elif schema is schemas.VISION:
            idx = [int(b["text"].split()[1]) for b in content if b.get("type") == "text" and b["text"].startswith("DIAPO")]
            data = {"slides": [{"index": i, "text": f"Titre {i}", "tables": "", "formulas": "", "figures": ""} for i in idx]}
        elif schema is schemas.GRADE:
            data = {"score": 3, "max_score": 4, "feedback": "Bien", "missing_points": ["patrimoine"]}
        else:
            raise AssertionError("schéma inattendu")
        return data, llm.Usage(input_tokens=1000, output_tokens=500)
    return call


@pytest.fixture
def client(monkeypatch):
    # Le traitement est lancé à la main (run_sync) pour des tests déterministes.
    from studyai import main
    monkeypatch.setattr(main.runner, "enqueue", lambda cid: None)
    monkeypatch.setattr(main.runner, "start", lambda: None)
    with TestClient(app) as c:
        yield c


def upload(client, path, options=None):
    with open(path, "rb") as f:
        r = client.post("/api/courses/upload", content=f.read(),
                        headers={"x-filename": "Cours%20compta.mp4", "x-options": json.dumps(options or {})})
    assert r.status_code == 200, r.text
    return r.json()


def test_full_pipeline_with_claude(client, video, fake_engine, monkeypatch):
    calls = []
    llm._call_override = fake_llm(calls)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    course = upload(client, video)
    assert course["title"] == "Cours compta" and course["status"] == "queued"
    Runner().run_sync(course["id"])

    c = client.get(f"/api/courses/{course['id']}").json()
    assert c["status"] == "done", c["error"]
    assert c["progress"] == 1.0
    assert c["language"] == "fr"
    assert c["counts"]["slides"] == 3
    assert c["counts"]["segments"] == 15
    assert c["steps"]["analysis"] == "done" and c["steps"]["vision"] == "done"
    assert c["cost_usd"] > 0

    tr = client.get(f"/api/courses/{course['id']}/transcript").json()
    assert tr[0]["start"] == 0 and tr[-1]["end"] == pytest.approx(75, abs=0.5)
    assert any(s["uncertain"] for s in tr)

    sl = client.get(f"/api/courses/{course['id']}/slides").json()
    assert [s["idx"] for s in sl] == [1, 2, 3]
    assert sl[0]["vision"]["text"] == "Titre 1"
    img = client.get(f"/api/courses/{course['id']}/slides/1/image")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"

    an = client.get(f"/api/courses/{course['id']}/analysis").json()
    assert an["course"]["title"] == "Le bilan"
    assert len(an["revision"]["mcq"]) == 1  # QCM mal formé écarté
    ex = an["revision"]["exercises"][0]
    assert ex["verification"]["status"] == "a_verifier"
    assert [s["check"] for s in ex["steps"]] == ["ok", "erreur"]
    assert ex["journal_entries"][0]["balanced"]

    # Le cours (transcription + diapos) est mis en cache pour les 3 appels d'analyse
    analysis_calls = [k for k in calls if k["schema"] is not schemas.VISION]
    assert len(analysis_calls) == 3
    assert all(k["content"][0]["cache_control"] == {"type": "ephemeral"} for k in analysis_calls)
    assert analysis_calls[0]["content"][0]["text"] == analysis_calls[1]["content"][0]["text"]

    # exports
    txt = client.get(f"/api/courses/{course['id']}/export/txt")
    assert txt.status_code == 200 and "[00:00:00] [?] Phrase" in txt.text
    srt = client.get(f"/api/courses/{course['id']}/export/srt").text
    assert srt.startswith("1\n00:00:00,000 --> 00:00:05,000\n")
    for fmt in ("pdf", "course.pdf"):
        r = client.get(f"/api/courses/{course['id']}/export/{fmt}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert "## Définitions" in client.get(f"/api/courses/{course['id']}/export/course.md").text

    # vidéo avec Range (lecteur intégré)
    r = client.get(f"/api/courses/{course['id']}/media", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100

    # révision
    cards = client.get("/api/flashcards", params={"course_id": course["id"], "due": True}).json()
    assert len(cards) == 1
    rev = client.post(f"/api/flashcards/{cards[0]['id']}/review", json={"grade": 2}).json()
    assert rev["interval_days"] == 1
    assert client.get("/api/flashcards", params={"course_id": course["id"], "due": True}).json() == []
    client.post("/api/attempts", json={"course_id": course["id"], "mode": "exam", "score": 0, "total": 1,
                                       "duration_seconds": 60,
                                       "details": [{"question_id": "q0", "notion": "TVA", "correct": False}]})
    st = client.get("/api/stats", params={"course_id": course["id"]}).json()
    assert st["attempts"][0]["mode"] == "exam"
    assert st["weak_notions"][0]["notion"] == "TVA"
    g = client.post("/api/grade", json={"course_id": course["id"], "question_id": "o0", "answer": "Une photo"}).json()
    assert g["score"] == 3

    # correction manuelle d'un passage douteux
    seg = next(s for s in tr if s["uncertain"])
    client.put(f"/api/courses/{course['id']}/transcript/{seg['id']}", json={"text": "Texte corrigé"})
    tr2 = client.get(f"/api/courses/{course['id']}/transcript").json()
    assert next(s for s in tr2 if s["id"] == seg["id"]) == {**seg, "text": "Texte corrigé", "uncertain": 0}


def test_without_api_key_stops_after_transcription(client, video, fake_engine):
    course = upload(client, video)
    Runner().run_sync(course["id"])
    c = client.get(f"/api/courses/{course['id']}").json()
    assert c["status"] == "done"
    assert c["steps"]["analysis"] == "no_key"
    assert c["counts"]["segments"] > 0 and c["counts"]["slides"] == 3
    assert client.get(f"/api/courses/{course['id']}/export/course.pdf").status_code == 400


def test_resume_after_interruption(client, tmp_path, fake_engine, monkeypatch):
    from conftest import make_video
    monkeypatch.setattr(media, "CHUNK_SECONDS", 30)
    v = make_video(tmp_path / "long.mp4", slides=("A", "B", "C", "D"), seconds=30)
    course = upload(client, v, {"analyze": False})
    original = fake_engine.transcribe
    state = {"n": 0}

    def crash_on_third(audio, language, prompt):
        state["n"] += 1
        if state["n"] == 3:
            raise RuntimeError("coupure de courant")
        return original(audio, language, prompt)

    monkeypatch.setattr(fake_engine, "transcribe", crash_on_third)
    with pytest.raises(RuntimeError):
        Runner().run_sync(course["id"])
    c = db.get_course(course["id"])
    assert c["status"] == "error" and "coupure" in c["error"]
    done = db.connect().execute("SELECT COUNT(*) FROM chunks WHERE course_id=? AND done=1", (course["id"],)).fetchone()[0]
    assert done == 2

    monkeypatch.setattr(fake_engine, "transcribe", original)
    fake_engine.calls = 0
    Runner().run_sync(course["id"])
    c = db.get_course(course["id"])
    assert c["status"] == "done"
    assert fake_engine.calls == 2  # seuls les 2 segments restants sont transcrits
    segs = db.connect().execute("SELECT start FROM segments WHERE course_id=? ORDER BY start", (course["id"],)).fetchall()
    starts = [r[0] for r in segs]
    assert starts == sorted(set(starts)) and starts[-1] >= 115


def test_cancel(client, video, fake_engine):
    course = upload(client, video, {"analyze": False})
    r = Runner()
    r.cancel_flags.add(course["id"])
    r.run_sync(course["id"])
    assert db.get_course(course["id"])["status"] == "cancelled"


def test_rejects_unknown_format(client):
    r = client.post("/api/courses/upload", content=b"x", headers={"x-filename": "notes.docx"})
    assert r.status_code == 400


def test_settings_and_key(client):
    st = client.get("/api/status").json()
    assert st["ffmpeg"] is True and st["api_key"] is False
    assert client.put("/api/settings/api-key", json={"key": "abc"}).status_code == 400
    assert client.put("/api/settings/api-key", json={"key": "sk-ant-api03-xyz1234"}).json() == {"api_key": True}
    st = client.get("/api/status").json()
    assert st["api_key_hint"] == "…1234"
    assert "sk-ant-api03-xyz1234" in config.ENV_FILE.read_text()
    r = client.put("/api/settings", json={"provider": "local", "local_model": "gemma3:12b"})
    assert r.json()["provider"] == "local"
    assert client.put("/api/settings", json={"claude_model": "gpt"}).status_code == 400


def test_tools(client):
    assert client.post("/api/tools/invoice", json={"gross": 1000, "discount_rate": 0.1}).json()["total"] == 1089.0
    assert client.post("/api/tools/calc", json={"expression": "1210 / 1,21"}).json()["result"] == 1000
    assert client.post("/api/tools/calc", json={"expression": "import os"}).status_code == 400
    dep = client.post("/api/tools/depreciation", json={"cost": 5000, "years": 5}).json()
    assert len(dep["rows"]) == 5
