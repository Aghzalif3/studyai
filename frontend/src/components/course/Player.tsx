"use client";

import { AlertTriangle, Check, Pencil, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, mediaUrl, type Course, type Segment, type Slide, slideUrl } from "@/lib/api";
import { activeSegment, hms } from "@/lib/format";
import { cn } from "../ui";

export function Player({ course, segments, slides, seek, onEdited }: {
  course: Course; segments: Segment[]; slides: Slide[]; seek: { t: number; n: number } | null; onEdited: () => void;
}) {
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState(0);
  const [follow, setFollow] = useState(true);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const starts = useMemo(() => segments.map((s) => s.start), [segments]);
  const active = activeSegment(starts, time);
  const slideIdx = activeSegment(slides.map((s) => s.ts), time);
  const currentSlide = slideIdx >= 0 ? slides[slideIdx] : null;

  useEffect(() => {
    if (seek && media.current) {
      media.current.currentTime = seek.t;
      media.current.play().catch(() => {});
    }
  }, [seek]);

  useEffect(() => {
    if (!follow || active < 0 || q) return;
    const el = list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [active, follow, q]);

  const go = (t: number) => {
    if (media.current) {
      media.current.currentTime = t;
      media.current.play().catch(() => {});
    }
  };

  const filtered = q ? segments.map((s, i) => [s, i] as const).filter(([s]) => s.text.toLowerCase().includes(q.toLowerCase())) : segments.map((s, i) => [s, i] as const);
  const uncertain = segments.filter((s) => s.uncertain).length;

  const save = async (s: Segment) => {
    await api.editSegment(course.id, s.id, draft);
    setEditing(null);
    onEdited();
  };

  return (
    <div className="grid gap-5 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-3">
        <div className="card overflow-hidden bg-black">
          {course.has_video ? (
            <video ref={media} src={mediaUrl(course.id)} controls playsInline className="aspect-video w-full"
              onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} />
          ) : (
            <div className="flex aspect-[3/1] items-center bg-gradient-to-br from-accent/30 to-fuchsia-500/20 p-6">
              <audio ref={media} src={mediaUrl(course.id)} controls className="w-full" onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} />
            </div>
          )}
        </div>
        {currentSlide && (
          <div className="card flex gap-4 p-3 animate-in">
            <img src={slideUrl(course.id, currentSlide.idx)} alt="" className="h-24 rounded-md border border-line object-cover" />
            <div className="min-w-0 text-sm">
              <div className="text-xs font-medium text-muted">Diapositive {currentSlide.idx} · {hms(currentSlide.ts)}</div>
              <p className="mt-1 line-clamp-4 whitespace-pre-line text-muted">{currentSlide.vision?.text || currentSlide.ocr_text || "Pas de texte détecté"}</p>
            </div>
          </div>
        )}
      </div>
      <div className="card flex h-[70vh] flex-col lg:col-span-2">
        <div className="flex items-center gap-2 border-b border-line p-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input py-1.5 pl-8" placeholder="Chercher dans la transcription" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <button className={cn("btn-ghost px-2 py-1.5 text-xs", follow && "text-accent")} onClick={() => setFollow(!follow)} title="Suivre la lecture">
            Suivre
          </button>
        </div>
        {uncertain > 0 && (
          <div className="flex items-center gap-2 border-b border-line bg-warn/10 px-3 py-2 text-xs">
            <AlertTriangle size={13} className="text-warn" />
            {uncertain} passage{uncertain > 1 ? "s" : ""} peu fiable{uncertain > 1 ? "s" : ""} (soulignés) : clique sur le crayon pour corriger.
          </div>
        )}
        <div ref={list} className="flex-1 space-y-0.5 overflow-y-auto p-2" onWheel={() => setFollow(false)}>
          {filtered.map(([s, i]) => (
            <div key={s.id} data-i={i}
              className={cn("group flex gap-3 rounded-lg px-2 py-1.5 text-sm transition", i === active ? "bg-accent/10" : "hover:bg-subtle")}>
              <button onClick={() => go(s.start)} className="w-12 shrink-0 pt-0.5 text-left font-mono text-xs text-muted hover:text-accent">{hms(s.start)}</button>
              {editing === s.id ? (
                <div className="flex flex-1 gap-1">
                  <input autoFocus className="input py-1" value={draft} onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") save(s); if (e.key === "Escape") setEditing(null); }} />
                  <button className="btn-ghost px-2" onClick={() => save(s)}><Check size={14} /></button>
                </div>
              ) : (
                <>
                  <span onClick={() => go(s.start)} className={cn("flex-1 cursor-pointer leading-relaxed",
                    s.uncertain && "underline decoration-warn decoration-wavy decoration-1 underline-offset-4")}>{s.text}</span>
                  <button onClick={() => { setEditing(s.id); setDraft(s.text); }} className="invisible px-1 text-muted hover:text-fg group-hover:visible" title="Corriger">
                    <Pencil size={12} />
                  </button>
                </>
              )}
            </div>
          ))}
          {segments.length === 0 && <p className="p-6 text-center text-sm text-muted">La transcription apparaîtra ici.</p>}
        </div>
      </div>
    </div>
  );
}
