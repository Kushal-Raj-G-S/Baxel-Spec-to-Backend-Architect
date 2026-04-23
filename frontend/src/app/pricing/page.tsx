import MarketingShell from "../components/marketing-shell";
import { pricingPlans } from "../../lib/pricing-plans";

export default function PricingPage() {
  return (
    <MarketingShell>
      <main className="mx-auto w-full max-w-6xl px-6 pb-16 pt-32 relative z-10">
        <section className="rounded-[2.5rem] bg-[#1F261D] border border-black/5 shadow-2xl p-10 reveal magnetic">
          <p className="text-xs uppercase tracking-[0.2em] text-[#C2D68C]">Pricing</p>
          <h1 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
            Pick a plan that matches your build cadence.
          </h1>
          <p className="mt-3 text-sm text-white/60">
            A project is your product workspace. A pipeline run is one generation attempt inside a project, so a single project can have many runs.
          </p>
          <div className="mt-8 grid gap-6 md:grid-cols-2 xl:grid-cols-5">
            {pricingPlans.map((tier) => (
              <div key={tier.code} className={`rounded-3xl border bg-white/5 p-6 reveal reveal-delay-1 magnetic ${tier.featured ? "border-[#C2D68C]/50 shadow-[0_0_30px_rgba(194,214,140,0.15)]" : "border-white/5"}`}>
                <p className="text-xs uppercase tracking-[0.2em] text-white/50">{tier.name}</p>
                <p className="mt-4 text-3xl font-semibold text-white">
                  {tier.priceLabel}
                  {tier.inrPriceLabel ? <span className="ml-2 text-base font-medium text-white/40">/ {tier.inrPriceLabel}</span> : null}
                </p>
                <p className="mt-2 text-sm text-white/60">{tier.desc}</p>
                <ul className="mt-4 space-y-2 text-sm text-white/80">
                  {tier.perks.map((perk) => (
                    <li key={perk} className="flex items-start gap-2">
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#C2D68C] mt-1.5" />
                      <span>{perk}</span>
                    </li>
                  ))}
                </ul>
                <a
                  href={tier.checkoutUrl}
                  target={tier.checkoutUrl.startsWith("http") ? "_blank" : "_self"}
                  rel="noreferrer"
                  className={`mt-6 block w-full rounded-full px-4 py-2 text-center text-sm font-semibold transition hover:scale-105 ${tier.featured ? "bg-[#C2D68C] text-[#1F261D] shadow-[0_0_15px_rgba(194,214,140,0.3)]" : "border border-white/20 text-white hover:bg-white/10"}`}
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
