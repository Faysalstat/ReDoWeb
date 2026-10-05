"""PayPal credit-pack purchases -- see docs/paypal-payments-plan.md.

Flow: create_order() writes a `pending` Purchase snapshotting the pack's
credits/price and creates the PayPal order for exactly that price; the
browser's onApprove calls capture_for_user(); PayPal's webhook
(handle_webhook_event) is the safety net for a buyer who closed the tab
after approving. Both paths converge on _capture_and_fulfill()/
_apply_capture() under a FOR UPDATE lock on the Purchase row, and the
ledger grant uses idempotency key `purchase:{id}` -- so a purchase is
credited exactly once even though the two paths routinely race (PayPal
sends CHECKOUT.ORDER.APPROVED for nearly every order).

Callers commit. Nothing here commits, so a PayPal failure inside
create_order() leaves no pending row behind once the router rolls back.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CreditPack, Purchase
from ..payments import mock_gateway, paypal_client
from ..payments.paypal_client import CURRENCY, PayPalError
from . import wallet_service

logger = logging.getLogger(__name__)

PurchaseOutcomeStatus = Literal["completed", "pending", "failed", "refunded"]


class PackNotFoundError(Exception):
    """Unknown or inactive credit pack -- router maps to 404."""


class PurchaseNotFoundError(Exception):
    """No purchase for this order id, or it isn't the caller's -- router
    maps to 404 (same response for both, like GET /projects/{id})."""


@dataclass(frozen=True)
class CaptureInfo:
    id: str
    status: str
    amount_value: str | None
    currency: str | None


@dataclass(frozen=True)
class CaptureOutcome:
    status: PurchaseOutcomeStatus
    credits_granted: int
    reason: str | None = None


# --- pure helpers (unit-tested directly) ------------------------------------


def to_cents(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        cents = Decimal(value) * 100
    except InvalidOperation:
        return None
    if cents != cents.to_integral_value():
        return None
    return int(cents)


def extract_capture(order: dict) -> CaptureInfo | None:
    """The first capture in a PayPal order payload, or None if the order
    hasn't been captured yet."""
    for unit in order.get("purchase_units") or []:
        captures = ((unit or {}).get("payments") or {}).get("captures") or []
        if captures:
            return capture_from_resource(captures[0])
    return None


def capture_from_resource(resource: dict) -> CaptureInfo | None:
    if not resource or not resource.get("id"):
        return None
    amount = resource.get("amount") or {}
    return CaptureInfo(
        id=resource["id"],
        status=str(resource.get("status") or "").upper(),
        amount_value=amount.get("value"),
        currency=amount.get("currency_code"),
    )


def validate_capture(
    capture: CaptureInfo | None, expected_cents: int
) -> tuple[PurchaseOutcomeStatus, str | None]:
    """Decides what a capture means for the purchase. Credits are only ever
    granted for a COMPLETED capture whose amount and currency match the
    server-side snapshot exactly -- anything else that took money (a
    mismatch) is `failed` for an admin to resolve by hand, never a grant."""
    if capture is None:
        return "pending", "PayPal has not captured this order yet"
    if capture.status == "COMPLETED":
        if capture.currency != CURRENCY:
            return "failed", f"captured in {capture.currency}, expected {CURRENCY}"
        if to_cents(capture.amount_value) != expected_cents:
            return "failed", f"captured {capture.amount_value}, expected {paypal_client.format_amount(expected_cents)}"
        return "completed", None
    if capture.status == "PENDING":
        return "pending", "PayPal is still processing this payment"
    if capture.status in ("REFUNDED", "PARTIALLY_REFUNDED"):
        return "refunded", f"capture is {capture.status}"
    return "failed", f"capture status {capture.status or 'unknown'}"


# --- queries -----------------------------------------------------------------


def list_active_packs(db: Session) -> list[CreditPack]:
    return list(
        db.scalars(
            select(CreditPack)
            .where(CreditPack.is_active.is_(True))
            .order_by(CreditPack.sort_order, CreditPack.price_usd_cents)
        ).all()
    )


def list_user_purchases(db: Session, user_id: uuid.UUID) -> list[Purchase]:
    return list(
        db.scalars(
            select(Purchase).where(Purchase.user_id == user_id).order_by(Purchase.created_at.desc())
        ).all()
    )


