// The shared results bento: status, our pick, what to fix, checks, carriers, confirmation, next steps.
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, BadgeCheck, Bot, CalendarClock, Check, ChevronDown, CircleDashed, ExternalLink, Info, Scale, ShieldCheck, Sparkles, Timer, Truck, Wand2, X, XCircle } from "lucide-react";
import { useState } from "react";
import { Button, Pill, Reveal, TiltCard } from "../components/fx";
import { boldSegments, cn, EASE, focusEl, niceDate } from "../lib/cn";
import type { CarrierOption, Finding, Result, Send, Severity, Tone } from "../types";
import { CountryRules, InvoiceChecklist, LivePrices } from "./Extras";

const TONE_TEXT: Record<Tone, string> = { red: "text-gradient-red", amber: "text-gradient-amber", green: "text-gradient-green" };
const TONE_RING: Record<Tone, string> = { red: "#f87171", amber: "#fbbf24", green: "#34d399" };
const GROUPS: { sev: Severity; title: string; sub: string; tone: "red" | "violet" | "amber" | "gray" }[] = [
  { sev: "Red", title: "Must fix", sub: "These stop the shipment", tone: "red" },
  { sev: "Data", title: "Missing information", sub: "We can't check these yet", tone: "violet" },
  { sev: "Amber", title: "Worth sorting", sub: "Could cause delays or charges", tone: "amber" },
  { sev: "Advisory", title: "Good to know", sub: "Advisory / reference only", tone: "gray" },
];

export function Bold({ text }: { text: string }) {
  return <>{boldSegments(text).map((s, i) => (s.bold ? <strong key={i} className="font-semibold text-white">{s.text}</strong> : <span key={i}>{s.text}</span>))}</>;
}

function CheckRing({ passed, tone }: { passed: number; tone: Tone }) {
  const segs = Array.from({ length: 10 });
  const r = 38, c = 2 * Math.PI * r, gap = 4, len = c / 10 - gap;
  return (
    <div className="relative h-28 w-28 shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        {segs.map((_, i) => (
          <motion.circle key={i} cx="50" cy="50" r={r} fill="none" strokeWidth="7" strokeLinecap="round"
            stroke={i < passed ? TONE_RING[tone] : "rgba(255,255,255,0.08)"}
            strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-(i * (len + gap))}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 + i * 0.05, duration: 0.4 }} />
        ))}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div><div className="text-[26px] font-semibold leading-none tracking-[-0.03em]">{passed}<span className="text-[15px] text-faint">/10</span></div>
          <div className="mt-1 text-[10.5px] uppercase tracking-[0.1em] text-faint">checks</div></div>
      </div>
    </div>
  );
}

function StatusCard({ r }: { r: Result }) {
  const Icon = r.view.tone === "green" ? BadgeCheck : r.view.tone === "amber" ? AlertTriangle : XCircle;
  return (
    <TiltCard max={3} className="p-6 sm:p-7">
      <div className="flex h-full items-center gap-6">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-[0.1em] text-faint">
            <Icon className="h-4 w-4" style={{ color: TONE_RING[r.view.tone] }} /> {r.id.startsWith("CHAT") ? "Your booking" : `Booking ${r.id}`}
          </div>
          <div className={cn("mt-2 text-[34px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[42px]", TONE_TEXT[r.view.tone])}>{r.view.label}</div>
          <div className="mt-2 text-[16px] font-medium text-fg">{r.view.headline}</div>
          <div className="mt-1 text-[14px] text-muted">{r.view.sub}</div>
          <div className="mt-4 flex flex-wrap gap-2">
            {([["Red", r.counts.red, "red", "must fix"], ["Data", r.counts.data, "violet", "missing info"],
               ["Amber", r.counts.amber, "amber", "to sort"], ["Advisory", r.counts.advisory, "gray", "advisory"]] as const)
              .filter(([, n]) => n > 0).map(([sev, n, tone, word]) => (
                <button key={sev} onClick={() => focusEl(`grp-${sev}`)} className="tile rounded-full" title="Show these">
                  <Pill tone={tone}>{n} {word} <ArrowRight className="h-3 w-3" /></Pill>
                </button>))}
          </div>
        </div>
        <CheckRing passed={r.counts.passed} tone={r.view.tone} />
      </div>
    </TiltCard>
  );
}

