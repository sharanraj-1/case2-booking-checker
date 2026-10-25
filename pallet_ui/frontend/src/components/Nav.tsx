import { motion } from "framer-motion";
import { Command as CmdIcon, FileSpreadsheet, MessageSquareText, Package } from "lucide-react";
import { cn, EASE } from "../lib/cn";
import { ToneDot } from "./fx";

export type Tab = "book" | "file";

export function Nav({ tab, setTab, ai, onPalette }: { tab: Tab; setTab: (t: Tab) => void; ai: boolean; onPalette: () => void }) {
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  const tabs: { id: Tab; label: string; short: string; icon: typeof Package }[] = [
    { id: "book", label: "Book a shipment", short: "Book", icon: MessageSquareText },
    { id: "file", label: "Check a file", short: "File", icon: FileSpreadsheet },
  ];
  return (
    <motion.header
      initial={{ y: -30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, ease: EASE }}
      className="fixed inset-x-0 top-3 z-50 flex justify-center px-3 sm:top-5"
    >
      <nav className="glass-strong flex w-full max-w-[760px] items-center gap-1 rounded-full p-1.5 pl-2.5 sm:gap-2">
        <div className="flex items-center gap-2 pr-1 sm:pr-2">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-[linear-gradient(135deg,#8b5cf6,#22d3ee)] shadow-[0_0_20px_rgba(139,92,246,0.5)]">
            <Package className="h-4 w-4 text-white" strokeWidth={2.2} />
          </div>
          <span className="hidden text-[15px] font-semibold tracking-[-0.02em] md:inline">Pre-Flight</span>
        </div>
        <div className="relative flex flex-1 items-center justify-center gap-1 sm:flex-none">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={cn("press relative flex h-9 items-center gap-2 rounded-full px-3.5 text-[13.5px] font-medium transition-colors sm:px-4",
                tab === t.id ? "text-white" : "text-muted hover:text-fg")}>
              {tab === t.id && (
                <motion.span layoutId="tab-pill" transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  className="absolute inset-0 rounded-full border border-white/12 bg-white/[0.09] shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]" />
              )}
              <t.icon className="relative h-4 w-4" />
              <span className="relative hidden sm:inline">{t.label}</span>
              <span className="relative sm:hidden">{t.short}</span>
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="hidden items-center gap-2 rounded-full px-2.5 text-[12px] text-muted lg:flex" title={ai ? "Type freely; the assistant understands plain English." : "Tap the options or type short answers."}>
            <ToneDot tone={ai ? "green" : "gray"} pulse={ai} /> {ai ? "Assistant on" : "Guided mode"}
          </span>
          <button onClick={onPalette} aria-label="Open command menu"
            className="press flex h-9 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.05] px-2.5 text-[12px] text-muted hover:text-fg">
            <CmdIcon className="h-3.5 w-3.5 sm:hidden" />
            <span className="hidden items-center gap-1 sm:flex"><kbd>{isMac ? "⌘" : "Ctrl"}</kbd><kbd>K</kbd></span>
          </button>
        </div>
      </nav>
    </motion.header>
  );
}
