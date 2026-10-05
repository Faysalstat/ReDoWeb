"""PayPal credit-pack purchases -- see docs/paypal-payments-plan.md and
services/billing_service.py for the flow and its exactly-once guarantees.
Config and pack listing are public (the /pricing page and the home page's
pricing section are public routes); creating/capturing orders needs a
login; the webhook is authenticated by PayPal's signature, not a JWT."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..db.session import get_db
from ..models import User
from ..payments import mock_gateway, paypal_client
from ..payments.paypal_client import PayPalError, PayPalNotConfiguredError
from ..rate_limit import limiter
from ..schemas.billing import (
    BillingConfigResponse,
    CaptureResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    CreditPackListResponse,
    CreditPackResponse,
    PurchaseHistoryItem,
    PurchaseHistoryResponse,
)
from ..services import billing_service, wallet_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/config", response_model=BillingConfigResponse)
def get_billing_config() -> BillingConfigResponse:
    settings = get_settings()
    if mock_gateway.is_active():
        return BillingConfigResponse(
            enabled=True, mode="mock", paypal_client_id="", paypal_env="mock", currency=paypal_client.CURRENCY
        )
    return BillingConfigResponse(
        enabled=paypal_client.is_configured(),
        mode="paypal",
        paypal_client_id=settings.paypal_client_id,
        paypal_env=settings.paypal_env,
        currency=paypal_client.CURRENCY,
    )


@router.get("/credit-packs", response_model=CreditPackListResponse)
def list_credit_packs(db: Session = Depends(get_db)) -> CreditPackListResponse:
    return CreditPackListResponse(
        items=[
            CreditPackResponse(
                id=str(pack.id), name=pack.name, credits=pack.credits, price_usd_cents=pack.price_usd_cents
            )
            for pack in billing_service.list_active_packs(db)
        ]
    )


@router.post("/paypal/orders", response_model=CreateOrderResponse)
@limiter.limit(get_settings().rate_limit_checkout)
def create_paypal_order(
    request: Request,
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreateOrderResponse:
    try:
        purchase = billing_service.create_order(db, current_user.id, body.pack_id)
    except billing_service.PackNotFoundError as exc:
        raise HTTPException(status_code=404, detail="That credit pack is not available") from exc
    except PayPalNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="Payments are not configured") from exc
    except PayPalError as exc:
        logger.warning("PayPal create-order failed for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=502, detail="PayPal could not start this payment, please try again") from exc
    db.commit()
    return CreateOrderResponse(order_id=purchase.paypal_order_id, purchase_id=str(purchase.id))


@router.post("/paypal/orders/{order_id}/capture", response_model=CaptureResponse)
def capture_paypal_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaptureResponse:
    try:
        outcome = billing_service.capture_for_user(db, current_user.id, order_id)
    except billing_service.PurchaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No such order") from exc
    except PayPalNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="Payments are not configured") from exc
    db.commit()
    balance = wallet_service.get_or_create_wallet(db, current_user.id).balance
    db.commit()
    return CaptureResponse(
        status=outcome.status, credits_granted=outcome.credits_granted, balance=balance, reason=outcome.reason
    )


@router.get("/purchases", response_model=PurchaseHistoryResponse)
def list_my_purchases(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> PurchaseHistoryResponse:
    return PurchaseHistoryResponse(
        items=[
            PurchaseHistoryItem(
                id=str(p.id),
                created_at=p.created_at,
                credits=p.credits_granted,
                amount_usd_cents=p.amount_usd_cents,
                status=p.status,
                source=p.source,
            )
            for p in billing_service.list_user_purchases(db, current_user.id)
        ]
    )


@router.post("/paypal/webhook")
def paypal_webhook(request: Request, event: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """400 on an unverified event (nothing is ever granted). 503 when PayPal
    itself couldn't be reached to verify -- a 5xx makes PayPal redeliver
    later. Sync on purpose: the DB session is synchronous, and an async
    handler would block the event loop on it. `event` is the parsed body as
    received, which is what PayPal's verify call expects back."""
    try:
        verified = paypal_client.verify_webhook_signature(request.headers, event)
    except PayPalError as exc:
        logger.warning("PayPal webhook verification call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Could not verify webhook") from exc
    if not verified:
        logger.warning("Rejected unverified PayPal webhook %s (%s)", event.get("id"), event.get("event_type"))
        raise HTTPException(status_code=400, detail="Signature verification failed")

    result = billing_service.handle_webhook_event(db, event)
    db.commit()
    logger.info("PayPal webhook %s (%s): %s", event.get("id"), event.get("event_type"), result)
    return {"status": "ok"}
