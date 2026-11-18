"use client";

import { Layers } from "lucide-react";
import { useState } from "react";
import { FlashcardDeck } from "@/components/course/Flashcards";
import { Empty, PageHeader, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

export default function ReviewPage() {
  const [course, setCourse] = useState("");
  const courses = useLoad(api.courses, []);
  const cards = useLoad(() => api.flashcards(course || undefined, true), [course]);
  const names = Object.fromEntries((courses.data || []).map((c) => [c.id, c.title]));
  const withCards = (courses.data || []).filter((c) => c.counts.flashcards > 0);
  return (
    <>
      <PageHeader title="Mode révision" subtitle="Les cartes dues aujourd'hui, tous cours confondus (répétition espacée)."
        actions={withCards.length > 1 ? (
          <select className="input w-64" value={course} onChange={(e) => setCourse(e.target.value)}>
            <option value="">Tous les cours</option>
            {withCards.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        ) : undefined} />
      {withCards.length === 0 && courses.data ? (
        <Empty icon={<Layers size={20} />} title="Pas encore de flashcards">Elles sont créées automatiquement quand un cours est analysé.</Empty>
      ) : cards.data ? (
        <FlashcardDeck cards={cards.data} onDone={cards.reload} showCourse={names} />
      ) : null}
      <p className="mt-8 text-center text-xs text-muted">Raccourcis : Espace pour retourner la carte, 1 à 4 pour répondre.</p>
    </>
  );
}
