"use client";

import { FileAudio, Film, Sparkles, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Notice, PageHeader, Progress, Toggle, cn, useLoad } from "@/components/ui";
import { api, uploadCourse } from "@/lib/api";
import { duration, usd } from "@/lib/format";

const ACCEPT = ".mp4,.mov,.mkv,.avi,.webm,.m4v,.wmv,.mpg,.mpeg,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus";

interface Item { file: File; title: string; seconds: number | null }

function probeDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const el = document.createElement(file.type.startsWith("audio") ? "audio" : "video");
    const url = URL.createObjectURL(file);
    const done = (v: number | null) => { URL.revokeObjectURL(url); resolve(v); };
    el.preload = "metadata";
    el.onloadedmetadata = () => done(Number.isFinite(el.duration) ? el.duration : null);
    el.onerror = () => done(null);
    setTimeout(() => done(null), 4000);
    el.src = url;
  });
}

export default function ImportPage() {
  const router = useRouter();
  const status = useLoad(api.status, []);
  const [items, setItems] = useState<Item[]>([]);
  const [drag, setDrag] = useState(false);
  const [mode, setMode] = useState<"claude" | "local" | "none">("claude");
  const [accounting, setAccounting] = useState(true);
  const [vision, setVision] = useState(true);
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState<{ index: number; progress: number } | null>(null);
  const [error, setError] = useState<string>();
  const [estimate, setEstimate] = useState<Record<string, { usd: number }>>();
  const input = useRef<HTMLInputElement>(null);
  const s = status.data;

  useEffect(() => {
    if (!s) return;
    setMode(s.settings.provider === "local" ? "local" : s.api_key ? "claude" : "none");
    setAccounting(s.settings.accounting_default);
    setVision(s.settings.vision_default);
    setLanguage(s.settings.language);
  }, [s]);

  const totalSeconds = items.reduce((a, i) => a + (i.seconds || 0), 0);
  useEffect(() => {
    if (!totalSeconds) return setEstimate(undefined);
    api.estimate(Math.max(1, totalSeconds / 60)).then(setEstimate).catch(() => {});
  }, [totalSeconds]);

  const add = async (files: FileList | File[]) => {
    setError(undefined);
    const list = Array.from(files);
    const added = await Promise.all(list.map(async (file) => ({
      file, title: file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "), seconds: await probeDuration(file),
    })));
    setItems((prev) => [...prev, ...added]);
  };

  const start = async () => {
    setError(undefined);
    let firstId: string | null = null;
    for (let i = 0; i < items.length; i++) {
      setBusy({ index: i, progress: 0 });
      try {
        const course = await uploadCourse(items[i].file, {
          title: items[i].title,
          analyze: mode !== "none",
          provider: mode === "local" ? "local" : "claude",
          accounting, vision: vision && mode === "claude", language,
        }, (p) => setBusy({ index: i, progress: p }));
        firstId = firstId || course.id;
      } catch (e) {
        setError(`${items[i].file.name} : ${(e as Error).message}`);
        setBusy(null);
        return;
      }
    }
    setBusy(null);
    router.push(items.length === 1 && firstId ? `/course?id=${firstId}` : "/library");
  };

  const claudeModel = s?.settings.claude_model || "claude-opus-5-5";

  return (
    <>
      <PageHeader title="Importer un cours" subtitle="Vidéo (MP4, MOV, MKV…) ou audio (MP3, WAV, M4A…), même de plusieurs heures." />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
            onClick={() => input.current?.click()}
            className={cn(
              "card flex cursor-pointer flex-col items-center justify-center border-2 border-dashed px-6 py-16 text-center transition",
              drag ? "scale-[1.01] border-accent bg-accent/5" : "hover:border-accent/50 hover:bg-subtle/40",
            )}
          >
            <div className={cn("mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-accent/10 text-accent transition", drag && "scale-110")}>
              <UploadCloud size={26} />
            </div>
            <p className="text-base font-medium">Glisse ta vidéo de cours ici</p>
            <p className="mt-1 text-sm text-muted">ou clique pour choisir un ou plusieurs fichiers</p>
            <input ref={input} type="file" accept={ACCEPT} multiple hidden onChange={(e) => e.target.files && add(e.target.files)} />
          </div>

          {items.length > 0 && (
            <div className="mt-4 space-y-2">
              {items.map((it, i) => {
                const Icon = it.file.type.startsWith("audio") ? FileAudio : Film;
                return (
                  <div key={i} className="card flex items-center gap-3 p-3 animate-in">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-subtle text-muted"><Icon size={17} /></div>
                    <div className="min-w-0 flex-1">
                      <input className="w-full bg-transparent text-sm font-medium outline-none" value={it.title}
                        onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} />
                      <div className="text-xs text-muted">
                        {(it.file.size / 1e6).toFixed(0)} Mo{it.seconds ? ` · ${duration(it.seconds)}` : ""}
                      </div>
                      {busy?.index === i && <Progress value={busy.progress} className="mt-2" />}
                      {busy && busy.index > i && <div className="mt-1 text-xs text-ok">Envoyé ✓</div>}
                    </div>
                    {!busy && <button className="btn-ghost px-2" onClick={() => setItems(items.filter((_, j) => j !== i))}><X size={15} /></button>}
                  </div>
                );
              })}
            </div>
          )}
          {error && <div className="mt-4"><Notice tone="bad">{error}</Notice></div>}
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div className="card space-y-5 p-5">
            <div>
              <span className="label">Analyse intelligente</span>
              <div className="grid gap-2">
                {([
                  ["claude", "Claude (API)", s?.api_key ? "Meilleure qualité · payant à l'usage" : "Clé API manquante (Réglages)"],
                  ["local", "Modèle local gratuit", s?.ollama_models ? "Ollama · hors ligne · qualité moindre" : "Ollama n'est pas lancé"],
                  ["none", "Transcription seule", "Whisper + diapositives + exports, gratuit"],
                ] as const).map(([id, label, hint]) => (
                  <button key={id} type="button" onClick={() => setMode(id)}
                    disabled={(id === "claude" && !s?.api_key) || (id === "local" && !s?.ollama_models)}
                    className={cn("rounded-lg border px-3 py-2.5 text-left transition disabled:opacity-50",
                      mode === id ? "border-accent bg-accent/5 ring-2 ring-accent/15" : "border-line hover:bg-subtle/50")}>
                    <div className="text-sm font-medium">{label}</div>
                    <div className="text-xs text-muted">{hint}</div>
                  </button>
                ))}
              </div>
            </div>
            <Toggle checked={accounting} onChange={setAccounting} label="Mode comptabilité"
              hint="PCMN, écritures, TVA, RRR, escomptes… Calculs revérifiés par StudyAI." />
            {mode === "claude" && (
              <Toggle checked={vision} onChange={setVision} label="Lire les diapositives avec Claude"
                hint="Tableaux, graphiques et formules. L'OCR gratuit est toujours utilisé." />
            )}
            <div>
              <label className="label" htmlFor="lang">Langue du cours</label>
              <select id="lang" className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="auto">Détection automatique</option>
                <option value="fr">Français</option>
                <option value="en">Anglais</option>
                <option value="nl">Néerlandais</option>
              </select>
            </div>
          </div>

          {mode === "claude" && estimate && (
            <div className="card p-4 text-sm">
              <div className="mb-1 font-medium">Coût estimé de l'analyse</div>
              <div className="text-2xl font-semibold tracking-tight">≈ {usd(estimate[claudeModel]?.usd ?? 0)}</div>
              <p className="mt-1 text-xs text-muted">
                Avec {s?.claude_models[claudeModel]?.label}. Facturé par Anthropic sur ta clé API (Claude Pro n'est pas utilisé).
                Transcription et diapositives : gratuites, sur ton Mac.
              </p>
            </div>
          )}

          <button className="btn-primary w-full py-3 text-base font-semibold tracking-wide" disabled={!items.length || !!busy} onClick={start}>
            <Sparkles size={18} />
            {busy ? `Envoi ${busy.index + 1}/${items.length}…` : "ANALYSER MON COURS"}
          </button>
          {totalSeconds > 0 && (
            <p className="text-center text-xs text-muted">
              Durée totale {duration(totalSeconds)}. Tu peux fermer cette page : le traitement continue et reprend après une interruption.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
