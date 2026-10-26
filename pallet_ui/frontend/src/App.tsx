import { AnimatePresence, motion } from "framer-motion";
import { Info } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CommandPalette, Icons, type PaletteAction } from "./components/CommandPalette";
import { Ambient, ScrollProgress, Skeleton } from "./components/fx";
import { Nav, type Tab } from "./components/Nav";
import { EASE } from "./lib/cn";
import { connect, eventId, healthUrl, setFrameHeight, setValue, standalone } from "./streamlit";
import type { Payload, UIEvent } from "./types";
import { BookView } from "./views/BookView";
import { downloadB64, FileView } from "./views/FileView";

interface Pending { id: string; type: string; label?: string }

/** The component is served by the Streamlit server; its health endpoint sits beside /component/. */
async function serverAlive(): Promise<boolean> {

  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), standalone ? 12000 : 4000);  // serverless may need a cold start
    const r = await fetch(healthUrl(), { cache: "no-store", signal: ctrl.signal });
    clearTimeout(t);
    return r.ok;
  } catch {
    return false;
  }
}

export default function App() {
  const [p, setP] = useState<Payload | null>(null);
  const [tab, setTab] = useState<Tab>("book");
  const [pending, setPending] = useState<Pending | null>(null);
  const [palette, setPalette] = useState(false);
  const [startedLocal, setStartedLocal] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  // Streamlit's frame has scrolling="no", so the app scrolls inside its own container.
  const scrollerRef = useRef<HTMLDivElement>(null);
  const toTop = useCallback(() => scrollerRef.current?.scrollTo({ top: 0, behavior: "smooth" }), []);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingRef = useRef<Pending | null>(null);
  pendingRef.current = pending;

  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const off = connect((args) => {
      const next = args.payload as Payload;
      setP(next);
      setOffline(false);
      if (pendingRef.current && next.ack === pendingRef.current.id) setPending(null);
      if (next.flash) setToast(next.flash);
    });
    setFrameHeight(window.innerHeight);
    window.focus();
    setTimeout(() => scrollerRef.current?.focus({ preventScroll: true }), 300);  // arrow keys / PageDown scroll
    return off;
  }, []);

  useEffect(() => {  // never leave the UI waiting forever
    if (!pending) return;
    const t = setTimeout(() => { setPending(null); setToast("That took too long. Please try again."); }, 60000);
    return () => clearTimeout(t);
  }, [pending]);

  const downloaded = useRef<string | null>(null);
  useEffect(() => {  // a file the server prepared (e.g. the draft invoice): save it once
    const d = p?.download;
    if (d && d.id !== downloaded.current) { downloaded.current = d.id; downloadB64(d.b64, d.name); setToast(`Downloaded ${d.name}`); }
  }, [p?.download]);

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 5000); return () => clearTimeout(t); } }, [toast]);

  const send = useCallback((ev: UIEvent) => {
    if (pendingRef.current) return;
    const id = eventId();
    const label = typeof ev.label === "string" ? ev.label : undefined;
    setPending({ id, type: ev.type, label });
    if (["sample", "upload"].includes(ev.type)) setTab("file");
    if (["say", "answer", "item"].includes(ev.type)) setStartedLocal(true);
    setValue({ ...ev, id });
    // If the Python server has stopped, say so instead of waiting silently.
    serverAlive().then((ok) => {
      if (!ok && pendingRef.current?.id === id) { setPending(null); setOffline(true); }
    });
  }, []);

  useEffect(() => {  // also notice a stopped server while idle
    const t = setInterval(() => serverAlive().then((ok) => setOffline(!ok)), 15000);
    return () => clearInterval(t);
  }, []);

  const goBook = useCallback(() => {
    setTab("book"); setStartedLocal(true);
    toTop();
    setTimeout(() => composerRef.current?.focus(), 450);
  }, [toTop]);
  const goFile = useCallback(() => { setTab("file"); toTop(); }, [toTop]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) { e.preventDefault(); goBook(); }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [goBook]);

  const actions: PaletteAction[] = useMemo(() => {
    const I = Icons;
    const list: PaletteAction[] = [
      { id: "book", group: "Go to", label: "Book a shipment", hint: "chat", icon: <I.MessageSquareText className="h-4 w-4" />, keys: ["/"], run: goBook },
      { id: "file", group: "Go to", label: "Check a bookings file", icon: <I.FileSpreadsheet className="h-4 w-4" />, run: goFile },
      { id: "new", group: "Actions", label: "Start a new booking", hint: "clears the current one", icon: <I.RotateCcw className="h-4 w-4" />, run: () => { send({ type: "reset" }); setStartedLocal(false); goBook(); } },
      { id: "upload", group: "Actions", label: "Upload a spreadsheet…", icon: <I.Upload className="h-4 w-4" />, run: () => { goFile(); setTimeout(() => fileInputRef.current?.click(), 300); } },
      { id: "sample", group: "Actions", label: "Try an example file", hint: "18 bookings, one mistake per rule", icon: <I.FlaskConical className="h-4 w-4" />, run: () => send({ type: "sample" }) },
    ];
    if (p?.chat.complete && !p.chat.confirmed) list.push({ id: "confirm", group: "Actions", label: "Confirm my booking", icon: <I.CheckCircle2 className="h-4 w-4" />, run: () => { goBook(); send({ type: "confirm" }); } });
    if (p?.file?.xlsx) list.push({ id: "dl", group: "Actions", label: "Download results (.xlsx)", icon: <I.Download className="h-4 w-4" />, run: () => downloadB64(p.file!.xlsx!, "preflight_results.xlsx") });
    for (const r of p?.file?.rows ?? []) {
      list.push({ id: `bk-${r.id}`, group: "Bookings in your file", label: `${r.id} · ${r.seller}`, hint: r.label, icon: <I.ArrowRight className="h-4 w-4" />, run: () => { setTab("file"); setOpenId(r.id); } });
    }
    return list;
  }, [p, goBook, goFile, send]);

  if (!p) {
    return (
      <div className="mx-auto max-w-[1180px] space-y-5 px-5 pt-32">
        <Ambient />
        <Skeleton className="h-14 w-[70%] rounded-2xl" /><Skeleton className="h-14 w-[50%] rounded-2xl" /><Skeleton className="h-5 w-[40%]" />
        <div className="grid grid-cols-1 gap-4 pt-6 lg:grid-cols-[1.35fr_1fr]"><Skeleton className="h-[420px] rounded-3xl" /><Skeleton className="h-[420px] rounded-3xl" /></div>
      </div>
    );
  }

  const started = startedLocal || p.chat.messages.length > 1;
  const ctx = { send, pending: !!pending, pendingType: pending?.type ?? null, today: p.today, coo: p.coo_options, fields: p.item_fields, tariff: p.tariff_link, limits: p.limits };
  const pendingText = pending && ["say", "answer", "item", "edit", "remove_item", "fix"].includes(pending.type) && tab === "book"
    ? (pending.type === "say" || pending.type === "answer" ? pending.label ?? null : null) : null;

  return (
    <div ref={scrollerRef} tabIndex={-1} className="scroll-thin relative h-[100dvh] overflow-y-auto overflow-x-hidden overscroll-contain outline-none">
      <Ambient />
      <ScrollProgress container={scrollerRef} />
      <Nav tab={tab} setTab={(t) => { setTab(t); toTop(); }} ai={p.ai} onPalette={() => setPalette(true)} />
      <main className="mx-auto max-w-[1180px] px-4 pb-24 sm:px-6">
        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.35, ease: EASE }}>
            {tab === "book" ? (
              <BookView chat={p.chat} ctx={ctx} ai={p.ai} pendingText={pendingText} started={started} composerRef={composerRef}
                onStart={goBook} onFile={goFile} onConfirm={() => send({ type: "confirm" })}
                onReset={() => { send({ type: "reset" }); setStartedLocal(false); toTop(); }} />
            ) : (
              <FileView file={p.file} send={send} uploadMb={p.limits.upload_mb} pendingType={pending?.type ?? null} pending={!!pending && ["sample", "upload", "file_clear"].includes(pending.type)} inputRef={fileInputRef} openId={openId} setOpenId={setOpenId} />
            )}
          </motion.div>
        </AnimatePresence>
        <footer className="mt-20 border-t border-white/6 pt-6 text-[12.5px] leading-relaxed text-faint">
          Rules, statuses, carrier picks and dates come from a fixed rulebook and rate card, worked out in code. {p.ai ? "The assistant only reads your messages and only answers from checked guidance; it never decides a result." : ""} Our carrier pick uses the fixed rate card; live market prices are shown for reference only. Delivery dates are estimates in working days. Today in London: {p.today}.
        </footer>
      </main>
      <CommandPalette open={palette} setOpen={setPalette} actions={actions} />
      <AnimatePresence>
        {offline && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="fixed inset-x-0 bottom-5 z-[95] flex justify-center px-4">
            <div role="alert" className="glass-strong flex max-w-[620px] flex-wrap items-center gap-3 rounded-2xl border-bad/40 px-5 py-4 text-[14px]">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-bad shadow-[0_0_12px_#f87171]" />
              <span className="min-w-0 flex-1">
                <span className="font-semibold text-white">Can't reach the app.</span>{" "}
                <span className="text-muted">{standalone ? "The server isn't responding or your connection dropped. Please try again in a moment." : <>The server has stopped or the connection dropped. Start it again with <code className="font-mono text-fg">streamlit run app.py</code>, then reload.</>}</span>
              </span>
              <button onClick={() => { try { window.parent.location.reload(); } catch { window.location.reload(); } }}
                className="press rounded-xl bg-white/10 px-3.5 py-2 text-[13px] font-medium hover:bg-white/15">Reload page</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {toast && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }} className="fixed inset-x-0 bottom-5 z-[90] flex justify-center px-4">
            <div className="glass-strong flex max-w-[560px] items-start gap-2.5 rounded-2xl px-4 py-3 text-[14px]"><Info className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />{toast}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
