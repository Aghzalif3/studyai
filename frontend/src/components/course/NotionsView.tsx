"use client";

import { AlertOctagon, BookMarked, Brain, FlaskConical, HelpCircle, Lightbulb, Sigma, Star } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Notions } from "@/lib/api";
import { cn } from "../ui";
import { TimeLink } from "./Summary";

function Section({ icon, title, count, children }: { icon: ReactNode; title: string; count: number; children: ReactNode }) {
  if (!count) return null;
  return (
    <section className="card p-5 animate-in">
      <h3 className="mb-4 flex items-center gap-2 font-semibold">
        <span className="text-accent">{icon}</span>{title}<span className="chip ml-1">{count}</span>
      </h3>
      {children}
    </section>
  );
}

export function NotionsView({ data, onSeek }: { data: Notions; onSeek: (t: number) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Section icon={<BookMarked size={17} />} title="Définitions" count={data.definitions.length}>
        <dl className="space-y-3">
          {data.definitions.map((d, i) => (
            <div key={i}>
              <dt className="flex items-center gap-2 font-medium">{d.term}<TimeLink t={d.timestamp} onSeek={onSeek} />
                <span className="chip">{d.source}</span></dt>
              <dd className="mt-0.5 text-sm text-muted">{d.definition}</dd>
            </div>
          ))}
        </dl>
      </Section>
      <Section icon={<Brain size={17} />} title="Notions à mémoriser" count={data.key_notions.length}>
        <ul className="space-y-3">
          {data.key_notions.map((d, i) => (
            <li key={i}><div className="flex items-center gap-2 font-medium">{d.notion}<TimeLink t={d.timestamp} onSeek={onSeek} /></div>
              <p className="text-sm text-muted">{d.explanation}</p></li>
          ))}
        </ul>
      </Section>
      <Section icon={<Sigma size={17} />} title="Formules" count={data.formulas.length}>
        <div className="space-y-3">
          {data.formulas.map((f, i) => (
            <div key={i} className="rounded-lg bg-subtle p-3">
              <div className="flex items-center gap-2 text-sm font-medium">{f.name}<TimeLink t={f.timestamp} onSeek={onSeek} /></div>
              <div className="my-2 font-mono text-[15px]">{f.formula}</div>
              {f.variables && <div className="text-xs text-muted">{f.variables}</div>}
              {f.explanation && <div className="mt-1 text-sm">{f.explanation}</div>}
            </div>
          ))}
        </div>
      </Section>
      <Section icon={<FlaskConical size={17} />} title="Exemples du professeur" count={data.examples.length}>
        <ul className="space-y-3">
          {data.examples.map((d, i) => (
            <li key={i}><div className="flex items-center gap-2 font-medium">{d.title}<TimeLink t={d.timestamp} onSeek={onSeek} /></div>
              <p className="whitespace-pre-line text-sm text-muted">{d.description}</p></li>
          ))}
        </ul>
      </Section>
      <Section icon={<Lightbulb size={17} />} title="Explications simplifiées" count={data.simplified.length}>
        <ul className="space-y-3">
          {data.simplified.map((d, i) => <li key={i}><div className="font-medium">{d.notion}</div><p className="text-sm text-muted">{d.explanation}</p></li>)}
        </ul>
      </Section>
      <Section icon={<AlertOctagon size={17} />} title="Erreurs fréquentes à éviter" count={data.common_mistakes.length}>
        <ul className="space-y-3 text-sm">
          {data.common_mistakes.map((d, i) => (
            <li key={i} className="rounded-lg border border-line p-3">
              <div className="text-bad">✗ {d.mistake}</div>
              <div className="mt-1 text-ok">✓ {d.correction}</div>
            </li>
          ))}
        </ul>
      </Section>
      <Section icon={<Star size={17} />} title="Important pour l'examen" count={data.exam_points.length}>
        <ul className="space-y-3">
          {data.exam_points.map((d, i) => (
            <li key={i}><div className="flex items-center gap-2 font-medium">{d.point}<TimeLink t={d.timestamp} onSeek={onSeek} /></div>
              <p className="text-sm text-muted">{d.reason}</p></li>
          ))}
        </ul>
      </Section>
      <Section icon={<HelpCircle size={17} />} title="Questions que le professeur pourrait poser" count={data.likely_questions.length}>
        <ul className="space-y-2">
          {data.likely_questions.map((d, i) => (
            <li key={i} className="rounded-lg border border-line">
              <button className="flex w-full items-center justify-between gap-2 p-3 text-left text-sm font-medium" onClick={() => setOpen(open === i ? null : i)}>
                {d.question}<span className={cn("text-muted transition", open === i && "rotate-90")}>›</span>
              </button>
              {open === i && <div className="border-t border-line p-3 text-sm text-muted animate-in">{d.expected_answer} <TimeLink t={d.timestamp} onSeek={onSeek} /></div>}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
