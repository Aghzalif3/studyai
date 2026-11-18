"use client";

import { AlertTriangle, PlayCircle } from "lucide-react";
import type { CourseAnalysis } from "@/lib/api";
import { hms } from "@/lib/format";
import { Md } from "../ui";

export function TimeLink({ t, onSeek }: { t: number; onSeek: (t: number) => void }) {
  return (
    <button onClick={() => onSeek(t)} className="no-print inline-flex items-center gap-1 rounded-md bg-subtle px-1.5 py-0.5 font-mono text-[11px] text-muted transition hover:bg-accent/10 hover:text-accent">
      <PlayCircle size={11} />{hms(t)}
    </button>
  );
}

export function Summary({ data, onSeek, onSlide }: { data: CourseAnalysis; onSeek: (t: number) => void; onSlide: (i: number) => void }) {
  return (
    <div className="grid gap-6 lg:grid-cols-4">
      <nav className="no-print hidden lg:block">
        <div className="sticky top-6 space-y-1">
          <div className="label">Chapitres</div>
          {data.chapters.map((c, i) => (
            <a key={i} href={`#ch-${i}`} className="block truncate rounded-md px-2 py-1 text-sm text-muted hover:bg-subtle hover:text-fg">
              {i + 1}. {c.title}
            </a>
          ))}
        </div>
      </nav>
      <div className="space-y-6 lg:col-span-3">
        <section className="card p-6 animate-in">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-accent">{data.subject}</div>
          <h2 className="mb-3 text-xl font-semibold tracking-tight">{data.title}</h2>
          <Md>{data.general_summary}</Md>
        </section>
        {data.uncertainties.length > 0 && (
          <section className="card border-warn/40 p-5">
            <h3 className="mb-3 flex items-center gap-2 font-semibold"><AlertTriangle size={16} className="text-warn" />Incertitudes de transcription</h3>
            <ul className="space-y-2 text-sm">
              {data.uncertainties.map((u, i) => (
                <li key={i} className="flex gap-2"><TimeLink t={u.timestamp} onSeek={onSeek} />
                  <span><i>« {u.excerpt} »</i> : <span className="text-muted">{u.issue}</span></span></li>
              ))}
            </ul>
          </section>
        )}
        {data.chapters.map((c, i) => (
          <section key={i} id={`ch-${i}`} className="card scroll-mt-6 p-6 animate-in">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-accent/10 text-xs font-semibold text-accent">{i + 1}</span>
              <h3 className="text-lg font-semibold tracking-tight">{c.title}</h3>
              <TimeLink t={c.start} onSeek={onSeek} />
            </div>
            <Md>{c.summary}</Md>
            {c.key_points.length > 0 && (
              <div className="mt-4 rounded-lg bg-subtle p-4">
                <div className="label">À retenir</div>
                <ul className="list-disc space-y-1 pl-5 text-sm">{c.key_points.map((p, j) => <li key={j}>{p}</li>)}</ul>
              </div>
            )}
            {c.slides.length > 0 && (
              <div className="no-print mt-3 flex flex-wrap gap-1">
                {c.slides.map((s) => <button key={s} onClick={() => onSlide(s)} className="chip hover:text-accent">Diapo {s}</button>)}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
