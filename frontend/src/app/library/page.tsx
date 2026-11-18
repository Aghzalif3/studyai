"use client";

import { BookOpen, Search, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CourseCard } from "@/components/CourseCard";
import { Empty, PageHeader, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

export default function Library() {
  const courses = useLoad(api.courses, [], { interval: 3000, active: (d) => !!d?.some((c) => c.status === "running" || c.status === "queued") });
  const [q, setQ] = useState("");
  const list = (courses.data || []).filter((c) => c.title.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHeader title="Bibliothèque" subtitle={`${courses.data?.length ?? 0} cours`}
        actions={<Link href="/import" className="btn-primary"><Upload size={16} />Importer</Link>} />
      <div className="relative mb-6 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input className="input pl-9" placeholder="Rechercher un cours…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {courses.data && list.length === 0 ? (
        <Empty icon={<BookOpen size={20} />} title={q ? "Aucun résultat" : "Ta bibliothèque est vide"}>
          {!q && "Importe un cours pour commencer."}
        </Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{list.map((c) => <CourseCard key={c.id} c={c} />)}</div>
      )}
    </>
  );
}
