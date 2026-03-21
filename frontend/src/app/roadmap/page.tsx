import MarketingShell from "../components/marketing-shell";

export default function RoadmapPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Roadmap</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">What we are building next</h1>
          <ul className="mt-4 space-y-2 text-sm text-dune">
            <li>Billing integration and subscription management</li>
            <li>One-click framework export templates</li>
            <li>Team workspaces with role-based access</li>
          </ul>
        </section>
      </main>
    </MarketingShell>
  );
}
