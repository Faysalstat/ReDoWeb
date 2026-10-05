from datetime import datetime

from pydantic import BaseModel, Field


class AdminTierRow(BaseModel):
    key: str
    label: str
    is_active: bool
    sort_order: int
    download_credit_cost: int
    updated_at: datetime
    updated_by_admin_id: str | None = None


class AdminTierListResponse(BaseModel):
    items: list[AdminTierRow]


class AdminTierUpdateRequest(BaseModel):
    """`key` is deliberately absent: it's embedded in storage paths and
    generation history, so it can never be edited."""

    label: str = Field(min_length=1, max_length=64)
    sort_order: int
    download_credit_cost: int = Field(ge=1)


class AdminTierActiveRequest(BaseModel):
    is_active: bool