function PickCard({ r }: { r: Result }) {
  const pick = r.options.find((o) => o.picked);
  return (
    <TiltCard max={4} glow className="p-6 sm:p-7">
      <div className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-[0.1em] text-faint"><Sparkles className="h-4 w-4 text-cyan" /> Our pick · {r.load.priority}</div>
      {pick ? (
        <>
          <div className="mt-2 text-[30px] font-semibold tracking-[-0.03em] text-gradient">{pick.carrier}</div>
          <div className="text-[13.5px] text-muted">Road freight · {pick.transit} working days</div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Stat label="Cost" value={r.confirmation.cost ?? pick.cost_label} />
            <Stat label="Arrives" value={niceDate(r.confirmation.eta)} />
            <Stat label="On time" value={`${pick.on_time}%`} />
          </div>
          <p className="mt-4 text-[13.5px] leading-relaxed text-fg/80">{r.reason}</p>
        </>
      ) : <p className="mt-3 text-[14px] text-muted">{r.reason || "We'll pick a carrier once we know where it's going."}</p>}
    </TiltCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2.5">
      <div className="text-[10.5px] uppercase tracking-[0.1em] text-faint">{label}</div>
      <div className="mt-0.5 text-[14px] font-semibold leading-tight tracking-[-0.01em] sm:text-[15px]">{value}</div>
    </div>
  );
}

