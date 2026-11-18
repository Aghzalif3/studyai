"use client";

import { CheckCircle2, Cpu, Download, KeyRound, XCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Notice, PageHeader, Spinner, Toggle, cn, useLoad } from "@/components/ui";
import { api, type Settings } from "@/lib/api";

function Row({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <div className="flex items-start gap-2 text-sm">{ok ? <CheckCircle2 size={16} className="mt-0.5 text-ok" /> : <XCircle size={16} className="mt-0.5 text-bad" />}<div>{children}</div></div>;
}

export default function SettingsPage() {
  const status = useLoad(api.status, [], { interval: 4000, active: (d) => !!d?.pulling.length });
  const s = status.data;
  const [form, setForm] = useState<Settings>();
  const [key, setKey] = useState("");
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string }>();
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (s && !form) setForm(s.settings); }, [s, form]);

  const save = async (patch: Partial<Settings>) => {
    if (!form) return;
    const next = { ...form, ...patch };
    setForm(next);
    try { await api.saveSettings(patch); setMsg({ tone: "ok", text: "Réglages enregistrés." }); }
    catch (e) { setMsg({ tone: "bad", text: (e as Error).message }); }
  };
  const saveKey = async (value: string) => {
    setSaving(true);
    try { await api.saveKey(value); setKey(""); await status.reload(); setMsg({ tone: "ok", text: value ? "Clé API enregistrée dans le fichier .env local." : "Clé supprimée." }); }
    catch (e) { setMsg({ tone: "bad", text: (e as Error).message }); }
    finally { setSaving(false); }
  };
  const pull = async (m: string) => {
    try { await api.pull(m); await status.reload(); } catch (e) { setMsg({ tone: "bad", text: (e as Error).message }); }
  };

  if (!s || !form) return <div className="skeleton h-64" />;
  const installed = new Set((s.ollama_models || []).map((m) => m.replace(/:latest$/, "")));

  return (
    <>
      <PageHeader title="Réglages" subtitle="Tout est stocké sur ton Mac. Les clés ne sont jamais envoyées ailleurs qu'à Anthropic." />
      {msg && <div className="mb-5"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card space-y-4 p-5">
          <h2 className="flex items-center gap-2 font-semibold"><Cpu size={17} className="text-accent" />Ton ordinateur</h2>
          <Row ok={s.ffmpeg}>FFmpeg {s.ffmpeg ? "installé" : "manquant (relance StudyAI.command)"}</Row>
          <Row ok={s.whisper_engines.length > 0}>Whisper : {s.whisper_engines.length ? s.whisper_engines.map((e) => ({ mlx: "mlx-whisper (puce Apple)", faster: "faster-whisper", openai: "openai-whisper" }[e] || e)).join(", ") : "aucun moteur installé"}</Row>
          <Row ok={!!s.ocr}>OCR des diapositives : {s.ocr === "vision" ? "Apple Vision (intégré à macOS)" : s.ocr === "tesseract" ? "Tesseract" : "aucun (installe Tesseract : brew install tesseract tesseract-lang)"}</Row>
          {!s.apple_silicon && <Notice tone="warn">Ce Mac n'a pas de puce Apple : la transcription sera nettement plus lente. Choisis le modèle « small » ou « medium » pour aller plus vite.</Notice>}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <label><span className="label">Modèle Whisper</span>
              <select className="input" value={form.whisper_model} onChange={(e) => save({ whisper_model: e.target.value })}>
                {s.whisper_models.map((m) => <option key={m} value={m}>{m === "turbo" ? "turbo (recommandé)" : m}</option>)}
              </select></label>
            <label><span className="label">Moteur</span>
              <select className="input" value={form.whisper_engine} onChange={(e) => save({ whisper_engine: e.target.value })}>
                <option value="auto">Automatique</option>
                {s.whisper_engines.map((e) => <option key={e} value={e}>{e}</option>)}
              </select></label>
            <label className="col-span-2"><span className="label">Langue par défaut</span>
              <select className="input" value={form.language} onChange={(e) => save({ language: e.target.value })}>
                <option value="auto">Détection automatique</option><option value="fr">Français</option><option value="en">Anglais</option><option value="nl">Néerlandais</option>
              </select></label>
          </div>
          <p className="text-xs text-muted">Le modèle est téléchargé une seule fois au premier usage (turbo ≈ 1,6 Go), puis tout fonctionne hors ligne.</p>
        </section>

        <section className="card space-y-4 p-5">
          <h2 className="flex items-center gap-2 font-semibold"><KeyRound size={17} className="text-accent" />Analyse intelligente</h2>
          <div className="grid grid-cols-2 gap-2">
            {(["claude", "local"] as const).map((p) => (
              <button key={p} onClick={() => save({ provider: p })}
                className={cn("rounded-lg border px-3 py-2.5 text-left text-sm", form.provider === p ? "border-accent bg-accent/5 ring-2 ring-accent/15" : "border-line hover:bg-subtle/50")}>
                <div className="font-medium">{p === "claude" ? "Claude (API)" : "Modèle local gratuit"}</div>
                <div className="text-xs text-muted">{p === "claude" ? "Meilleure qualité, payant à l'usage" : "Ollama, hors ligne, qualité moindre"}</div>
              </button>
            ))}
          </div>

          {form.provider === "claude" ? (
            <>
              <Notice>
                <b>Claude Pro ≠ API.</b> Ton abonnement Claude Pro ne donne pas accès à l'API. Il faut créer une clé sur{" "}
                <a className="font-medium text-accent underline" href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">console.anthropic.com</a>{" "}
                et y ajouter du crédit (paiement à l'usage, séparé de Pro). Compte environ 0,50 à 1,50 $ pour un cours de 2 h avec Opus.
              </Notice>
              <div>
                <span className="label">Clé API {s.api_key && <span className="normal-case text-ok">· configurée ({s.api_key_hint})</span>}</span>
                <div className="flex gap-2">
                  <input className="input font-mono" type="password" placeholder="sk-ant-…" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
                  <button className="btn-primary" disabled={!key || saving} onClick={() => saveKey(key)}>{saving ? <Spinner /> : "Enregistrer"}</button>
                </div>
                {s.api_key && <button className="mt-1 text-xs text-muted hover:text-bad" onClick={() => saveKey("")}>Supprimer la clé</button>}
              </div>
              <label className="block"><span className="label">Modèle</span>
                <select className="input" value={form.claude_model} onChange={(e) => save({ claude_model: e.target.value })}>
                  {Object.entries(s.claude_models).map(([id, m]) => <option key={id} value={id}>{m.label} · {m.input} $ / {m.output} $ par million de tokens</option>)}
                </select></label>
              <label className="block"><span className="label">Profondeur d'analyse</span>
                <select className="input" value={form.effort} onChange={(e) => save({ effort: e.target.value })}>
                  <option value="medium">Rapide</option><option value="high">Approfondie (recommandé)</option><option value="xhigh">Très approfondie (plus cher)</option>
                </select></label>
              <Toggle checked={form.vision_default} onChange={(v) => save({ vision_default: v })} label="Lire les diapositives avec Claude par défaut"
                hint="≈ 0,01 $ par diapositive avec Opus. Lit tableaux, graphiques et formules." />
            </>
          ) : (
            <>
              <Notice tone={s.ollama_models ? "ok" : "warn"}>
                {s.ollama_models
                  ? <>Ollama est lancé. Modèles installés : {s.ollama_models.length ? s.ollama_models.join(", ") : "aucun"}.</>
                  : <>Ollama n'est pas lancé. Installe-le depuis <a className="underline" href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com</a> (StudyAI.command le fait aussi), puis ouvre l'application.</>}
              </Notice>
              <p className="text-sm text-muted">Gratuit et hors ligne, mais nettement moins précis que Claude : relis les résumés avec ton cours. Un cours de 2 h prend 15 à 40 min d'analyse sur un Mac M1/M2 16 Go.</p>
              <div className="space-y-2">
                {Object.entries(s.local_models).map(([id, label]) => {
                  const has = installed.has(id);
                  return (
                    <div key={id} className={cn("flex items-center gap-3 rounded-lg border px-3 py-2", form.local_model === id ? "border-accent bg-accent/5" : "border-line")}>
                      <input type="radio" checked={form.local_model === id} onChange={() => save({ local_model: id })} />
                      <div className="flex-1 text-sm"><div className="font-medium">{id}</div><div className="text-xs text-muted">{label}</div></div>
                      {has ? <span className="chip text-ok">Installé</span> : s.pulling.includes(id)
                        ? <span className="chip"><Spinner className="h-3 w-3" />Téléchargement…</span>
                        : <button className="btn-outline px-2.5 py-1 text-xs" disabled={!s.ollama_models} onClick={() => pull(id)}><Download size={12} />Installer</button>}
                    </div>
                  );
                })}
              </div>
            </>
          )}
          <Toggle checked={form.accounting_default} onChange={(v) => save({ accounting_default: v })} label="Mode comptabilité par défaut" />
        </section>
      </div>
    </>
  );
}
