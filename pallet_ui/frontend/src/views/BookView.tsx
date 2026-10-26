// Book a shipment: hero, conversation with tap-to-answer controls, live booking card, results.
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ArrowUp, BadgeCheck, FileSpreadsheet, RotateCcw, ShieldCheck, Sparkles, Truck } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Button, Reveal, Skeleton } from "../components/fx";
import { cn, EASE } from "../lib/cn";
import type { ChatView, Message } from "../types";
import { AskControl, type AskCtx } from "./Ask";
import { AssistantAvatar, RevealText, StepRail, TypingDots } from "./ChatParts";
import { LiveCard } from "./LiveCard";
import { Bold, Results } from "./Results";

const Hero3D = lazy(() => import("../components/Hero3D"));

export function Hero({ onStart, onFile, ai }: { onStart: () => void; onFile: () => void; ai: boolean }) {
  const [wide, setWide] = useState(() => window.matchMedia("(min-width: 900px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 900px)");
    const f = () => setWide(window.innerWidth >= 900);
    f();  // the iframe may have been resized between first render and now
    mq.addEventListener("change", f);
    window.addEventListener("resize", f);
    return () => { mq.removeEventListener("change", f); window.removeEventListener("resize", f); };
  }, []);
  const words = ["Ship", "pallets", "to", "Europe,"];
  return (
    <section className="relative grid items-center gap-6 pb-6 pt-28 sm:pt-32 lg:grid-cols-[1.1fr_0.9fr]">
      <div>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12.5px] text-muted">
          <Sparkles className="h-3.5 w-3.5 text-cyan" /> UK → Germany · France · Netherlands
        </motion.div>
        <h1 className="text-[40px] font-semibold leading-[1.02] tracking-[-0.045em] sm:text-[60px]">
          {words.map((w, i) => (
            <motion.span key={i} className="mr-[0.22em] inline-block" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.07, duration: 0.8, ease: EASE }}>{w}</motion.span>
          ))}
          <br />
          <motion.span className="text-gradient inline-block" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.42, duration: 0.9, ease: EASE }}>minus the paperwork surprises.</motion.span>
        </h1>
        <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6, duration: 0.7, ease: EASE }}
          className="mt-5 max-w-[560px] text-[16.5px] leading-relaxed text-muted">
          Tell us what you're sending. We check it against 10 customs and carrier rules, tell you exactly what to fix, and pick the right truck for you.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.72, duration: 0.7, ease: EASE }} className="mt-7 flex flex-wrap gap-3">
          <Button size="lg" glow onClick={onStart}>Start a booking <ArrowRight className="h-4.5 w-4.5" /></Button>
          <Button size="lg" variant="ghost" onClick={onFile}><FileSpreadsheet className="h-4.5 w-4.5" /> Check a spreadsheet</Button>
        </motion.div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9, duration: 0.8 }} className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-muted">
          <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-good" /> 10 checks before it leaves</span>
          <span className="flex items-center gap-2"><Truck className="h-4 w-4 text-cyan" /> 3 carriers compared</span>
          <span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-violet" /> {ai ? "Type in plain English" : "Tap-to-answer questions"}</span>
        </motion.div>
      </div>
      {wide && (
        <motion.div initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3, duration: 1.2, ease: EASE }} className="relative h-[420px]">
          <div className="absolute inset-0 bg-[radial-gradient(circle,rgba(139,92,246,0.28)_0%,transparent_60%)]" />
          <Suspense fallback={<div className="grid h-full place-items-center"><Skeleton className="h-48 w-48 rounded-full" /></div>}><Hero3D /></Suspense>
        </motion.div>
      )}
    </section>
  );
}