function FindingCard({ f, onFix, pending, i, anchor }: { f: Finding; onFix?: (a: Record<string, unknown>) => void; pending?: boolean; i: number; anchor?: string }) {
  const [why, setWhy] = useState(false);
  const accent = { Red: "bg-bad", Data: "bg-violet", Amber: "bg-warn", Advisory: "bg-faint" }[f.severity];
  return (
    <Reveal i={i}>
      <div id={anchor} className="glass relative scroll-mt-28 overflow-hidden rounded-2xl p-4 pl-5 sm:p-5 sm:pl-6">
        <span className={cn("absolute bottom-3 left-0 top-3 w-[3px] rounded-r-full", accent)} />
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[15px] font-semibold tracking-[-0.01em]">{f.title}</span>
          <span className="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[11px] text-muted">{f.rule}</span>
          {f.sku && <span className="font-mono text-[11.5px] text-faint">{f.sku}</span>}
          {f.from_ai && <Pill tone="violet"><Bot className="h-3 w-3" /> AI flag · please confirm</Pill>}
        </div>
        <p className="mt-2 text-[14.5px] leading-relaxed text-fg/90">{f.message}</p>
        <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-white/8 bg-white/[0.03] p-3">
          <Wand2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
          <p className="text-[14px] leading-relaxed text-fg/85"><span className="font-medium text-white">How to fix: </span>{f.fix}</p>
        </div>
        {f.ai && f.ai.contains_dg !== "yes" && (
          <p className="mt-2 flex items-center gap-1.5 text-[12.5px] text-muted"><Bot className="h-3.5 w-3.5" /> AI review: {f.ai.contains_dg === "no" ? "likely safe" : "unsure"}. {f.ai.why}</p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {onFix && f.action && f.action_label && (
            <Button size="sm" disabled={pending} onClick={() => onFix(f.action!)}><Wand2 className="h-3.5 w-3.5" /> Fix it: {f.action_label.replace(/^Set /, "set ")}</Button>
          )}
          {f.why && (
            <button onClick={() => setWhy(!why)} className="press flex items-center gap-1 rounded-lg px-2 py-1 text-[12.5px] text-muted hover:text-fg">
              Why it matters <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", why && "rotate-180")} />
            </button>
          )}
        </div>
        {why && f.why && <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-2 text-[13.5px] leading-relaxed text-muted">{f.why}</motion.p>}
      </div>
    </Reveal>
  );
}

function Findings({ r, onFix, pending }: { r: Result; onFix?: (a: Record<string, unknown>) => void; pending?: boolean }) {
  if (!r.findings.length) {
    return (
      <div className="glass flex items-center gap-4 rounded-3xl p-6">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-good/15"><ShieldCheck className="h-6 w-6 text-good" /></div>
        <div><div className="text-[16px] font-semibold">Nothing to fix</div><div className="text-[14px] text-muted">Every check from R-01 to R-10 passed.</div></div>
      </div>
    );
  }
  let n = 0;
  const seen = new Set<string>();
  const anchorFor = (f: Finding) => (seen.has(f.rule) ? undefined : (seen.add(f.rule), `f-${f.rule}`));
  return (
    <div className="space-y-6">
      {GROUPS.map((g) => {
        const list = r.findings.filter((f) => f.severity === g.sev);
        if (!list.length) return null;
        return (
          <div key={g.sev} id={`grp-${g.sev}`} className="scroll-mt-28 rounded-2xl">
            <div className="mb-3 flex items-baseline gap-2.5">
              <Pill tone={g.tone}>{g.title} · {list.length}</Pill>
              <span className="text-[13px] text-faint">{g.sub}</span>
            </div>
            <div className="space-y-3">{list.map((f) => <FindingCard key={n} f={f} onFix={onFix} pending={pending} i={n++} anchor={anchorFor(f)} />)}</div>
          </div>
        );
      })}
    </div>
  );
}

function ChecksGrid({ r }: { r: Result }) {
  const [open, setOpen] = useState<string | null>(null);
  const icon = { Pass: <Check className="h-3.5 w-3.5 text-good" />, Red: <X className="h-3.5 w-3.5 text-bad" />, Amber: <AlertTriangle className="h-3.5 w-3.5 text-warn" />, Data: <CircleDashed className="h-3.5 w-3.5 text-violet" /> };
  const tap = (id: string, state: string) => { if (!(state !== "Pass" && focusEl(`f-${id}`))) setOpen(open === id ? null : id); };
  const cur = r.rules.find((x) => x.id === open);
  return (
    <div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
        {r.rules.map((x, i) => (
          <Reveal key={x.id} i={i}>
            <button onClick={() => tap(x.id, x.state)} title={x.state === "Pass" ? "Why this check matters" : "Show the problem"}
              className={cn("tile flex h-full w-full items-start gap-2.5 rounded-2xl border p-3",
                x.state === "Pass" ? "border-white/8 bg-white/[0.025]" : x.state === "Red" ? "border-bad/25 bg-bad/[0.06]" : x.state === "Amber" ? "border-warn/25 bg-warn/[0.06]" : "border-violet/25 bg-violet/[0.06]",
                open === x.id && "border-violet/50")}>
              <span className="mt-0.5">{icon[x.state]}</span>
              <span className="min-w-0 flex-1"><span className="block font-mono text-[10.5px] text-faint">{x.id}</span><span className="block text-[13px] leading-snug text-fg/90">{x.name}</span></span>
              <ChevronDown className={cn("mt-0.5 h-3.5 w-3.5 shrink-0 text-faint transition-transform", x.state !== "Pass" && "-rotate-90", open === x.id && "rotate-180")} />
            </button>
          </Reveal>
        ))}
      </div>
      {cur && (
        <motion.p key={cur.id} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 rounded-2xl border border-white/8 bg-white/[0.03] p-3.5 text-[13.5px] leading-relaxed text-muted">
          <span className="font-medium text-fg">{cur.id} · {cur.name}: </span>{cur.why}
        </motion.p>
      )}
    </div>
  );
}

function CarrierCard({ o, i, why }: { o: CarrierOption; i: number; why: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Reveal i={i} className="h-full">
      <TiltCard glow={o.picked} className={cn("p-5", o.eligible === false && "opacity-75")}>
        <button onClick={() => setOpen(!open)} className="absolute inset-0 z-10 cursor-pointer rounded-3xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/70"
          aria-label={`${open ? "Hide" : "Show"} why ${o.picked ? "we picked" : "we did not pick"} ${o.carrier}`} />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={cn("grid h-9 w-9 place-items-center rounded-xl border", o.picked ? "border-cyan/40 bg-cyan/10" : "border-white/10 bg-white/[0.04]")}><Truck className={cn("h-4.5 w-4.5", o.picked ? "text-cyan" : "text-muted")} /></div>
            <div><div className="text-[16px] font-semibold tracking-[-0.01em]">{o.carrier}</div><div className="text-[12.5px] text-muted">Road freight</div></div>
          </div>
          {o.picked ? <Pill tone="cyan"><Sparkles className="h-3 w-3" /> Our pick</Pill> : o.eligible === false ? <Pill tone="red">Can't take it</Pill> : <Pill tone="gray">Option</Pill>}
        </div>
        <div className="mt-4 text-[24px] font-semibold tracking-[-0.03em]">{o.cost_label}</div>
        <div className="text-[12px] text-faint">{o.per_pallet} per pallet</div>
        <div className="mt-4 space-y-2.5 text-[13px]">
          <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 text-muted"><Timer className="h-3.5 w-3.5" /> Transit</span><span>{o.transit} working days</span></div>
          <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 text-muted"><CalendarClock className="h-3.5 w-3.5" /> Arrives</span><span>{niceDate(o.eta)}</span></div>
          <div>
            <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 text-muted"><ShieldCheck className="h-3.5 w-3.5" /> On time</span><span>{o.on_time}%</span></div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/8">
              <motion.div className="h-full rounded-full bg-gradient-to-r from-violet to-cyan" initial={{ width: 0 }} whileInView={{ width: `${(o.on_time - 85) / 15 * 100}%` }} viewport={{ once: true }} transition={{ duration: 1, ease: EASE, delay: 0.2 + i * 0.1 }} />
            </div>
          </div>
          <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 text-muted"><Scale className="h-3.5 w-3.5" /> Max per pallet</span><span>{o.max_kg} kg</span></div>
        </div>
        {o.excluded && <p className="mt-3 rounded-xl border border-bad/20 bg-bad/[0.07] p-2.5 text-[12.5px] text-red-100/90">{o.excluded}</p>}
        <div className="mt-3 flex items-center gap-1 text-[12.5px] text-cyan">{open ? "Hide" : o.picked ? "Why we picked it" : "Why not this one"} <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} /></div>
        {open && why && <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-2 text-[13px] leading-relaxed text-fg/85">{why}</motion.p>}
      </TiltCard>
    </Reveal>
  );
}

function Carriers({ r }: { r: Result }) {
  if (!r.options.length) return <div className="glass rounded-3xl p-6 text-[14px] text-muted">{r.reason}</div>;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13.5px] text-muted">
        {r.load.gross && <span>Load <span className="text-fg">{r.load.gross}</span></span>}
        {r.load.pallets && <span>on <span className="text-fg">{r.load.pallets} pallet{r.load.pallets === "1" ? "" : "s"}</span></span>}
        {r.load.per_pallet && <span>= <span className="text-fg">{r.load.per_pallet} per pallet</span></span>}
        <span>Priority <span className="text-fg">{r.load.priority}</span></span>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">{r.options.map((o, i) => (
        <CarrierCard key={o.carrier} o={o} i={i} why={o.picked ? r.reason : (r.why_others.find((w) => w.startsWith(o.carrier)) ?? o.excluded ?? "")} />))}</div>
      {r.why_others.length > 0 && (
        <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.025] p-4">
          <div className="mb-2 text-[13px] font-medium text-fg">Why not the others</div>
          <ul className="space-y-1.5 text-[13.5px] text-muted">{r.why_others.map((w, i) => <li key={i} className="flex gap-2"><ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />{w}</li>)}</ul>
        </div>
      )}
      {r.load.priority === "Balanced" && (
        <p className="mt-3 flex gap-2 text-[12.5px] leading-relaxed text-faint"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Balanced means we pick the carrier whose weakest point is least bad across price, speed and reliability. Simply averaging would always pick the most expensive one.</p>
      )}
    </div>
  );
}

