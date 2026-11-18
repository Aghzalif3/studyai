import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from studyai import db
from studyai.analysis import analyze, llm, schemas
from studyai.pipeline import media, slides


@pytest.mark.skipif(slides.ocr_backend() is None, reason="aucun OCR installé")
def test_ocr_reads_slide_text(video, tmp_path):
    img = tmp_path / "s.jpg"
    media.extract_frame(video, 30, img)
    text = slides.ocr_image(img)
    assert "TVA" in text and "Diapo 2" in text


@pytest.fixture
def ollama(monkeypatch):
    received = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"models": [{"name": "qwen3:8b"}]}).encode())

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            props = body["format"]["properties"]
            if "chapters" in props:
                out = {"title": "t", "subject": "s", "general_summary": "", "uncertainties": [],
                       "chapters": [{"title": f"Ch{len(received)}", "start": 0, "end": 1, "summary": "r",
                                     "key_points": [], "slides": []}]}
            elif "general_summary" in props:
                out = {"title": "Cours fusionné", "subject": "Compta", "general_summary": "Résumé global"}
            else:
                out = {k: [] for k in props}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"message": {"content": json.dumps(out)},
                                         "prompt_eval_count": 10, "eval_count": 5}).encode())

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{srv.server_port}")
    yield received
    srv.shutdown()


def test_ollama_local_analysis_in_pieces(ollama):
    assert llm.ollama_models() == ["qwen3:8b"]
    cid = db.create_course("c", "c.mp4", "/x", {})
    document = "\n".join(f"[00:00:{i % 60:02d}] phrase numéro {i} " + "x" * 200 for i in range(300))
    assert len(analyze.split_document(document)) == 3
    usage = analyze.run_analysis(cid, document, model="ollama:qwen3:8b", effort="high", accounting_mode=True)
    an = db.get_analysis(cid)
    assert [c["title"] for c in an["course"]["chapters"]] == ["Ch1", "Ch2", "Ch3"]
    assert an["course"]["title"] == "Cours fusionné"
    assert usage.cost("ollama:qwen3:8b") == 0
    assert db.get_course(cid)["cost_usd"] == 0
    assert all(r["model"] == "qwen3:8b" and r["format"]["type"] == "object" for r in ollama)
    assert len(ollama) == 3 * 3 + 1


def test_ollama_not_running(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    assert llm.ollama_models() is None
    with pytest.raises(llm.ClaudeError, match="Ollama ne répond pas"):
        llm.ollama_call("s", [{"type": "text", "text": "x"}], schemas.GRADE, model="qwen3:8b")


def test_no_api_key_message():
    with pytest.raises(llm.NoApiKey, match="Claude Pro"):
        llm.structured_call("s", [{"type": "text", "text": "x"}], schemas.GRADE, model="claude-opus-5-5")


def test_cost_estimate_reasonable():
    est = analyze.estimate(len("x") * 117_000, 60, "claude-opus-5-5", True)  # ≈ 2 h de cours
    assert 0.3 < est["usd"] < 3
    assert analyze.estimate(117_000, 60, "claude-haiku-5-5", True)["usd"] < 0.1


def test_course_document_interleaves_slides():
    doc = analyze.build_course_document(
        [{"start": 5, "text": "Bonjour", "uncertain": 0}, {"start": 65, "text": "mot douteux", "uncertain": 1}],
        [{"idx": 1, "ts": 60, "ocr_text": "Le bilan", "vision": None}],
    )
    lines = doc.splitlines()
    assert lines[0] == "[00:00:05] Bonjour"
    assert lines[1] == "[00:01:00] ===== DIAPO 1 ====="
    assert lines[-1] == "[00:01:05] (?) mot douteux"
