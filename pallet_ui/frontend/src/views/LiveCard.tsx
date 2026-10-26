// "Your booking": live summary that the seller can tap to change. Updates after every answer.
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, ChevronRight, CircleDashed, Minus, Pencil, Plus, Sparkles, Trash2, X } from "lucide-react";
import { useState } from "react";
import { Button, Limit, Pill } from "../components/fx";
import { Flag } from "../components/Icon";
import { cn, EASE, focusEl, niceDate, softFocus, toDDMMYYYY, toISO } from "../lib/cn";
import type { ChatView, Row } from "../types";
import { ItemForm, type AskCtx } from "./Ask";

function Progress({ done, total }: { done: number; total: number }) {
  const pct = total ? done / total : 0;
  const r = 20, c = 2 * Math.PI * r;
  return (
    <div className="relative h-12 w-12">
      <svg viewBox="0 0 48 48" className="h-full w-full -rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="4" />
        <motion.circle cx="24" cy="24" r={r} fill="none" stroke="url(#pg)" strokeWidth="4" strokeLinecap="round" strokeDasharray={c}
          animate={{ strokeDashoffset: c * (1 - pct) }} transition={{ duration: 0.8, ease: EASE }} />
        <defs><linearGradient id="pg" x1="0" x2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      </svg>
      <div className="absolute inset-0 grid place-items-center text-[11px] font-semibold">{Math.round(pct * 100)}%</div>
    </div>
  );
}

function Route({ rows }: { rows: Row[] }) {
  const from = rows.find((r) => r.key === "origin_city")?.display?.replace(", UK", "") ?? "UK";
  const toRow = rows.find((r) => r.key === "dest_city")?.display ?? "";
  const to = toRow.split(",")[0] || "Europe";
  const code = { Germany: "DE", France: "FR", Netherlands: "NL" }[toRow.split(", ")[1] ?? ""] ?? "";
  return (
    <div className="relative mt-4 flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.025] px-4 py-3.5">
      <div className="min-w-0"><div className="text-[10.5px] uppercase tracking-[0.1em] text-faint">From</div><div className="flex items-center gap-1.5 truncate text-[15px] font-semibold"><Flag code="GB" /> {from}</div></div>
      <svg className="h-6 flex-1" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden>
        <path d="M2 12 C 30 0, 70 24, 98 12" fill="none" stroke="url(#rg)" strokeWidth="1.5" className="route-dash" />
        <defs><linearGradient id="rg" x1="0" x2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
        <circle r="2.6" fill="#fff"><animateMotion dur="3s" repeatCount="indefinite" path="M2 12 C 30 0, 70 24, 98 12" /></circle>
      </svg>
      <div className="min-w-0 text-right"><div className="text-[10.5px] uppercase tracking-[0.1em] text-faint">To</div><div className="flex items-center justify-end gap-1.5 truncate text-[15px] font-semibold">{to} {code && <Flag code={code} />}</div></div>
    </div>
  );
}

