from pydantic import BaseModel


class AdminRevenueResponse(BaseModel):
    revenue_usd_in_range: float
    revenue_usd_all_time: float
    stripe_revenue_usd_in_range: float
    manual_revenue_usd_in_range: float
    purchase_count_in_range: int
