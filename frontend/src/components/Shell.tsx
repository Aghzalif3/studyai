"use client";

import { BarChart3, BookOpen, Calculator, GraduationCap, LayoutDashboard, Moon, Settings, Sun, Upload, Layers } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "./ui";

const NAV = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/import", label: "Importer un cours", icon: Upload },
  { href: "/library", label: "Bibliothèque", icon: BookOpen },
  { href: "/review", label: "Mode révision", icon: Layers },
  { href: "/results", label: "Mes résultats", icon: BarChart3 },
  { href: "/tools", label: "Outils compta", icon: Calculator },
  { href: "/settings", label: "Réglages", icon: Settings },
];

type Theme = "light" | "dark" | "system";

function applyTheme(t: Theme) {
  const dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [theme, setTheme] = useState<Theme>("system");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let t: Theme = "system";
    try { t = (localStorage.getItem("studyai-theme") as Theme) || "system"; } catch {}
    setTheme(t);
    applyTheme(t);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme((localStorage.getItem("studyai-theme") as Theme) || "system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => setOpen(false), [path]);

  const cycle = () => {
    const next: Theme = document.documentElement.classList.contains("dark") ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem("studyai-theme", next); } catch {}
    applyTheme(next);
  };

  return (
    <div className="flex min-h-screen">
      <aside className={cn(
        "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-panel/80 backdrop-blur-xl transition-transform md:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      )}>
        <Link href="/" className="flex items-center gap-2.5 px-5 pb-6 pt-6">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-fuchsia-500 text-white shadow-card">
            <GraduationCap className="h-4.5 w-4.5" size={18} />
          </div>
          <div>
            <div className="text-[15px] font-semibold leading-tight tracking-tight">StudyAI</div>
            <div className="text-[11px] text-muted">Assistant de cours</div>
          </div>
        </Link>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href) || (href === "/library" && path.startsWith("/course"));
            return (
              <Link key={href} href={href} className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                active ? "bg-subtle font-medium text-fg" : "text-muted hover:bg-subtle/60 hover:text-fg",
              )}>
                <Icon size={16} className={active ? "text-accent" : ""} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-line p-3">
          <button onClick={cycle} className="btn-ghost w-full justify-start text-muted" title={`Thème : ${theme}`}>
            <Sun size={16} className="hidden dark:block" />
            <Moon size={16} className="dark:hidden" />
            <span className="dark:hidden">Mode sombre</span>
            <span className="hidden dark:inline">Mode clair</span>
          </button>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col md:pl-60">
        <header className="no-print sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-bg/80 px-4 py-3 backdrop-blur md:hidden">
          <button className="btn-ghost px-2" onClick={() => setOpen(true)} aria-label="Menu">☰</button>
          <span className="font-semibold">StudyAI</span>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 md:px-10 md:py-10">{children}</main>
      </div>
    </div>
  );
}
