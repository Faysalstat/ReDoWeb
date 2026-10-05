"""Admin actions on a single purchase -- see docs/admin-payments-plan.md.

Each action locks the Purchase row FOR UPDATE (the same lock the browser
capture and PayPal webhook take in billing_service, so an admin action can
never race a live payment), stamps resolved_by_admin_id/resolved_at, and is
safe to repeat. No action here sends or refunds money: refunds are made in
the PayPal dashboard, never from this app. Callers commit.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from ..config import get_settings
from ..models import CreditPack, CreditTransaction, CreditWallet, Purchase, User
from ..payments import mock_gateway, paypal_client
from . import billing_service, wallet_service
from .billing_service import CaptureOutcome

# A checkout younger than this may still be in progress -- don't let an
# admin fail it out from under a buyer who is mid-payment.
MARK_FAILED_MIN_AGE = timedelta(hours=24)


class PurchaseNotFoundError(LookupError):
    pass


class PurchaseActionNotAllowedError(Exception):
    """The purchase isn't in a state this action applies to (router: 409)."""


@dataclass(frozen=True)
class TakeBackResult:
    taken_back: int
    requested: int
    balance_after: int
    already_done: bool


@dataclass(frozen=True)
class MarkFailedResult:
    marked_failed: bool
    # What Re-check found. When marked_failed is False this explains why
    # (e.g. the buyer had actually paid, so the credits were granted).
    outcome: CaptureOutcome


def clawback_key(purchase_id: uuid.UUID) -> str:
    return f"refund_clawback:{purchase_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock(db: Session, purchase_id: uuid.UUID) -> Purchase:
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).with_for_update().one_or_none()
    if purchase is None:
        raise PurchaseNotFoundError(f"no purchase {purchase_id}")
    return purchase


def _require_gateway_purchase(purchase: Purchase) -> None:
    if purchase.source not in billing_service.GATEWAY_SOURCES or not purchase.paypal_order_id:
        raise PurchaseActionNotAllowedError("Only PayPal (or test) purchases can be checked with the payment provider")


def _stamp(purchase: Purchase, admin_id: uuid.UUID) -> None:
    purchase.resolved_by_admin_id = admin_id
    purchase.resolved_at = _now()


def _require_note(note: str) -> str:
    cleaned = (note or "").strip()
    if not cleaned:
        raise ValueError("a note is required")
    return cleaned


def recheck(db: Session, purchase_id: uuid.UUID, admin_id: uuid.UUID) -> CaptureOutcome:
    purchase = _lock(db, purchase_id)
    _require_gateway_purchase(purchase)
    result = billing_service.recheck_purchase(db, purchase)
    _stamp(purchase, admin_id)
    db.flush()
    return result.outcome


def take_back_credits(db: Session, purchase_id: uuid.UUID, admin_id: uuid.UUID, note: str) -> TakeBackResult:
    """Removes a refunded purchase's credits -- at most once per purchase
    (ledger key refund_clawback:{id}), and never more than the user still
    has. When the user has 0 credits nothing is written, so the action stays
    available for after they top up; a zero row would burn the once-only
    key for good."""
    cleaned = _require_note(note)
    purchase = _lock(db, purchase_id)
    if purchase.status != "refunded":
        raise PurchaseActionNotAllowedError("Credits can only be taken back from a refunded purchase")

    requested = purchase.credits_granted
    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.idempotency_key == clawback_key(purchase.id))
        .one_or_none()
    )
    wallet = (
        db.query(CreditWallet).filter(CreditWallet.user_id == purchase.user_id).with_for_update().one_or_none()
    )
    balance = wallet.balance if wallet is not None else 0
    if existing is not None:
        return TakeBackResult(taken_back=-existing.amount, requested=requested, balance_after=balance, already_done=True)

    amount = min(requested, balance)
    if amount <= 0:
        return TakeBackResult(taken_back=0, requested=requested, balance_after=balance, already_done=False)

    wallet, txn = wallet_service.admin_adjust(
        db, purchase.user_id, -amount, idempotency_key=clawback_key(purchase.id)
    )
    txn.related_purchase_id = purchase.id
    purchase.note = f"{amount} of {requested} credits taken back after refund: {cleaned}"
    _stamp(purchase, admin_id)
    db.flush()
    return TakeBackResult(taken_back=amount, requested=requested, balance_after=wallet.balance, already_done=False)