# Purchases created through a payment gateway (vs. source="manual_admin").
GATEWAY_SOURCES = ("paypal", mock_gateway.SOURCE)


def _gateway(purchase: Purchase):
    """The module that talks to the payment provider for this purchase --
    the always-succeeds mock for a source="mock" purchase (local testing
    only, see payments/mock_gateway.py), real PayPal otherwise. Chosen per
    purchase, so flipping the mode never sends a mock order to PayPal."""
    return mock_gateway if purchase.source == mock_gateway.SOURCE else paypal_client


def _lock_purchase_by_order(db: Session, order_id: str) -> Purchase | None:
    return (
        db.query(Purchase)
        .filter(Purchase.paypal_order_id == order_id, Purchase.source.in_(GATEWAY_SOURCES))
        .with_for_update()
        .one_or_none()
    )


def _lock_purchase_by_id(db: Session, purchase_id: str | None) -> Purchase | None:
    try:
        parsed = uuid.UUID(str(purchase_id))
    except (TypeError, ValueError):
        return None
    return (
        db.query(Purchase)
        .filter(Purchase.id == parsed, Purchase.source.in_(GATEWAY_SOURCES))
        .with_for_update()
        .one_or_none()
    )


def _lock_purchase_by_capture(db: Session, capture_id: str | None) -> Purchase | None:
    if not capture_id:
        return None
    return (
        db.query(Purchase).filter(Purchase.paypal_capture_id == capture_id).with_for_update().one_or_none()
    )


# --- order lifecycle -----------------------------------------------------------


def create_order(db: Session, user_id: uuid.UUID, pack_id: uuid.UUID) -> Purchase:
    """Snapshots the pack into a pending Purchase and creates the matching
    PayPal order. The price sent to PayPal comes only from this server-side
    snapshot, never from the client. Raises PackNotFoundError or
    PayPalError; caller commits on success."""
    pack = db.get(CreditPack, pack_id)
    if pack is None or not pack.is_active:
        raise PackNotFoundError(f"no active credit pack {pack_id}")

    purchase = Purchase(
        user_id=user_id,
        amount_usd_cents=pack.price_usd_cents,
        credits_granted=pack.credits,
        status="pending",
        source=mock_gateway.SOURCE if mock_gateway.is_active() else "paypal",
        credit_pack_id=pack.id,
    )
    db.add(purchase)
    db.flush()

    purchase.paypal_order_id = _gateway(purchase).create_order(
        purchase_id=str(purchase.id),
        amount_cents=pack.price_usd_cents,
        description=f"{pack.credits} ReDoWebs credits ({pack.name})",
    )
    db.flush()
    return purchase


def capture_for_user(db: Session, user_id: uuid.UUID, order_id: str) -> CaptureOutcome:
    """The browser's onApprove path. Ownership is checked here (and only
    here -- the webhook path has no user)."""
    purchase = _lock_purchase_by_order(db, order_id)
    if purchase is None or purchase.user_id != user_id:
        raise PurchaseNotFoundError(f"no purchase for order {order_id}")
    return _capture_and_fulfill(db, purchase)


def _outcome_for_settled(purchase: Purchase) -> CaptureOutcome | None:
    """Only `completed` and `refunded` are terminal. `failed` deliberately
    is not: after a declined capture PayPal lets the buyer retry the same
    order with another funding source, and that later COMPLETED capture
    must still be able to grant credits. Re-validating a failed purchase is
    harmless -- a mismatched capture just fails validation again."""
    if purchase.status == "completed":
        return CaptureOutcome("completed", purchase.credits_granted)
    if purchase.status == "refunded":
        return CaptureOutcome("refunded", 0, purchase.note)
    return None


