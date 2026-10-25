import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const EASE = [0.16, 1, 0.3, 1] as const;

/** Render **bold** segments from the Python text without using HTML. */
export function boldSegments(text: string): { text: string; bold: boolean }[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((s) =>
    s.startsWith("**") && s.endsWith("**") ? { text: s.slice(2, -2), bold: true } : { text: s, bold: false });
}

export function toDDMMYYYY(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

export function toISO(ddmmyyyy: string | null | undefined): string {
  if (!ddmmyyyy) return "";
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(String(ddmmyyyy));
  return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
}

export function addDays(ddmmyyyy: string, days: number): Date {
  const [d, m, y] = ddmmyyyy.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt;
}

export function fmt(dt: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(dt.getUTCDate())}-${p(dt.getUTCMonth() + 1)}-${dt.getUTCFullYear()}`;
}

export function niceDate(ddmmyyyy: string | null | undefined): string {
  if (!ddmmyyyy) return "—";
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(ddmmyyyy);
  if (!m) return ddmmyyyy;
  const dt = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
  return dt.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}
