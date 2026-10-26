// Chat-only pieces: the assistant's avatar, the step tracker, typing dots and word-by-word replies.
import { motion, useReducedMotion } from "framer-motion";
import { Boxes, CalendarClock, Check, MapPin, Package, Store, UserRound } from "lucide-react";
import { boldSegments, cn, EASE } from "../lib/cn";
import type { ChatView } from "../types";

export function AssistantAvatar({ size = 36, thinking = false }: { size?: number; thinking?: boolean }) {
  const reduce = useReducedMotion();
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {!reduce && (
        <motion.span className="absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,#8b5cf6,#22d3ee,#f43f5e,#8b5cf6)]"
          animate={{ rotate: 360 }} transition={{ duration: thinking ? 1.6 : 6, repeat: Infinity, ease: "linear" }} />
      )}
      {reduce && <span className="absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,#8b5cf6,#22d3ee,#f43f5e,#8b5cf6)]" />}
      <span className="absolute inset-[2px] grid place-items-center rounded-full bg-[radial-gradient(circle_at_35%_30%,#2a2340,#0b0d12_70%)]">
        <motion.span className="block rounded-full bg-[radial-gradient(circle,#c4b5fd,#8b5cf6_55%,transparent_70%)]"
          style={{ width: size * 0.42, height: size * 0.42 }}
          animate={reduce ? undefined : { scale: thinking ? [1, 1.25, 1] : [1, 1.08, 1], opacity: [0.85, 1, 0.85] }}
          transition={{ duration: thinking ? 0.9 : 2.8, repeat: Infinity, ease: "easeInOut" }} />
      </span>
    </div>
  );
}

const STEPS = [
  { key: "route", label: "Route", icon: MapPin },
  { key: "goods", label: "Goods", icon: Package },
  { key: "plan", label: "Timing", icon: CalendarClock },
  { key: "load", label: "Load", icon: Boxes },
  { key: "delivery", label: "Delivery", icon: Store },
  { key: "you", label: "You", icon: UserRound },
];

function stepDone(chat: ChatView): Record<string, boolean> {
  const has = (k: string) => !!chat.rows.find((r) => r.key === k)?.display;
  const warehouse = chat.rows.find((r) => r.key === "dest_type")?.raw === "Warehouse";
  return {
    route: has("dest_city"),
    goods: chat.items.length > 0 && chat.items.every((i) => i.missing.length === 0),
    plan: has("priority") && has("ready_date"),
    load: has("gross_kg") && has("pallets"),
    delivery: has("dest_type") && (!warehouse || has("appointment")),
    you: has("origin_city") && has("seller"),
  };
}

export function StepRail({ chat }: { chat: ChatView }) {
  const done = stepDone(chat);
  const active = STEPS.findIndex((s) => !done[s.key]);
  return (
    <div className="relative px-5 pb-4 pt-1">
      <div className="absolute left-[38px] right-[38px] top-[17px] h-[2px] rounded-full bg-white/8" />
      <motion.div className="absolute left-[38px] top-[17px] h-[2px] rounded-full bg-gradient-to-r from-violet via-cyan to-good"
        initial={false} animate={{ width: `calc((100% - 76px) * ${active === -1 ? 1 : active / (STEPS.length - 1)})` }} transition={{ duration: 0.8, ease: EASE }} />
      <div className="relative flex justify-between">
        {STEPS.map((s, i) => {
          const isDone = done[s.key], isActive = i === active;
          return (
            <div key={s.key} className="flex w-12 flex-col items-center gap-1.5">
              <motion.div initial={false} animate={{ scale: isActive ? 1.12 : 1 }} transition={{ type: "spring", stiffness: 400, damping: 20 }}
                className={cn("relative grid h-[34px] w-[34px] place-items-center rounded-full border text-[11px] transition-colors duration-300",
                  isDone ? "border-good/50 bg-good/15 text-good" : isActive ? "border-violet/70 bg-violet/20 text-white" : "border-white/10 bg-ink-2 text-faint")}>
                {isActive && <motion.span className="absolute inset-0 rounded-full border border-violet/60" animate={{ scale: [1, 1.5], opacity: [0.7, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />}
                {isDone ? <Check className="h-4 w-4" strokeWidth={3} /> : <s.icon className="h-4 w-4" />}
              </motion.div>
              <span className={cn("text-[11px] font-medium", isDone ? "text-fg/80" : isActive ? "text-white" : "text-faint")}>{s.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TypingDots() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="flex items-end gap-2.5">
      <AssistantAvatar size={30} thinking />
      <div className="flex items-center gap-1.5 rounded-[20px] rounded-bl-md border border-white/8 bg-white/[0.05] px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <motion.span key={i} className="h-2 w-2 rounded-full bg-gradient-to-br from-violet to-cyan"
            animate={{ y: [0, -6, 0], opacity: [0.5, 1, 0.5] }} transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }} />
        ))}
        <span className="ml-1.5 text-[12px] text-faint">Piper is thinking…</span>
      </div>
    </motion.div>
  );
}

/** Reveal a reply word by word (only for the newest message), keeping **bold** parts. */
export function RevealText({ text, animate }: { text: string; animate: boolean }) {
  const reduce = useReducedMotion();
  const segs = boldSegments(text);
  if (!animate || reduce) {
    return <>{segs.map((s, i) => (s.bold ? <strong key={i} className="font-semibold text-white">{s.text}</strong> : <span key={i}>{s.text}</span>))}</>;
  }
  let w = 0;
  const step = Math.min(0.035, 1.6 / Math.max(1, text.split(/\s+/).length));
  return (
    <>
      {segs.map((s, i) => s.text.split(/(\s+)/).map((tok, j) => {
        if (/^\s+$/.test(tok)) return tok.includes("\n") ? <span key={`${i}-${j}`}>{tok}</span> : " ";
        const d = (w++) * step;
        return (
          <motion.span key={`${i}-${j}`} className={cn("inline-block", s.bold && "font-semibold text-white")}
            initial={{ opacity: 0, y: 6, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.35, delay: d, ease: EASE }}>{tok}</motion.span>
        );
      }))}
    </>
  );
}