export function Confirmation({ r, confirmed }: { r: Result; confirmed: boolean }) {
  const c = r.confirmation;
  const rows: [string, string | null][] = [["Route", c.route], ["Carrier", c.carrier], ["Total cost", c.cost && `${c.cost}${c.cost_detail ? ` · ${c.cost_detail}` : ""}`],
    ["Collection", c.collection && niceDate(c.collection) + ` (${c.collection})`], [c.blocked ? "Delivery (estimate)" : "Estimated delivery", c.eta && niceDate(c.eta) + ` (${c.eta})`], ["Goods", c.goods]];
  return (
    <div className={cn("glass relative h-full overflow-hidden rounded-3xl p-6 sm:p-7", !c.blocked && confirmed && "glow-border")}>
      <div className="flex items-center gap-3">
        <div className={cn("grid h-11 w-11 place-items-center rounded-2xl", c.blocked ? "bg-bad/15" : "bg-good/15")}>
          {c.blocked ? <XCircle className="h-5.5 w-5.5 text-bad" /> : <BadgeCheck className="h-5.5 w-5.5 text-good" />}
        </div>
        <div>
          <div className="text-[20px] font-semibold tracking-[-0.02em]">{c.blocked ? "Not booked yet" : confirmed ? "Booking confirmed" : "Ready to confirm"}</div>
          <div className="text-[13.5px] text-muted">{c.seller || "Your shipment"}</div>
        </div>
      </div>
      <dl className="mt-5 divide-y divide-white/6">
        {rows.filter(([, v]) => v).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2.5 text-[14px]"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>
        ))}
      </dl>
      {c.blocked && <p className="mt-3 text-[12.5px] text-faint">The carrier, cost and date are provisional and may change once the problems are fixed.</p>}
      {c.todo.length > 0 && (
        <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <div className="mb-2 text-[13px] font-medium">{c.blocked ? "Fix these first" : "Sort these before collection"}</div>
          <ol className="list-decimal space-y-1.5 pl-5 text-[13.5px] text-fg/85">{c.todo.map((t, i) => <li key={i}>{t}</li>)}</ol>
        </div>
      )}
      <p className="mt-3 text-[12px] leading-relaxed text-faint">{c.eta_notes}</p>
    </div>
  );
}

