"use client";

import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

export function cn(...c: (string | number | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Md({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("prose-study", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children || ""}</ReactMarkdown>
    </div>
  );
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-subtle", className)}>
      <div className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out"
        style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} />;
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4 animate-in">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-14 text-center animate-in">
      <div className="mb-3 rounded-xl bg-subtle p-3 text-muted">{icon}</div>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "bad" | "ok"; children: ReactNode }) {
  const styles = {
    info: "border-accent/30 bg-accent/5",
    warn: "border-warn/40 bg-warn/10",
    bad: "border-bad/40 bg-bad/10",
    ok: "border-ok/40 bg-ok/10",
  }[tone];
  const Icon = tone === "ok" ? CheckCircle2 : AlertTriangle;
  return (
    <div className={cn("flex gap-3 rounded-lg border px-4 py-3 text-sm", styles)}>
      {tone !== "info" && <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone === "ok" ? "text-ok" : tone === "warn" ? "text-warn" : "text-bad")} />}
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted">
        {label}
        {icon}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cn("relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition", checked ? "bg-accent" : "bg-line")}>
        <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      <span className="text-sm">
        <span className="font-medium">{label}</span>
        {hint && <span className="block text-muted">{hint}</span>}
      </span>
    </label>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="no-print flex flex-wrap gap-1 rounded-lg border border-line bg-panel p-1">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)} className={cn("tab flex items-center gap-1.5", value === t.id && "tab-active")}>
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}

/** Charge une ressource et la recharge toutes les `interval` ms tant que `active` est vrai. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[], opts: { interval?: number; active?: (d: T | undefined) => boolean } = {}) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    try {
      const d = await fnRef.current();
      setData(d);
      setError(undefined);
      return d;
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const d = await reload();
      if (stop) return;
      if (opts.interval && (!opts.active || opts.active(d))) timer = setTimeout(tick, opts.interval);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, reload, setData };
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    queued: ["En attente", "bg-subtle text-muted"],
    running: ["En cours", "bg-accent/10 text-accent"],
    done: ["Prêt", "bg-ok/10 text-ok"],
    error: ["Erreur", "bg-bad/10 text-bad"],
    cancelled: ["Annulé", "bg-subtle text-muted"],
  };
  const [label, cls] = map[status] || [status, "bg-subtle text-muted"];
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", cls)}>
    {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
    {label}
  </span>;
}
