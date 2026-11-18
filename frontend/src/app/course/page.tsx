"use client";

import { BookText, Download, FileText, GraduationCap, Image as ImageIcon, ListChecks, PlayCircle, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { NotionsView } from "@/components/course/NotionsView";
import { Player } from "@/components/course/Player";
import { RevisionView } from "@/components/course/RevisionView";
import { SlidesView } from "@/components/course/SlidesView";
import { Summary } from "@/components/course/Summary";
import { Empty, Notice, Progress, Spinner, StatusBadge, Tabs, cn, useLoad } from "@/components/ui";
import { api, exportUrl, type Course } from "@/lib/api";
import { duration, eta, usd } from "@/lib/format";

type Tab = "summary" | "video" | "slides" | "notions" | "revision";

const STEPS: [string, string][] = [
  ["transcribe", "Transcription"], ["slides", "Diapositives"], ["ocr", "Texte des diapos"], ["vision", "Lecture IA des diapos"], ["analysis", "Analyse"],
];

function ExportMenu({ course }: { course: Course }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);
  const analysed = course.analysis_kinds.length > 0;
  const items: [string, string, boolean][] = [
    ["txt", "Transcription (TXT)", course.counts.segments > 0],
    ["srt", "Sous-titres (SRT)", course.counts.segments > 0],
    ["pdf", "Transcription (PDF)", course.counts.segments > 0],
    ["course.pdf", "Cours complet (PDF)", analysed],
    ["course.md", "Cours complet (Markdown)", analysed],
  ];
  return (
    <div ref={ref} className="relative">
      <button className="btn-outline" onClick={() => setOpen(!open)}><Download size={15} />Exporter</button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-line bg-panel p-1 shadow-pop animate-in">
          {items.map(([fmt, label, ok]) => ok ? (
            <a key={fmt} href={exportUrl(course.id, fmt)} className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-subtle">
              <FileText size={14} className="text-muted" />{label}
            </a>
          ) : (
            <div key={fmt} className="flex items-center gap-2 px-3 py-2 text-sm text-muted/60"><FileText size={14} />{label}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function CoursePage() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id") || "";
  const [tab, setTab] = useState<Tab>((params.get("tab") as Tab) || "summary");
  const [seek, setSeek] = useState<{ t: number; n: number } | null>(null);
  const [slideFocus, setSlideFocus] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const course = useLoad(() => api.course(id), [id], { interval: 2500, active: (c) => c?.status === "running" || c?.status === "queued" });
  const c = course.data;
  const version = `${c?.status}-${c?.counts.segments}-${c?.counts.slides}-${c?.analysis_kinds.join()}`;
  const transcript = useLoad(() => api.transcript(id), [id, version]);
  const slides = useLoad(() => api.slides(id), [id, version]);
  const analysis = useLoad(() => api.analysis(id), [id, version]);
  const status = useLoad(api.status, []);

  const a = analysis.data;
  const hasAnalysis = !!a?.course;
  useEffect(() => {
    if (c && !hasAnalysis && tab === "summary" && analysis.data) setTab("video");
  }, [c, hasAnalysis, tab, analysis.data]);

  if (!id) return <Empty icon={<BookText />} title="Aucun cours sélectionné" />;
  if (course.error && !c) return <Notice tone="bad">{course.error}</Notice>;
  if (!c) return <div className="space-y-3"><div className="skeleton h-8 w-72" /><div className="skeleton h-64 w-full" /></div>;

  const onSeek = (t: number) => { setTab("video"); setSeek({ t, n: Date.now() }); };
  const onSlide = (i: number) => { setTab("slides"); setSlideFocus(i); };
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setActionError(undefined);
    try { await fn(); await course.reload(); } catch (e) { setActionError((e as Error).message); } finally { setBusy(false); }
  };
  const running = c.status === "running" || c.status === "queued";
  const s = status.data;
  const canClaude = !!s?.api_key;
  const canLocal = !!s?.ollama_models;

  const tabs = [
    hasAnalysis && { id: "summary" as Tab, label: "Résumé", icon: <BookText size={14} /> },
    { id: "video" as Tab, label: c.has_video ? "Vidéo & transcription" : "Audio & transcription", icon: <PlayCircle size={14} /> },
    c.counts.slides > 0 && { id: "slides" as Tab, label: `Diapositives (${c.counts.slides})`, icon: <ImageIcon size={14} /> },
    a?.notions && { id: "notions" as Tab, label: "Notions", icon: <ListChecks size={14} /> },
    a?.revision && { id: "revision" as Tab, label: "Révision", icon: <GraduationCap size={14} /> },
  ].filter(Boolean) as { id: Tab; label: string; icon: React.ReactNode }[];

  return (
    <>
      <div className="mb-6 animate-in">
        <Link href="/library" className="text-xs text-muted hover:text-fg">← Bibliothèque</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{a?.course?.title || c.title}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted">
              <StatusBadge status={c.status} />
              {c.duration ? <span>{duration(c.duration)}</span> : null}
              {c.language && <span>· {c.language.toUpperCase()}</span>}
              {c.cost_usd > 0 && <span>· coût IA {usd(c.cost_usd)}</span>}
            </div>
          </div>
          <div className="no-print flex flex-wrap gap-2">
            {running && <button className="btn-outline" disabled={busy} onClick={() => act(() => api.cancel(c.id))}><X size={15} />Annuler</button>}
            {(c.status === "error" || c.status === "cancelled") && (
              <button className="btn-primary" disabled={busy} onClick={() => act(() => api.retry(c.id))}><RefreshCw size={15} />Reprendre</button>
            )}
            <ExportMenu course={c} />
            <button className="btn-ghost text-muted hover:text-bad" title="Supprimer" disabled={busy}
              onClick={() => confirmDelete() && act(async () => { await api.remove(c.id); router.push("/library"); })}><Trash2 size={15} /></button>
          </div>
        </div>
      </div>

      {running && (
        <div className="card mb-6 p-5 animate-in">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 font-medium"><Spinner className="text-accent" />{c.status === "queued" ? "En attente de traitement" : c.stage_label || "Préparation"}</span>
            <span className="text-muted">{Math.round(c.progress * 100)} %{c.eta_seconds != null ? ` · reste ${eta(c.eta_seconds)}` : ""}</span>
          </div>
          <Progress value={c.progress} />
          <div className="mt-4 flex flex-wrap gap-2">
            {STEPS.map(([k, label]) => {
              const st = c.steps[k];
              const isCurrent = c.stage === k;
              return <span key={k} className={cn("chip", st === "done" && "border-ok/40 text-ok", isCurrent && "border-accent/40 text-accent")}>
                {st === "done" ? "✓" : isCurrent ? "•" : "○"} {label}</span>;
            })}
          </div>
          <p className="mt-3 text-xs text-muted">Tu peux fermer StudyAI : la progression est sauvegardée et reprendra au prochain lancement. Les résultats apparaissent au fur et à mesure.</p>
        </div>
      )}
      {c.status === "error" && <div className="mb-6"><Notice tone="bad"><b>Le traitement s'est arrêté.</b> {c.error} Ce qui était déjà fait est conservé : clique sur Reprendre.</Notice></div>}
      {actionError && <div className="mb-6"><Notice tone="bad">{actionError}</Notice></div>}

      {c.status === "done" && !hasAnalysis && (
        <div className="mb-6"><Notice>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <b>Transcription prête.</b>{" "}
              {c.steps.analysis === "no_key" ? "L'analyse IA n'a pas été faite (aucune clé API Claude configurée)." : "Lance l'analyse pour obtenir le cours structuré, les fiches et les exercices."}
            </div>
            <div className="flex gap-2">
              <button className="btn-primary" disabled={busy || !canClaude} title={canClaude ? "" : "Ajoute une clé API dans Réglages"}
                onClick={() => act(() => api.reanalyze(c.id, { provider: "claude" }))}><Sparkles size={15} />Analyser avec Claude</button>
              <button className="btn-outline" disabled={busy || !canLocal} title={canLocal ? "" : "Ollama n'est pas lancé"}
                onClick={() => act(() => api.reanalyze(c.id, { provider: "local" }))}>Modèle local gratuit</button>
            </div>
          </div>
        </Notice></div>
      )}

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs<Tab> tabs={tabs} value={tab} onChange={setTab} />
        {hasAnalysis && !running && (
          <button className="no-print btn-ghost text-xs text-muted" disabled={busy}
            onClick={() => window.confirm("Refaire toute l'analyse ? (nouveau coût API si Claude est utilisé)") && act(() => api.reanalyze(c.id, {}))}>
            <RefreshCw size={13} />Refaire l'analyse
          </button>
        )}
      </div>

      {tab === "summary" && a?.course && <Summary data={a.course} onSeek={onSeek} onSlide={onSlide} />}
      {tab === "video" && <Player course={c} segments={transcript.data || []} slides={slides.data || []} seek={seek} onEdited={transcript.reload} />}
      {tab === "slides" && <SlidesView courseId={c.id} slides={slides.data || []} focus={slideFocus} onSeek={onSeek} />}
      {tab === "notions" && a?.notions && <NotionsView data={a.notions} onSeek={onSeek} />}
      {tab === "revision" && a?.revision && <RevisionView courseId={c.id} rev={a.revision} onSeek={onSeek} />}
    </>
  );
}

function confirmDelete() {
  return window.confirm("Supprimer ce cours, sa vidéo et tous ses résultats ?");
}

export default function Page() {
  return <Suspense fallback={<div className="skeleton h-8 w-72" />}><CoursePage /></Suspense>;
}