def _capture_and_fulfill(db: Session, purchase: Purchase) -> CaptureOutcome:
    """Captures the (already locked) purchase's order and applies the
    result. Shared by the browser and the CHECKOUT.ORDER.APPROVED webhook.

    - Already settled -> returned as-is, no PayPal call (the racing path
      that lost the lock lands here).
    - 422 ORDER_ALREADY_CAPTURED -> not an error: the other path captured
      first, so fetch the order and fulfil from its existing capture.
    - Timeout/network/5xx -> purchase stays pending; a retry is safe
      (PayPal-Request-Id) and the webhook completes it otherwise.
    - Any other rejection (e.g. INSTRUMENT_DECLINED) -> reported as failed
      to the caller but the purchase stays pending: PayPal lets the buyer
      retry the same order with another funding source.
    """
    settled = _outcome_for_settled(purchase)
    if settled is not None:
        return settled

    try:
        order = _gateway(purchase).capture_order(purchase.paypal_order_id)
    except PayPalError as exc:
        if exc.issue == "ORDER_ALREADY_CAPTURED":
            try:
                order = _gateway(purchase).get_order(purchase.paypal_order_id)
            except PayPalError as fetch_exc:
                logger.warning("purchase %s: order already captured but fetch failed: %s", purchase.id, fetch_exc)
                return CaptureOutcome("pending", 0, "Payment received, confirming with PayPal")
        elif exc.transient:
            logger.warning("purchase %s: capture got no clean answer from PayPal: %s", purchase.id, exc)
            return CaptureOutcome("pending", 0, "PayPal did not respond in time; your payment will be confirmed shortly")
        else:
            logger.info("purchase %s: capture rejected (%s): %s", purchase.id, exc.issue, exc)
            return CaptureOutcome("failed", 0, exc.issue or str(exc))

    return _apply_capture(db, purchase, extract_capture(order))


def _apply_capture(db: Session, purchase: Purchase, capture: CaptureInfo | None) -> CaptureOutcome:
    settled = _outcome_for_settled(purchase)
    if settled is not None:
        return settled

    status, reason = validate_capture(capture, purchase.amount_usd_cents)
    if capture is not None:
        purchase.paypal_capture_id = capture.id

    if status == "completed":
        wallet_service.grant_purchase_credits(
            db,
            purchase.user_id,
            purchase.credits_granted,
            purchase_id=purchase.id,
            idempotency_key=f"purchase:{purchase.id}",
        )
        purchase.status = "completed"
        db.flush()
        return CaptureOutcome("completed", purchase.credits_granted)

    if status == "pending":
        db.flush()
        return CaptureOutcome("pending", 0, reason)

    purchase.status = status
    purchase.note = reason
    if status == "refunded":
        mark_refunded(purchase, reason)
    db.flush()
    logger.warning("purchase %s marked %s: %s", purchase.id, status, reason)
    return CaptureOutcome(status, 0, reason)


def mark_refunded(purchase: Purchase, note: str | None) -> None:
    """The one place a purchase becomes refunded, so `refunded_at` is set on
    every path (webhook, a capture that comes back refunded, admin re-check).
    Credits are never reversed here -- PRD: refunds are reconciled manually
    (admin "Take back credits", admin_payments_service.take_back_credits)."""
    purchase.status = "refunded"
    if purchase.refunded_at is None:
        purchase.refunded_at = datetime.now(timezone.utc)
    if note:
        purchase.note = note


# --- admin re-check ------------------------------------------------------------


@dataclass(frozen=True)
class RecheckOutcome:
    outcome: CaptureOutcome
    # True only when PayPal positively said the buyer never approved the
    # order (or it's voided/expired) -- the one situation in which an admin
    # may mark the purchase failed.
    never_approved: bool = False


_NEVER_APPROVED_STATUSES = {"CREATED", "SAVED", "PAYER_ACTION_REQUIRED"}


