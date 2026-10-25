// Icon keys from bridge.py -> drawn icons (flags as SVG, since Windows has no flag emoji).
import { Check, Clock, PoundSterling, Scale, ShieldCheck, Store, Warehouse, Zap } from "lucide-react";
import { cn } from "../lib/cn";

export function Flag({ code, className }: { code: string; className?: string }) {
  const cls = cn("inline-block h-[14px] w-[21px] shrink-0 overflow-hidden rounded-[3px] shadow-[0_0_0_1px_rgba(255,255,255,0.15)]", className);
  if (code === "DE") return <svg viewBox="0 0 5 3" className={cls}><rect width="5" height="1" fill="#000" /><rect y="1" width="5" height="1" fill="#DD0000" /><rect y="2" width="5" height="1" fill="#FFCE00" /></svg>;
  if (code === "FR") return <svg viewBox="0 0 3 2" className={cls}><rect width="1" height="2" fill="#0055A4" /><rect x="1" width="1" height="2" fill="#fff" /><rect x="2" width="1" height="2" fill="#EF4135" /></svg>;
  if (code === "NL") return <svg viewBox="0 0 9 6" className={cls}><rect width="9" height="2" fill="#AE1C28" /><rect y="2" width="9" height="2" fill="#fff" /><rect y="4" width="9" height="2" fill="#21468B" /></svg>;
  if (code === "GB") return (
    <svg viewBox="0 0 60 30" className={cls}>
      <rect width="60" height="30" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="2.5" />
      <path d="M30,0 V30 M0,15 H60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 V30 M0,15 H60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  );
  return null;
}

const MAP = { pound: PoundSterling, zap: Zap, shield: ShieldCheck, scale: Scale, warehouse: Warehouse, store: Store, check: Check, clock: Clock };

export function OptionIcon({ name }: { name: string }) {
  if (!name) return null;
  if (name.startsWith("flag-")) return <Flag code={name.slice(5)} className="h-[18px] w-[27px]" />;
  const I = MAP[name as keyof typeof MAP];
  return I ? <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.05]"><I className="h-4.5 w-4.5 text-cyan" /></span> : null;
}
