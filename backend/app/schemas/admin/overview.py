from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    users_total: int
    users_new_in_range: int
    projects_total: int
    projects_in_range: int
    generation_success_rate_pct: float | None
    ai_cost_usd_in_range: float
    ai_cost_usd_all_time: float
    revenue_usd_in_range: float
    revenue_usd_all_time: float
    net_margin_usd_in_range: float
    credits_outstanding: int
    active_jobs_running: int
    # Payments (PayPal only -- never test or manual-adjustment rows).
    purchases_in_range: int = 0
    pending_purchases: int = 0
    refunds_in_range: int = 0
    paying_users: int = 0
