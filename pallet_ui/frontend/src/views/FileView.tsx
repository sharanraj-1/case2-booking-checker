// Check a file: drop zone, summary counters, booking list, slide-over with the full results.
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronRight, Download, FileSpreadsheet, FlaskConical, Pencil, RotateCcw, UploadCloud, X, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button, Counter, Pill, Reveal, Skeleton, TiltCard } from "../components/fx";
import { cn } from "../lib/cn";
import type { FileView as FV, Send } from "../types";
import { Results } from "./Results";

function readFiles(files: FileList | File[]): Promise<{ name: string; b64: string }[]> {
  return Promise.all(Array.from(files).map((f) => new Promise<{ name: string; b64: string }>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve({ name: f.name, b64: String(r.result).split(",")[1] ?? "" });
    r.onerror = reject;
    r.readAsDataURL(f);
  })));
}

export function downloadB64(b64: string, name: string) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function FileView({ file, send, pending, inputRef, openId, setOpenId }: {
  file: FV | null; send: Send; pending: boolean; inputRef: React.RefObject<HTMLInputElement>; openId: string | null; setOpenId: (id: string | null) => void;
}) {
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function upload(list: FileList | File[] | null) {
    if (!list || !list.length) return;
    const arr = Array.from(list);
    if (arr.some((f) => f.size > 15 * 1024 * 1024)) { setErr("That file is over 15 MB. Please upload just the Bookings and Items sheets."); return; }
    setErr(null);
    try { send({ type: "upload", files: await readFiles(arr) }); } catch { setErr("We couldn't read that file. Please try again."); }
  }
  const open = openId && file?.results[openId];

  return (
    <div className="pt-28 sm:pt-32">
      <Reveal>
        <h1 className="text-[36px] font-semibold leading-[1.05] tracking-[-0.04em] sm:text-[48px]">Check a <span className="text-gradient">bookings file</span></h1>
        <p className="mt-3 max-w-[620px] text-[16px] leading-relaxed text-muted">Upload your spreadsheet. We check every booking against the 10 rules, say exactly what to fix, and pick a carrier for each one. Your file is never changed.</p>
      </Reveal>

      <input ref={inputRef} type="file" multiple accept=".xlsx,.xlsm,.csv" className="hidden" onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />

      {!file && !pending && (
        <Reveal i={1}>
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}
            className={cn("mt-8 rounded-[28px] transition-all", drag && "glow-border scale-[1.01]")}>
            <div className={cn("glass flex flex-col items-center rounded-[28px] border-2 border-dashed px-6 py-14 text-center transition-colors", drag ? "border-violet/60 bg-violet/[0.06]" : "border-white/12")}>
              <motion.div animate={{ y: [0, -6, 0] }} transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                className="grid h-16 w-16 place-items-center rounded-2xl bg-[linear-gradient(135deg,rgba(139,92,246,0.25),rgba(34,211,238,0.2))] shadow-[0_0_40px_rgba(139,92,246,0.3)]">
                <UploadCloud className="h-7 w-7 text-white" />
              </motion.div>
              <div className="mt-5 text-[20px] font-semibold tracking-[-0.02em]">Drop your Excel file here</div>
              <div className="mt-1.5 max-w-[480px] text-[14px] text-muted">One .xlsx with a <b className="text-fg">Bookings</b> sheet and an <b className="text-fg">Items</b> sheet, or two CSV files.</div>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <Button size="lg" glow onClick={() => inputRef.current?.click()}><FileSpreadsheet className="h-4.5 w-4.5" /> Choose file</Button>
                <Button size="lg" variant="ghost" onClick={() => send({ type: "sample" })}><FlaskConical className="h-4.5 w-4.5" /> No file? Try an example</Button>
              </div>
              {err && <div className="mt-4 text-[13.5px] text-bad">{err}</div>}
            </div>
          </div>
        </Reveal>
      )}

      {pending && (
        <div className="mt-8 space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[104px] rounded-3xl" />)}</div>
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-[76px] rounded-2xl" />)}
        </div>
      )}

      {file && !pending && (
        <div className="mt-8 space-y-6">
          <Reveal>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.05]"><FileSpreadsheet className="h-5 w-5 text-cyan" /></div>
                <div className="min-w-0"><div className="truncate text-[15px] font-medium">{file.label}</div><div className="text-[12.5px] text-muted">{file.counts.total} booking{file.counts.total === 1 ? "" : "s"} checked</div></div>
              </div>
              {file.xlsx && <Button variant="soft" onClick={() => downloadB64(file.xlsx!, "preflight_results.xlsx")}><Download className="h-4 w-4" /> Download results</Button>}
              <Button variant="ghost" onClick={() => { setOpenId(null); send({ type: "file_clear" }); }}><RotateCcw className="h-4 w-4" /> Check another file</Button>
            </div>
          </Reveal>

          {file.notices.length > 0 && (
            <Reveal i={1}>
              <div className={cn("rounded-2xl border p-4", file.notices.some((n) => n.level === "error") ? "border-bad/30 bg-bad/[0.07]" : "border-warn/25 bg-warn/[0.06]")}>
                <div className="mb-1.5 flex items-center gap-2 text-[14px] font-medium"><AlertTriangle className="h-4 w-4 text-warn" /> Things we noticed in the file</div>
                <ul className="space-y-1 pl-6 text-[13.5px] text-fg/85">{file.notices.map((n, i) => <li key={i} className="list-disc">{n.message}</li>)}</ul>
              </div>
            </Reveal>
          )}

          {file.counts.total > 0 && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                { label: "Bookings", v: file.counts.total, icon: <FileSpreadsheet className="h-4 w-4 text-cyan" />, sub: "in this file" },
                { label: "Can't ship yet", v: file.counts.Blocked, icon: <XCircle className="h-4 w-4 text-bad" />, sub: "need fixing first" },
                { label: "OK to ship", v: file.counts["Ready with warnings"], icon: <AlertTriangle className="h-4 w-4 text-warn" />, sub: "small things to sort" },
                { label: "Good to go", v: file.counts.Ready, icon: <CheckCircle2 className="h-4 w-4 text-good" />, sub: "all checks passed" },
              ].map((m, i) => (
                <Reveal key={m.label} i={i}>
                  <TiltCard max={5} className="p-5">
                    <div className="flex items-center gap-2 text-[12.5px] text-muted">{m.icon}{m.label}</div>
                    <div className="mt-2 text-[38px] font-semibold leading-none tracking-[-0.04em]"><Counter value={m.v} /></div>
                    <div className="mt-1 text-[12px] text-faint">{m.sub}</div>
                  </TiltCard>
                </Reveal>
              ))}
            </div>
          )}

          <div className="space-y-2.5">
            {file.rows.map((r, i) => (
              <Reveal key={r.id} i={i}>
                <motion.button whileHover={{ x: 3 }} whileTap={{ scale: 0.99 }} onClick={() => setOpenId(r.id)}
                  className="glass group flex w-full items-center gap-4 rounded-2xl p-4 text-left transition-colors hover:bg-white/[0.07]">
                  <span className={cn("h-10 w-1 shrink-0 rounded-full", { red: "bg-bad", amber: "bg-warn", green: "bg-good" }[r.tone])} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[12.5px] text-muted">{r.id}</span>
                      <span className="truncate text-[15px] font-medium">{r.seller || "—"}</span>
                      {r.edited && <Pill tone="cyan"><Pencil className="h-3 w-3" /> changed here</Pill>}
                    </div>
                    <div className="mt-0.5 truncate text-[13px] text-muted">{r.route}</div>
                  </div>
                  <div className="hidden text-right sm:block">
                    <div className="text-[13.5px] font-medium">{r.carrier ?? "—"} · {r.cost}</div>
                    <div className="text-[12px] text-faint">arrives {r.eta}</div>
                  </div>
                  <Pill tone={r.tone} className="shrink-0">{r.label}{r.problems ? ` · ${r.problems}` : r.warnings ? ` · ${r.warnings}` : ""}</Pill>
                  <ChevronRight className="h-4 w-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5" />
                </motion.button>
              </Reveal>
            ))}
          </div>
        </div>
      )}

      <Drawer open={!!open} onClose={() => setOpenId(null)} title={open ? `${open.id} · ${open.confirmation.seller}` : ""}
        extra={open && file?.rows.find((x) => x.id === openId)?.edited ? (
          <Button size="sm" variant="soft" onClick={() => send({ type: "file_undo", booking_id: openId })}><RotateCcw className="h-3.5 w-3.5" /> Undo my changes</Button>) : null}>
        {open && <Results r={open} pending={pending} onFix={(a) => send({ type: "fix", scope: "file", booking_id: openId, action: a })} />}
      </Drawer>
    </div>
  );
}

function Drawer({ open, onClose, title, children, extra }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; extra?: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", k); document.body.style.overflow = ""; };
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
          <motion.div ref={ref} initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 260, damping: 32 }}
            className="glass-strong scroll-thin absolute bottom-0 right-0 top-0 w-full max-w-[980px] overflow-y-auto rounded-l-[28px] max-sm:rounded-none">
            <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-white/8 bg-ink/70 px-5 py-4 backdrop-blur-xl sm:px-7">
              <div className="min-w-0 flex-1 truncate text-[16px] font-semibold tracking-[-0.02em]">{title}</div>
              {extra}
              <button onClick={onClose} aria-label="Close" className="press grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/[0.05] hover:bg-white/[0.1]"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-6 sm:px-7">{children}</div>
            <div className="px-7 pb-8"><button onClick={onClose} className="press flex items-center gap-1.5 text-[13px] text-muted hover:text-fg">Back to all bookings <ArrowRight className="h-3.5 w-3.5" /></button></div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
