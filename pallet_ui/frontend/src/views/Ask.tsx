// The control for the current question: option tiles, number, date, text or a product card.
import { motion } from "framer-motion";
import { ArrowRight, ChevronRight, ExternalLink, Minus, Plus, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, Limit } from "../components/fx";
import { OptionIcon } from "../components/Icon";
import { addDays, cn, EASE, fmt, niceDate, softFocus, toDDMMYYYY, toISO } from "../lib/cn";
import type { Ask, Item, Limits, Send } from "../types";

export interface AskCtx { send: Send; pending: boolean; pendingType: string | null; today: string; coo: string[]; fields: Record<string, [string, string, string, string]>; tariff: string; limits: Limits }

export function AskControl({ ask, ctx, items }: { ask: Ask; ctx: AskCtx; items: Item[] }) {
  return (
    <motion.div key={`${ask.field}-${ask.item_index ?? ""}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}
      className="relative rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(139,92,246,0.07),rgba(255,255,255,0.025))] p-4 shadow-[0_12px_40px_rgba(0,0,0,0.3)] sm:p-5">
      <div className="text-[16px] font-semibold tracking-[-0.015em]">{ask.question}</div>
      {ask.hint && <div className="mt-0.5 text-[13px] text-muted">{ask.hint}</div>}
      {ask.kind !== "number" && ask.kind !== "text" && <Limit text={ask.limit} />}
      <div className="mt-4">
        {ask.kind === "choice" && <Choice ask={ask} ctx={ctx} />}
        {ask.kind === "number" && <NumberAsk ask={ask} ctx={ctx} />}
        {ask.kind === "date" && <DateAsk ask={ask} ctx={ctx} />}
        {ask.kind === "text" && <TextAsk ask={ask} ctx={ctx} />}
        {ask.kind === "item" && (
          <ItemForm ctx={ctx} index={ask.item_index ?? null} item={ask.item_index != null ? items[ask.item_index] : undefined} only={ask.item_index != null ? ask.missing : undefined} />
        )}
      </div>
    </motion.div>
  );
}

function Choice({ ask, ctx }: { ask: Ask; ctx: AskCtx }) {
  const opts = ask.options ?? [];
  return (
    <div className={cn("grid gap-2.5", opts.length >= 4 ? "grid-cols-2" : opts.length === 3 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-2")}>
      {opts.map((o, i) => (
        <motion.button key={o.value} disabled={ctx.pending}
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, duration: 0.4, ease: EASE }}
          whileHover={{ y: -3 }} whileTap={{ scale: 0.96 }}
          onClick={() => ctx.send({ type: "answer", field: ask.field, value: o.value, label: o.label })}
          className={cn("group relative flex min-h-[76px] cursor-pointer items-center gap-3 rounded-2xl border p-4 text-left outline-none transition-[border-color,background-color,box-shadow] duration-200 focus-visible:ring-2 focus-visible:ring-violet/70 disabled:cursor-not-allowed disabled:opacity-50",
            o.suggested ? "glow-border border-cyan/40 bg-cyan/[0.07] hover:bg-cyan/[0.11]" : "border-white/10 bg-white/[0.04] hover:border-violet/55 hover:bg-violet/[0.09] hover:shadow-[0_10px_30px_rgba(0,0,0,0.35)]")}>
          <OptionIcon name={o.icon} />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2 text-[15.5px] font-medium">{o.label}{o.suggested && <span className="rounded-full bg-cyan/15 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-cyan">Suggested</span>}</span>
            {o.hint && <span className={cn("block truncate text-[12.5px]", o.suggested ? "text-cyan/90" : "text-muted")}>{o.hint}</span>}
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-fg" />
        </motion.button>
      ))}
    </div>
  );
}

function NumberAsk({ ask, ctx }: { ask: Ask; ctx: AskCtx }) {
  const isPallets = ask.field === "pallets";
  const [v, setV] = useState<string>(isPallets && !ask.suggestions?.length ? "1" : "");
  const n = Number(v);
  const whole = !isPallets || Number.isInteger(n);
  const ok = v.trim() !== "" && Number.isFinite(n) && n > 0 && whole;
  const over = !isPallets && ask.max && n > ask.max
    ? `That's over the limit: ${n.toLocaleString()} kg is more than ${ask.max.toLocaleString()} kg. You can still continue and we'll tell you how many pallets you need.`
    : isPallets && v && !whole ? "Pallets must be a whole number." : null;
  const submit = () => ok && ctx.send({ type: "answer", field: ask.field, value: v.trim(), label: `${v.trim()} ${ask.unit ?? ""}`.trim() });
  const sug = ask.suggestions ?? [];
  return (
    <div className="space-y-3">
      {sug.length > 0 && (
        <div className={cn("grid gap-2.5", sug.length === 2 ? "grid-cols-2" : sug.length > 2 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-1")}>
          {sug.map((o, i) => (
            <motion.button key={o.value} disabled={ctx.pending} onClick={() => ctx.send({ type: "answer", field: ask.field, value: o.value, label: o.label })}
              initial={{ opacity: 0, y: 12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 24, delay: i * 0.07 }}
              whileHover={{ y: -3 }} whileTap={{ scale: 0.96 }}
              className={cn("group relative min-h-[84px] cursor-pointer overflow-hidden rounded-2xl border p-4 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-violet/70",
                o.suggested ? "glow-border shimmer border-cyan/40 bg-[linear-gradient(135deg,rgba(34,211,238,0.12),rgba(139,92,246,0.12))]" : "border-white/10 bg-white/[0.04] hover:border-violet/55 hover:bg-violet/[0.09]")}>
              {o.suggested && <span className="mb-1.5 inline-flex items-center gap-1 rounded-full bg-cyan/15 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-cyan"><Sparkles className="h-3 w-3" /> Recommended</span>}
              <span className="block text-[19px] font-semibold tracking-[-0.02em]">{o.label}</span>
              <span className={cn("mt-0.5 block text-[12.5px] leading-snug", o.suggested ? "text-cyan-100/90" : "text-muted")}>{o.hint}</span>
              <ArrowRight className="absolute right-3.5 top-3.5 h-4 w-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-fg" />
            </motion.button>
          ))}
        </div>
      )}
      {sug.length > 0 && <div className="flex items-center gap-3 pt-1 text-[12px] text-faint"><span className="h-px flex-1 bg-white/8" />or enter your own<span className="h-px flex-1 bg-white/8" /></div>}
      <div className="flex items-stretch gap-2">
        {isPallets && <StepBtn onClick={() => setV(String(Math.max(1, (n || 1) - 1)))}><Minus className="h-4 w-4" /></StepBtn>}
        <div className="relative flex-1">
          <input ref={softFocus} inputMode="decimal" type="number" min={ask.min as number} step={ask.step} value={v} onChange={(e) => setV(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()} placeholder={isPallets ? "e.g. 2" : "e.g. 620"}
            className="field h-14 pr-20 text-center text-[22px] font-semibold tracking-[-0.02em]" />
          <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[14px] text-muted">{ask.unit}</span>
        </div>
        {isPallets && <StepBtn onClick={() => setV(String((n || 0) + 1))}><Plus className="h-4 w-4" /></StepBtn>}
      </div>
      <Limit text={ask.limit} over={over} className="-mt-1" />
      <Button className="w-full" size="lg" disabled={!ok || ctx.pending} onClick={submit}>Continue <ArrowRight className="h-4 w-4" /></Button>
    </div>
  );
}

function StepBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return <motion.button whileTap={{ scale: 0.9 }} onClick={onClick} className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[0.05] hover:bg-white/[0.09]">{children}</motion.button>;
}

function DateAsk({ ask, ctx }: { ask: Ask; ctx: AskCtx }) {
  const quick = useMemo(() => {
    const today = addDays(ctx.today, 0);
    const dow = today.getUTCDay();
    let toMon = ((8 - dow) % 7) || 7;
    if (toMon === 1) toMon = 8; // tomorrow is already Monday
    return [["Today", 0], ["Tomorrow", 1], ["Next Monday", toMon], ["In a week", 7]].map(([l, d]) => ({ label: l as string, value: fmt(addDays(ctx.today, d as number)) }));
  }, [ctx.today]);
  const [iso, setIso] = useState("");
  const send = (dd: string, label?: string) => ctx.send({ type: "answer", field: ask.field, value: dd, label: label ? `${label} (${dd})` : dd });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {quick.map((q) => (
          <motion.button whileTap={{ scale: 0.96 }} whileHover={{ y: -2 }} key={q.label} disabled={ctx.pending} onClick={() => send(q.value, q.label)}
            className="min-h-[64px] cursor-pointer rounded-2xl border border-white/10 bg-white/[0.04] p-3.5 text-left outline-none transition-colors hover:border-violet/55 hover:bg-violet/[0.09] focus-visible:ring-2 focus-visible:ring-violet/70">
            <div className="text-[14px] font-medium">{q.label}</div><div className="text-[12px] text-muted">{niceDate(q.value)}</div>
          </motion.button>
        ))}
      </div>
      <div className="flex gap-2">
        <input type="date" min={toISO(ctx.today)} value={iso} onChange={(e) => setIso(e.target.value)} className="field h-12 flex-1" aria-label="Pick a date" />
        <Button disabled={!iso || ctx.pending} onClick={() => send(toDDMMYYYY(iso))}>Use date</Button>
      </div>
    </div>
  );
}

function TextAsk({ ask, ctx }: { ask: Ask; ctx: AskCtx }) {
  const [v, setV] = useState("");
  const max = ask.field === "seller" ? ctx.limits.seller_max : 200;
  const submit = () => v.trim() && ctx.send({ type: "answer", field: ask.field, value: v.trim(), label: v.trim() });
  return (
    <div>
      <div className="flex gap-2">
        <input ref={softFocus} value={v} maxLength={max} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder={ask.placeholder} className="field h-12 flex-1" />
        <Button disabled={!v.trim() || ctx.pending} onClick={submit}>Continue</Button>
      </div>
      <Limit text={`${ask.limit ?? ""} ${v.length}/${max} used.`.trim()} over={v.length >= max ? `That's the maximum: ${max} characters.` : null} />
    </div>
  );
}

const ORDER = ["description", "qty", "unit_price", "units_per_carton", "unit_kg", "hs_code", "coo", "cartons"];

export function ItemForm({ ctx, index, item, only, onDone }: { ctx: AskCtx; index: number | null; item?: Item; only?: string[]; onDone?: () => void }) {
  const init = () => Object.fromEntries(ORDER.map((k) => [k, item && (item as unknown as Record<string, unknown>)[k] != null ? String((item as unknown as Record<string, unknown>)[k]) : ""]));
  const [vals, setVals] = useState<Record<string, string>>(init);
  const [showAll, setShowAll] = useState(!only);
  useEffect(() => { setVals(init()); setShowAll(!only); }, [index, item?.description]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = ORDER.filter((k) => showAll || (only ?? []).includes(k) || k === "description" && !item);
  const visible = shown.filter((k) => k !== "cartons" || showAll);
  const numeric = (k: string) => ["qty", "unit_price", "units_per_carton", "unit_kg", "cartons"].includes(k);
  const qtyNow = Number(vals.qty || (item?.qty ?? NaN));
  const problem = (k: string): string | null => {
    const raw = vals[k].trim();
    if (!raw) return null;
    const n = Number(raw);
    if (numeric(k) && !(n > 0)) return "Must be more than 0.";
    if (["qty", "units_per_carton", "cartons"].includes(k) && !Number.isInteger(n)) return "Must be a whole number.";
    if (k === "units_per_carton" && Number.isFinite(qtyNow) && n > qtyNow) return `Can't be more than the quantity (${qtyNow.toLocaleString()}).`;
    if (k === "hs_code" && !/^\d+$/.test(raw)) return "Digits only.";
    if (k === "hs_code" && raw.length < 6) return `Needs at least 6 digits (${raw.length} so far).`;
    if (k === "description" && raw.length >= ctx.limits.description_max) return `That's the maximum: ${ctx.limits.description_max} characters.`;
    return null;
  };
  const blocking = (k: string) => { const p = problem(k); return !!p && !p.startsWith("Needs at least") && !p.startsWith("That's the maximum"); };
  const bad = (k: string) => blocking(k);
  const canSave = (index !== null || vals.description.trim() !== "") && !ORDER.some(bad);
  function save() {
    const fields: Record<string, string> = {};
    for (const k of ORDER) if (vals[k].trim() !== "" && (index === null || vals[k] !== String((item as unknown as Record<string, unknown>)?.[k] ?? ""))) fields[k] = vals[k].trim();
    if (index !== null && Object.keys(fields).length === 0) { onDone?.(); return; }
    ctx.send({ type: "item", index, fields });
    onDone?.();
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {visible.map((k) => {
          const [label, ph, kind] = ctx.fields[k] ?? [k, "", "text", ""];
          return (
            <label key={k} className={cn("block", k === "description" && "sm:col-span-2")}>
              <span className="mb-1.5 flex items-center justify-between text-[12.5px] font-medium text-muted">
                {label}
                {k === "hs_code" && <a href={ctx.tariff} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-cyan hover:underline">Find my code <ExternalLink className="h-3 w-3" /></a>}
              </span>
              {kind === "choice" ? (
                <select value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} className="field h-12">
                  <option value="">Choose a country…</option>
                  {ctx.coo.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              ) : (
                <input value={vals[k]} inputMode={numeric(k) || k === "hs_code" ? "decimal" : undefined} placeholder={ph}
                  maxLength={k === "description" ? ctx.limits.description_max : k === "hs_code" ? ctx.limits.hs_max : undefined}
                  onChange={(e) => setVals({ ...vals, [k]: k === "hs_code" ? e.target.value.replace(/[^\d]/g, "") : e.target.value })}
                  onKeyDown={(e) => e.key === "Enter" && canSave && save()}
                  className={cn("field h-12", bad(k) && "border-bad/60")} />
              )}
              <Limit text={(ctx.fields[k]?.[3] ?? "") + (k === "description" && vals[k] ? ` (${vals[k].length}/${ctx.limits.description_max})` : "")} over={problem(k)} />
            </label>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!canSave || ctx.pending} onClick={save}>{index === null ? "Add product" : "Save details"} <ArrowRight className="h-4 w-4" /></Button>
        {!showAll && <button onClick={() => setShowAll(true)} className="press rounded-lg px-2 py-1 text-[13px] text-muted hover:text-fg">Show all fields</button>}
        {onDone && <button onClick={onDone} className="press rounded-lg px-2 py-1 text-[13px] text-muted hover:text-fg">Cancel</button>}
        <span className="text-[12px] text-faint">Not sure of something? Leave it blank and add it later.</span>
      </div>
    </div>
  );
}
