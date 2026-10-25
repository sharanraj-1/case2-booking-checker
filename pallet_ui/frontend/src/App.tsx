import { AnimatePresence, motion } from "framer-motion";
import { Info } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CommandPalette, Icons, type PaletteAction } from "./components/CommandPalette";
import { Ambient, ScrollProgress, Skeleton } from "./components/fx";
import { Nav, type Tab } from "./components/Nav";
import { EASE } from "./lib/cn";
import { connect, eventId, setFrameHeight, setValue } from "./streamlit";
import type { Payload, UIEvent } from "./types";
import { BookView } from "./views/BookView";
import { downloadB64, FileView } from "./views/FileView";

interface Pending { id: string; type: string; label?: string }

export default function App() {
  const [p, setP] = useState<Payload | null>(null);
  const [tab, setTab] = useState<Tab>("book");
  const [pending, setPending] = useState<Pending | null>(null);
  const [palette, setPalette] = useState(false);
  const [startedLocal, setStartedLocal] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingRef = useRef<Pending | null>(null);
  pendingRef.current = pending;

  useEffect(() => {
    const off = connect((args) => {
      const next = args.payload as Payload;
      setP(next);
      if (pendingRef.current && next.ack === pendingRef.current.id) setPending(null);
      if (next.flash) setToast(next.flash);
    });
    setFrameHeight(window.innerHeight);
    window.focus();
    return off;
  }, []);

  useEffect(() => {  // never leave the UI waiting forever
    if (!pending) return;
    const t = setTimeout(() => { setPending(null); setToast("That took too long. Please try again."); }, 60000);
    return () => clearTimeout(t);
  }, [pending]);

  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(null), 5000); return () => clearTimeout(t); } }, [toast]);

  const send = useCallback((ev: UIEvent) => {
    if (pendingRef.current) return;
    const id = eventId();
    const label = typeof ev.label === "string" ? ev.label : undefined;
    setPending({ id, type: ev.type, label });
    if (["sample", "upload"].includes(ev.type)) setTab("file");
    if (["say", "answer", "item"].includes(ev.type)) setStartedLocal(true);
    setValue({ ...ev, id });
  }, []);

  const goBook = useCallback(() => {
    setTab("book"); setStartedLocal(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => composerRef.current?.focus(), 450);
  }, []);
  const goFile = useCallback(() => { setTab("file"); window.scrollTo({ top: 0, behavior: "smooth" }); }, []);

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
  const ctx = { send, pending: !!pending, today: p.today, coo: p.coo_options, fields: p.item_fields, tariff: p.tariff_link };
  const pendingText = pending && ["say", "answer", "item", "edit", "remove_item", "fix"].includes(pending.type) && tab === "book"
    ? (pending.type === "say" || pending.type === "answer" ? pending.label ?? null : null) : null;

  return (
    <div className="relative min-h-screen">
      <Ambient />
      <ScrollProgress />
      <Nav tab={tab} setTab={(t) => { setTab(t); window.scrollTo({ top: 0, behavior: "smooth" }); }} ai={p.ai} onPalette={() => setPalette(true)} />
      <main className="mx-auto max-w-[1180px] px-4 pb-24 sm:px-6">
        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0, y: 14, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -10, filter: "blur(6px)" }} transition={{ duration: 0.45, ease: EASE }}>
            {tab === "book" ? (
              <BookView chat={p.chat} ctx={ctx} ai={p.ai} pendingText={pendingText} started={started} composerRef={composerRef}
                onStart={goBook} onFile={goFile} onConfirm={() => send({ type: "confirm" })}
                onReset={() => { send({ type: "reset" }); setStartedLocal(false); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
            ) : (
              <FileView file={p.file} send={send} pending={!!pending && ["sample", "upload", "file_clear"].includes(pending.type)} inputRef={fileInputRef} openId={openId} setOpenId={setOpenId} />
            )}
          </motion.div>
        </AnimatePresence>
        <footer className="mt-20 border-t border-white/6 pt-6 text-[12.5px] leading-relaxed text-faint">
          Rules, statuses, carrier picks and dates come from a fixed rulebook and rate card, worked out in code. {p.ai ? "The assistant only reads your messages; it never decides a result." : ""} Prices are the fixed rate card, not live quotes. Delivery dates are estimates in working days. Today in London: {p.today}.
        </footer>
      </main>
      <CommandPalette open={palette} setOpen={setPalette} actions={actions} />
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
