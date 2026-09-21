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
    created_at: datetime


class AdminUserDetailResponse(BaseModel):
    user_id: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    wallet_balance: int
    ledger: list[AdminCreditLedgerEntry]
    # Reuses the existing cross-user project schema so the frontend can
    # reuse the same row-rendering component as the standalone Projects page.
    projects: list[AdminProjectListItem]
