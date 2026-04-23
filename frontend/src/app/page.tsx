"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import MarketingShell from "./components/marketing-shell";
import { pricingPlans } from "../lib/pricing-plans";
import ScrollytellingSphere from "./components/scrollytelling-sphere";

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
  const [pipelineStep, setPipelineStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setPipelineStep((prev) => (prev + 1) % 7);
    }, 1500);
    return () => clearInterval(timer);
  }, []);

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
      <ScrollytellingSphere />
      
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-6 pb-16 pt-24 relative z-10">
        
        {/* We can keep the live pipeline box as a visual element, but the main hero is now the scrollytelling */}
        <section className="relative overflow-hidden rounded-[2.5rem] p-8 md:p-12 border border-black/5 bg-[#1F261D] shadow-2xl reveal hover-rise magnetic">
          <div className="grid gap-10 md:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-6">
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Live pipeline</p>
              <h2 className="text-3xl font-semibold leading-tight text-white md:text-4xl">
                See the extraction in real-time.
              </h2>
              <p className="max-w-xl text-base text-white/60 md:text-lg">
                As you type, Baxel translates your product intent into structured data models, APIs, and rules.
              </p>
              <div className="flex flex-wrap gap-3 text-xs uppercase tracking-[0.2em] text-white/50">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">No-code-ready</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Traceable</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Supabase-friendly</span>
              </div>
            </div>
            
            <div className="space-y-3">
              {[
                "Spec cleanup",
                "Entities & relations",
                "Model proposal",
                "API surface",
                "Business rules",
                "Code skeleton"
              ].map((item, index) => {
                let status = "QUEUED";
                let statusColor = "text-white/30";
                
                if (index < pipelineStep) {
                  status = "DONE";
                  statusColor = "text-[#C2D68C]"; // Pistachio
                } else if (index === pipelineStep) {
                  status = "PROCESSING";
                  statusColor = "text-[#869E58] animate-pulse"; // Moss green blinking
                }
                
                return (
                  <div
                    key={item}
                    className={`flex items-center justify-between rounded-2xl border transition-all duration-500 px-4 py-3 ${
                      index === pipelineStep 
                        ? 'border-[#869E58]/40 bg-[#869E58]/10' 
                        : 'border-white/5 bg-white/5'
                    }`}
                  >
                    <span className="text-sm font-medium text-white/90">{item}</span>
                    <span className={`text-[10px] sm:text-xs uppercase tracking-[0.2em] ${statusColor} transition-colors duration-500`}>
                      {status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="pointer-events-none absolute -right-10 -top-10 h-64 w-64 rounded-full bg-[#869E58]/20 blur-[100px] floaty" />
          <div className="pointer-events-none absolute bottom-6 right-6 h-32 w-32 rounded-full bg-[#C2D68C]/20 blur-[80px]" />
        </section>

        {/* Replaced Live Metrics with Ecosystem */}
        <section className="relative overflow-hidden rounded-[2.5rem] p-8 md:p-12 border border-black/5 bg-[#1F261D] shadow-2xl reveal hover-rise magnetic">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-8">
            <div className="max-w-md">
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Ecosystem</p>
              <h2 className="mt-3 text-3xl font-semibold text-white">Works with your modern stack.</h2>
              <p className="mt-4 text-base text-white/60 leading-relaxed">
                Baxel doesn't reinvent the wheel. It exports standardized, clean code using the frameworks you already know and trust.
              </p>
            </div>
            <div className="flex flex-wrap gap-4 max-w-sm md:justify-end">
              {['Next.js', 'React', 'FastAPI', 'Node.js', 'PostgreSQL', 'Supabase', 'Tailwind', 'TypeScript'].map(tech => (
                <div key={tech} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white">
                  {tech}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-3">
          {highlights.map((item) => (
            <div key={item.title} className="relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[#1F261D] shadow-2xl p-8 reveal reveal-delay-1 hover-rise magnetic">
              <div className="h-10 w-10 rounded-full bg-white/5 flex items-center justify-center mb-6 border border-white/10">
                <div className="h-3 w-3 rounded-full bg-[#C2D68C]" />
              </div>
              <p className="text-lg font-semibold tracking-wide text-white">{item.title}</p>
              <p className="mt-4 text-sm text-white/60 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[#1F261D] shadow-2xl p-8 md:p-12 reveal hover-rise magnetic">
            <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">How it works</p>
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {steps.map((step, index) => (
                <div key={step} className="rounded-2xl border border-white/5 bg-white/5 p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-white/40">Step {index + 1}</p>
                  <p className="mt-3 text-sm font-medium text-white/90">{step}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[#1F261D] shadow-2xl p-8 md:p-12 reveal reveal-delay-2 hover-rise magnetic">
            <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Outputs</p>
            <div className="mt-8 space-y-6 text-sm text-white/60">
              <p className="flex items-center gap-4"><span className="h-2 w-2 rounded-full bg-[#C2D68C] shadow-[0_0_10px_#C2D68C]" />Interactive ERD with validation hints.</p>
              <p className="flex items-center gap-4"><span className="h-2 w-2 rounded-full bg-[#C2D68C] shadow-[0_0_10px_#C2D68C]" />Endpoint catalog with error shapes.</p>
              <p className="flex items-center gap-4"><span className="h-2 w-2 rounded-full bg-[#C2D68C] shadow-[0_0_10px_#C2D68C]" />Version diffs with migration notes.</p>
              <p className="flex items-center gap-4"><span className="h-2 w-2 rounded-full bg-[#C2D68C] shadow-[0_0_10px_#C2D68C]" />Code bundles for FastAPI or Node.</p>
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[#1F261D] shadow-2xl p-8 md:p-12 reveal hover-rise magnetic">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between relative z-10">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Ready to prototype?</p>
              <h2 className="mt-3 text-3xl font-semibold text-white">Build a backend architecture in minutes.</h2>
              <p className="mt-2 text-base text-white/60">Drop a spec and walk away with a blueprint and code starter.</p>
            </div>
            <div className="flex flex-wrap gap-4">
              <Link href="/auth" className="rounded-full bg-[#C2D68C] px-8 py-3 text-sm font-semibold text-[#1F261D] shadow-[0_0_20px_rgba(194,214,140,0.4)] transition hover:scale-105">
                Start free
              </Link>
              <Link href="/pricing" className="rounded-full border border-white/20 bg-white/5 backdrop-blur-md px-8 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
                View pricing
              </Link>
            </div>
          </div>
          <div className="pointer-events-none absolute -left-20 -bottom-20 h-64 w-64 rounded-full bg-[#869E58]/20 blur-[100px]" />
        </section>

        <section className="relative overflow-hidden rounded-[2.5rem] border border-black/5 bg-[#1F261D] shadow-2xl p-8 md:p-12 reveal hover-rise magnetic">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Pricing plans</p>
              <h2 className="mt-3 text-3xl font-semibold text-white">Choose a lane and scale when needed.</h2>
              <p className="mt-2 text-base text-white/60">Limits are enforced monthly by projects and pipeline runs.</p>
            </div>
            <Link href="/pricing" className="rounded-full border border-white/20 px-6 py-2.5 text-sm font-medium text-white/80 hover:text-white hover:bg-white/5 transition">
              Compare details
            </Link>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {pricingPlans.map((plan) => (
              <div key={plan.code} className={`rounded-3xl border bg-white/5 p-6 ${plan.featured ? "border-[#C2D68C]/50 shadow-[0_0_30px_rgba(194,214,140,0.1)]" : "border-white/5"}`}>
                <p className="text-xs uppercase tracking-[0.2em] text-white/50">{plan.name}</p>
                <p className="mt-3 text-3xl font-semibold text-white">
                  {plan.priceLabel}
                  {plan.inrPriceLabel ? <span className="ml-2 text-sm font-medium text-white/40">/ {plan.inrPriceLabel}</span> : null}
                </p>
                <div className="mt-6 space-y-3">
                  <p className="text-sm text-white/70 flex items-start gap-2"><span className="text-[#C2D68C] mt-[2px]">✓</span> <span>{plan.perks[0]}</span></p>
                  <p className="text-sm text-white/70 flex items-start gap-2"><span className="text-[#C2D68C] mt-[2px]">✓</span> <span>{plan.perks[1]}</span></p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