def recheck_purchase(db: Session, purchase: Purchase) -> RecheckOutcome:
    """Asks the purchase's gateway what really happened to its order and
    reconciles -- for purchases a webhook never resolved (always the case
    locally). The caller must hold the Purchase row lock. Never
    double-grants (same `purchase:{id}` ledger key as capture/webhook).

    - pending/failed: COMPLETED capture -> credits granted; APPROVED but
      uncaptured -> captured now; never approved -> stays pending; VOIDED or
      404 (expired) -> failed.
    - completed: a capture now REFUNDED -> marked refunded (credits kept;
      taking them back is a separate admin action); otherwise unchanged.
    - refunded: no change.

    Raises PayPalNotConfiguredError, or PayPalError with transient=True when
    PayPal didn't answer -- nothing is changed in either case.
    """
    if purchase.status == "refunded":
        return RecheckOutcome(CaptureOutcome("refunded", 0, "Already marked refunded"))

    gateway = _gateway(purchase)
    try:
        order = gateway.get_order(purchase.paypal_order_id)
    except PayPalError as exc:
        expired = exc.status_code == 404 or exc.issue == "RESOURCE_NOT_FOUND"
        if not expired:
            raise
        if purchase.status == "completed":
            return RecheckOutcome(CaptureOutcome("completed", purchase.credits_granted, "PayPal no longer has this order"))
        reason = "PayPal no longer has this order (it expired without payment)"
        purchase.status = "failed"
        purchase.note = reason
        db.flush()
        return RecheckOutcome(CaptureOutcome("failed", 0, reason), never_approved=True)

    order_status = str(order.get("status") or "").upper()
    capture = extract_capture(order)

    if purchase.status == "completed":
        if capture is not None and capture.status in ("REFUNDED", "PARTIALLY_REFUNDED"):
            mark_refunded(purchase, f"Refund found by admin re-check (capture {capture.status}); credits not taken back yet")
            db.flush()
            return RecheckOutcome(CaptureOutcome("refunded", 0, purchase.note))
        return RecheckOutcome(CaptureOutcome("completed", purchase.credits_granted, "Still paid at PayPal"))

    if capture is not None:
        return RecheckOutcome(_apply_capture(db, purchase, capture))
    if order_status == "APPROVED":
        return RecheckOutcome(_capture_and_fulfill(db, purchase))
    if order_status == "VOIDED":
        reason = "PayPal voided this order"
        purchase.status = "failed"
        purchase.note = reason
        db.flush()
        return RecheckOutcome(CaptureOutcome("failed", 0, reason), never_approved=True)
    if order_status in _NEVER_APPROVED_STATUSES:
        return RecheckOutcome(
            CaptureOutcome("pending", 0, "The buyer never approved this payment"), never_approved=True
        )
    return RecheckOutcome(CaptureOutcome("pending", 0, f"PayPal order status {order_status or 'unknown'}"))


# --- webhooks ------------------------------------------------------------------


def _refund_capture_id(resource: dict) -> str | None:
    """A refund resource links back to its capture via rel=up
    (.../v2/payments/captures/{id})."""
    for link in resource.get("links") or []:
        if link.get("rel") == "up" and "/captures/" in (link.get("href") or ""):
            return link["href"].rstrip("/").rsplit("/", 1)[-1]
    return None


def handle_webhook_event(db: Session, event: dict) -> str:
    """Applies an already signature-verified webhook event. Returns a short
    description of what happened, for logging. Unknown purchases and
    unhandled event types are ignored (PayPal still gets a 200 so it stops
    retrying an event we will never act on)."""
    event_type = event.get("event_type") or ""
    resource = event.get("resource") or {}

    if event_type == "CHECKOUT.ORDER.APPROVED":
        purchase = _lock_purchase_by_order(db, resource.get("id") or "")
        if purchase is None:
            return "ignored: unknown order"
        return f"order approved -> {_capture_and_fulfill(db, purchase).status}"

    if event_type in ("PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.PENDING", "PAYMENT.CAPTURE.DENIED"):
        order_id = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
        purchase = _lock_purchase_by_order(db, order_id) if order_id else None
        if purchase is None:
            purchase = _lock_purchase_by_id(db, resource.get("custom_id"))
        if purchase is None:
            return "ignored: unknown purchase"
        return f"{event_type} -> {_apply_capture(db, purchase, capture_from_resource(resource)).status}"

    if event_type in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"):
        purchase = _lock_purchase_by_capture(db, _refund_capture_id(resource))
        if purchase is None:
            purchase = _lock_purchase_by_capture(db, resource.get("id"))
        if purchase is None:
            purchase = _lock_purchase_by_id(db, resource.get("custom_id"))
        if purchase is None:
            return "ignored: unknown purchase"
        # Marked only -- credits are never clawed back automatically (PRD:
        # refund reconciliation is manual, via the admin adjustment tool).
        mark_refunded(purchase, f"{event_type} received; credits not reversed automatically")
        db.flush()
        logger.warning("purchase %s refunded/reversed at PayPal; review the user's balance", purchase.id)
        return f"{event_type} -> refunded"

    return f"ignored: {event_type or 'no event_type'}"
