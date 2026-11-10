export type PricingPlan = {
  code: string;
  name: string;
  priceLabel: string;
  inrPriceLabel?: string;
  desc: string;
  perks: string[];
  checkoutUrl: string;
  ctaLabel?: string;
  featured?: boolean;
};

export const pricingPlans: PricingPlan[] = [
  {
    code: "free",
    name: "Free",
    priceLabel: "$0",
    inrPriceLabel: "₹0",
    desc: "Experience the full swarm engine, no quality caps — just a small monthly run budget.",
    perks: [
      "Full swarm engine — no quality throttling",
      "3 pipeline runs / month",
      "3 active projects",
      "Up to 3,000 character prompt specs",
      "SAGE AI chatbot — 15 messages / day",
      "7-day pipeline history"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_FREE_URL || "/auth"
  },
  {
    code: "pro",
    name: "Pro",
    priceLabel: "$14",
    inrPriceLabel: "₹1,199",
    desc: "For solo builders shipping real projects on a regular cadence.",
    perks: [
      "25 pipeline runs / month",
      "15 active projects",
      "Up to 6,000 character prompt specs",
      "SAGE AI chatbot — unlimited messages",
      "Unlimited pipeline history",
      "Email support"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_PRO_URL || "mailto:billing@baxel.app?subject=Pro%20Plan",
    featured: true
  },
  {
    code: "team",
    name: "Team",
    priceLabel: "$45",
    inrPriceLabel: "₹3,799",
    desc: "For small teams running product sprints together.",
    perks: [
      "100 pipeline runs / month",
      "50 active projects",
      "Up to 10,000 character prompt specs",
      "5 team seats + shared workspace",
      "Priority support (24h SLA)",
      "Unlimited SAGE chatbot & history"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_TEAM_URL || "mailto:billing@baxel.app?subject=Team%20Plan"
  },
  {
    code: "enterprise",
    name: "Enterprise",
    priceLabel: "Custom",
    desc: "For org-wide backend generation programs with compliance needs.",
    perks: [
      "Custom pipeline run & project volume",
      "Custom prompt spec limits",
      "SSO / SAML + audit logs",
      "Dedicated support & onboarding",
      "Custom contract & invoicing"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_ENTERPRISE_URL || "mailto:billing@baxel.app?subject=Enterprise%20Plan",
    ctaLabel: "Contact Sales"
  }
];
