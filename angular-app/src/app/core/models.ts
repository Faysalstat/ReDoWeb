export type ScanPhaseState = 'done' | 'running' | 'waiting' | 'failed';

export interface ScanPhase {
  name: string;
  state: ScanPhaseState;
  detail?: string;
}

export interface Finding {
  title: string;
  severity: 'High' | 'Medium' | 'Low';
  fix: string;
}

export interface Scan {
  id: string;
  url: string;
  percent: number;
  phaseIndex: number;
  phases: ScanPhase[];
  findings: Finding[];
  etaMinutes: number;
}

export interface Plan {
  id: 'basic' | 'pro' | 'premium';
  name: string;
  price: number;
  blurb: string;
  features: string[];
  recommended: boolean;
}

export type SiteStatus = 'Rebuilding' | 'Your review' | 'Live' | 'Archived';

export interface Site {
  id: string;
  domain: string;
  note: string;
  status: SiteStatus;
  plan: string;
  lastRebuild: string;
  action: string;
}

export interface Invoice {
  date: string;
  description: string;
  amount: number;
  status: 'Paid' | 'Refunded' | 'Failed';
}

export interface PreviewScores {
  performanceBefore: number;
  performanceAfter: number;
  accessibilityBefore: number;
  accessibilityAfter: number;
  pagesRebuilt: number;
  fixesApplied: number;
}

export interface Job {
  id: string;
  domain: string;
  phase: string;
  cost: number;
  age: string;
  state: 'Running' | 'Retry' | 'Failed' | 'Delivered';
}

export interface FailureGroup {
  title: string;
  owner: 'Ours' | 'Customer action' | 'Billing';
  detail: string;
}

export interface Ticket {
  ref: string;
  subject: string;
  domain: string;
  age: string;
}

export interface AdminOverview {
  mrr: string;
  mrrDelta: string;
  payingAccounts: string;
  costPerJob: string;
  failed24h: number;
  openTickets: number;
  queueDepth: number;
  medianJob: string;
  jobs: Job[];
  failures: FailureGroup[];
  tickets: Ticket[];
  revenueSeries: { month: string; value: number }[];
  accountStats: { label: string; value: string; accent?: boolean }[];
}
