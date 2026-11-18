export function hms(seconds: number | null | undefined): string {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

export function duration(seconds: number | null | undefined): string {
  const s = Math.round(seconds || 0);
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`;
}

export function eta(seconds: number | null | undefined): string | null {
  if (seconds == null) return null;
  if (seconds < 60) return "moins d'une minute";
  return `environ ${duration(seconds)}`;
}

export function relDate(ts: number): string {
  const d = new Date(ts * 1000);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  return d.toLocaleDateString("fr-BE", { day: "numeric", month: "short", year: "numeric" });
}

export function euro(n: number): string {
  return n.toLocaleString("fr-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
}

export function usd(n: number): string {
  return n < 0.01 && n > 0 ? "< 0,01 $" : n.toLocaleString("fr-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " $";
}

export function pct(n: number): string {
  return `${Math.round(n * 100)} %`;
}

/** Mélange déterministe si une graine est fournie (Fisher-Yates). */
export function shuffle<T>(arr: T[], seed = Math.random()): T[] {
  const a = [...arr];
  let s = Math.floor(seed * 2 ** 31) || 1;
  const rand = () => ((s = (s * 48271) % 2147483647) / 2147483647);
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** Index du segment de transcription en cours de lecture (recherche dichotomique). */
export function activeSegment(starts: number[], t: number): number {
  let lo = 0, hi = starts.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (starts[mid] <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return ans;
}

export function parseNumber(v: string): number {
  return Number(String(v).replace(/\s/g, "").replace(",", "."));
}