export function NextSteps({ r }: { r: Result }) {
  return (
    <div className="glass h-full rounded-3xl p-6 sm:p-7">
      <div className="text-[17px] font-semibold tracking-[-0.02em]">What happens next</div>
      <ol className="relative mt-5 space-y-5 border-l border-white/10 pl-6">
        {r.next_steps.map((s, i) => (
          <Reveal as="li" key={i} i={i} className="relative">
            <span className="absolute -left-[33px] grid h-[18px] w-[18px] place-items-center rounded-full border border-white/15 bg-ink-2 font-mono text-[10px] text-muted">{i + 1}</span>
            <div className="text-[14.5px] font-medium">{s.title}</div>
            <p className="mt-0.5 text-[13.5px] leading-relaxed text-muted">{s.body}
              {s.link && <a href={s.link} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-0.5 text-cyan hover:underline">{s.link_label}<ExternalLink className="h-3 w-3" /></a>}</p>
          </Reveal>
        ))}
      </ol>
    </div>
  );
}

function Section({ title, sub, children, i = 0 }: { title: string; sub?: string; children: React.ReactNode; i?: number }) {
  return (
    <Reveal i={i} as="section">
      <div className="mb-4 mt-2">
        <h3 className="text-[19px] font-semibold tracking-[-0.025em]">{title}</h3>
        {sub && <p className="text-[13.5px] text-muted">{sub}</p>}
      </div>
      {children}
    </Reveal>
  );
}

export function Results({ r, onFix, pending, showConfirmation = true, confirmed = false, onEvent, scope = "chat", pendingType }: {
  r: Result; onFix?: (a: Record<string, unknown>) => void; pending?: boolean; showConfirmation?: boolean; confirmed?: boolean;
  onEvent?: Send; scope?: "chat" | "file"; pendingType?: string | null;
}) {
  const target = { scope, booking_id: r.id };
  return (
    <div className="space-y-10">
      {r.notices.length > 0 && <div className="rounded-2xl border border-cyan/20 bg-cyan/[0.06] p-3.5 text-[13.5px] text-cyan-100">{r.notices.join(" ")}</div>}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Reveal className="lg:col-span-7"><StatusCard r={r} /></Reveal>
        <Reveal i={1} className="lg:col-span-5"><PickCard r={r} /></Reveal>
      </div>
      <Section title="What we found" sub="Each problem says what's wrong and exactly how to fix it.">
        <Findings r={r} onFix={onFix} pending={pending} />
      </Section>
      <Section title="The 10 checks" sub="Green means passed. Tap a check to see the problem or why it matters.">
        <div id="checks-grid" className="scroll-mt-28 rounded-2xl"><ChecksGrid r={r} /></div>
      </Section>
      <Section title="Carriers compared" sub="All three options on this route. Tap a card to see why it was or wasn't picked. (Economy, Standard and Express are Carriers A, B and C on the rate card.)">
        <Carriers r={r} />
      </Section>
      <Section title="Compare with the market" sub="Optional: real prices from other carriers right now.">
        <LivePrices r={r} loading={pendingType === "live_rates"} onFetch={onEvent ? () => onEvent({ type: "live_rates", ...target }) : undefined} />
      </Section>
      <Section title="Paperwork" sub="What the commercial invoice needs, and the rules on each side of the border.">
        <div className="space-y-4">
          <InvoiceChecklist r={r} loading={pendingType === "invoice"} onDownload={onEvent ? () => onEvent({ type: "invoice", ...target }) : undefined} />
          <CountryRules r={r} />
        </div>
      </Section>
      {showConfirmation && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Reveal className="lg:col-span-7"><Confirmation r={r} confirmed={confirmed} /></Reveal>
          <Reveal i={1} className="lg:col-span-5"><NextSteps r={r} /></Reveal>
        </div>
      )}
    </div>
  );
}
