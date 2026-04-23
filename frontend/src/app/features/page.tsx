import MarketingShell from "../components/marketing-shell";

const features = [
  {
    title: "Spec intelligence",
    desc: "Multi-agent extraction of entities, roles, and constraints with traceability to source text."
  },
  {
    title: "Visual architecture",
    desc: "ERD editor with relationship hints, field validations, and type guidance."
  },
  {
    title: "API generator",
    desc: "REST + OpenAPI drafts with payload shapes, error contracts, and auth requirements."
  },
  {
    title: "Business rules",
    desc: "Invariants and compliance checks highlighted as actionable checklists."
  },
  {
    title: "Version diffs",
    desc: "Spec changes mapped to schema and endpoint deltas with migration guidance."
  },
  {
    title: "Code export",
    desc: "Push FastAPI or Node skeletons with migrations, tests, and docs."
  }
];

export default function FeaturesPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16 pt-32 relative z-10">
        <section className="rounded-[2.5rem] bg-[#1F261D] border border-black/5 shadow-2xl p-10 reveal magnetic">
          <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Technology</p>
          <h1 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
            Everything you need to go from spec to backend in one flow.
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-white/60">
            Baxel compresses weeks of architecture thinking into a guided, auditable workflow.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {features.map((item) => (
              <div key={item.title} className="rounded-2xl border border-white/5 bg-white/5 p-6 reveal reveal-delay-1 magnetic transition-colors hover:bg-white/10">
                <p className="text-sm font-semibold text-white">{item.title}</p>
                <p className="mt-2 text-sm text-white/60">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
