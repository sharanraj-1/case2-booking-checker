// Visual building blocks: ambient light, scroll progress, reveal, tilt, magnetic buttons, skeletons.
import { motion, useMotionValue, useReducedMotion, useScroll, useSpring, type HTMLMotionProps } from "framer-motion";
import { forwardRef, useRef, type ReactNode, type MouseEvent as RMouseEvent } from "react";
import { cn, EASE } from "../lib/cn";

export function Ambient() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(139,92,246,0.10),transparent_55%)]" />
      <div className="orb drift-a" style={{ width: "46vw", height: "46vw", left: "-12vw", top: "-14vw", background: "#8b5cf6" }} />
      <div className="orb drift-b" style={{ width: "40vw", height: "40vw", right: "-10vw", top: "18vh", background: "#22d3ee" }} />
      <div className="orb drift-c" style={{ width: "36vw", height: "36vw", left: "28vw", bottom: "-18vw", background: "#f43f5e" }} />
      <div className="absolute inset-0 opacity-[0.035] [background-image:linear-gradient(rgba(255,255,255,.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.6)_1px,transparent_1px)] [background-size:56px_56px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
    </div>
  );
}

export function ScrollProgress({ container }: { container: React.RefObject<HTMLElement> }) {
  const { scrollYProgress } = useScroll({ container });
  const x = useSpring(scrollYProgress, { stiffness: 140, damping: 30, mass: 0.3 });
  return (
    <motion.div
      aria-hidden
      style={{ scaleX: x, transformOrigin: "0% 50%" }}
      className="fixed left-0 right-0 top-0 z-[60] h-[2px] bg-gradient-to-r from-violet via-cyan to-rose"
    />
  );
}

/** Fade-and-slide in when scrolled into view; pass `i` for a 50ms stagger. */
export function Reveal({ children, i = 0, className, as = "div" }: { children: ReactNode; i?: number; className?: string; as?: "div" | "li" | "section" }) {
  const reduce = useReducedMotion();
  const Comp = motion[as];
  return (
    <Comp
      className={className}
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -40px 0px" }}
      transition={{ duration: 0.6, ease: EASE, delay: Math.min(i, 12) * 0.05 }}
    >
      {children}
    </Comp>
  );
}

/** Card with cursor-tracking 3D tilt and a specular sheen. */
export function TiltCard({ children, className, max = 7, glow }: { children: ReactNode; className?: string; max?: number; glow?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const rx = useSpring(useMotionValue(0), { stiffness: 180, damping: 18 });
  const ry = useSpring(useMotionValue(0), { stiffness: 180, damping: 18 });
  function onMove(e: RMouseEvent) {
    if (reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
    ry.set((px - 0.5) * max * 2);
    rx.set(-(py - 0.5) * max * 2);
    ref.current.style.setProperty("--mx", `${px * 100}%`);
    ref.current.style.setProperty("--my", `${py * 100}%`);
  }
  return (
    <div style={{ perspective: 1000 }} className="h-full">
      <motion.div
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={() => { rx.set(0); ry.set(0); }}
        style={{ rotateX: rx, rotateY: ry }}
        className={cn("tilt glass relative h-full rounded-3xl", glow && "glow-border", className)}
      >
        <div className="sheen" />
        <div className="relative h-full" style={{ transform: "translateZ(24px)" }}>{children}</div>
      </motion.div>
    </div>
  );
}

type BtnProps = Omit<HTMLMotionProps<"button">, "children"> & {
  children: ReactNode; variant?: "primary" | "ghost" | "soft" | "danger"; size?: "sm" | "md" | "lg"; magnetic?: boolean; glow?: boolean;
};

/** Button with magnetic pull, spring press and (for primary) a metallic shimmer. */
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { children, variant = "primary", size = "md", magnetic = true, glow, className, onMouseMove, onMouseLeave, ...rest }, fwd) {
  const reduce = useReducedMotion();
  const x = useSpring(0, { stiffness: 260, damping: 16 });
  const y = useSpring(0, { stiffness: 260, damping: 16 });
  const sizes = { sm: "h-9 px-3.5 text-[13px] rounded-xl gap-1.5", md: "h-11 px-5 text-[14px] rounded-2xl gap-2", lg: "h-14 px-7 text-[16px] rounded-2xl gap-2.5" };
  const variants = {
    primary: "text-white bg-[linear-gradient(135deg,#7c3aed,#4f46e5_45%,#0891b2)] shadow-[0_8px_30px_rgba(124,58,237,0.35),inset_0_1px_0_rgba(255,255,255,0.25)] shimmer",
    ghost: "text-fg/90 glass hover:bg-white/[0.08]",
    soft: "text-fg bg-white/[0.07] border border-white/10 hover:bg-white/[0.11]",
    danger: "text-white bg-[linear-gradient(135deg,#e11d48,#be123c)] shadow-[0_8px_30px_rgba(225,29,72,0.3)] shimmer",
  };
  return (
    <motion.button
      ref={fwd}
      style={{ x, y }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
      onMouseMove={(e) => {
        if (magnetic && !reduce) {
          const r = e.currentTarget.getBoundingClientRect();
          x.set((e.clientX - r.left - r.width / 2) * 0.18);
          y.set((e.clientY - r.top - r.height / 2) * 0.28);
        }
        onMouseMove?.(e);
      }}
      onMouseLeave={(e) => { x.set(0); y.set(0); onMouseLeave?.(e); }}
      className={cn("inline-flex select-none items-center justify-center font-medium tracking-[-0.01em] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-violet/70 disabled:pointer-events-none disabled:opacity-45",
        sizes[size], variants[variant], glow && "glow-border", className)}
      {...rest}
    >
      {children}
    </motion.button>
  );
});

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function ToneDot({ tone, pulse }: { tone: "red" | "amber" | "green" | "violet" | "gray"; pulse?: boolean }) {
  const c = { red: "bg-bad", amber: "bg-warn", green: "bg-good", violet: "bg-violet", gray: "bg-faint" }[tone];
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", c)} />}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", c)} />
    </span>
  );
}

export function Pill({ tone, children, className }: { tone: "red" | "amber" | "green" | "violet" | "gray" | "cyan"; children: ReactNode; className?: string }) {
  const map = {
    red: "bg-bad/12 text-red-200 border-bad/25", amber: "bg-warn/12 text-amber-100 border-warn/25",
    green: "bg-good/12 text-emerald-100 border-good/25", violet: "bg-violet/15 text-violet-100 border-violet/30",
    gray: "bg-white/6 text-muted border-white/10", cyan: "bg-cyan/12 text-cyan-100 border-cyan/25",
  };
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-medium", map[tone], className)}>{children}</span>;
}

export function Counter({ value }: { value: number }) {
  return (
    <motion.span key={value} initial={{ opacity: 0, y: 10, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 0.5, ease: EASE }}>
      {value}
    </motion.span>
  );
}