def mark_failed(
    db: Session, purchase_id: uuid.UUID, admin_id: uuid.UUID, note: str, *, now: datetime | None = None
) -> MarkFailedResult:
    """Closes an abandoned checkout. Re-checks with the payment provider
    first and only marks it failed when the provider positively says the
    buyer never paid -- if they did, the credits are granted instead. Still
    reversible in the right direction: `failed` isn't terminal, so a real
    payment that PayPal reports later still credits the buyer."""
    cleaned = _require_note(note)
    purchase = _lock(db, purchase_id)
    if purchase.status != "pending":
        raise PurchaseActionNotAllowedError("Only a pending purchase can be marked as failed")
    _require_gateway_purchase(purchase)
    created_at = purchase.created_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at is not None and (now or _now()) - created_at < MARK_FAILED_MIN_AGE:
        raise PurchaseActionNotAllowedError("This checkout is less than 24 hours old and may still be in progress")

    result = billing_service.recheck_purchase(db, purchase)
    _stamp(purchase, admin_id)
    if not result.never_approved:
        db.flush()
        return MarkFailedResult(marked_failed=False, outcome=result.outcome)

    purchase.status = "failed"
    purchase.note = f"Marked failed by admin ({result.outcome.reason}): {cleaned}"
    db.flush()
    return MarkFailedResult(marked_failed=True, outcome=CaptureOutcome("failed", 0, purchase.note))


# --- read side: status, list, detail -------------------------------------------


@dataclass(frozen=True)
class PaymentsStatus:
    mode: str
    mock_requested_but_ignored: bool
    paypal_configured: bool
    webhook_configured: bool


def payments_status() -> PaymentsStatus:
    settings = get_settings()
    if mock_gateway.is_active():
        mode = "mock"
    else:
        mode = "paypal_live" if settings.paypal_env.lower() == "live" else "paypal_sandbox"
    return PaymentsStatus(
        mode=mode,
        mock_requested_but_ignored=mock_gateway.is_requested() and not mock_gateway.is_active(),
        paypal_configured=paypal_client.is_configured(),
        webhook_configured=bool(settings.paypal_webhook_id),
    )


@dataclass(frozen=True)
class PurchaseView:
    purchase: Purchase
    user_email: str | None
    pack_name: str | None
    resolved_by_email: str | None


@dataclass(frozen=True)
class PurchaseListPage:
    items: list[PurchaseView]
    total: int


_Resolver = aliased(User)


def _view_query():
    return (
        select(Purchase, User.email, CreditPack.name, _Resolver.email)
        .join(User, User.id == Purchase.user_id)
        .outerjoin(CreditPack, CreditPack.id == Purchase.credit_pack_id)
        .outerjoin(_Resolver, _Resolver.id == Purchase.resolved_by_admin_id)
    )


def list_purchases(
    db: Session,
    *,
    status: str | None = None,
    source: str | None = None,
    email: str | None = None,
    include_mock: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> PurchaseListPage:
    """Newest first. Test (source="mock") purchases are hidden unless asked
    for -- an explicit source=mock always wins over include_mock=False, so
    the two filters can't silently cancel out to nothing."""
    filters = []
    if status:
        filters.append(Purchase.status == status)
    if source:
        filters.append(Purchase.source == source)
    elif not include_mock:
        filters.append(Purchase.source != mock_gateway.SOURCE)
    if email and email.strip():
        filters.append(User.email.ilike(f"%{email.strip()}%"))

    total = (
        db.scalar(select(func.count(Purchase.id)).join(User, User.id == Purchase.user_id).where(*filters)) or 0
    )
    rows = db.execute(
        _view_query().where(*filters).order_by(Purchase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PurchaseListPage(items=[PurchaseView(*row) for row in rows], total=total)


@dataclass(frozen=True)
class PurchaseDetail:
    view: PurchaseView
    ledger: list[CreditTransaction]
    credits_taken_back: int
    can_recheck: bool
    can_take_back: bool
    can_mark_failed: bool


def _old_enough_to_fail(purchase: Purchase, now: datetime) -> bool:
    created_at = purchase.created_at
    if created_at is None:
        return True
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return now - created_at >= MARK_FAILED_MIN_AGE


def get_purchase_detail(db: Session, purchase_id: uuid.UUID, *, now: datetime | None = None) -> PurchaseDetail:
    row = db.execute(_view_query().where(Purchase.id == purchase_id)).one_or_none()
    if row is None:
        raise PurchaseNotFoundError(f"no purchase {purchase_id}")
    view = PurchaseView(*row)
    purchase = view.purchase
    ledger = list(
        db.scalars(
            select(CreditTransaction)
            .where(CreditTransaction.related_purchase_id == purchase.id)
            .order_by(CreditTransaction.created_at)
        ).all()
    )
    taken_back = sum(-t.amount for t in ledger if t.idempotency_key == clawback_key(purchase.id))
    gateway = purchase.source in billing_service.GATEWAY_SOURCES and bool(purchase.paypal_order_id)
    return PurchaseDetail(
        view=view,
        ledger=ledger,
        credits_taken_back=taken_back,
        can_recheck=gateway and purchase.status in ("pending", "failed", "completed"),
        can_take_back=purchase.status == "refunded" and taken_back == 0,
        can_mark_failed=gateway and purchase.status == "pending" and _old_enough_to_fail(purchase, now or _now()),
    )
