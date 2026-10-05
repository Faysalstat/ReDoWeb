from datetime import datetime

from pydantic import BaseModel, Field


class AdminCreditPackRow(BaseModel):
    id: str
    name: str
    credits: int
    price_usd_cents: int
    is_active: bool
    sort_order: int
    updated_at: datetime | None = None
    updated_by_admin_id: str | None = None


class AdminCreditPackListResponse(BaseModel):
    items: list[AdminCreditPackRow]


class AdminCreditPackCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    credits: int = Field(ge=1)
    price_usd_cents: int = Field(ge=1)
    is_active: bool = False
    sort_order: int = 0


class AdminCreditPackUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    credits: int = Field(ge=1)
    price_usd_cents: int = Field(ge=1)
    sort_order: int = 0


class AdminCreditPackActiveRequest(BaseModel):
    is_active: bool

