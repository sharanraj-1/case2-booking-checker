// Advisory sections: live prices, export-invoice checklist, country rules. Nothing here changes the check result.
import { motion } from "framer-motion";
import { Check, CircleDashed, Copy, Download, ExternalLink, FileText, Globe2, Info, Plane, Plus, RefreshCw, Search, Truck } from "lucide-react";
import { useState } from "react";
import { Button, Pill, Reveal, Skeleton } from "../components/fx";
import { cn, EASE } from "../lib/cn";
import type { Result } from "../types";

const gbp = (n: number) => `£${n.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function LivePrices({ r, loading, onFetch }: { r: Result; loading: boolean; onFetch?: () => void }) {
  const live = r.live;
  const max = live?.ok ? Math.max(...live.quotes.map((q) => q.price), live.ours?.cost ?? 0) : 1;
  return (
    <div className="glass rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-[640px]">
          <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.015em]"><Search className="h-4 w-4 text-cyan" /> Live market prices</div>
          <p className="mt-1 text-[13.5px] leading-relaxed text-muted">
            Real prices right now from other carriers for the same route and load, so you can see how our pick compares.
            Reference only: our pick and the checks use the fixed rate card.
          </p>
        </div>
        {onFetch && (
          <Button size="md" variant={live ? "soft" : "primary"} glow={!live} disabled={loading || !r.can_live} onClick={onFetch}>
            {live ? <><RefreshCw className="h-4 w-4" /> Refresh</> : <><Search className="h-4 w-4" /> Check live prices</>}
          </Button>
        )}
      </div>
      {!r.can_live && !live && <p className="mt-3 text-[13px] text-faint">Add the destination, pallets and total weight first.</p>}
      <p className="mt-2 text-[12px] text-faint"><span className="font-medium text-muted">Limit:</span> live quotes cover up to 50 pallets and 1,200 kg per pallet.</p>
      {loading && <div className="mt-4 space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12 rounded-2xl" />)}</div>}
      {!loading && live && !live.ok && <p className="mt-4 rounded-2xl border border-warn/25 bg-warn/[0.06] p-3 text-[13.5px]">{live.error}</p>}
      {!loading && live?.ok && (
        <div className="mt-4">
          {live.summary && <p className="mb-3 text-[14px] text-fg/90">{live.summary}</p>}
          <div className="space-y-2">
            {live.ours && (
              <Bar label={`Our pick · ${live.ours.carrier}`} sub="Fixed rate card" price={live.ours.cost} max={max} ours i={0} />
            )}
            {live.quotes.map((q, i) => (
              <Bar key={q.service} label={q.service} sub={[q.transit, q.mode === "Air" ? "Air freight" : "Road"].filter(Boolean).join(" · ")}
                price={q.price} max={max} cheapest={i === 0} air={q.mode === "Air"} i={i + 1} />
            ))}
          </div>
          <p className="mt-3 flex items-start gap-1.5 text-[12px] leading-relaxed text-faint">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Live quotes from {live.source} at {live.fetched_at} for {live.pallet_type}. Prices as shown by {live.source}; they may exclude VAT,
            insurance and extras, and change at any time.
          </p>
        </div>
      )}
    </div>
  );
}

function Bar({ label, sub, price, max, ours, cheapest, air, i }: { label: string; sub: string; price: number; max: number; ours?: boolean; cheapest?: boolean; air?: boolean; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04, duration: 0.4, ease: EASE }}
      className={cn("relative overflow-hidden rounded-2xl border px-4 py-2.5", ours ? "border-cyan/35 bg-cyan/[0.06]" : "border-white/8 bg-white/[0.025]")}>
      <motion.div className={cn("absolute inset-y-0 left-0", ours ? "bg-cyan/10" : cheapest ? "bg-good/10" : "bg-white/[0.035]")}
        initial={{ width: 0 }} animate={{ width: `${Math.max(4, (price / max) * 100)}%` }} transition={{ duration: 0.9, ease: EASE, delay: 0.1 + i * 0.04 }} />
      <div className="relative flex items-center gap-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.05]">
          {air ? <Plane className="h-3.5 w-3.5 text-muted" /> : <Truck className={cn("h-3.5 w-3.5", ours ? "text-cyan" : "text-muted")} />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 truncate text-[14px] font-medium">{label}{cheapest && <Pill tone="green">Cheapest</Pill>}</div>
          <div className="truncate text-[12px] text-faint">{sub}</div>
        </div>
        <div className="text-[15px] font-semibold tabular-nums">{gbp(price)}</div>
      </div>
    </motion.div>
  );
}

export function InvoiceChecklist({ r, onDownload, loading }: { r: Result; onDownload?: () => void; loading: boolean }) {
  const [open, setOpen] = useState<number | null>(null);
  const icon = { ready: <Check className="h-3.5 w-3.5 text-good" />, check: <Info className="h-3.5 w-3.5 text-warn" />,
    add: <Plus className="h-3.5 w-3.5 text-violet" />, info: <CircleDashed className="h-3.5 w-3.5 text-faint" /> };
  const label = { ready: "We have it", check: "Check it", add: "You add", info: "If needed" };
  const c = r.invoice.counts;
  return (
    <div className="glass rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-[620px]">
          <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.015em]"><FileText className="h-4 w-4 text-cyan" /> Export invoice checklist</div>
          <p className="mt-1 text-[13.5px] text-muted">The 15 things a commercial invoice needs, from the UK government's export guide. Tap any line for detail.</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Pill tone="green">{c.ready ?? 0} ready</Pill>{(c.check ?? 0) > 0 && <Pill tone="amber">{c.check} to check</Pill>}
            <Pill tone="violet">{c.add ?? 0} for you to add</Pill>
          </div>
        </div>
        {onDownload && <Button disabled={loading} onClick={onDownload}><Download className="h-4 w-4" /> Download draft invoice</Button>}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
        {r.invoice.rows.map((row) => (
          <button key={row.n} onClick={() => setOpen(open === row.n ? null : row.n)}
            className={cn("tile rounded-2xl border p-3", open === row.n ? "border-violet/40 bg-violet/[0.06]" : "border-white/8 bg-white/[0.025]")}>
            <div className="flex items-center gap-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.04]">{icon[row.state]}</span>
              <span className="flex-1 text-[13.5px] font-medium">{row.n}. {row.title}</span>
              <span className="text-[11px] text-faint">{label[row.state]}</span>
            </div>
            {open === row.n && <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-2 pl-8 text-[13px] leading-relaxed text-muted">{row.detail}</motion.p>}
          </button>
        ))}
      </div>
      <a href={r.invoice.source} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-[12.5px] text-cyan hover:underline">
        Source: business.gov.uk, How to create an export invoice <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  );
}

export function CountryRules({ r }: { r: Result }) {
  const [copied, setCopied] = useState(false);
  const c = r.country;
  if (!c) return null;
  return (
    <div className="glass rounded-3xl p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[16px] font-semibold tracking-[-0.015em]"><Globe2 className="h-4 w-4 text-cyan" /> Rules for UK → {c.country}</div>
      <p className="mt-1 text-[13.5px] text-muted">What each side of the border needs. Reference only; your buyer or customs agent can confirm product-specific rules.</p>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {[["Leaving the UK (export)", c.export], [`Entering ${c.country} (import)`, c.import]].map(([title, list], k) => (
          <Reveal key={String(title)} i={k}>
            <div className="h-full rounded-2xl border border-white/8 bg-white/[0.025] p-4">
              <div className="mb-2 text-[13.5px] font-semibold">{title as string}</div>
              <ul className="space-y-2 text-[13.5px] leading-relaxed text-fg/85">
                {(list as string[]).map((x, i) => <li key={i} className="flex gap-2"><Check className="mt-1 h-3.5 w-3.5 shrink-0 text-good" />{x}</li>)}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
      {c.statement_on_origin && (
        <div className="mt-4 rounded-2xl border border-cyan/20 bg-cyan/[0.05] p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[13.5px] font-semibold">Statement on origin (for UK-made lines)</div>
            <button className="tile flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.05] px-2.5 py-1.5 text-[12.5px]"
              onClick={() => { navigator.clipboard?.writeText(c.statement_on_origin!).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800); }).catch(() => {}); }}>
              {copied ? <><Check className="h-3.5 w-3.5 text-good" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
            </button>
          </div>
          <p className="mt-2 font-mono text-[12.5px] leading-relaxed text-fg/85">{c.statement_on_origin}</p>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {c.sources.map((s) => <a key={s} href={s} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] text-cyan hover:underline">{s.replace("https://www.", "")}<ExternalLink className="h-3 w-3" /></a>)}
      </div>
    </div>
  );
}