function Editor({ row, ctx, close }: { row: Row; ctx: AskCtx; close: () => void }) {
  const [v, setV] = useState(row.kind === "date" ? toISO(String(row.raw ?? "")) : row.raw != null ? String(row.raw) : "");
  const commit = (value: string, label?: string) => { if (value.trim()) { ctx.send({ type: "edit", field: row.key, value, label: label ?? value }); close(); } };
  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: EASE }} className="overflow-hidden">
      <div className="pb-3 pt-1">
        <Limit text={row.limit} className="mb-2 mt-0" />
        {row.kind === "choice" ? (
          <div className="flex flex-wrap gap-1.5">
            {(row.options ?? []).map((o) => (
              <button key={o} onClick={() => commit(o)} className={cn("press rounded-xl border px-3 py-1.5 text-[13px]", String(row.raw) === o ? "border-violet/60 bg-violet/15" : "border-white/10 bg-white/[0.04] hover:bg-white/[0.08]")}>{o}</button>
            ))}
          </div>
        ) : (
          <div className="flex gap-2">
            <input ref={softFocus} type={row.kind === "date" ? "date" : "text"} inputMode={row.kind === "number" || row.kind === "stepper" ? "decimal" : undefined} value={v} onChange={(e) => setV(e.target.value)}
              maxLength={row.key === "seller" ? ctx.limits.seller_max : 40} min={row.kind === "date" ? toISO(ctx.today) : undefined}
              onKeyDown={(e) => e.key === "Enter" && commit(row.kind === "date" ? toDDMMYYYY(v) : v)} className="field h-10 flex-1 text-[14px]" />
            <Button size="sm" onClick={() => commit(row.kind === "date" ? toDDMMYYYY(v) : v)}>Save</Button>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export function LiveCard({ chat, ctx }: { chat: ChatView; ctx: AskCtx }) {
  const [open, setOpen] = useState<string | null>(null);
  const [editItem, setEditItem] = useState<number | null>(null);
  const r = chat.result;
  const answered = (k: string) => !!chat.rows.find((x) => x.key === k)?.display;
  const loadKnown = answered("pallets") && answered("gross_kg");
  const pick = loadKnown ? r?.options.find((o) => o.picked) : undefined;
  // Which answers each check needs; until they're in, the check shows as waiting rather than failing.
  const needs: Record<string, string[]> = { "R-05": ["pallets", "gross_kg"], "R-07": ["gross_kg"], "R-08": ["dest_type"], "R-10": ["ready_date"] };
  const waiting = (id: string) => !chat.complete && (needs[id] ?? []).some((k) => !answered(k));
  const ruleIcon = { Pass: <Check className="h-3 w-3 text-good" />, Red: <X className="h-3 w-3 text-bad" />, Amber: <AlertTriangle className="h-3 w-3 text-warn" />, Data: <CircleDashed className="h-3 w-3 text-faint" /> };
  return (
    <div className="glass rounded-3xl p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[17px] font-semibold tracking-[-0.02em]">Your booking</div>
          <div className="text-[12.5px] text-muted">{chat.complete ? "All details in. Tap anything to change it." : "Fills in as you answer. Tap any line to change it."}</div>
        </div>
        {chat.complete && r ? <Pill tone={r.view.tone}>{r.view.label}</Pill> : <Progress done={chat.progress.done} total={chat.progress.total} />}
      </div>
      <Route rows={chat.rows} />
      <div className="mt-3 divide-y divide-white/6">
        {chat.rows.map((row) => (
          <div key={row.key}>
            <div className={cn("-mx-2 flex min-h-[46px] items-center gap-2 rounded-xl px-2 transition-colors", row.kind !== "stepper" && "cursor-pointer hover:bg-white/[0.05]", open === row.key && "bg-white/[0.05]")}
              onClick={() => row.kind !== "stepper" || row.raw == null ? setOpen(open === row.key ? null : row.key) : undefined}
              role={row.kind !== "stepper" || row.raw == null ? "button" : undefined} tabIndex={row.kind !== "stepper" || row.raw == null ? 0 : undefined}
              onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && (row.kind !== "stepper" || row.raw == null)) { e.preventDefault(); setOpen(open === row.key ? null : row.key); } }}>
              <span className="flex-1 text-[13.5px] text-muted">{row.label}{row.calculated && <span className="ml-1.5 text-[11px] text-faint">(calculated)</span>}</span>
              {row.kind === "stepper" && row.raw != null ? (
                <span className="flex items-center gap-1.5">
                  <motion.button whileTap={{ scale: 0.85 }} disabled={ctx.pending || Number(row.raw) <= 1} aria-label="One fewer pallet"
                    onClick={() => ctx.send({ type: "edit", field: "pallets", value: "-1", label: String(Number(row.raw) - 1) })}
                    className="grid h-9 w-9 cursor-pointer place-items-center rounded-xl border border-white/10 bg-white/[0.05] transition-colors hover:border-violet/50 hover:bg-violet/[0.1] disabled:cursor-not-allowed disabled:opacity-40"><Minus className="h-4 w-4" /></motion.button>
                  <motion.span key={String(row.raw)} initial={{ y: -8, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="w-8 text-center text-[14px] font-semibold">{row.display}</motion.span>
                  <motion.button whileTap={{ scale: 0.85 }} disabled={ctx.pending} aria-label="One more pallet"
                    onClick={() => ctx.send({ type: "edit", field: "pallets", value: "+1", label: String(Number(row.raw) + 1) })}
                    className="grid h-9 w-9 cursor-pointer place-items-center rounded-xl border border-white/10 bg-white/[0.05] transition-colors hover:border-violet/50 hover:bg-violet/[0.1] disabled:cursor-not-allowed disabled:opacity-40"><Plus className="h-4 w-4" /></motion.button>
                </span>
              ) : (
                <span className="group flex max-w-[62%] items-center gap-1.5 text-right">
                  {row.display ? <span className="truncate text-[14px] font-medium">{row.kind === "date" ? niceDate(row.display) : row.display}</span>
                    : <span className={cn("text-[13px]", row.missing ? "font-medium text-warn" : "text-faint")}>{row.missing ? "Tap to add" : row.key === "cartons" || row.key === "declared_value" ? "From products" : "—"}</span>}
                  <ChevronRight className={cn("h-3.5 w-3.5 text-faint transition-transform", open === row.key && "rotate-90")} />
                </span>
              )}
            </div>
            <AnimatePresence>{open === row.key && <div onClick={(e) => e.stopPropagation()}><Editor row={row} ctx={ctx} close={() => setOpen(null)} /></div>}</AnimatePresence>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[13px] font-medium">Products</span>
          {chat.items.length > 0 && <button onClick={() => setEditItem(-1)} className="tile flex items-center gap-1 rounded-xl border border-cyan/25 bg-cyan/[0.06] px-2.5 py-1.5 text-[12.5px] text-cyan"><Plus className="h-3.5 w-3.5" /> Add another</button>}
        </div>
        {chat.items.length === 0 && <div className="rounded-2xl border border-dashed border-white/12 p-3 text-[13px] text-faint">No products yet.</div>}
        <div className="space-y-2">
          {chat.items.map((it) => (
            <div key={it.index} className={cn("rounded-2xl border bg-white/[0.03] p-3 transition-colors", editItem === it.index ? "border-violet/40" : "border-white/8 hover:border-white/15")}>
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1 cursor-pointer" role="button" tabIndex={0} onClick={() => setEditItem(editItem === it.index ? null : it.index)}
                  onKeyDown={(e) => { if (e.key === "Enter") setEditItem(editItem === it.index ? null : it.index); }}>
                  <div className="truncate text-[14px] font-medium">{it.description || "Product"}</div>
                  <div className="text-[12.5px] text-muted">
                    {[it.qty != null && `${it.qty.toLocaleString()} units`, it.unit_price != null && `£${it.unit_price}`, it.cartons != null && `${it.cartons} boxes`, it.hs_code && `HS ${it.hs_code}`].filter(Boolean).join(" · ") || "Details needed"}
                  </div>
                  {it.missing.length > 0 && <div className="mt-1 text-[12px] text-warn">{it.missing.length} detail{it.missing.length > 1 ? "s" : ""} still needed</div>}
                </div>
                <button aria-label="Edit product" onClick={() => setEditItem(editItem === it.index ? null : it.index)} className="tile grid h-9 w-9 place-items-center rounded-xl border border-white/8 text-muted hover:text-fg"><Pencil className="h-3.5 w-3.5" /></button>
                <button aria-label="Remove product" disabled={ctx.pending} onClick={() => ctx.send({ type: "remove_item", index: it.index })} className="tile grid h-9 w-9 place-items-center rounded-xl border border-white/8 text-muted hover:text-bad"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
              <AnimatePresence>
                {editItem === it.index && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="pt-3"><ItemForm ctx={ctx} index={it.index} item={it} onDone={() => setEditItem(null)} /></div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
          <AnimatePresence>
            {editItem === -1 && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3"><ItemForm ctx={ctx} index={null} onDone={() => setEditItem(null)} /></div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {r && (
        <div className="mt-5">
          <div className="mb-2 text-[13px] font-medium">Live checks</div>
          <div className="grid grid-cols-2 gap-1.5">
            {r.rules.map((x) => (
              <button key={x.id} title={`${x.id}: ${x.why}`} onClick={() => { if (!focusEl(`f-${x.id}`)) focusEl("checks-grid"); }}
                className="tile flex min-h-[36px] items-center gap-1.5 rounded-xl border border-white/6 bg-white/[0.02] px-2 py-1.5 text-[12px]">
                {waiting(x.id) ? ruleIcon.Data : ruleIcon[x.state]}
                <span className={cn("truncate", waiting(x.id) ? "text-faint" : x.state === "Pass" ? "text-fg/80" : x.state === "Data" ? "text-faint" : "text-fg")}>{x.name}</span>
              </button>
            ))}
          </div>
          {pick && (
            <motion.div key={pick.carrier + (r.confirmation.cost ?? "")} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              className="mt-3 flex items-center gap-3 rounded-2xl border border-cyan/20 bg-cyan/[0.06] p-3">
              <Sparkles className="h-4 w-4 shrink-0 text-cyan" />
              <div className="text-[13px] leading-snug"><span className="font-semibold">{pick.carrier}</span> · {r.confirmation.cost ?? pick.cost_label}
                {r.confirmation.eta && <span className="text-muted"> · arrives {niceDate(r.confirmation.eta)}</span>}</div>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}
