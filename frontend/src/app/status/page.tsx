import MarketingShell from "../components/marketing-shell";

export default function StatusPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Status</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">Service Status</h1>
          <p className="mt-3 text-sm text-dune">All core services are operational.</p>
        </section>
      </main>
    </MarketingShell>
  );
}
