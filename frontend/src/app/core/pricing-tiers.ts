export interface PricingTier {
  name: string;
  price: string;
  period: string;
  tagline: string;
  features: string[];
  highlighted: boolean;
  ctaLabel: string;
}

// Placeholder pricing — dummy figures/copy, to be replaced with real tier data
// from the backend's `tiers` table once checkout is wired up. Shared between
// the home page's embedded pricing section and the standalone /pricing page.
export const PRICING_TIERS: PricingTier[] = [
  {
    name: 'Basic',
    price: '$19',
    period: 'one-time',
    tagline: 'A clean, modern refresh of your current site.',
    features: ['1 full redesign', 'Modern responsive layout', 'Basic on-page SEO', 'Email support'],
    highlighted: false,
    ctaLabel: 'Get Started',
  },
  {
    name: 'Premium',
    price: '$39',
    period: 'one-time',
    tagline: 'Sharper copy and a more polished, on-brand result.',
    features: [
      'Everything in Basic',
      'Enhanced copywriting & tone matching',
      'Accessibility (WCAG) pass',
      'Priority generation queue',
    ],
    highlighted: true,
    ctaLabel: 'Get Started',
  },
  {
    name: 'Pro',
    price: '$79',
    period: 'one-time',
    tagline: 'Maximum design polish for sites that need to impress.',
    features: [
      'Everything in Premium',
      'Advanced layout & micro-interactions',
      'Full SEO + Open Graph tags',
      'Priority support',
    ],
    highlighted: false,
    ctaLabel: 'Get Started',
  },
];

export interface PricingMatrixRow {
  label: string;
  basic: string;
  premium: string;
  pro: string;
}

export const PRICING_MATRIX: PricingMatrixRow[] = [
  { label: 'Full redesign', basic: 'Yes', premium: 'Yes', pro: 'Yes' },
  { label: 'Responsive layout', basic: 'Yes', premium: 'Yes', pro: 'Yes' },
  { label: 'Copywriting', basic: 'On-page SEO only', premium: 'Enhanced & tone-matched', pro: 'Enhanced & tone-matched' },
  { label: 'Accessibility (WCAG) pass', basic: '—', premium: 'Yes', pro: 'Yes' },
  { label: 'Layout & micro-interactions', basic: 'Standard', premium: 'Standard', pro: 'Advanced' },
  { label: 'SEO + Open Graph tags', basic: 'Basic', premium: 'Basic', pro: 'Full' },
  { label: 'Support', basic: 'Email', premium: 'Priority queue', pro: 'Priority support' },
];
