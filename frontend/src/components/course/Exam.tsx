"use client";

import { Clock, Sparkles, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type Revision } from "@/lib/api";
import { pct, shuffle } from "@/lib/format";
import { cn, Notice, Spinner } from "../ui";

type Phase = "setup" | "running" | "review";
interface Grade { score: number; feedback?: string; missing?: string[] }

/** Examen blanc chronométré : QCM + questions ouvertes, correction automatique ou par Claude. */
export function Exam({ courseId, rev }: { courseId: string; rev: Revision }) {
  const [phase, setPhase] = useState<Phase>("setup");
  const [nMcq, setNMcq] = useState(Math.min(10, rev.mcq.length));
  const [nOpen, setNOpen] = useState(Math.min(3, rev.open_questions.length));
  const [minutes, setMinutes] = useState(30);
  const [seed, setSeed] = useState(0);
  const mcq = useMemo(() => shuffle(rev.mcq, seed).slice(0, nMcq), [rev.mcq, seed, nMcq]);
  const open = useMemo(() => shuffle(rev.open_questions, seed + 0.5).slice(0, nOpen), [rev.open_questions, seed, nOpen]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [grades, setGrades] = useState<Record<string, Grade>>({});
  const [left, setLeft] = useState(0);
  const [startedAt, setStartedAt] = useState(0);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (phase !== "running") return;
    const t = setInterval(() => {
      const remaining = minutes * 60 - (Date.now() - startedAt) / 1000;
      setLeft(Math.max(0, remaining));
      if (remaining <= 0) setPhase("review");
    }, 500);
    return () => clearInterval(t);
  }, [phase, minutes, startedAt]);

  const begin = () => {
    setSeed(Math.random()); setAnswers({}); setTexts({}); setGrades({}); setSaved(false);
    setStartedAt(Date.now()); setLeft(minutes * 60); setPhase("running");
  };

  const mcqScore = mcq.filter((q) => answers[q.id] === q.correct_index).length;
  const openMax = open.reduce((a, q) => a + (q.points || 5), 0);
  const openScore = open.reduce((a, q) => a + (grades[q.id]?.score || 0), 0);
  const allGraded = open.every((q) => grades[q.id] !== undefined);
  const total = mcq.length + openMax;
  const score = mcqScore + openScore;

  const gradeWithAI = async () => {
    setGrading(true);
    setError(undefined);
    try {
      const out: Record<string, Grade> = { ...grades };
      for (const q of open) {
        const g = await api.grade(courseId, q.id, texts[q.id] || "");
        out[q.id] = { score: Math.min(g.score * ((q.points || 5) / (g.max_score || q.points || 5)), q.points || 5), feedback: g.feedback, missing: g.missing_points };
        setGrades({ ...out });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGrading(false);
    }
  };

  const save = async () => {
    await api.attempt({
      course_id: courseId, mode: "exam", score, total, duration_seconds: (Date.now() - startedAt) / 1000,
      details: [
        ...mcq.map((q) => ({ question_id: q.id, notion: q.notion, correct: answers[q.id] === q.correct_index })),
        ...open.map((q) => ({ question_id: q.id, notion: q.notion, correct: (grades[q.id]?.score || 0) >= (q.points || 5) / 2 })),
      ],
    });
    setSaved(true);
  };

  if (phase === "setup") {
    return (
      <div className="card mx-auto max-w-lg p-6 animate-in">
        <h3 className="mb-1 flex items-center gap-2 text-lg font-semibold"><Timer size={18} className="text-accent" />Examen blanc</h3>
        <p className="mb-5 text-sm text-muted">Conditions d'examen : pas de correction avant la fin, chronomètre visible.</p>
        <div className="grid grid-cols-3 gap-3">
          <label><span className="label">QCM</span>
            <input type="number" className="input" min={0} max={rev.mcq.length} value={nMcq} onChange={(e) => setNMcq(+e.target.value)} /></label>
          <label><span className="label">Questions ouvertes</span>
            <input type="number" className="input" min={0} max={rev.open_questions.length} value={nOpen} onChange={(e) => setNOpen(+e.target.value)} /></label>
          <label><span className="label">Durée (min)</span>
            <input type="number" className="input" min={1} value={minutes} onChange={(e) => setMinutes(+e.target.value)} /></label>
        </div>
        <button className="btn-primary mt-6 w-full" disabled={!nMcq && !nOpen} onClick={begin}>Commencer l'examen</button>
      </div>
    );
  }

  const review = phase === "review";
  const mm = Math.floor(left / 60), ss = Math.floor(left % 60);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="sticky top-2 z-10 flex items-center justify-between rounded-xl border border-line bg-panel/90 px-4 py-3 shadow-card backdrop-blur">
        {review ? (
          <div className="text-sm"><b>Résultat : </b>{allGraded ? `${score.toFixed(1)} / ${total} (${pct(score / Math.max(total, 1))})` : `QCM ${mcqScore}/${mcq.length}, questions ouvertes à corriger`}</div>
        ) : (
          <div className={cn("flex items-center gap-2 font-mono text-lg", left < 60 && "text-bad")}><Clock size={17} />{mm}:{String(ss).padStart(2, "0")}</div>
        )}
        {!review && <button className="btn-primary" onClick={() => setPhase("review")}>Rendre ma copie</button>}
        {review && <button className="btn-outline" onClick={() => setPhase("setup")}>Nouvel examen</button>}
      </div>

      {mcq.map((q, i) => (
        <div key={q.id} className="card p-5">
          <p className="mb-3 font-medium"><span className="text-muted">{i + 1}. </span>{q.question}</p>
          <div className="grid gap-2">
            {q.choices.map((c, k) => {
              const chosen = answers[q.id] === k;
              const cls = review ? (k === q.correct_index ? "border-ok bg-ok/10" : chosen ? "border-bad bg-bad/10" : "opacity-60") : chosen ? "border-accent bg-accent/5" : "";
              return (
                <button key={k} disabled={review} onClick={() => setAnswers({ ...answers, [q.id]: k })}
                  className={cn("rounded-lg border border-line px-3 py-2 text-left text-sm transition hover:bg-subtle/60", cls)}>
                  {String.fromCharCode(65 + k)}. {c}
                </button>
              );
            })}
          </div>
          {review && <p className="mt-3 text-sm text-muted">{q.explanation}</p>}
        </div>
      ))}

      {open.map((q, i) => (
        <div key={q.id} className="card p-5">
          <p className="mb-3 font-medium"><span className="text-muted">{mcq.length + i + 1}. </span>{q.question} <span className="chip">{q.points} pts</span></p>
          <textarea className="input min-h-28" disabled={review} value={texts[q.id] || ""} placeholder="Ta réponse…"
            onChange={(e) => setTexts({ ...texts, [q.id]: e.target.value })} />
          {review && (
            <div className="mt-3 space-y-2 text-sm">
              <div className="rounded-lg bg-subtle p-3"><b>Réponse modèle : </b>{q.model_answer}</div>
              {grades[q.id]?.feedback && (
                <div className="rounded-lg border border-accent/30 p-3"><b>Correction : </b>{grades[q.id].feedback}
                  {!!grades[q.id].missing?.length && <ul className="mt-1 list-disc pl-5 text-muted">{grades[q.id].missing!.map((m) => <li key={m}>{m}</li>)}</ul>}
                </div>
              )}
              <label className="flex items-center gap-2">Note :
                <input type="number" step={0.5} min={0} max={q.points} className="input w-20 py-1" value={grades[q.id]?.score ?? ""}
                  onChange={(e) => setGrades({ ...grades, [q.id]: { ...grades[q.id], score: Math.min(+e.target.value, q.points) } })} />
                / {q.points}
              </label>
            </div>
          )}
        </div>
      ))}

      {review && (
        <div className="card space-y-3 p-5">
          {open.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn-outline" disabled={grading} onClick={gradeWithAI}>
                {grading ? <Spinner /> : <Sparkles size={15} />}Corriger les questions ouvertes avec l'IA
              </button>
              <span className="text-xs text-muted">ou note-toi toi-même en comparant avec la réponse modèle.</span>
            </div>
          )}
          {error && <Notice tone="bad">{error}</Notice>}
          <button className="btn-primary" disabled={!allGraded || saved} onClick={save}>{saved ? "Résultat enregistré ✓" : "Enregistrer mon résultat"}</button>
        </div>
      )}
    </div>
  );
}
