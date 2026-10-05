export interface AdminOverviewResponse {
  users_total: number;
  users_new_in_range: number;
  projects_total: number;
  projects_in_range: number;
  generation_success_rate_pct: number | null;
  ai_cost_usd_in_range: number;
  ai_cost_usd_all_time: number;
  revenue_usd_in_range: number;
  revenue_usd_all_time: number;
  net_margin_usd_in_range: number;
  credits_outstanding: number;
  active_jobs_running: number;
  // Payments -- PayPal only, never test or manual-adjustment rows.
  purchases_in_range: number;
  pending_purchases: number;
  refunds_in_range: number;
  paying_users: number;
}

// -- Projects (cross-user browse + detail) ----------------------------------

export interface AdminProjectListItem {
  project_id: string;
  source_url: string;
  status: string;
  owner_email: string;
  tier: string | null;
  created_at: string;
}

export interface AdminProjectListResponse {
  items: AdminProjectListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminBlueprintSummary {
  site_name: string | null;
  colors: Record<string, unknown> | null;
  fonts: Record<string, unknown> | null;
  tone: string | null;
  version: number;
}

export interface AdminGenerationOutputSummary {
  template_used: string;
  preview_url_path: string;
  summary: string | null;
  contrast_warnings: string[];
  prompt_tokens: number;
  completion_tokens: number;
  iterations: number;
}

export interface AdminGenerationJobSummary {
  job_id: string;
  tier: string;
  scope: string;
  overall_status: string;
  failure_reason: string | null;
  created_at: string;
  finished_at: string | null;
  output: AdminGenerationOutputSummary | null;
  models_used: string[];
  total_cost_usd: number;
}

export interface AdminProjectDetailResponse {
  project_id: string;
  source_url: string;
  status: string;
  rejection_reason: string | null;
  owner_email: string;
  owner_id: string;
  created_at: string;
  blueprint: AdminBlueprintSummary | null;
  generation_jobs: AdminGenerationJobSummary[];
  paid_tiers: AdminPaidTier[];
}

export interface AdminPaidTier {
  tier: string;
  credits: number;
  charged_at: string;
}

// -- Users --------------------------------------------------------------

export interface AdminUserListItem {
  user_id: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  wallet_balance: number;
  projects_count: number;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminCreditLedgerEntry {
  id: string;
  amount: number;
  reason: string;
  related_project_id: string | null;
  related_job_id: string | null;
  related_purchase_id: string | null;
  created_at: string;
}

export interface AdminUserPurchase {
  id: string;
  created_at: string;
  credits_granted: number;
  amount_usd_cents: number;
  status: string;
  source: string;
}

export interface AdminUserDetailResponse {
  user_id: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  wallet_balance: number;
  ledger: AdminCreditLedgerEntry[];
  purchases: AdminUserPurchase[];
  projects: AdminProjectListItem[];
}

// -- Credits / refunds --------------------------------------------------

export interface AdminIssueAdjustmentRequest {
  amount: number;
  note: string;
  related_project_id?: string | null;
}

export interface AdminAdjustmentResponse {
  wallet_balance: number;
  transaction_id: string;
  purchase_id: string;
}

// -- Cost / token usage ---------------------------------------------------

export interface AdminModelCostRow {
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  call_count: number;
}

export interface AdminModelCostResponse {
  items: AdminModelCostRow[];
}

export interface AdminCostByUserRow {
  user_id: string;
  email: string;
  cost_usd: number;
  call_count: number;
}

export interface AdminCostByUserResponse {
  items: AdminCostByUserRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminCostByProjectRow {
  project_id: string;
  source_url: string;
  cost_usd: number;
  call_count: number;
}

export interface AdminCostByProjectResponse {
  items: AdminCostByProjectRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminModelPricingRow {
  model_name: string;
  prompt_price_per_1m: number;
  completion_price_per_1m: number;
  updated_at: string | null;
  updated_by_admin_id: string | null;
}

export interface AdminModelPricingResponse {
  items: AdminModelPricingRow[];
}

export interface AdminModelPricingUpdateRequest {
  prompt_price_per_1m: number;
  completion_price_per_1m: number;
}

// -- Model config (generation / vision model) ----------------------------

export interface AdminTierModelRow {
  key: string;
  label: string;
  is_active: boolean;
  generation_model: string | null;
  effective_generation_model: string;
  updated_at: string;
  updated_by_admin_id: string | null;
}

export interface AdminTierModelListResponse {
  items: AdminTierModelRow[];
}

export interface AdminTierModelUpdateRequest {
  generation_model: string | null;
}

export interface AdminVisionModelResponse {
  model_name: string | null;
  effective_model_name: string;
  updated_at: string | null;
  updated_by_admin_id: string | null;
}

export interface AdminVisionModelUpdateRequest {
  model_name: string;
}

// -- Prompt templates -----------------------------------------------------

export interface AdminPromptTemplateRow {
  filename: string;
  category: string;
  is_active: boolean;
  uploaded_by_admin_id: string | null;
  uploaded_at: string | null;
}

export interface AdminPromptTemplateListResponse {
  items: AdminPromptTemplateRow[];
}

// -- Cost gate (pre-generation cost estimate + wallet-balance gate) --------
// See docs/generation-cost-gate-plan.md.

export interface AdminCostSettingResponse {
  value: number;
  is_default: boolean;
  updated_at: string | null;
  updated_by_admin_id: string | null;
}

export interface AdminCostSettingUpdateRequest {
  value: number;
}

// -- Earnings ---------------------------------------------------------------

export interface AdminRevenueResponse {
  revenue_usd_in_range: number;
  revenue_usd_all_time: number;
  paypal_revenue_usd_in_range: number;
  manual_revenue_usd_in_range: number;
  purchase_count_in_range: number;
}

// -- Credit packs + purchases (PayPal) -----------------------------------------
// See docs/paypal-payments-plan.md.

export interface AdminCreditPackRow {
  id: string;
  name: string;
  credits: number;
  price_usd_cents: number;
  is_active: boolean;
  sort_order: number;
  updated_at: string | null;
  updated_by_admin_id: string | null;
}

export interface AdminCreditPackListResponse {
  items: AdminCreditPackRow[];
}

export interface AdminCreditPackCreateRequest {
  name: string;
  credits: number;
  price_usd_cents: number;
  is_active: boolean;
  sort_order: number;
}

export interface AdminCreditPackUpdateRequest {
  name: string;
  credits: number;
  price_usd_cents: number;
  sort_order: number;
}

// -- Payments (purchases + admin actions) -------------------------------------
// See docs/admin-payments-plan.md.

export type AdminPaymentsMode = 'mock' | 'paypal_sandbox' | 'paypal_live';

export interface AdminPaymentsStatusResponse {
  mode: AdminPaymentsMode;
  mock_requested_but_ignored: boolean;
  paypal_configured: boolean;
  webhook_configured: boolean;
}

export interface AdminPurchaseRow {
  id: string;
  user_id: string;
  user_email: string | null;
  pack_name: string | null;
  created_at: string;
  credits_granted: number;
  amount_usd_cents: number;
  status: string;
  source: string;
  paypal_order_id: string | null;
  paypal_capture_id: string | null;
  note: string | null;
  refunded_at: string | null;
  resolved_at: string | null;
  resolved_by_email: string | null;
}

export interface AdminPurchaseListResponse {
  items: AdminPurchaseRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminPurchaseLedgerEntry {
  id: string;
  amount: number;
  reason: string;
  created_at: string;
}

export interface AdminPurchaseDetailResponse {
  purchase: AdminPurchaseRow;
  ledger: AdminPurchaseLedgerEntry[];
  credits_taken_back: number;
  can_recheck: boolean;
  can_take_back: boolean;
  can_mark_failed: boolean;
}

export interface AdminPurchaseActionResponse {
  status: string;
  credits_granted: number;
  reason: string | null;
  marked_failed: boolean | null;
  purchase: AdminPurchaseRow;
}

export interface AdminTakeBackResponse {
  taken_back: number;
  requested: number;
  balance_after: number;
  already_done: boolean;
  purchase: AdminPurchaseRow;
}

// -- Tiers & pricing ---------------------------------------------------------

export interface AdminTierRow {
  key: string;
  label: string;
  is_active: boolean;
  sort_order: number;
  download_credit_cost: number;
  updated_at: string;
  updated_by_admin_id: string | null;
}

export interface AdminTierListResponse {
  items: AdminTierRow[];
}

export interface AdminTierUpdateRequest {
  label: string;
  sort_order: number;
  download_credit_cost: number;
}
