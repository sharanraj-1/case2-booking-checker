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

/** Smoothly scroll an element into view inside whatever scrolls it, then pulse a highlight ring. */
export function focusEl(id: string) {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
  return true;
}

/** Ref callback: focus a new input and glide it into view, instead of the browser snapping the page to it. */
export function softFocus(el: HTMLElement | null) {
  if (!el) return;
  requestAnimationFrame(() => {
    el.focus({ preventScroll: true });
    const r = el.getBoundingClientRect();  // leave room for the button and limit under it
    if (r.top < 90 || r.bottom + 150 > window.innerHeight) el.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
