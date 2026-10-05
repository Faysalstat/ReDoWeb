from datetime import datetime

from pydantic import BaseModel


class AdminPaymentsStatusResponse(BaseModel):
    """Read-only: which payment mode is running. The mode itself is an .env
    setting on purpose -- a UI switch into test mode would be a free-credits
    button. Never carries a secret."""

    mode: str  # "mock" | "paypal_sandbox" | "paypal_live"
    mock_requested_but_ignored: bool
    paypal_configured: bool
    webhook_configured: bool


class AdminPurchaseRow(BaseModel):
    id: str
    user_id: str
    user_email: str | None = None
    pack_name: str | None = None
    created_at: datetime
    credits_granted: int
    amount_usd_cents: int
    status: str
    source: str
    paypal_order_id: str | None = None
    paypal_capture_id: str | None = None
    note: str | None = None
    refunded_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by_email: str | None = None


class AdminPurchaseListResponse(BaseModel):
    items: list[AdminPurchaseRow]
    total: int
    page: int
    page_size: int


class AdminPurchaseLedgerEntry(BaseModel):
    id: str
    amount: int
    reason: str
    created_at: datetime


class AdminPurchaseDetailResponse(BaseModel):
    purchase: AdminPurchaseRow
    # Ledger rows linked to this purchase: the original credit grant and any
    # take-back after a refund.
    ledger: list[AdminPurchaseLedgerEntry]
    credits_taken_back: int
    can_recheck: bool
    can_take_back: bool
    can_mark_failed: bool


class AdminPurchaseNoteRequest(BaseModel):
    note: str


class AdminPurchaseActionResponse(BaseModel):
    """Result of Re-check / Mark as failed: what the payment provider said,
    plus the purchase as it is now."""

    status: str
    credits_granted: int
    reason: str | None = None
    marked_failed: bool | None = None
    purchase: AdminPurchaseRow


class AdminTakeBackResponse(BaseModel):
    taken_back: int
    requested: int
    balance_after: int
    already_done: bool
    purchase: AdminPurchaseRow
