"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import MarketingShell from "./components/marketing-shell";

const highlights = [
  {
    title: "Spec intelligence",
    desc: "Extract actors, entities, and constraints with a multi-stage reasoning pipeline."
  },
  {
    title: "Architecture clarity",
    desc: "See models, APIs, and business rules in a living ERD workspace."
  },
  {
    title: "Deployable output",
    desc: "Export a FastAPI or Node skeleton with migrations, tests, and docs."
  }
];

const steps = [
  "Ingest PRD and normalize language",
  "Propose schema + endpoint draft",
  "Surface gaps and conflicts",
  "Generate code skeleton",
  "Push to repo for review"
];

export default function Home() {
  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
    []
  );
  const [metrics, setMetrics] = useState([
    { label: "Specs processed", value: "0" },
    { label: "Schemas generated", value: "0" },
    { label: "API endpoints", value: "0" },
    { label: "Rules captured", value: "0" }
  ]);
  const carouselRef = useRef<HTMLDivElement | null>(null);
  const [metricIndex, setMetricIndex] = useState(0);

  useEffect(() => {
    let isMounted = true;

    const loadMetrics = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/dashboard/public-metrics`);
        if (!response.ok) return;
        const payload = await response.json();
        if (!isMounted) return;
        setMetrics([
          { label: "Specs processed", value: Number(payload.specs_processed || 0).toLocaleString() },
          { label: "Schemas generated", value: Number(payload.schemas_generated || 0).toLocaleString() },
          { label: "API endpoints", value: Number(payload.api_endpoints || 0).toLocaleString() },
          { label: "Rules captured", value: Number(payload.rules_captured || 0).toLocaleString() }
        ]);
      } catch {
        // Keep graceful zero-state if backend is unavailable.
      }
    };

    loadMetrics();
    const timer = window.setInterval(loadMetrics, 30000);
    return () => {
      isMounted = false;
      window.clearInterval(timer);
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    const timer = setInterval(() => {
      setMetricIndex((prev) => (prev + 1) % metrics.length);
    }, 2500);
    return () => clearInterval(timer);
  }, [metrics.length]);

  useEffect(() => {
    const track = carouselRef.current;
    if (!track) return;
    const first = track.firstElementChild as HTMLElement | null;
    if (!first) return;
    const gap = 16;
    const cardWidth = first.getBoundingClientRect().width + gap;
    track.scrollTo({ left: metricIndex * cardWidth, behavior: "smooth" });
  }, [metricIndex]);

  return (
    <MarketingShell>
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-6 pb-16">
        <section className="grid gap-10 md:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6 reveal">
            <p className="label">Baxel / Spec-to-Backend</p>
            <h1 className="text-4xl font-semibold leading-tight md:text-6xl">
              Turn messy PRDs into production-ready backend blueprints.
            </h1>
            <p className="max-w-xl text-base text-dune md:text-lg">
              Baxel translates product intent into structured data models, APIs, and rules you can ship.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/auth" className="rounded-full bg-ink px-5 py-2 text-sm text-bone btn-glow ripple">
                Start with a spec
              </Link>
              <Link href="/features" className="rounded-full border border-dune/40 px-5 py-2 text-sm hover-rise ripple">
                Explore features
              </Link>
            </div>
            <div className="glass inline-flex items-center gap-3 rounded-full px-5 py-2 text-sm hover-rise magnetic">
              <span className="code-pill">Groq</span>
              <span>Pipeline ready</span>
            </div>
            <div className="flex flex-wrap gap-3 text-xs uppercase tracking-[0.25em] text-dune">
              <span className="rounded-full border border-dune/30 px-3 py-1">No-code-ready</span>
              <span className="rounded-full border border-dune/30 px-3 py-1">Traceable</span>
              <span className="rounded-full border border-dune/30 px-3 py-1">Supabase-friendly</span>
            </div>
          </div>
          <div className="glass relative overflow-hidden rounded-3xl p-8 reveal reveal-delay-1 hover-rise magnetic">
            <p className="label">Live pipeline</p>
            <div className="mt-6 space-y-3">
              {[
                "Spec cleanup",
                "Entities & relations",
                "Model proposal",
                "API surface",
                "Business rules",
                "Code skeleton"
              ].map((item, index) => (
                <div
                  key={item}
                  className="flex items-center justify-between rounded-2xl border border-dune/20 bg-white/70 px-4 py-3"
                >
                  <span className="text-sm font-medium text-ink">{item}</span>
                  <span className="text-xs uppercase tracking-[0.2em] text-dune">
                    {index < 2 ? "done" : "queued"}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-6 rounded-2xl bg-ink p-4 text-bone">
              <p className="text-xs uppercase tracking-[0.2em]">Latest insight</p>
              <p className="mt-3 text-sm">Missing SLA targets detected. Suggest adding NFRs.</p>
            </div>
            <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-ember/30 blur-3xl floaty" />
            <div className="pointer-events-none absolute bottom-6 right-6 h-24 w-24 rounded-full bg-mint/30 blur-2xl" />
          </div>
        </section>

        <section className="glass rounded-3xl p-8 reveal hover-rise glass-carousel magnetic">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="label">Live metrics</p>
              <h2 className="mt-3 text-2xl font-semibold text-ink">A glass carousel of momentum.</h2>
              <p className="mt-2 text-sm text-dune">Animated proof points as your spec flows through Baxel.</p>
            </div>
            <div className="rounded-full border border-dune/30 px-4 py-2 text-xs uppercase tracking-[0.2em] text-dune">
              Auto-cycling
            </div>
          </div>
          <div ref={carouselRef} className="mt-6 glass-carousel-track">
            {metrics.map((metric) => (
              <div key={metric.label} className="metric-card magnetic">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">{metric.label}</p>
                <p className="mt-3 text-3xl font-semibold text-ink">{metric.value}</p>
                <p className="mt-2 text-xs text-dune">Updated just now</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-3">
          {highlights.map((item) => (
            <div key={item.title} className="glass rounded-3xl p-6 reveal reveal-delay-1 hover-rise magnetic">
              <p className="label">{item.title}</p>
              <p className="mt-4 text-sm text-dune">{item.desc}</p>
            </div>
          ))}
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="glass rounded-3xl p-8 reveal hover-rise magnetic">
            <p className="label">How it works</p>
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {steps.map((step, index) => (
                <div key={step} className="rounded-2xl border border-dune/20 bg-white/70 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-dune">Step {index + 1}</p>
                  <p className="mt-3 text-sm font-medium text-ink">{step}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="glass rounded-3xl p-8 reveal reveal-delay-2 hover-rise magnetic">
            <p className="label">Outputs</p>
            <div className="mt-6 space-y-4 text-sm text-dune">
              <p>Interactive ERD with validation hints.</p>
              <p>Endpoint catalog with error shapes.</p>
              <p>Version diffs with migration notes.</p>
              <p>Code bundles for FastAPI or Node.</p>
            </div>
          </div>
        </section>

        <section className="glass rounded-3xl p-8 reveal hover-rise magnetic">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="label">Ready to prototype?</p>
              <h2 className="mt-3 text-2xl font-semibold text-ink">Build a backend architecture in minutes.</h2>
              <p className="mt-2 text-sm text-dune">Drop a spec and walk away with a blueprint and code starter.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/auth" className="rounded-full bg-ink px-5 py-2 text-sm text-bone btn-glow ripple">
                Start free
              </Link>
              <Link href="/pricing" className="rounded-full border border-dune/40 px-5 py-2 text-sm hover-rise ripple">
                View pricing
              </Link>
            </div>
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
