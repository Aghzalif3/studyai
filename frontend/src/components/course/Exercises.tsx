"use client";

import { AlertTriangle, CheckCircle2, ChevronDown } from "lucide-react";
import { useState } from "react";
import type { Exercise } from "@/lib/api";
import { cn, Md } from "../ui";

const n2 = (n: number) => n.toLocaleString("fr-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function ExerciseCard({ ex, index, startOpen = false }: { ex: Exercise; index: number; startOpen?: boolean }) {
  const [open, setOpen] = useState(startOpen);
  const v = ex.verification;
  return (
    <div className="card p-5 animate-in">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-accent/10 text-xs font-semibold text-accent">{index}</span>
        <h3 className="font-semibold">{ex.title}</h3>
        <span className="chip">{ex.from_course ? "Fait en cours" : "Nouvel exercice"}</span>
        {ex.notion && <span className="chip">{ex.notion}</span>}
      </div>
      <Md>{ex.statement}</Md>
      <button className="btn-outline mt-4" onClick={() => setOpen(!open)}>
        <ChevronDown size={15} className={cn("transition", open && "rotate-180")} />{open ? "Masquer la correction" : "Voir la correction"}
      </button>
      {open && (
        <div className="mt-5 space-y-4 animate-in">
          {v.checked_steps > 0 && (
            <div className={cn("flex items-center gap-2 rounded-lg px-3 py-2 text-sm", v.status === "ok" ? "bg-ok/10 text-ok" : "bg-warn/10 text-warn")}>
              {v.status === "ok" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
              {v.status === "ok"
                ? `${v.checked_steps} calcul${v.checked_steps > 1 ? "s" : ""} revérifié${v.checked_steps > 1 ? "s" : ""} par StudyAI : tout est juste.`
                : `${v.errors} problème${v.errors > 1 ? "s" : ""} détecté${v.errors > 1 ? "s" : ""} par la vérification automatique : regarde les étapes signalées.`}
            </div>
          )}
          <ol className="space-y-3">
            {ex.steps.map((s, i) => (
              <li key={i} className="flex gap-3">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-subtle text-[11px] font-medium">{i + 1}</span>
                <div className="flex-1 text-sm">
                  <p>{s.explanation}</p>
                  {s.expression && (
                    <div className={cn("mt-1.5 inline-flex flex-wrap items-center gap-2 rounded-md px-2.5 py-1 font-mono text-[13px]",
                      s.check === "erreur" ? "bg-bad/10" : "bg-subtle")}>
                      {s.expression} = <b>{n2(s.result)}</b> {s.unit}
                      {s.check === "ok" && <CheckCircle2 size={13} className="text-ok" />}
                      {s.check === "erreur" && <span className="font-sans text-xs text-bad">✗ le bon résultat est {n2(s.computed ?? 0)}</span>}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
          {ex.journal_entries.map((e, i) => (
            <div key={i} className="overflow-x-auto">
              <div className="mb-1 text-sm font-medium">{e.label}</div>
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-xs text-muted">
                  <th className="py-1.5 pr-2">Compte</th><th className="pr-2">Libellé</th><th className="pr-2 text-right">Débit</th><th className="text-right">Crédit</th>
                </tr></thead>
                <tbody>
                  {e.lines.map((l, j) => (
                    <tr key={j} className="border-b border-line/60">
                      <td className="py-1.5 pr-2 font-mono">{l.account}</td>
                      <td className={cn("pr-2", l.credit && !l.debit && "pl-6")}>{l.credit && !l.debit ? "à " : ""}{l.account_name}</td>
                      <td className="pr-2 text-right font-mono">{l.debit ? n2(l.debit) : ""}</td>
                      <td className="text-right font-mono">{l.credit ? n2(l.credit) : ""}</td>
                    </tr>
                  ))}
                  <tr className="font-medium"><td colSpan={2} className="py-1.5 text-xs text-muted">Totaux</td>
                    <td className="pr-2 text-right font-mono">{n2(e.total_debit)}</td><td className="text-right font-mono">{n2(e.total_credit)}</td></tr>
                </tbody>
              </table>
              {e.problems.map((p, k) => <p key={k} className="mt-1 text-xs text-bad">⚠ {p}</p>)}
            </div>
          ))}
          <div className="rounded-lg border border-accent/30 bg-accent/5 p-3 text-sm"><b>Réponse : </b>{ex.final_answer}</div>
        </div>
      )}
    </div>
  );
}
