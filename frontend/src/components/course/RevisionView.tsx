"use client";

import { Printer } from "lucide-react";
import { useState } from "react";
import { type Flashcard, type Revision } from "@/lib/api";
import { Md, Tabs, useLoad } from "../ui";
import { api } from "@/lib/api";
import { Exam } from "./Exam";
import { ExerciseCard } from "./Exercises";
import { FlashcardDeck } from "./Flashcards";
import { Quiz } from "./Quiz";

type Sub = "sheets" | "cards" | "qcm" | "exam" | "exercises";

export function RevisionView({ courseId, rev, onSeek }: { courseId: string; rev: Revision; onSeek: (t: number) => void }) {
  const [sub, setSub] = useState<Sub>("sheets");
  const [allCards, setAllCards] = useState(false);
  const cards = useLoad<Flashcard[]>(() => api.flashcards(courseId, !allCards), [courseId, allCards]);
  return (
    <div className="space-y-5">
      <Tabs<Sub> value={sub} onChange={setSub} tabs={[
        { id: "sheets", label: `Fiches (${rev.sheets.length})` },
        { id: "cards", label: `Flashcards (${rev.flashcards.length})` },
        { id: "qcm", label: `QCM (${rev.mcq.length})` },
        { id: "exam", label: "Examen blanc" },
        { id: "exercises", label: `Exercices (${rev.exercises.length})` },
      ]} />
      {sub === "sheets" && (
        <div className="space-y-4">
          <div className="no-print flex justify-end"><button className="btn-outline" onClick={() => window.print()}><Printer size={15} />Imprimer les fiches</button></div>
          {rev.sheets.map((s, i) => (
            <section key={i} className="card p-6 print-break animate-in">
              <h3 className="mb-2 text-lg font-semibold tracking-tight">{s.title}</h3>
              <Md>{s.content}</Md>
            </section>
          ))}
        </div>
      )}
      {sub === "cards" && (
        <div>
          <div className="mb-4 flex justify-center gap-2 text-sm">
            <button className={!allCards ? "btn-outline border-accent" : "btn-ghost"} onClick={() => setAllCards(false)}>Cartes dues</button>
            <button className={allCards ? "btn-outline border-accent" : "btn-ghost"} onClick={() => setAllCards(true)}>Toutes les cartes</button>
          </div>
          {cards.data && <FlashcardDeck cards={cards.data} onDone={cards.reload} />}
        </div>
      )}
      {sub === "qcm" && <Quiz courseId={courseId} questions={rev.mcq} onSeek={onSeek} />}
      {sub === "exam" && <Exam courseId={courseId} rev={rev} />}
      {sub === "exercises" && <div className="space-y-4">{rev.exercises.map((e, i) => <ExerciseCard key={i} ex={e} index={i + 1} />)}</div>}
    </div>
  );
}
