"use client";

import { FileAudio, Film, Image as ImageIcon, Clock } from "lucide-react";
import Link from "next/link";
import type { Course } from "@/lib/api";
import { duration, eta, relDate } from "@/lib/format";
import { Progress, StatusBadge } from "./ui";

export function CourseCard({ c }: { c: Course }) {
  const Icon = c.has_video ? Film : FileAudio;
  return (
    <Link href={`/course?id=${c.id}`} className="card group block p-4 transition hover:-translate-y-0.5 hover:shadow-pop animate-in">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-subtle text-muted group-hover:text-accent">
            <Icon size={17} />
          </div>
          <div className="min-w-0">
            <div className="truncate font-medium">{c.title}</div>
            <div className="text-xs text-muted">{relDate(c.created_at)}</div>
          </div>
        </div>
        <StatusBadge status={c.status} />
      </div>
      {(c.status === "running" || c.status === "queued") && (
        <div className="mt-4">
          <div className="mb-1.5 flex justify-between text-xs text-muted">
            <span>{c.status === "queued" ? "En attente" : c.stage_label || "Préparation"}</span>
            <span>{Math.round(c.progress * 100)} %</span>
          </div>
          <Progress value={c.progress} />
          {c.eta_seconds != null && c.status === "running" && <div className="mt-1.5 text-xs text-muted">Reste {eta(c.eta_seconds)}</div>}
        </div>
      )}
      {c.status === "error" && <p className="mt-3 line-clamp-2 text-xs text-bad">{c.error}</p>}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {c.duration ? <span className="chip"><Clock size={11} />{duration(c.duration)}</span> : null}
        {c.counts.slides > 0 && <span className="chip"><ImageIcon size={11} />{c.counts.slides} diapos</span>}
        {c.analysis_kinds.length > 0 && <span className="chip">Analysé</span>}
        {c.steps.analysis === "no_key" && <span className="chip">Transcription seule</span>}
      </div>
    </Link>
  );
}
