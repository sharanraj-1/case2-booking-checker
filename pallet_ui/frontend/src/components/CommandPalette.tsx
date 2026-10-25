import { Command } from "cmdk";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Download, FileSpreadsheet, FlaskConical, MessageSquareText, RotateCcw, Search, Upload } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { EASE } from "../lib/cn";

export interface PaletteAction { id: string; label: string; hint?: string; icon: ReactNode; keys?: string[]; group: string; run: () => void }

export const Icons = { MessageSquareText, FileSpreadsheet, RotateCcw, Upload, Download, FlaskConical, CheckCircle2, ArrowRight };

export function CommandPalette({ open, setOpen, actions }: { open: boolean; setOpen: (v: boolean) => void; actions: PaletteAction[] }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open); }
      if (e.key === "Escape" && open) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const groups = Array.from(new Set(actions.map((a) => a.group)));
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[80] flex items-start justify-center px-3 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <motion.div initial={{ opacity: 0, y: -14, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.35, ease: EASE }} className="glass-strong relative w-full max-w-[600px] overflow-hidden rounded-3xl">
            <Command label="Command menu" loop>
              <div className="flex items-center gap-3 border-b border-white/8 px-4">
                <Search className="h-4 w-4 text-muted" />
                <Command.Input autoFocus placeholder="What do you want to do?" className="h-14 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-faint" />
                <kbd>Esc</kbd>
              </div>
              <Command.List className="scroll-thin max-h-[52vh] overflow-y-auto p-2">
                <Command.Empty className="px-4 py-10 text-center text-[14px] text-muted">Nothing found. Try "book", "file" or a booking ID.</Command.Empty>
                {groups.map((g) => (
                  <Command.Group key={g} heading={g} className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.08em] [&_[cmdk-group-heading]]:text-faint">
                    {actions.filter((a) => a.group === g).map((a) => (
                      <Command.Item key={a.id} value={`${a.label} ${a.hint ?? ""}`} onSelect={() => { setOpen(false); a.run(); }}
                        className="group flex cursor-pointer items-center gap-3 rounded-2xl px-3 py-2.5 text-[14px] text-fg/90 data-[selected=true]:bg-white/[0.08] data-[selected=true]:text-white">
                        <span className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.05] text-muted group-data-[selected=true]:text-cyan">{a.icon}</span>
                        <span className="flex-1">
                          {a.label}
                          {a.hint && <span className="ml-2 text-[12.5px] text-faint">{a.hint}</span>}
                        </span>
                        {a.keys && <span className="flex gap-1">{a.keys.map((k) => <kbd key={k}>{k}</kbd>)}</span>}
                      </Command.Item>
                    ))}
                  </Command.Group>
                ))}
              </Command.List>
              <div className="flex items-center justify-between border-t border-white/8 px-4 py-2.5 text-[11.5px] text-faint">
                <span className="flex items-center gap-1.5"><kbd>↑</kbd><kbd>↓</kbd> move <kbd>↵</kbd> open</span>
                <span>Pallet Pre-Flight</span>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
