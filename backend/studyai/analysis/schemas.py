"""Schémas JSON imposés aux réponses de Claude (sorties structurées)."""
from __future__ import annotations

S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}


def obj(**props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


TS = {"type": "number", "description": "Instant dans la vidéo, en secondes, où l'élément est abordé."}

COURSE = obj(
    title=S,
    subject=S,
    general_summary={"type": "string", "description": "Résumé général en Markdown."},
    chapters=arr(obj(
        title=S, start=TS, end=TS,
        summary={"type": "string", "description": "Résumé détaillé du chapitre en Markdown."},
        key_points=arr(S),
        slides=arr(I),
    )),
    uncertainties=arr(obj(
        timestamp=TS, excerpt=S,
        issue={"type": "string", "description": "Pourquoi ce passage est douteux (mot mal reconnu, phrase coupée...)."},
    )),
)

NOTIONS = obj(
    definitions=arr(obj(term=S, definition=S, timestamp=TS, source={"type": "string", "enum": ["oral", "diapo", "oral+diapo"]})),
    key_notions=arr(obj(notion=S, explanation=S, timestamp=TS)),
    formulas=arr(obj(name=S, formula=S, variables=S, explanation=S, timestamp=TS)),
    examples=arr(obj(title=S, description=S, timestamp=TS)),
    simplified=arr(obj(notion=S, explanation=S)),
    common_mistakes=arr(obj(mistake=S, correction=S)),
    exam_points=arr(obj(point=S, reason=S, timestamp=TS)),
    likely_questions=arr(obj(question=S, expected_answer=S, timestamp=TS)),
)

STEP = obj(
    explanation=S,
    expression={"type": "string", "description": "Calcul arithmétique pur (ex: 1000 * 0.21), ou chaîne vide."},
    result=N,
    unit=S,
)
JOURNAL_LINE = obj(account=S, account_name=S, debit=N, credit=N)
JOURNAL_ENTRY = obj(label=S, lines=arr(JOURNAL_LINE))

REVISION = obj(
    sheets=arr(obj(title=S, content={"type": "string", "description": "Fiche de révision en Markdown."})),
    flashcards=arr(obj(front=S, back=S, notion=S)),
    mcq=arr(obj(question=S, choices=arr(S), correct_index=I, explanation=S, notion=S, timestamp=TS)),
    open_questions=arr(obj(question=S, model_answer=S, notion=S, points=N)),
    exercises=arr(obj(
        title=S, statement=S, notion=S, from_course=B,
        steps=arr(STEP), journal_entries=arr(JOURNAL_ENTRY), final_answer=S,
    )),
)

VISION = obj(slides=arr(obj(
    index=I,
    text=S,
    tables={"type": "string", "description": "Tableaux recopiés en Markdown, ou chaîne vide."},
    formulas=S,
    figures={"type": "string", "description": "Description des graphiques/schémas, ou chaîne vide."},
)))

GRADE = obj(score=N, max_score=N, feedback=S, missing_points=arr(S))
