import MarketingShell from "../components/marketing-shell";

const posts = [
  {
    title: "From PRD to schema: the missing middle",
    date: "Mar 12, 2026",
    excerpt: "Why most AI dev tools skip the hardest part of software design."
  },
  {
    title: "Designing API contracts with traceability",
    date: "Feb 27, 2026",
    excerpt: "How to keep stakeholder context attached to every endpoint."
  },
  {
    title: "Rules, invariants, and the sanity layer",
    date: "Jan 30, 2026",
    excerpt: "The business logic checklist that saves you from late-stage churn."
  }
];

export default function BlogPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Journal</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink md:text-4xl">Thoughts on spec-driven engineering.</h1>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {posts.map((post) => (
              <article key={post.title} className="rounded-2xl border border-dune/20 bg-white/70 p-6 reveal reveal-delay-1 magnetic">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">{post.date}</p>
                <h2 className="mt-3 text-lg font-semibold text-ink">{post.title}</h2>
                <p className="mt-2 text-sm text-dune">{post.excerpt}</p>
                <button className="mt-4 rounded-full border border-dune/40 px-4 py-2 text-sm ripple">
                  Read post
                </button>
              </article>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
