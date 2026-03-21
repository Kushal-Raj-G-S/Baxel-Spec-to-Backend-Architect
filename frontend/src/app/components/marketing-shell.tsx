"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

const navLinks = [
  { label: "Features", href: "/features" },
  { label: "Pricing", href: "/pricing" },
  { label: "About", href: "/about" },
  { label: "Blog", href: "/blog" }
];

export default function MarketingShell({ children }: { children: React.ReactNode }) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        document.documentElement.style.setProperty("--scroll-y", `${window.scrollY}`);
        frame = 0;
      });
    };

    const root = rootRef.current;
    let active: HTMLElement | null = null;

    const onMove = (event: MouseEvent) => {
      if (!root) return;
      const rect = root.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      root.style.setProperty("--mx", `${x}%`);
      root.style.setProperty("--my", `${y}%`);

      const target = (event.target as HTMLElement | null)?.closest(".magnetic") as HTMLElement | null;
      if (active && active !== target) {
        active.style.setProperty("--tx", "0px");
        active.style.setProperty("--ty", "0px");
      }
      active = target;
      if (!target) return;
      const targetRect = target.getBoundingClientRect();
      const localX = ((event.clientX - targetRect.left) / targetRect.width) * 100;
      const localY = ((event.clientY - targetRect.top) / targetRect.height) * 100;
      target.style.setProperty("--mx", `${localX}%`);
      target.style.setProperty("--my", `${localY}%`);
      target.style.setProperty("--tx", `${(localX - 50) / 6}px`);
      target.style.setProperty("--ty", `${(localY - 50) / 6}px`);
    };

    const onClick = (event: MouseEvent) => {
      const target = (event.target as HTMLElement | null)?.closest(".ripple") as HTMLElement | null;
      if (!target) return;
      const rect = target.getBoundingClientRect();
      const ink = document.createElement("span");
      ink.className = "ripple-ink";
      ink.style.left = `${event.clientX - rect.left - 60}px`;
      ink.style.top = `${event.clientY - rect.top - 60}px`;
      target.appendChild(ink);
      window.setTimeout(() => ink.remove(), 700);
    };

    window.addEventListener("scroll", onScroll);
    root?.addEventListener("mousemove", onMove);
    root?.addEventListener("click", onClick);

    return () => {
      window.removeEventListener("scroll", onScroll);
      root?.removeEventListener("mousemove", onMove);
      root?.removeEventListener("click", onClick);
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, []);

  return (
    <div ref={rootRef} className="baxel-shell cursor-reactive">
      <div className="orb-wrap">
        <div className="orb sun" />
        <div className="orb mint" />
        <div className="orb sand" />
        <div className="sparkle" style={{ top: "18%", left: "12%" }} />
        <div className="sparkle" style={{ top: "64%", right: "14%" }} />
      </div>
      <header
        className="pointer-events-auto"
        style={{
          position: "fixed",
          top: "12px",
          left: "50%",
          transform: "translateX(-50%)",
          width: "min(94vw, 72rem)",
          zIndex: 9999
        }}
      >
        <div className="flex w-full items-center justify-between gap-4 rounded-full border border-white/45 bg-white/25 px-5 py-3 shadow-[0_16px_40px_rgba(15,15,15,0.18)] backdrop-blur-2xl transition">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-ink text-bone">B</div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-dune">Baxel</p>
              <p className="text-sm text-ink">Spec-to-Backend</p>
            </div>
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-dune lg:flex">
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className="nav-link hover:text-ink transition">
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/auth"
              className="rounded-full border border-white/40 px-4 py-2 text-sm text-ink/80 transition hover:text-ink hover:border-white/60 ripple"
            >
              Sign in
            </Link>
            <Link href="/auth" className="rounded-full bg-ink px-4 py-2 text-sm text-bone btn-glow ripple">
              Start free
            </Link>
          </div>
        </div>
      </header>
      <div className="h-24" />
      {children}
      <footer className="mx-auto mt-16 w-full max-w-6xl px-6 pb-10">
        <div className="glass flex flex-col gap-6 rounded-3xl p-8 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="label">Baxel / Spec-to-Backend</p>
            <p className="mt-3 text-sm text-dune">
              Turn unclear product intent into production-ready backend architecture.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm text-dune">
            <Link href="/security" className="transition hover:text-ink">Security</Link>
            <Link href="/roadmap" className="transition hover:text-ink">Roadmap</Link>
            <Link href="/status" className="transition hover:text-ink">Status</Link>
            <Link href="/docs" className="transition hover:text-ink">Docs</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
