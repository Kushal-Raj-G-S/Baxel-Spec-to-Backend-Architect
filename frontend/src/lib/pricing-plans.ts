export type PricingPlan = {
  code: string;
  name: string;
  priceLabel: string;
  inrPriceLabel?: string;
  desc: string;
  perks: string[];
  checkoutUrl: string;
  featured?: boolean;
};

export const pricingPlans: PricingPlan[] = [
  {
    code: "starter",
    name: "Starter",
    priceLabel: "$0",
    inrPriceLabel: "₹0",
    desc: "For first projects and student experiments.",
    perks: ["3 projects per month", "9 pipeline runs per month", "Schema + API outputs"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STARTER_URL || "/auth"
  },
  {
    code: "creator",
    name: "Creator",
    priceLabel: "$8",
    inrPriceLabel: "₹699",
    desc: "For solo makers shipping customer prototypes.",
    perks: ["7 projects per month", "25 pipeline runs", "Adds SQL + Rules outputs"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_CREATOR_URL || "mailto:billing@baxel.app?subject=Creator%20Plan"
  },
  {
    code: "studio",
    name: "Studio",
    priceLabel: "$20",
    inrPriceLabel: "₹1699",
    desc: "For indie teams running product sprints.",
    perks: ["15 projects per month", "75 pipeline runs", "Full outputs including code skeleton"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STUDIO_URL || "mailto:billing@baxel.app?subject=Studio%20Plan",
    featured: true
  },
  {
    code: "growth",
    name: "Growth",
    priceLabel: "$50",
    inrPriceLabel: "₹4199",
    desc: "For scaling teams with multiple products.",
    perks: ["60 projects per month", "300 pipeline runs", "Full outputs + high throughput"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_GROWTH_URL || "mailto:billing@baxel.app?subject=Growth%20Plan"
  },
  {
    code: "enterprise",
    name: "Enterprise",
    priceLabel: "$158",
    inrPriceLabel: "₹13199",
    desc: "For org-wide backend generation programs.",
    perks: ["250 projects per month", "High-volume runs", "Full outputs + dedicated support"],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_ENTERPRISE_URL || "mailto:billing@baxel.app?subject=Enterprise%20Plan"
  }
];
