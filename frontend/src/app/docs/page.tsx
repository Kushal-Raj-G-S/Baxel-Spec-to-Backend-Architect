import MarketingShell from "../components/marketing-shell";

export default function DocsPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Docs</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink">Baxel Documentation</h1>
          <p className="mt-3 text-sm text-dune">
            API references, pipeline stage explanations, and export formats are being expanded.
          </p>
        </section>
      </main>
    </MarketingShell>
  );
}
