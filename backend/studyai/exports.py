"""Exports : transcription en TXT / SRT / PDF, cours complet en PDF et Markdown."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fpdf import FPDF

FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

_LATIN1_MAP = {"œ": "oe", "Œ": "OE", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
               "€": "EUR", "≠": "!=", "≤": "<=", "≥": ">=", "→": "->", "×": "x", "−": "-", "•": "-", " ": " "}


def ts_srt(t: float) -> str:
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def ts_hms(t: float) -> str:
    s = int(max(t, 0))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def to_txt(segments: list[dict], with_timestamps: bool = True) -> str:
    lines = []
    for s in segments:
        mark = " [?]" if s.get("uncertain") else ""
        lines.append(f"[{ts_hms(s['start'])}]{mark} {s['text']}" if with_timestamps else s["text"])
    return "\n".join(lines) + "\n"


def to_srt(segments: list[dict]) -> str:
    out = []
    for i, s in enumerate(segments, start=1):
        out.append(f"{i}\n{ts_srt(s['start'])} --> {ts_srt(max(s['end'], s['start'] + 0.3))}\n{s['text'].strip()}\n")
    return "\n".join(out)


class _PDF(FPDF):
    def __init__(self, title: str):
        super().__init__(format="A4")
        self.doc_title = title
        self.set_auto_page_break(True, margin=18)
        self.set_margins(18, 18, 18)
        self.unicode = False
        for regular, bold in FONT_CANDIDATES:
            if Path(regular).exists() and Path(bold).exists():
                self.add_font("Body", "", regular)
                self.add_font("Body", "B", bold)
                self.unicode = True
                break
        self.family_name = "Body" if self.unicode else "Helvetica"

    def clean(self, text: str) -> str:
        if self.unicode:
            return text
        for k, v in _LATIN1_MAP.items():
            text = text.replace(k, v)
        return text.encode("latin-1", "replace").decode("latin-1")

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self.family_name, "", 8)
        self.set_text_color(140)
        self.cell(0, 6, self.clean(f"StudyAI · {self.doc_title} · page {self.page_no()}"), align="C")
        self.set_text_color(0)

    def heading(self, text: str, size: float = 15) -> None:
        self.ln(2)
        self.set_font(self.family_name, "B", size)
        self.multi_cell(0, size * 0.5, self.clean(text))
        self.ln(1)

    def para(self, text: str, size: float = 10.5) -> None:
        self.set_font(self.family_name, "", size)
        self.multi_cell(0, size * 0.52, self.clean(text), markdown=True)
        self.ln(1)

    def markdown(self, md: str) -> None:
        for raw in (md or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                self.ln(2)
                continue
            m = re.match(r"^(#{1,6})\s+(.*)", line)
            if m:
                self.heading(m.group(2).replace("**", ""), size=max(11.5, 15 - len(m.group(1))))
                continue
            m = re.match(r"^(\s*)[-*+]\s+(.*)", line)
            if m:
                indent = 4 + len(m.group(1)) * 2
                self.set_x(self.l_margin + indent)
                self.set_font(self.family_name, "", 10.5)
                self.multi_cell(0, 5.4, self.clean("• " if self.unicode else "- ") + self.clean(m.group(2)), markdown=True)
                continue
            self.para(line)


def transcript_pdf(title: str, segments: list[dict]) -> bytes:
    pdf = _PDF(title)
    pdf.add_page()
    pdf.heading(title, 18)
    pdf.para("Transcription automatique (Whisper). Les passages marqués [?] sont peu fiables.", 9)
    for s in segments:
        mark = " [?]" if s.get("uncertain") else ""
        pdf.para(f"**{ts_hms(s['start'])}**{mark}  {s['text']}")
    return bytes(pdf.output())


def course_markdown(course: dict, analysis: dict[str, Any]) -> str:
    c = analysis.get("course", {})
    n = analysis.get("notions", {})
    r = analysis.get("revision", {})
    md = [f"# {c.get('title') or course['title']}", ""]
    if c.get("general_summary"):
        md += ["## Résumé général", c["general_summary"], ""]
    for ch in c.get("chapters", []):
        md += [f"## {ch['title']} ({ts_hms(ch['start'])} – {ts_hms(ch['end'])})", ch["summary"], ""]
        md += [f"- {p}" for p in ch.get("key_points", [])] + [""]
    sections = [
        ("Définitions", n.get("definitions", []), lambda d: f"- **{d['term']}** : {d['definition']}"),
        ("Notions à mémoriser", n.get("key_notions", []), lambda d: f"- **{d['notion']}** : {d['explanation']}"),
        ("Formules", n.get("formulas", []), lambda d: f"- **{d['name']}** : {d['formula']} ({d['variables']})"),
        ("Exemples du professeur", n.get("examples", []), lambda d: f"- **{d['title']}** : {d['description']}"),
        ("Explications simplifiées", n.get("simplified", []), lambda d: f"- **{d['notion']}** : {d['explanation']}"),
        ("Erreurs fréquentes", n.get("common_mistakes", []), lambda d: f"- {d['mistake']} → {d['correction']}"),
        ("Important pour l'examen", n.get("exam_points", []), lambda d: f"- **{d['point']}** ({d['reason']})"),
        ("Questions possibles", n.get("likely_questions", []), lambda d: f"- **{d['question']}**\n  {d['expected_answer']}"),
    ]
    for title, items, fmt in sections:
        if items:
            md += [f"## {title}"] + [fmt(i) for i in items] + [""]
    for sheet in r.get("sheets", []):
        md += [f"## Fiche : {sheet['title']}", sheet["content"], ""]
    if c.get("uncertainties"):
        md += ["## Incertitudes de transcription"]
        md += [f"- {ts_hms(u['timestamp'])} « {u['excerpt']} » : {u['issue']}" for u in c["uncertainties"]] + [""]
    return "\n".join(md)


def course_pdf(course: dict, analysis: dict[str, Any]) -> bytes:
    title = analysis.get("course", {}).get("title") or course["title"]
    pdf = _PDF(title)
    pdf.add_page()
    pdf.markdown(course_markdown(course, analysis))
    return bytes(pdf.output())
