"use client";

import { Check, RotateCcw, X } from "lucide-react";
import { useMemo, useState } from "react";
import { api, type MCQ } from "@/lib/api";
import { pct, shuffle } from "@/lib/format";
import { cn } from "../ui";
import { TimeLink } from "./Summary";

export function Quiz({ courseId, questions, onSeek }: { courseId: string; questions: MCQ[]; onSeek: (t: number) => void }) {
  const [seed, setSeed] = useState(Math.random());
  const order = useMemo(() => shuffle(questions, seed), [questions, seed]);
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [results, setResults] = useState<{ question_id: string; notion: string; correct: boolean }[]>([]);
  const [start] = useState(Date.now());
  const q = order[i];

  const pick = (k: number) => {
    if (picked !== null) return;
    setPicked(k);
    setResults((r) => [...r, { question_id: q.id, notion: q.notion, correct: k === q.correct_index }]);
  };
  const next = async () => {
    if (i + 1 >= order.length) {
      const score = results.filter((r) => r.correct).length;
      await api.attempt({ course_id: courseId, mode: "qcm", score, total: order.length, duration_seconds: (Date.now() - start) / 1000, details: results });
    }
    setPicked(null);
    setI(i + 1);
  };

  if (!order.length) return <p className="text-sm text-muted">Aucun QCM généré pour ce cours.</p>;
  if (i >= order.length) {
    const score = results.filter((r) => r.correct).length;
    const wrong = results.filter((r) => !r.correct);
    return (
      <div className="card mx-auto max-w-xl p-8 text-center animate-in">
        <div className="text-sm text-muted">Résultat</div>
        <div className="my-2 text-5xl font-semibold tracking-tight">{score}/{order.length}</div>
        <div className={cn("font-medium", score / order.length >= 0.5 ? "text-ok" : "text-bad")}>{pct(score / order.length)}</div>
        {wrong.length > 0 && (
          <div className="mt-6 text-left text-sm">
            <div className="label">Notions à retravailler</div>
            <ul className="list-disc pl-5">{[...new Set(wrong.map((w) => w.notion))].map((n) => <li key={n}>{n}</li>)}</ul>
          </div>
        )}
        <button className="btn-primary mt-6" onClick={() => { setSeed(Math.random()); setI(0); setResults([]); }}><RotateCcw size={15} />Recommencer</button>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-2xl animate-in" key={q.id}>
      <div className="mb-3 flex items-center gap-3 text-xs text-muted">
        <span>Question {i + 1}/{order.length}</span>
        <div className="h-1 flex-1 rounded-full bg-subtle"><div className="h-1 rounded-full bg-accent transition-all" style={{ width: `${(i / order.length) * 100}%` }} /></div>
        <span>{q.notion}</span>
      </div>
      <div className="card p-6">
        <p className="mb-5 text-lg font-medium leading-snug">{q.question}</p>
        <div className="space-y-2">
          {q.choices.map((c, k) => {
            const state = picked === null ? "" : k === q.correct_index ? "border-ok bg-ok/10" : k === picked ? "border-bad bg-bad/10" : "opacity-60";
            return (
              <button key={k} onClick={() => pick(k)} disabled={picked !== null}
                className={cn("flex w-full items-center gap-3 rounded-lg border border-line px-4 py-3 text-left text-sm transition hover:bg-subtle/60", state)}>
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-subtle text-xs font-medium">{String.fromCharCode(65 + k)}</span>
                <span className="flex-1">{c}</span>
                {picked !== null && k === q.correct_index && <Check size={16} className="text-ok" />}
                {picked === k && k !== q.correct_index && <X size={16} className="text-bad" />}
              </button>
            );
          })}
        </div>
        {picked !== null && (
          <div className="mt-5 rounded-lg bg-subtle p-4 text-sm animate-in">
            <span className="font-medium">{picked === q.correct_index ? "Correct ! " : "Pas tout à fait. "}</span>
            {q.explanation} <TimeLink t={q.timestamp} onSeek={onSeek} />
          </div>
        )}
      </div>
      {picked !== null && <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={next}>{i + 1 >= order.length ? "Voir mon score" : "Question suivante"}</button></div>}
    </div>
  );
}
