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
}
