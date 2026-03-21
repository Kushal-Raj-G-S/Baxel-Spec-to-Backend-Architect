import MarketingShell from "../components/marketing-shell";

export default function SecurityPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Security</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">Security and data handling</h1>
          <p className="mt-3 text-sm text-dune">
            Baxel isolates user data by ownership, applies row-level security policies, and validates auth tokens.
          </p>
        </section>
      </main>
    </MarketingShell>
  );
}
