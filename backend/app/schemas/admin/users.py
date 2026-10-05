from datetime import datetime

from pydantic import BaseModel

from .projects import AdminProjectListItem


class AdminUserListItem(BaseModel):
    user_id: str
    email: str
    is_admin: bool
    is_active: bool
    wallet_balance: int
    projects_count: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminCreditLedgerEntry(BaseModel):
    id: str
    amount: int
    reason: str
    related_project_id: str | None = None
    related_job_id: str | None = None
    related_purchase_id: str | None = None
    created_at: datetime


class AdminUserPurchase(BaseModel):
    id: str
    created_at: datetime
    credits_granted: int
    amount_usd_cents: int
    status: str
    source: str


class AdminUserDetailResponse(BaseModel):
    user_id: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    wallet_balance: int
    ledger: list[AdminCreditLedgerEntry]
    # Every purchase incl. test (source="mock") and manual adjustments --
    # the frontend labels them; on one user's page there's nothing to hide.
    purchases: list[AdminUserPurchase] = []
    # Reuses the existing cross-user project schema so the frontend can
    # reuse the same row-rendering component as the standalone Projects page.
    projects: list[AdminProjectListItem]
