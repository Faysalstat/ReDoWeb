import { AdminOverview, Finding, Invoice, Plan, PreviewScores, ScanPhase, Site } from './models';

export const PHASES: ScanPhase[] = [
  { name: 'Crawl every page', state: 'done' },
  { name: 'Audit structure, speed, access', state: 'done' },
  { name: 'Rebuild pages', state: 'running' },
  { name: 'Render preview', state: 'waiting' },
  { name: 'Quality check', state: 'waiting' },
];

export const FINDINGS: Finding[] = [
  { title: 'No mobile layout below 640px', severity: 'High', fix: 'Rebuilt as a single-column layout with 48px touch targets.' },
  { title: 'Contact form posts nowhere', severity: 'High', fix: 'Wired to your inbox with a confirmation screen and spam guard.' },
  { title: 'Hero image 4.2 MB', severity: 'Medium', fix: 'Compressed to 180 KB, served in modern formats.' },
  { title: 'Body text at 3.1:1 contrast', severity: 'Medium', fix: 'Ink darkened to meet AA at every size.' },
  { title: 'Opening hours differ on 3 pages', severity: 'Low', fix: 'Pulled to one source; flagged for you to confirm.' },
  { title: 'No page titles or descriptions', severity: 'Low', fix: 'Written per page from your own copy.' },
];

export const PLANS: Plan[] = [
  {
    id: 'basic', name: 'Basic', price: 19, recommended: false,
    blurb: 'One small site, published and hosted. For a five-page shopfront that just needs to stop embarrassing you.',
    features: ['5 pages rebuilt', '1 regeneration a month', 'Custom domain + SSL', 'Email support'],
  },
  {
    id: 'pro', name: 'Pro', price: 49, recommended: true,
    blurb: 'The working plan. Rewrite the whole site, regenerate as often as you like, keep every version.',
    features: ['25 pages rebuilt', '10 regenerations a month', 'Full copy rewriting', 'Version history and rollback', 'Support in one business day'],
  },
  {
    id: 'premium', name: 'Premium', price: 149, recommended: false,
    blurb: 'For people who would rather hand it over. A designer reviews every rebuild before you see it.',
    features: ['Unlimited pages', 'Unlimited regenerations', 'Brand voice training', 'Human design review', 'Named contact'],
  },
];

export const PLAN_MATRIX: { label: string; basic: string; pro: string; premium: string }[] = [
  { label: 'Pages rebuilt', basic: '5', pro: '25', premium: 'Unlimited' },
  { label: 'Regenerations per month', basic: '1', pro: '10', premium: 'Unlimited' },
  { label: 'Custom domain', basic: 'Yes', pro: 'Yes', premium: 'Yes' },
  { label: 'Copy rewriting', basic: 'Headlines only', pro: 'Full site', premium: 'Full site + brand voice' },
  { label: 'Human design review', basic: '—', pro: '—', premium: 'Included' },
  { label: 'Support', basic: 'Email', pro: 'Email, 1 business day', premium: 'Named contact' },
];

export const SITES: Site[] = [
  { id: 's1', domain: 'brightwood-dental.com', note: 'Rebuild in progress — phase 3 of 5', status: 'Rebuilding', plan: 'Pro', lastRebuild: 'Live now', action: 'Open scan' },
  { id: 's2', domain: 'maple-hardware.co.uk', note: 'Preview ready, expires in 6 days', status: 'Your review', plan: 'Pro', lastRebuild: '26 Aug', action: 'Publish' },
  { id: 's3', domain: 'copperkettle.cafe', note: 'Published, 1,284 visitors this week', status: 'Live', plan: 'Basic', lastRebuild: '02 Aug', action: 'Regenerate' },
  { id: 's4', domain: 'hillside-vets.com', note: 'Archived after cancellation', status: 'Archived', plan: '—', lastRebuild: '11 Jun', action: 'Restore' },
];

export const INVOICES: Invoice[] = [
  { date: '12 Aug 2026', description: 'Pro — monthly', amount: 49, status: 'Paid' },
  { date: '12 Jul 2026', description: 'Pro — monthly', amount: 49, status: 'Paid' },
  { date: '12 Jun 2026', description: 'Basic — monthly', amount: 19, status: 'Paid' },
  { date: '12 May 2026', description: 'Basic — monthly', amount: 19, status: 'Refunded' },
];

export const PREVIEW_SCORES: PreviewScores = {
  performanceBefore: 34, performanceAfter: 96,
  accessibilityBefore: 51, accessibilityAfter: 100,
  pagesRebuilt: 9, fixesApplied: 14,
};

export const ADMIN: AdminOverview = {
  mrr: '$184.2k', mrrDelta: '+6.1% MoM', payingAccounts: '9,812', costPerJob: '$0.71',
  failed24h: 14, openTickets: 7, queueDepth: 38, medianJob: '4:12',
  jobs: [
    { id: '#48213', domain: 'brightwood-dental.com', phase: 'Rebuilding 3/5', cost: 0.64, age: '2m 41s', state: 'Running' },
    { id: '#48212', domain: 'maple-hardware.co.uk', phase: 'Crawling 1/5', cost: 0.08, age: '0m 22s', state: 'Running' },
    { id: '#48209', domain: 'silverline-yoga.com', phase: 'Rendering 4/5', cost: 0.92, age: '5m 09s', state: 'Running' },
    { id: '#48204', domain: 'northgate-legal.com', phase: 'Auditing 2/5', cost: 1.41, age: '14m 02s', state: 'Retry' },
    { id: '#48198', domain: 'copperkettle.cafe', phase: 'Crawl blocked', cost: 0.03, age: '18m 55s', state: 'Failed' },
    { id: '#48191', domain: 'hillside-vets.com', phase: 'Done', cost: 0.58, age: '26m 10s', state: 'Delivered' },
  ],
  failures: [
    { title: 'robots.txt disallows crawl — 6 jobs', owner: 'Customer action', detail: 'Auto-email sent with verification-file instructions. No retry queued.' },
    { title: 'Render timeout over 90s — 5 jobs', owner: 'Ours', detail: 'All on sites above 400 pages. Retried on the large-page worker; 3 recovered.' },
    { title: 'Payment declined at publish — 3 jobs', owner: 'Billing', detail: 'Preview held for 7 days; dunning sequence started.' },
  ],
  tickets: [
    { ref: '#T-2291', subject: 'New site dropped my booking form', domain: 'silverline-yoga.com', age: '42m open' },
    { ref: '#T-2288', subject: 'Can I keep my old logo colours?', domain: 'maple-hardware.co.uk', age: '3h open' },
    { ref: '#T-2284', subject: 'Charged twice for August', domain: 'northgate-legal.com', age: '6h open' },
  ],
  revenueSeries: [
    { month: 'Mar', value: 112 }, { month: 'Apr', value: 129 }, { month: 'May', value: 141 },
    { month: 'Jun', value: 158 }, { month: 'Jul', value: 171 }, { month: 'Aug', value: 184 },
  ],
  accountStats: [
    { label: 'Trials, this week', value: '1,204' },
    { label: 'Preview → publish', value: '18.4%', accent: true },
    { label: 'Churn, monthly', value: '3.1%' },
    { label: 'Gross margin', value: '81%' },
  ],
};
