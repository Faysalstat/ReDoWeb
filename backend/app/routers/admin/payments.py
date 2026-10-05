import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...auth.dependencies import require_admin
from ...db.session import get_db
from ...models import User
from ...payments.paypal_client import PayPalError, PayPalNotConfiguredError
from ...schemas.admin.payments import (
    AdminPaymentsStatusResponse,
    AdminPurchaseActionResponse,
    AdminPurchaseDetailResponse,
    AdminPurchaseLedgerEntry,
    AdminPurchaseListResponse,
    AdminPurchaseNoteRequest,
    AdminPurchaseRow,
    AdminTakeBackResponse,
)
from ...services import admin_payments_service
from ...services.admin_payments_service import (
    PurchaseActionNotAllowedError,
    PurchaseNotFoundError,
    PurchaseView,
)

router = APIRouter()


def _row(view: PurchaseView) -> AdminPurchaseRow:
    p = view.purchase
    return AdminPurchaseRow(
        id=str(p.id),
        user_id=str(p.user_id),
        user_email=view.user_email,
        pack_name=view.pack_name,
        created_at=p.created_at,
        credits_granted=p.credits_granted,
        amount_usd_cents=p.amount_usd_cents,
        status=p.status,
        source=p.source,
        paypal_order_id=p.paypal_order_id,
        paypal_capture_id=p.paypal_capture_id,
        note=p.note,
        refunded_at=p.refunded_at,
        resolved_at=p.resolved_at,
        resolved_by_email=view.resolved_by_email,
    )


def _current_row(db: Session, purchase_id: uuid.UUID) -> AdminPurchaseRow:
    return _row(admin_payments_service.get_purchase_detail(db, purchase_id).view)


def _run(db: Session, action):
    """Shared error mapping for the three purchase actions. Rolls back on
    any failure so a half-applied action never commits."""
    try:
        result = action()
    except PurchaseNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PurchaseActionNotAllowedError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PayPalNotConfiguredError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="PayPal is not configured on this server") from exc
    except PayPalError as exc:
        db.rollback()
        detail = (
            "PayPal didn't respond -- nothing was changed, try again shortly"
            if exc.transient
            else f"PayPal rejected the request: {exc.issue or exc}"
        )
        raise HTTPException(status_code=502, detail=detail) from exc
    db.commit()
    return result


@router.get("/payments/status", response_model=AdminPaymentsStatusResponse)
def get_payments_status() -> AdminPaymentsStatusResponse:
    return AdminPaymentsStatusResponse(**admin_payments_service.payments_status().__dict__)


@router.get("/purchases", response_model=AdminPurchaseListResponse)
def list_purchases(
    status: str | None = None,
    source: str | None = None,
    email: str | None = None,
    include_mock: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminPurchaseListResponse:
    result = admin_payments_service.list_purchases(
        db, status=status, source=source, email=email, include_mock=include_mock, page=page, page_size=page_size
    )
    return AdminPurchaseListResponse(
        items=[_row(view) for view in result.items], total=result.total, page=page, page_size=page_size
    )


@router.get("/purchases/{purchase_id}", response_model=AdminPurchaseDetailResponse)
def get_purchase(purchase_id: uuid.UUID, db: Session = Depends(get_db)) -> AdminPurchaseDetailResponse:
    try:
        detail = admin_payments_service.get_purchase_detail(db, purchase_id)
    except PurchaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AdminPurchaseDetailResponse(
        purchase=_row(detail.view),
        ledger=[
            AdminPurchaseLedgerEntry(id=str(t.id), amount=t.amount, reason=t.reason, created_at=t.created_at)
            for t in detail.ledger
        ],
        credits_taken_back=detail.credits_taken_back,
        can_recheck=detail.can_recheck,
        can_take_back=detail.can_take_back,
        can_mark_failed=detail.can_mark_failed,
    )


@router.post("/purchases/{purchase_id}/recheck", response_model=AdminPurchaseActionResponse)
def recheck_purchase(
    purchase_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminPurchaseActionResponse:
    outcome = _run(db, lambda: admin_payments_service.recheck(db, purchase_id, current_admin.id))
    return AdminPurchaseActionResponse(
        status=outcome.status,
        credits_granted=outcome.credits_granted,
        reason=outcome.reason,
        purchase=_current_row(db, purchase_id),
    )


@router.post("/purchases/{purchase_id}/take-back", response_model=AdminTakeBackResponse)
def take_back_credits(
    purchase_id: uuid.UUID,
    body: AdminPurchaseNoteRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminTakeBackResponse:
    result = _run(
        db, lambda: admin_payments_service.take_back_credits(db, purchase_id, current_admin.id, body.note)
    )
    return AdminTakeBackResponse(**result.__dict__, purchase=_current_row(db, purchase_id))


@router.post("/purchases/{purchase_id}/mark-failed", response_model=AdminPurchaseActionResponse)
def mark_purchase_failed(
    purchase_id: uuid.UUID,
    body: AdminPurchaseNoteRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> AdminPurchaseActionResponse:
    result = _run(db, lambda: admin_payments_service.mark_failed(db, purchase_id, current_admin.id, body.note))
    return AdminPurchaseActionResponse(
        status=result.outcome.status,
        credits_granted=result.outcome.credits_granted,
        reason=result.outcome.reason,
        marked_failed=result.marked_failed,
        purchase=_current_row(db, purchase_id),
    )
