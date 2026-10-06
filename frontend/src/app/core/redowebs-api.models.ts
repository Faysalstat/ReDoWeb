export interface PageRecord {
  url: string;
  http_status: number;
  storage_path: string;
}

export interface AssetRecord {
  original_url: string;
  asset_type: string;
  storage_path: string;
  content_type?: string | null;
}

export interface CrawlResponse {
  project_id: string;
  source_url: string;
  page_count: number;
  pages: PageRecord[];
  assets: AssetRecord[];
}

export interface ColorPalette {
  primary: string;
  secondary: string;
  accent: string;
}

export interface Fonts {
  heading: string;
  body: string;
}

export interface Frontmatter {
  site_name: string;
  colors: ColorPalette;
  logo?: string | null;
  fonts: Fonts;
  tone?: string | null;
}

export interface BlueprintResponse {
  project_id: string;
  design_md_path: string;
  frontmatter: Frontmatter;
  design_md: string;
}

export interface PostprocessReport {
  alt_text_added: string[];
  og_tags_added: string[];
  contrast_warnings: string[];
  sitemap_written: boolean;
}

export interface GenerationUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface GenerationResponse {
  project_id: string;
  tier: string;
  postprocess: PostprocessReport;
  template_used: string;
  output_dir: string;
  files: string[];
  summary: string;
  usage: GenerationUsage;
  iterations: number;
}

// --- Async job (Celery-backed) submission + polling ---

export interface ProjectSubmitResponse {
  project_id: string;
  status: string;
}

export interface ProjectBlueprintSummary {
  site_name?: string | null;
  colors?: ColorPalette | null;
  fonts?: Fonts | null;
  tone?: string | null;
}

export interface ProjectGenerationSummary {
  tier: string;
  template_used: string;
  preview_url_path: string;
  summary?: string | null;
  contrast_warnings: string[];
}

/** An enabled tier whose latest generation failed. Reported alongside any
 * tiers that succeeded -- one tier failing never fails the whole project,
 * and each failure is retryable at no extra credit cost. */
export interface ProjectTierFailure {
  tier: string;
  failure_reason?: string | null;
}

export interface TierRetryResponse {
  project_id: string;
  tier: string;
  status: string;
}

/** Only present while status === "awaiting_cost_approval" -- see
 * docs/generation-cost-gate-plan.md. */
export interface GenerationCostGateInfo {
  estimated_cost_usd: number;
  required_credits: number;
  current_balance: number;
  shortfall_credits: number;
}

export interface GenerationApprovalResponse {
  project_id: string;
  status: string;
  approved: boolean;
  estimated_cost_usd: number;
  required_credits: number;
  current_balance: number;
  shortfall_credits: number;
}

export interface ProjectStatusResponse {
  project_id: string;
  status: string;
  rejection_reason?: string | null;
  source_url: string;
  blueprint?: ProjectBlueprintSummary | null;
  /** One entry per tier that has finished generating so far -- populated
   * progressively, not only once the whole project is "ready". */
  generations: ProjectGenerationSummary[];
  tiers_total: number;
  tiers_completed: number;
  /** Tiers now fan out and generate independently, so more than one can be
   * "running" at once -- plural, not just the tail of a chain. */
  current_tiers: string[];
  /** Populated whenever an enabled tier's latest generation failed,
   * including on an otherwise-"ready" project where other tiers succeeded. */
  tier_failures: ProjectTierFailure[];
  cost_gate?: GenerationCostGateInfo | null;
  /** Tiers already paid for -- re-downloading these is free. */
  purchased_tiers: string[];
  /** Crawled page count -- "Generate all pages" is offered only when > 1. */
  page_count: number;
  /** Per finished tier: Generate all pages / Run SEO state. */
  tier_actions: Record<string, ProjectTierActions>;
}

export type TierActionStatus = 'none' | 'running' | 'succeeded' | 'failed';

/** Post-purchase action state for one tier (backend
 * services/tier_actions_service.py). `seo_available` is the single source
 * of truth for which tiers offer the SEO agent (Pro/Premium). */
export interface ProjectTierActions {
  full_site_status: TierActionStatus;
  full_site_failure_reason?: string | null;
  seo_available: boolean;
  seo_status: TierActionStatus;
  seo_failure_reason?: string | null;
  /** Live progress of the latest SEO run (user-facing slice; the full log
   * incl. debug entries is admin-only). */
  seo_progress?: JobProgress | null;
}

export interface JobProgressStep {
  key: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed';
}

export interface JobActivityEntry {
  at: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
}

/** A long-running job's progress (backend services/job_progress.py). */
export interface JobProgress {
  status: 'running' | 'succeeded' | 'failed';
  step?: string | null;
  label: string;
  percent: number;
  detail: string;
  steps: JobProgressStep[];
  /** Last few user-facing entries (status response) -- or the full log as
   * `log` on the admin project page. */
  activity?: JobActivityEntry[];
  log?: JobActivityEntry[];
  seconds?: number;
  updated_at?: string;
}

export interface ProjectListItem {
  project_id: string;
  source_url: string;
  status: string;
  created_at: string;
  tier?: string | null;
  purchased_tiers: string[];
}

// --- Auth (Google SSO) ---

export interface UserOut {
  id: string;
  email: string;
  is_admin: boolean;
}

export interface WalletResponse {
  balance: number;
}

// --- Preview (authed, owner-or-admin) ---

export interface PreviewTokenResponse {
  preview_token: string;
  expires_in: number;
}

// --- Buy a design, then Download / Generate all pages / Run SEO ---

export interface PurchaseResponse {
  purchased: boolean;
  project_id: string;
  tier: string;
}

/** POST /full-site and POST /seo -- the action is now running. */
export interface ActionStartResponse {
  status: 'running';
  project_id: string;
  tier: string;
  job_id: string;
}

/** Body of a 402 from POST /projects/{id}/purchase -- enough to offer an
 * exact top-up instead of a generic failure. */
export interface InsufficientCreditsDetail {
  message: string;
  required: number;
  balance: number;
  shortfall: number;
}

// --- Billing (PayPal credit packs) ---

export interface BillingConfigResponse {
  /** False until the backend has PayPal credentials configured. */
  enabled: boolean;
  /** 'mock' = local test mode: every payment succeeds, no PayPal involved. */
  mode: 'paypal' | 'mock';
  paypal_client_id: string;
  paypal_env: string;
  currency: string;
}

export interface CreditPack {
  id: string;
  name: string;
  credits: number;
  price_usd_cents: number;
}

export interface CreditPackListResponse {
  items: CreditPack[];
}

export interface CreateOrderResponse {
  order_id: string;
  purchase_id: string;
}

export interface CaptureResponse {
  status: 'completed' | 'pending' | 'failed' | 'refunded';
  credits_granted: number;
  balance: number;
  reason?: string | null;
}

export interface PurchaseHistoryItem {
  id: string;
  created_at: string;
  credits: number;
  amount_usd_cents: number;
  status: string;
  source: string;
}

export interface PurchaseHistoryResponse {
  items: PurchaseHistoryItem[];
}

export interface PublicTier {
  key: string;
  label: string;
  download_credit_cost: number;
}

export interface PublicTierListResponse {
  items: PublicTier[];
}
