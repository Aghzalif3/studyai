"use client";

import { useState, type ReactNode } from "react";
import { Notice, PageHeader, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { euro, parseNumber } from "@/lib/format";

type T = "invoice" | "vat" | "dep" | "interest" | "calc";

function Field({ label, value, onChange, suffix }: { label: string; value: string; onChange: (v: string) => void; suffix?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <div className="relative">
        <input className="input pr-10" inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted">{suffix}</span>}
      </div>
    </label>
  );
}

function Panel({ form, result, onRun, error }: { form: ReactNode; result: ReactNode; onRun: () => void; error?: string }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="card space-y-4 p-5">{form}<button className="btn-primary w-full" onClick={onRun}>Calculer</button>{error && <Notice tone="bad">{error}</Notice>}</div>
      <div className="card p-5">{result || <p className="text-sm text-muted">Le détail du calcul s'affichera ici, étape par étape.</p>}</div>
    </div>
  );
}

const rate = (v: string) => parseNumber(v) / 100;

type StepsResult = { steps: { label: string; expression: string; value: number }[] };

export default function Tools() {
  const [t, setT] = useState<T>("invoice");
  const [err, setErr] = useState<string>();
  const [res, setRes] = useState<unknown>(null);
  const [f, setF] = useState<Record<string, string>>({
    gross: "1000", discount: "10", rebate: "0", cash: "2", vat: "21", transport: "0",
    ttc: "121", cost: "10000", years: "5", residual: "0", prorata: "100", method: "lineaire",
    capital: "10000", irate: "5", days: "90", iyears: "2", kind: "simple", expr: "1250 * 21 %",
  });
  const set = (k: string) => (v: string) => setF({ ...f, [k]: v });
  const run = async (name: string, body: unknown) => {
    setErr(undefined);
    try { setRes(await api.tool(name, body)); } catch (e) { setErr((e as Error).message); setRes(null); }
  };
  const change = (x: T) => { setT(x); setRes(null); setErr(undefined); };

  const stepsView = (r: StepsResult) => (
    <ol className="space-y-2 text-sm">
      {r.steps.map((s, i) => (
        <li key={i} className="flex items-baseline justify-between gap-3 border-b border-line/60 pb-2">
          <span><span className="font-medium">{s.label}</span><span className="ml-2 font-mono text-xs text-muted">{s.expression}</span></span>
          <span className="font-mono">{euro(s.value)}</span>
        </li>
      ))}
    </ol>
  );

  return (
    <>
      <PageHeader title="Outils compta" subtitle="Calculs exacts (droit belge), détaillés étape par étape pour vérifier tes exercices." />
      <div className="mb-5"><Tabs<T> value={t} onChange={change} tabs={[
        { id: "invoice", label: "Facture (RRR, escompte, TVA)" }, { id: "vat", label: "TVA depuis TVAC" },
        { id: "dep", label: "Amortissements" }, { id: "interest", label: "Intérêts" }, { id: "calc", label: "Calculatrice" },
      ]} /></div>

      {t === "invoice" && <Panel error={err}
        onRun={() => run("invoice", { gross: parseNumber(f.gross), discount_rate: rate(f.discount), rebate_rate: rate(f.rebate), cash_discount_rate: rate(f.cash), vat_rate: rate(f.vat), transport: parseNumber(f.transport) })}
        form={<div className="grid grid-cols-2 gap-3">
          <Field label="Prix brut HTVA" value={f.gross} onChange={set("gross")} suffix="€" />
          <Field label="Frais de transport" value={f.transport} onChange={set("transport")} suffix="€" />
          <Field label="Remise" value={f.discount} onChange={set("discount")} suffix="%" />
          <Field label="Rabais" value={f.rebate} onChange={set("rebate")} suffix="%" />
          <Field label="Escompte" value={f.cash} onChange={set("cash")} suffix="%" />
          <Field label="Taux de TVA" value={f.vat} onChange={set("vat")} suffix="%" />
          <p className="col-span-2 text-xs text-muted">En Belgique, la TVA est calculée sur la base diminuée de l'escompte, même si le client ne le prend pas.</p>
        </div>}
        result={res ? stepsView(res as StepsResult) : null} />}

      {t === "vat" && <Panel error={err} onRun={() => run("vat", { ttc: parseNumber(f.ttc), vat_rate: rate(f.vat) })}
        form={<div className="grid grid-cols-2 gap-3"><Field label="Montant TVAC" value={f.ttc} onChange={set("ttc")} suffix="€" /><Field label="Taux de TVA" value={f.vat} onChange={set("vat")} suffix="%" /></div>}
        result={res ? (() => { const r = res as { ht: number; vat: number; ttc: number }; return (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>HTVA = {f.ttc} / (1 + {f.vat} %)</span><b className="font-mono">{euro(r.ht)}</b></div>
            <div className="flex justify-between"><span>TVA</span><b className="font-mono">{euro(r.vat)}</b></div>
            <div className="flex justify-between border-t border-line pt-2"><span>TVAC</span><b className="font-mono">{euro(r.ttc)}</b></div>
          </div>); })() : null} />}

      {t === "dep" && <Panel error={err}
        onRun={() => run("depreciation", { cost: parseNumber(f.cost), years: Math.round(parseNumber(f.years)), residual: parseNumber(f.residual), method: f.method, first_year_prorata: rate(f.prorata) })}
        form={<div className="grid grid-cols-2 gap-3">
          <Field label="Valeur d'acquisition" value={f.cost} onChange={set("cost")} suffix="€" />
          <Field label="Durée" value={f.years} onChange={set("years")} suffix="ans" />
          <Field label="Valeur résiduelle" value={f.residual} onChange={set("residual")} suffix="€" />
          <Field label="Prorata 1re année" value={f.prorata} onChange={set("prorata")} suffix="%" />
          <label className="col-span-2"><span className="label">Méthode</span>
            <select className="input" value={f.method} onChange={(e) => set("method")(e.target.value)}>
              <option value="lineaire">Linéaire</option><option value="degressif">Dégressif (double du linéaire, max 40 %)</option>
            </select></label>
        </div>}
        result={res ? (() => { const r = res as { rate: number; rows: { year: number; annuity: number; cumulated: number; book_value: number }[] }; return (
          <div className="overflow-x-auto text-sm">
            <div className="mb-2 text-xs text-muted">Taux : {(r.rate * 100).toFixed(2)} %</div>
            <table className="w-full"><thead><tr className="border-b border-line text-left text-xs text-muted"><th className="py-1">Année</th><th className="text-right">Annuité</th><th className="text-right">Cumul</th><th className="text-right">Valeur comptable</th></tr></thead>
              <tbody>{r.rows.map((x) => <tr key={x.year} className="border-b border-line/50 font-mono"><td className="py-1.5 font-sans">{x.year}</td><td className="text-right">{euro(x.annuity)}</td><td className="text-right">{euro(x.cumulated)}</td><td className="text-right">{euro(x.book_value)}</td></tr>)}</tbody>
            </table>
          </div>); })() : null} />}

      {t === "interest" && <Panel error={err}
        onRun={() => run("interest", { capital: parseNumber(f.capital), annual_rate: rate(f.irate), days: Math.round(parseNumber(f.days)), years: parseNumber(f.iyears), kind: f.kind })}
        form={<div className="grid grid-cols-2 gap-3">
          <label className="col-span-2"><span className="label">Type</span>
            <select className="input" value={f.kind} onChange={(e) => set("kind")(e.target.value)}><option value="simple">Intérêts simples (jours / 365)</option><option value="compose">Intérêts composés (années)</option></select></label>
          <Field label="Capital" value={f.capital} onChange={set("capital")} suffix="€" />
          <Field label="Taux annuel" value={f.irate} onChange={set("irate")} suffix="%" />
          {f.kind === "simple" ? <Field label="Durée" value={f.days} onChange={set("days")} suffix="jours" /> : <Field label="Durée" value={f.iyears} onChange={set("iyears")} suffix="ans" />}
        </div>}
        result={res ? (() => { const r = res as { interest: number; expression: string; total?: number; final?: number }; return (
          <div className="space-y-2 text-sm">
            <div className="font-mono text-xs text-muted">{r.expression}</div>
            <div className="flex justify-between"><span>Intérêts</span><b className="font-mono">{euro(r.interest)}</b></div>
            <div className="flex justify-between border-t border-line pt-2"><span>Capital final</span><b className="font-mono">{euro(r.total ?? r.final ?? 0)}</b></div>
          </div>); })() : null} />}

      {t === "calc" && <Panel error={err} onRun={() => run("calc", { expression: f.expr })}
        form={<div><Field label="Expression (ex : 1500 × 0,9 × 1,21)" value={f.expr} onChange={set("expr")} /><p className="mt-2 text-xs text-muted">Accepte la virgule décimale, ×, ÷, % et les espaces dans les milliers.</p></div>}
        result={res ? <div className="text-3xl font-semibold tracking-tight">{(res as { result: number }).result.toLocaleString("fr-BE", { maximumFractionDigits: 6 })}</div> : null} />}
    </>
  );
}
