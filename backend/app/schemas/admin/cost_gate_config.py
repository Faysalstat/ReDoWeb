from datetime import datetime

from pydantic import BaseModel


class AdminCostSettingResponse(BaseModel):
    """Shared shape for both cost-gate settings (generation_cost_alert_usd,
    usd_per_credit) -- both are a single admin-editable float with the same
    row-present-wins-else-config-default semantics, so one response schema
    covers both endpoints in routers/admin/cost_gate_config.py."""

    value: float
    is_default: bool
    updated_at: datetime | None = None
    updated_by_admin_id: str | None = None


class AdminCostSettingUpdateRequest(BaseModel):
    value: float
