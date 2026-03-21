import MarketingShell from "../components/marketing-shell";

export default function AboutPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">About</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink md:text-4xl">Built for the messy part of software.</h1>
          <div className="mt-6 grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-4 text-sm text-dune reveal magnetic">
              <p>
                Baxel is focused on the step before code: turning ambiguous product intent into structured architecture.
              </p>
              <p>
                We blend AI reasoning with human-in-the-loop edits so teams can move from spec to a backend blueprint
                without losing context or ownership.
              </p>
              <p>
                Every output can be traced back to the exact sentences that informed it.
              </p>
            </div>
            <div className="rounded-3xl border border-dune/20 bg-white/70 p-6 reveal reveal-delay-1 magnetic">
              <p className="label">Principles</p>
              <ul className="mt-4 space-y-3 text-sm text-ink">
                <li>Clarity beats speed.</li>
                <li>Traceability builds trust.</li>
                <li>Design before code.</li>
                <li>Readable beats clever.</li>
              </ul>
            </div>
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
