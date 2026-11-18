"use client";

import { ArrowRight, BookOpen, Layers, Target, Upload, Sparkles } from "lucide-react";
import Link from "next/link";
import { CourseCard } from "@/components/CourseCard";
import { Empty, Notice, PageHeader, Stat, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";

export default function Dashboard() {
  const courses = useLoad(api.courses, [], { interval: 3000, active: (d) => !!d?.some((c) => c.status === "running" || c.status === "queued") });
  const stats = useLoad(() => api.stats(), []);
  const status = useLoad(api.status, []);
  const list = courses.data || [];
  const active = list.filter((c) => c.status === "running" || c.status === "queued");
  const recent = list.filter((c) => !active.includes(c)).slice(0, 6);
  const names = Object.fromEntries(list.map((c) => [c.id, c.title]));
  const s = status.data;
  const hour = new Date().getHours();

  return (
    <>
      <PageHeader
        title={hour < 18 ? "Bonjour 👋" : "Bonsoir 👋"}
        subtitle="Dépose une vidéo de cours, StudyAI s'occupe du reste."
        actions={<Link href="/import" className="btn-primary"><Upload size={16} />Importer un cours</Link>}
      />

      {courses.error && <div className="mb-6"><Notice tone="bad">{courses.error}</Notice></div>}
      {s && (!s.ffmpeg || s.whisper_engines.length === 0) && (
        <div className="mb-6"><Notice tone="warn">
          {!s.ffmpeg && <p>FFmpeg n'est pas installé : relance <b>StudyAI.command</b> pour l'installer automatiquement.</p>}
          {s.whisper_engines.length === 0 && <p>Aucun moteur Whisper n'est installé : relance <b>StudyAI.command</b>.</p>}
        </Notice></div>
      )}
      {s && s.settings.provider === "claude" && !s.api_key && (
        <div className="mb-6"><Notice>
          <b>Analyse IA non configurée.</b> La transcription, les diapositives et les exports fonctionnent gratuitement.
          Pour les résumés, fiches, QCM et examens, ajoute une clé API Claude ou choisis le modèle local gratuit dans{" "}
          <Link href="/settings" className="font-medium text-accent underline-offset-2 hover:underline">Réglages</Link>.
        </Notice></div>
      )}

      <div className="mb-10 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Cours" value={list.length} hint={(() => { const n = list.filter((c) => c.status === "done").length; return `${n} prêt${n > 1 ? "s" : ""}`; })()} icon={<BookOpen size={14} />} />
        <Stat label="Cartes à revoir" value={stats.data?.flashcards_due ?? "–"} hint={`${stats.data?.flashcards_total ?? 0} au total`} icon={<Layers size={14} />} />
        <Stat label="Réussite" value={stats.data?.success_rate != null ? pct(stats.data.success_rate) : "–"} hint={`${stats.data?.answers ?? 0} réponses`} icon={<Target size={14} />} />
        <Stat label="Examens blancs" value={stats.data?.attempts.filter((a) => a.mode === "exam").length ?? "–"} icon={<Sparkles size={14} />} />
      </div>

      {active.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-3 text-sm font-semibold text-muted">En cours d'analyse</h2>
          <div className="grid gap-3 md:grid-cols-2">{active.map((c) => <CourseCard key={c.id} c={c} />)}</div>
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-3">
        <section className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted">Cours récents</h2>
            {list.length > 0 && <Link href="/library" className="flex items-center gap-1 text-sm text-muted hover:text-fg">Tout voir <ArrowRight size={14} /></Link>}
          </div>
          {list.length === 0 && courses.data ? (
            <Empty icon={<Upload size={20} />} title="Aucun cours pour l'instant">
              Importe ta première vidéo ou ton premier enregistrement audio.
              <div className="mt-4"><Link href="/import" className="btn-primary">Importer un cours</Link></div>
            </Empty>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">{recent.map((c) => <CourseCard key={c.id} c={c} />)}</div>
          )}
        </section>
        <section>
          <h2 className="mb-3 text-sm font-semibold text-muted">Mes points faibles</h2>
          <div className="card divide-y divide-line">
            {(stats.data?.weak_notions || []).slice(0, 6).map((w) => (
              <Link key={w.course_id + w.notion} href={`/course?id=${w.course_id}&tab=revision`} className="block px-4 py-3 hover:bg-subtle/50">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{w.notion}</span>
                  <span className="text-xs font-medium text-bad">{pct(w.success_rate)}</span>
                </div>
                <div className="truncate text-xs text-muted">{names[w.course_id]}</div>
              </Link>
            ))}
            {!stats.data?.weak_notions.length && (
              <p className="px-4 py-6 text-center text-sm text-muted">Fais un QCM ou un examen blanc : tes difficultés apparaîtront ici.</p>
            )}
          </div>
          {!!stats.data?.flashcards_due && (
            <Link href="/review" className="card mt-3 flex items-center justify-between p-4 hover:bg-subtle/40">
              <div>
                <div className="text-sm font-medium">{stats.data.flashcards_due} cartes à revoir</div>
                <div className="text-xs text-muted">Répétition espacée</div>
              </div>
              <ArrowRight size={16} className="text-muted" />
            </Link>
          )}
        </section>
      </div>
    </>
  );
}
