"use client";

import { useEffect, useRef } from "react";
import { slideUrl, type Slide } from "@/lib/api";
import { Md } from "../ui";
import { TimeLink } from "./Summary";

export function SlidesView({ courseId, slides, focus, onSeek }: { courseId: string; slides: Slide[]; focus: number | null; onSeek: (t: number) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focus) ref.current?.querySelector(`#slide-${focus}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focus]);
  return (
    <div ref={ref} className="space-y-4">
      {slides.map((s) => (
        <div key={s.idx} id={`slide-${s.idx}`} className="card grid scroll-mt-6 gap-4 p-4 md:grid-cols-2 animate-in">
          <a href={slideUrl(courseId, s.idx)} target="_blank" rel="noreferrer">
            <img src={slideUrl(courseId, s.idx)} alt={`Diapositive ${s.idx}`} loading="lazy" className="w-full rounded-lg border border-line" />
          </a>
          <div className="min-w-0 text-sm">
            <div className="mb-2 flex items-center gap-2">
              <span className="font-semibold">Diapositive {s.idx}</span>
              <TimeLink t={s.ts} onSeek={onSeek} />
              <span className="chip">{s.vision ? "Analysée par Claude" : "OCR"}</span>
            </div>
            {s.vision ? (
              <div className="space-y-3">
                {s.vision.text && <p className="whitespace-pre-line">{s.vision.text}</p>}
                {s.vision.tables && <Md>{s.vision.tables}</Md>}
                {s.vision.formulas && <div className="rounded-md bg-subtle p-2 font-mono text-xs">{s.vision.formulas}</div>}
                {s.vision.figures && <p className="text-muted"><b>Figures :</b> {s.vision.figures}</p>}
              </div>
            ) : (
              <p className="whitespace-pre-line text-muted">{s.ocr_text || "Aucun texte détecté sur cette image."}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
