import MarketingShell from "../components/marketing-shell";

const tiers = [
  {
    name: "Starter",
    price: "$0",
    desc: "Best for personal projects and student teams.",
    perks: ["1 workspace", "3 specs / month", "Basic pipeline", "Community support"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STARTER_URL || "/auth"
  },
  {
    name: "Studio",
    price: "$24",
    desc: "For indie teams shipping production backends.",
    perks: ["5 workspaces", "Unlimited specs", "Version diffs", "Export templates"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STUDIO_URL || "mailto:billing@baxel.app?subject=Studio%20Plan"
  },
  {
    name: "Scale",
    price: "$120",
    desc: "For product orgs managing multiple teams.",
    perks: ["SAML SSO", "Audit trails", "Custom models", "Priority support"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_SCALE_URL || "mailto:billing@baxel.app?subject=Scale%20Plan"
  }
];

export default function PricingPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16">
        <section className="glass rounded-3xl p-10 reveal magnetic">
          <p className="label">Pricing</p>
          <h1 className="mt-4 text-3xl font-semibold text-ink md:text-4xl">
            Pick a plan that matches your build cadence.
          </h1>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {tiers.map((tier) => (
              <div key={tier.name} className="rounded-3xl border border-dune/20 bg-white/70 p-6 reveal reveal-delay-1 magnetic">
                <p className="text-xs uppercase tracking-[0.2em] text-dune">{tier.name}</p>
                <p className="mt-4 text-3xl font-semibold text-ink">{tier.price}</p>
                <p className="mt-2 text-sm text-dune">{tier.desc}</p>
                <ul className="mt-4 space-y-2 text-sm text-ink">
                  {tier.perks.map((perk) => (
                    <li key={perk} className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-ember" />
                      {perk}
                    </li>
                  ))}
                </ul>
                <a
                  href={tier.checkoutUrl}
                  target={tier.checkoutUrl.startsWith("http") ? "_blank" : "_self"}
                  rel="noreferrer"
                  className="mt-6 block w-full rounded-full bg-ink px-4 py-2 text-center text-sm text-bone ripple"
                >
                  Choose {tier.name}
                </a>
              </div>
            ))}
          </div>
        </section>
      </main>
    </MarketingShell>
  );
}
