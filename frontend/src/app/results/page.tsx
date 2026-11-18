"use client";

import { BarChart3 } from "lucide-react";
import Link from "next/link";
import { Empty, PageHeader, Stat, cn, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { duration, pct, relDate } from "@/lib/format";

export default function Results() {
  const stats = useLoad(() => api.stats(), []);
  const courses = useLoad(api.courses, []);
  const names = Object.fromEntries((courses.data || []).map((c) => [c.id, c.title]));
  const s = stats.data;
  const attempts = [...(s?.attempts || [])].reverse();
  const last = (s?.attempts || []).slice(-20);
  return (
    <>
      <PageHeader title="Mes résultats" subtitle="Ta progression et les notions qui te posent problème." />
      {s && s.answers === 0 ? (
        <Empty icon={<BarChart3 size={20} />} title="Aucun résultat pour l'instant">Fais un QCM, un examen blanc ou une séance de flashcards.</Empty>
      ) : s && (
        <>
          <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Taux de réussite" value={s.success_rate != null ? pct(s.success_rate) : "–"} hint={`${s.answers} réponses`} />
            <Stat label="QCM faits" value={s.attempts.filter((a) => a.mode === "qcm").length} />
            <Stat label="Examens blancs" value={s.attempts.filter((a) => a.mode === "exam").length} />
            <Stat label="Cartes à revoir" value={s.flashcards_due} hint={`${s.flashcards_total} cartes`} />
          </div>
          {last.length > 1 && (
            <div className="card mb-8 p-5">
              <div className="label">Évolution des scores</div>
              <div className="mt-3 flex h-40 items-end gap-1.5">
                {last.map((a) => {
                  const r = a.score / Math.max(a.total, 1);
                  return (
                    <div key={a.id} className="group relative flex-1" title={`${names[a.course_id] || ""} · ${pct(r)}`}>
                      <div className={cn("w-full rounded-t-md transition-all", r >= 0.5 ? "bg-accent/70 group-hover:bg-accent" : "bg-bad/50 group-hover:bg-bad")}
                        style={{ height: `${Math.max(4, r * 160)}px` }} />
                    </div>
                  );
                })}
              </div>
              <div className="mt-1 border-t border-dashed border-line pt-1 text-right text-[10px] text-muted">ligne = 50 %</div>
            </div>
          )}
          <div className="grid gap-6 lg:grid-cols-2">
            <section>
              <h2 className="mb-3 text-sm font-semibold text-muted">Notions difficiles</h2>
              <div className="card divide-y divide-line">
                {s.weak_notions.map((w) => (
                  <Link key={w.course_id + w.notion} href={`/course?id=${w.course_id}&tab=revision`} className="flex items-center gap-3 px-4 py-3 hover:bg-subtle/50">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{w.notion}</div>
                      <div className="truncate text-xs text-muted">{names[w.course_id]} · {w.answers} réponses</div>
                    </div>
                    <div className="w-24"><div className="h-1.5 rounded-full bg-subtle"><div className="h-1.5 rounded-full bg-bad" style={{ width: `${w.success_rate * 100}%` }} /></div></div>
                    <span className="w-10 text-right text-xs font-medium">{pct(w.success_rate)}</span>
                  </Link>
                ))}
                {!s.weak_notions.length && <p className="px-4 py-6 text-center text-sm text-muted">Aucune difficulté repérée. Bravo !</p>}
              </div>
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold text-muted">Historique</h2>
              <div className="card divide-y divide-line">
                {attempts.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                    <span className="chip">{a.mode === "exam" ? "Examen" : "QCM"}</span>
                    <span className="min-w-0 flex-1 truncate">{names[a.course_id]}</span>
                    <span className="text-xs text-muted">{relDate(a.created_at)}{a.duration_seconds ? ` · ${duration(a.duration_seconds)}` : ""}</span>
                    <span className={cn("w-16 text-right font-medium", a.score / a.total >= 0.5 ? "text-ok" : "text-bad")}>{+a.score.toFixed(1)}/{a.total}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
    </>
  );
}