function Bubble({ m, i, latest }: { m: Message; i: number; latest?: boolean }) {
  const me = m.role === "user";
  return (
    <motion.div initial={me ? { opacity: 0, x: 24, scale: 0.96 } : { opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: Math.min(i, 2) * 0.03 }}
      className={cn("flex items-end gap-2.5", me && "justify-end")}>
      {!me && <AssistantAvatar size={30} still={!latest} />}
      <div className={cn("relative max-w-[86%] whitespace-pre-line rounded-[22px] px-4 py-3 text-[14.5px] leading-relaxed",
        me ? "rounded-br-md bg-[linear-gradient(135deg,#7c3aed,#4f46e5_55%,#0e7490)] text-white shadow-[0_10px_30px_rgba(109,40,217,0.35)]"
          : "rounded-bl-md border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.075),rgba(255,255,255,0.035))] text-fg/95 shadow-[0_8px_24px_rgba(0,0,0,0.25)]")}>
        {me ? <Bold text={m.text} /> : <RevealText text={m.text} animate={!!latest} />}
        {(m.changes?.length || m.effects?.length) ? (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {m.changes?.map((c, k) => <span key={`c${k}`} className="rounded-full border border-cyan/25 bg-cyan/10 px-2 py-0.5 text-[11.5px] text-cyan-100">{c}</span>)}
            {m.effects?.map((c, k) => <span key={`e${k}`} className="rounded-full border border-violet/30 bg-violet/12 px-2 py-0.5 text-[11.5px] text-violet-100">{c}</span>)}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

export function BookView({ chat, ctx, ai, pendingText, started, onStart, onFile, onConfirm, onReset, composerRef }: {
  chat: ChatView; ctx: AskCtx; ai: boolean; pendingText: string | null; started: boolean;
  onStart: () => void; onFile: () => void; onConfirm: () => void; onReset: () => void; composerRef: React.RefObject<HTMLTextAreaElement>;
}) {
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const prevComplete = useRef(chat.complete);
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [chat.messages.length, pendingText, chat.ask?.field, chat.ask?.item_index]);
  useEffect(() => {
    if (chat.complete && !prevComplete.current) setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
    prevComplete.current = chat.complete;
  }, [chat.complete]);

  const submit = () => {
    const t = text.trim();
    if (!t || ctx.pending) return;
    ctx.send({ type: "say", text: t, label: t });
    setText("");
  };

  return (
    <div>
      <AnimatePresence initial={false}>
        {!started && <motion.div exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.5, ease: EASE }}><Hero onStart={onStart} onFile={onFile} ai={ai} /></motion.div>}
      </AnimatePresence>
      <div id="book" className={cn("grid grid-cols-1 gap-5 lg:grid-cols-[1.35fr_1fr]", started ? "pt-24 sm:pt-28" : "pt-6")}>
        <Reveal>
          <div className="glass flex flex-col rounded-3xl">
            <div className="relative overflow-hidden rounded-t-3xl border-b border-white/8">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(139,92,246,0.22),transparent_60%),radial-gradient(ellipse_at_top_right,rgba(34,211,238,0.14),transparent_55%)]" />
              <div className="relative flex items-center gap-3 px-5 py-4">
                <AssistantAvatar size={42} thinking={ctx.pending} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[16.5px] font-semibold tracking-[-0.02em]">Piper <span className="rounded-full border border-white/10 bg-white/[0.06] px-2 py-0.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-muted">Shipping assistant</span></div>
                  <div className="flex items-center gap-1.5 text-[12.5px] text-muted">
                    <span className="relative inline-flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-good opacity-60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-good" /></span>
                    {ctx.pending ? "Typing…" : ai ? "Online · type freely or tap the answers" : "Online · tap the answers as we go"}
                  </div>
                </div>
                {started && <button onClick={onReset} className="tile flex items-center gap-1.5 rounded-xl border border-white/10 px-2.5 py-1.5 text-[12.5px] text-muted hover:text-fg"><RotateCcw className="h-3.5 w-3.5" /> Start over</button>}
              </div>
              {started && <StepRail chat={chat} />}
            </div>
            <div ref={listRef} className="scroll-thin relative max-h-[56vh] min-h-[280px] space-y-4 overflow-y-auto px-4 py-5 sm:px-5">
              <div aria-hidden className="pointer-events-none sticky top-0 -mb-[280px] h-[280px] opacity-60 [background:radial-gradient(400px_200px_at_20%_0%,rgba(139,92,246,0.10),transparent),radial-gradient(300px_180px_at_90%_30%,rgba(34,211,238,0.07),transparent)]" />
              {chat.messages.map((m, i) => <Bubble key={i} m={m} i={i} latest={i === chat.messages.length - 1 && m.role === "assistant" && i > 0} />)}
              {pendingText && <Bubble m={{ role: "user", text: pendingText }} i={0} />}
              <AnimatePresence>{ctx.pending && ["say", "answer", "item", "edit", "remove_item", "fix"].includes(ctx.pendingType ?? "") && <TypingDots />}</AnimatePresence>
            </div>
            <div className="space-y-3 border-t border-white/8 p-4 sm:p-5">
              <AnimatePresence mode="wait">
                {chat.ask && !ctx.pending && <AskControl key={`${chat.ask.field}${chat.ask.item_index ?? ""}`} ask={chat.ask} ctx={ctx} items={chat.items} />}
              </AnimatePresence>
              <div className="group/composer relative flex items-end gap-2 rounded-2xl border border-white/10 bg-white/[0.045] p-1.5 pl-4 transition-shadow focus-within:border-transparent focus-within:shadow-[0_0_0_1px_rgba(139,92,246,0.6),0_0_32px_rgba(139,92,246,0.25)]">
                <textarea ref={composerRef} rows={1} value={text} maxLength={ctx.limits.message_max} onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
                  placeholder={ai ? (started ? "Type anything, e.g. \"make it 4 pallets\" or \"drop the candles\"" : "e.g. 3 pallets of mugs from London to a warehouse in Berlin next Thursday")
                    : (chat.ask ? "Or type your answer…" : "Tap a detail on the right to change it")}
                  className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[15px] outline-none placeholder:text-faint" />
                <Button size="sm" className="h-10 w-10 rounded-xl px-0" disabled={!text.trim() || ctx.pending} onClick={submit} aria-label="Send"><ArrowUp className="h-4.5 w-4.5" /></Button>
              </div>
              {text.length > ctx.limits.message_max * 0.8 && (
                <div className={cn("-mt-1 text-right text-[12px]", text.length >= ctx.limits.message_max ? "text-warn" : "text-faint")}>
                  {text.length.toLocaleString()} / {ctx.limits.message_max.toLocaleString()} characters (limit)
                </div>
              )}
              {!started && ai && (
                <div className="flex flex-wrap gap-2">
                  {["I need to send some mugs to Germany next week", "4 pallets of candles to a shop in Paris, cheapest"].map((ex) => (
                    <button key={ex} onClick={() => ctx.send({ type: "say", text: ex, label: ex })} className="press rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[12.5px] text-muted hover:text-fg">“{ex}”</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Reveal>
        <Reveal i={1}><div className="lg:sticky lg:top-24"><LiveCard chat={chat} ctx={ctx} /></div></Reveal>
      </div>

      <div ref={resultsRef} className="scroll-mt-24">
        <AnimatePresence>
          {chat.complete && chat.result && (
            <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.7, ease: EASE }} className="mt-14">
              <div className="mb-6">
                <h2 className="text-[30px] font-semibold tracking-[-0.035em] sm:text-[36px]"><span className="text-gradient">Your pre-flight check</span></h2>
                <p className="mt-1 text-[14.5px] text-muted">Everything below updates the moment you change something above.</p>
              </div>
              <Results r={chat.result} onFix={(a) => ctx.send({ type: "fix", scope: "chat", action: a })} pending={ctx.pending}
                onEvent={ctx.send} scope="chat" pendingType={ctx.pendingType}
                showConfirmation={chat.confirmed} confirmed={chat.confirmed} />
              {!chat.confirmed && (
                <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6, ease: EASE }}
                  className="glass mt-10 flex flex-col items-start justify-between gap-4 rounded-3xl p-6 sm:flex-row sm:items-center">
                  <div>
                    <div className="text-[18px] font-semibold tracking-[-0.02em]">{chat.result.status === "Blocked" ? "Want to see where this stands?" : "Happy with this?"}</div>
                    <div className="text-[14px] text-muted">{chat.result.status === "Blocked" ? "You'll see what's still stopping it and the provisional carrier." : "Confirm to get your booking summary and next steps. You can still change things afterwards."}</div>
                  </div>
                  <Button size="lg" glow onClick={onConfirm} disabled={ctx.pending}><BadgeCheck className="h-5 w-5" /> Confirm booking</Button>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
