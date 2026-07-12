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
    perks: [
      "3 active projects",
      "Up to 3,000 character prompt specs",
      "Full API, DB, and code stubs generation"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STARTER_URL || "/auth"
  },
  {
    code: "creator",
    name: "Creator",
    priceLabel: "$8",
    inrPriceLabel: "₹699",
    desc: "For solo makers shipping customer prototypes.",
    perks: [
      "7 active projects",
      "Up to 4,500 character prompt specs",
      "Full API, DB, and code stubs generation"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_CREATOR_URL || "mailto:billing@baxel.app?subject=Creator%20Plan"
  },
  {
    code: "studio",
    name: "Studio",
    priceLabel: "$20",
    inrPriceLabel: "₹1699",
    desc: "For indie teams running product sprints.",
    perks: [
      "15 active projects",
      "Up to 6,500 character prompt specs",
      "Full API, DB, and code stubs generation"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_STUDIO_URL || "mailto:billing@baxel.app?subject=Studio%20Plan",
    featured: true
  },
  {
    code: "growth",
    name: "Growth",
    priceLabel: "$50",
    inrPriceLabel: "₹4199",
    desc: "For scaling teams with multiple products.",
    perks: [
      "30 active projects",
      "Up to 9,000 character prompt specs",
      "Full API, DB, and code stubs generation"
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_GROWTH_URL || "mailto:billing@baxel.app?subject=Growth%20Plan"
  },
  {
    code: "enterprise",
    name: "Enterprise",
    priceLabel: "$158",
    inrPriceLabel: "₹13199",
    desc: "For org-wide backend generation programs.",
    perks: [
      "60 active projects",
      "Up to 15,000 character prompt specs",
      "Full API, DB, and code stubs generation",
    ],
    checkoutUrl: process.env.NEXT_PUBLIC_BILLING_ENTERPRISE_URL || "mailto:billing@baxel.app?subject=Enterprise%20Plan"
  }
];
