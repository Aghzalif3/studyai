"use client";

import { PartyPopper, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Flashcard } from "@/lib/api";
import { cn } from "../ui";

const GRADES = [
  { g: 0, label: "À revoir", key: "1", cls: "hover:border-bad hover:text-bad" },
  { g: 1, label: "Difficile", key: "2", cls: "hover:border-warn hover:text-warn" },
  { g: 2, label: "Bien", key: "3", cls: "hover:border-ok hover:text-ok" },
  { g: 3, label: "Facile", key: "4", cls: "hover:border-accent hover:text-accent" },
];

/** Révision par répétition espacée : la carte revient plus ou moins vite selon ta réponse. */
export function FlashcardDeck({ cards, onDone, showCourse }: { cards: Flashcard[]; onDone?: () => void; showCourse?: Record<string, string> }) {
  const [queue, setQueue] = useState(cards);
  const [flipped, setFlipped] = useState(false);
  const [done, setDone] = useState(0);
  useEffect(() => { setQueue(cards); setDone(0); setFlipped(false); }, [cards]);
  const card = queue[0];

  const grade = async (g: number) => {
    if (!card) return;
    await api.review(card.id, g);
    setFlipped(false);
    setDone((d) => d + 1);
    // « À revoir » : la carte revient en fin de séance
    setQueue((q) => (g === 0 ? [...q.slice(1), q[0]] : q.slice(1)));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === " ") { e.preventDefault(); setFlipped((f) => !f); }
      const g = GRADES.find((x) => x.key === e.key);
      if (g && flipped) grade(g.g);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!card) {
    return (
      <div className="card flex flex-col items-center px-6 py-14 text-center animate-in">
        <PartyPopper className="mb-3 text-accent" />
        <p className="font-medium">{done ? `Séance terminée : ${done} carte${done > 1 ? "s" : ""} revue${done > 1 ? "s" : ""}` : "Aucune carte à revoir pour l'instant"}</p>
        <p className="mt-1 text-sm text-muted">Les cartes reviendront au bon moment pour être mémorisées durablement.</p>
        {onDone && <button className="btn-outline mt-4" onClick={onDone}><RotateCcw size={14} />Recharger</button>}
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-3 flex justify-between text-xs text-muted">
        <span>{queue.length} restante{queue.length > 1 ? "s" : ""}{card.notion ? ` · ${card.notion}` : ""}</span>
        {showCourse && <span>{showCourse[card.course_id]}</span>}
      </div>
      <button onClick={() => setFlipped(!flipped)} className="block w-full [perspective:1200px]">
        <div className={cn("relative h-72 transition-transform duration-500 [transform-style:preserve-3d]", flipped && "[transform:rotateY(180deg)]")}>
          <div className="card absolute inset-0 flex items-center justify-center p-8 text-center text-lg font-medium [backface-visibility:hidden]">
            {card.front}
            <span className="absolute bottom-4 text-xs font-normal text-muted">Espace ou clic pour retourner</span>
          </div>
          <div className="card absolute inset-0 flex items-center justify-center overflow-y-auto border-accent/40 p-8 text-center [backface-visibility:hidden] [transform:rotateY(180deg)]">
            <p className="whitespace-pre-line">{card.back}</p>
          </div>
        </div>
      </button>
      <div className={cn("mt-4 grid grid-cols-4 gap-2 transition", !flipped && "pointer-events-none opacity-30")}>
        {GRADES.map((g) => (
          <button key={g.g} className={cn("btn-outline flex-col gap-0 py-2.5", g.cls)} onClick={() => grade(g.g)}>
            {g.label}<span className="text-[10px] text-muted">{g.key}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
