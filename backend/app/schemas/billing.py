import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class BillingConfigResponse(BaseModel):
    """Everything the frontend needs to load the PayPal JS SDK. The client
    id is public by design; `enabled` is false until the backend has PayPal
    credentials, so the checkout page can say so instead of erroring."""

    enabled: bool
    # "paypal" or "mock" -- in mock mode the checkout shows a test-payment
    # button instead of loading the PayPal SDK.
    mode: str
    paypal_client_id: str
    paypal_env: str
    currency: str


class CreditPackResponse(BaseModel):
    id: str
    name: str
    credits: int
    price_usd_cents: int


class CreditPackListResponse(BaseModel):
    items: list[CreditPackResponse]


class CreateOrderRequest(BaseModel):
    pack_id: uuid.UUID


class CreateOrderResponse(BaseModel):
    order_id: str
    purchase_id: str


class CaptureResponse(BaseModel):
    status: Literal["completed", "pending", "failed", "refunded"]
    credits_granted: int
    balance: int
    reason: str | None = None


class PurchaseHistoryItem(BaseModel):
    id: str
    created_at: datetime
    credits: int
    amount_usd_cents: int
    status: str
    source: str


class PurchaseHistoryResponse(BaseModel):
    items: list[PurchaseHistoryItem]


class PublicTierResponse(BaseModel):
    key: str
    label: str
    download_credit_cost: int


class PublicTierListResponse(BaseModel):
    items: list[PublicTierResponse]
