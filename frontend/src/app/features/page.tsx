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
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Features</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink md:text-4xl">
            Everything you need to go from spec to backend in one flow.
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-dune">
            Baxel compresses weeks of architecture thinking into a guided, auditable workflow.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {features.map((item) => (
              <div key={item.title} className="rounded-2xl border border-dune/20 bg-white/70 p-5 reveal reveal-delay-1 magnetic">
                <p className="text-sm font-semibold text-ink">{item.title}</p>
                <p className="mt-2 text-sm text-dune">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
